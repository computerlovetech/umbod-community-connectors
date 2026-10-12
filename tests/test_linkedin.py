import json

import httpx
import pytest

from umbod_community_connectors import linkedin
from umbod_community_connectors.http import AuthenticationError, ConnectorError
from umbod_community_connectors.linkedin.admin_configuration import LinkedInConfiguration
from umbod_community_connectors.linkedin.api_client import LinkedInClient, restli
from umbod_community_connectors.server import bind_tool

CONFIG = LinkedInConfiguration(li_at="fixture-cookie", jsessionid='"ajax:123"')

# Expected request routes are protocol observations, not generated from implementation constants.
READS = [
    ("profile_me", {}, "/voyager/api/me", {}),
    ("profile_viewers", {}, "/voyager/api/identity/wvmpCards", {}),
    (
        "feed_list",
        {"start": 2, "count": 7},
        "/voyager/api/feed/updates",
        {"q": "findFeed", "start": "2", "count": "7"},
    ),
    (
        "connections_list",
        {"start": 3, "count": 9},
        "/voyager/api/relationships/connections",
        {"start": "3", "count": "9", "sortType": "RECENTLY_ADDED"},
    ),
]
QUERIES = [
    (
        "profile_view",
        {"public_id": "jane"},
        "voyagerIdentityDashProfiles.5f50f83f76a1e270603613bdd0fb0252",
        "(memberIdentity:jane)",
    ),
    (
        "profile_visit",
        {"public_id": "jane"},
        "voyagerIdentityDashProfiles.a3de77c32c473719f1c58fae6bff43a5",
        "(vanityName:jane)",
    ),
    (
        "search_people",
        {"keywords": "rust", "start": 1, "count": 2},
        "voyagerSearchDashClusters.fae19421cdd51a7cd735e0b7d7b32e0f",
        "(count:2,origin:GLOBAL_SEARCH_HEADER,query:(flagshipSearchIntent:SEARCH_SRP,keywords:rust,queryParameters:(resultType:List(PEOPLE))),start:1)",
    ),
    (
        "search_jobs",
        {"keywords": "rust", "start": 1, "count": 2},
        "voyagerJobsDashJobCards.4ef915ad5827cd8ea1351ad72f8e4268",
        "(count:2,includeJobState:true,query:(keywords:rust,origin:FACETED_SEARCH),start:1)",
    ),
    (
        "connections_invitations",
        {"start": 1, "count": 2},
        "voyagerRelationshipsDashInvitationViews.48949225027e0a85d063176777f08e7f",
        "(start:1,count:2,includeInsights:true)",
    ),
    (
        "notifications_list",
        {"start": 1, "count": 2},
        "voyagerIdentityDashNotificationCards.1a1ca07d1f7a6e1033fd88d5fd2da611",
        "(start:1,count:2)",
    ),
    (
        "messages_list",
        {"count": 3, "before": 123},
        "voyagerMessagingDashMessengerConversations.7dc50d3efc3953190125aca9c05f0af6",
        "(mailboxUrn:urn:li:fsd_profile:owner,category:PRIMARY_INBOX,count:3,lastActivityBefore:123)",
    ),
    (
        "messages_read",
        {"conversation": "thread", "before": 456},
        "voyagerMessagingDashMessengerMessages.7cde5843a127bbecc3de900d3894a74a",
        "(conversationUrn:urn:li:msg_conversation:(urn:li:fsd_profile:owner,thread),deliveredBefore:456)",
    ),
]


def install_transport(monkeypatch, handler):
    monkeypatch.setattr(
        linkedin,
        "LinkedInClient",
        lambda config: LinkedInClient(config, httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize("name,arguments,path,params", READS)
def test_rest_tools(monkeypatch, name, arguments, path, params):
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == path
        assert dict(request.url.params) == params
        assert request.headers["csrf-token"] == "ajax:123"
        assert 'JSESSIONID="ajax:123"' in request.headers["cookie"]
        assert "li_at=fixture-cookie" in request.headers["cookie"]
        return httpx.Response(200, json={"untouched": [1, {"x": True}]})

    install_transport(monkeypatch, handler)
    assert bind_tool(getattr(linkedin, name), CONFIG)(**arguments) == {
        "untouched": [1, {"x": True}]
    }


@pytest.mark.parametrize("name,arguments,query_id,variables", QUERIES)
def test_graphql_tools(monkeypatch, name, arguments, query_id, variables):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/voyager/api/me":
            return httpx.Response(
                200, json={"miniProfile": {"dashEntityUrn": "urn:li:fsd_profile:owner"}}
            )
        assert request.url.path == "/voyager/api/graphql"
        assert request.url.params["queryId"] == query_id
        assert request.url.params["variables"] == variables
        assert request.headers["x-li-graphql-pegasus-client"] == "true"
        return httpx.Response(200, json={"data": {"originalEnvelope": []}})

    install_transport(monkeypatch, handler)
    assert bind_tool(getattr(linkedin, name), CONFIG)(**arguments) == {
        "data": {"originalEnvelope": []}
    }
    assert len(calls) == (2 if name in ("messages_list", "messages_read") else 1)


@pytest.mark.parametrize(
    "name,key,query_id",
    [
        ("feed_react", "entity", "voyagerSocialDashReactions.fd68eadaf15da416b0d839e21399b763"),
        ("feed_unreact", None, "voyagerSocialDashReactions.315cef4773de8e3a0ddad7655cc1685f"),
    ],
)
def test_reactions(monkeypatch, name, key, query_id):
    def handler(request):
        assert request.method == "POST"
        assert request.url.params["action"] == "execute"
        assert request.url.params["queryId"] == query_id
        body = json.loads(request.content)
        expected = {"threadUrn": "urn:li:activity:123", "reactionType": "PRAISE"}
        if key:
            expected[key] = dict(expected)
        assert body["variables"] == expected
        return httpx.Response(204)

    install_transport(monkeypatch, handler)
    assert bind_tool(getattr(linkedin, name), CONFIG)(post="123", reaction="PRAISE") is None


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("feed_comment", {"post": "123", "text": "Hello"}),
        ("feed_post", {"text": "Hello", "visibility": "CONNECTIONS_ONLY"}),
        (
            "connections_accept",
            {"invitation": "urn:li:invitation:123", "shared_secret": "fixture-secret"},
        ),
        ("connections_invite", {"recipient": "urn:li:fsd_profile:friend", "message": "Hello"}),
        ("messages_send", {"recipient": "urn:li:fsd_profile:friend", "text": "Hello"}),
    ],
)
def test_writes(monkeypatch, name, arguments):
    writes = []

    def handler(request):
        if request.method == "GET":
            assert request.url.path == "/voyager/api/me"
            return httpx.Response(
                200, json={"miniProfile": {"dashEntityUrn": "urn:li:fsd_profile:owner"}}
            )
        writes.append(request)
        body = json.loads(request.content)
        if name == "feed_comment":
            assert body["variables"] == {
                "entity": {
                    "commentary": {"text": "Hello"},
                    "threadUrn": "urn:li:activity:123",
                    "origin": "FEED",
                }
            }
            assert (
                request.url.params["queryId"]
                == "voyagerSocialDashNormComments.cd3d2a3fd6c9b2881c7cac32847ec05e"
            )
        elif name == "feed_post":
            post = body["variables"]["post"]
            assert post["visibilityDataUnion"] == {"visibilityType": "CONNECTIONS_ONLY"}
            assert post["commentary"] == {"text": "Hello", "attributesV2": []}
            assert post["intendedShareLifeCycleState"] == "PUBLISHED"
            assert (
                body["queryId"]
                == "voyagerContentcreationDashShares.279996efa5064c01775d5aff003d9377"
            )
        elif name == "connections_accept":
            assert request.url.path.endswith("/urn:li:invitation:123")
            assert request.url.params["action"] == "accept"
            assert body == {
                "invitationUrn": "urn:li:invitation:123",
                "sharedSecret": "fixture-secret",
            }
        elif name == "connections_invite":
            assert request.url.path.endswith("/voyagerGrowthNormInvitations")
            assert body["invitee"]["com.linkedin.voyager.growth.invitation.InviteeProfile"] == {
                "profileId": "friend"
            }
            assert body["message"] == "Hello"
            import base64

            assert len(base64.b64decode(body["trackingId"])) == 16
        else:
            assert request.url.params["action"] == "createMessage"
            assert body["hostRecipientUrns"] == ["urn:li:fsd_profile:friend"]
            assert body["mailboxUrn"] == "urn:li:fsd_profile:owner"
            assert body["message"]["body"] == {"attributes": [], "text": "Hello"}
            assert len(body["trackingId"]) == 16
        return httpx.Response(200, json={"result": "unchanged"})

    install_transport(monkeypatch, handler)
    assert bind_tool(getattr(linkedin, name), CONFIG)(**arguments) == {"result": "unchanged"}
    assert len(writes) == 1


def test_restli_non_ascii_and_reserved_characters():
    assert restli("a,b:(x)'% &ø") == "a%2Cb%3A%28x%29%27%25%20%26%C3%B8"
    assert restli("") == "''"

    def handler(request):
        assert b"a%2Cb" in request.url.query
        assert b"%252C" not in request.url.query
        assert len(request.url.params) == 3
        return httpx.Response(200, json={})

    with LinkedInClient(CONFIG, httpx.MockTransport(handler)) as client:
        client.search("people", "a,b&queryId=evil", 0, 2)


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, ConnectorError),
        (500, ConnectorError),
        (302, ConnectorError),
    ],
)
def test_errors_are_redacted_and_never_retry_writes(status, expected):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="fixture-cookie private content",
            headers={"Location": "https://example.org"},
        )

    with LinkedInClient(CONFIG, httpx.MockTransport(handler)) as client:
        with pytest.raises(expected) as error:
            client.create_post("private text", "PUBLIC")
    assert "private" not in str(error.value)
    assert "fixture-cookie" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["valid", "auth", "network", "graphql", "html"])
def test_configuration_checks(monkeypatch, mode):
    import importlib

    checks = importlib.import_module("umbod_community_connectors.linkedin.configuration_check")

    def handler(request):
        if mode == "network":
            raise httpx.ConnectError("fixture-cookie", request=request)
        if mode == "auth":
            return httpx.Response(401)
        if mode == "graphql":
            return httpx.Response(200, json={"errors": [{"message": "private"}]})
        if mode == "html":
            return httpx.Response(200, text="<html>login</html>")
        return httpx.Response(200, json={"miniProfile": {"dashEntityUrn": "owner"}})

    monkeypatch.setattr(
        checks, "LinkedInClient", lambda cfg: LinkedInClient(cfg, httpx.MockTransport(handler))
    )
    result = linkedin.auth_status(CONFIG)
    assert result["valid"] is (mode == "valid")
    assert "fixture-cookie" not in str(result)


def test_resolve_fallback_and_cookie_support():
    requests = []
    config = LinkedInConfiguration(
        li_at="fixture", browser_cookies='{"JSESSIONID":"ajax:9","liap":"true"}'
    )

    def handler(request):
        requests.append(request)
        assert request.headers["csrf-token"] == "ajax:9"
        assert "liap=true" in request.headers["cookie"]
        if "miniprofiles" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, json={"entityUrn": "urn:li:fs_miniProfile:person"})

    with LinkedInClient(config, httpx.MockTransport(handler)) as client:
        assert client.resolve("jane") == "urn:li:fsd_profile:person"
    assert len(requests) == 2


def test_bad_cookies_are_rejected():
    with pytest.raises(ValueError):
        LinkedInConfiguration(li_at="fixture\r\nInjected: yes")
    with pytest.raises(ValueError):
        LinkedInConfiguration(li_at="fixture", browser_cookies='["bad"]')


def test_public_post_default_and_numeric_invitation(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        if len(calls) == 1:
            assert body["variables"]["post"]["visibilityDataUnion"]["visibilityType"] == "ANYONE"
        else:
            assert body == {
                "invitationUrn": "urn:li:fsd_invitation:123",
                "sharedSecret": "fixture-secret",
            }
            assert request.url.path.endswith("/urn:li:fsd_invitation:123")
        return httpx.Response(200, json={"ok": True})

    install_transport(monkeypatch, handler)
    bind_tool(linkedin.feed_post, CONFIG)(text="hello")
    bind_tool(linkedin.connections_accept, CONFIG)(invitation="123", shared_secret="fixture-secret")
    assert len(calls) == 2


@pytest.mark.parametrize(
    "urn", ["urn:li:member:42", "urn:li:fs_miniProfile:friend", "urn:li:fsd_profile:friend"]
)
def test_direct_recipient_urn_requires_no_resolution(urn):
    with LinkedInClient(CONFIG) as client:
        assert client.resolve(urn) == urn
