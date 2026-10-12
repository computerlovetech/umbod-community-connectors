"""Voyager protocol implementation; source observations are recorded in docs/parity.md."""

import base64
import json
import secrets
import uuid
from urllib.parse import quote

import httpx

from umbod_community_connectors.http import AuthenticationError, ConnectorError, request_json

from .admin_configuration import LinkedInConfiguration

BASE = "https://www.linkedin.com/voyager/api/"
QUERIES = {
    "profile": (
        "voyagerIdentityDashProfiles.5f50f83f76a1e270603613bdd0fb0252",
        "ProfilesByMemberIdentity",
    ),
    "visit": (
        "voyagerIdentityDashProfiles.a3de77c32c473719f1c58fae6bff43a5",
        "ProfilesByMemberIdentity",
    ),
    "conversations": (
        "voyagerMessagingDashMessengerConversations.7dc50d3efc3953190125aca9c05f0af6",
        "MessengerConversationsByCategory",
    ),
    "messages": (
        "voyagerMessagingDashMessengerMessages.7cde5843a127bbecc3de900d3894a74a",
        "MessengerMessagesByConversation",
    ),
    "people": (
        "voyagerSearchDashClusters.fae19421cdd51a7cd735e0b7d7b32e0f",
        "SearchClusterCollection",
    ),
    "jobs": ("voyagerJobsDashJobCards.4ef915ad5827cd8ea1351ad72f8e4268", "JobCardsByJobSearch"),
    "notifications": (
        "voyagerIdentityDashNotificationCards.1a1ca07d1f7a6e1033fd88d5fd2da611",
        "NotificationsCardsByFilterVanityName",
    ),
    "invitations": (
        "voyagerRelationshipsDashInvitationViews.48949225027e0a85d063176777f08e7f",
        "ReceivedInvitationViews",
    ),
    "react": (
        "voyagerSocialDashReactions.fd68eadaf15da416b0d839e21399b763",
        "CreateSocialDashReactions",
    ),
    "unreact": (
        "voyagerSocialDashReactions.315cef4773de8e3a0ddad7655cc1685f",
        "DoDeleteReactionSocialDashReactions",
    ),
    "comment": (
        "voyagerSocialDashNormComments.cd3d2a3fd6c9b2881c7cac32847ec05e",
        "CreateSocialDashNormComments",
    ),
}
POST_QUERY = "voyagerContentcreationDashShares.279996efa5064c01775d5aff003d9377"


def restli(value: str) -> str:
    return quote(value, safe="-._~!*@/") if value else "''"


def activity(value: str) -> str:
    return value if value.startswith("urn:li:") else f"urn:li:activity:{value}"


class LinkedInClient:
    def __init__(self, configuration: LinkedInConfiguration, transport=None):
        cookies = (
            json.loads(configuration.browser_cookies.get_secret_value())
            if configuration.browser_cookies
            else {}
        )
        cookies["li_at"] = configuration.li_at.get_secret_value()
        csrf = (
            configuration.jsessionid.get_secret_value()
            if configuration.jsessionid
            else cookies.get("JSESSIONID", f"ajax:{secrets.randbelow(2**63):019d}")
        ).strip('"')
        cookies["JSESSIONID"] = f'"{csrf}"'
        device = str(uuid.uuid4())
        track = {
            "osName": "Android OS",
            "osVersion": "34",
            "clientVersion": "4.2.1058",
            "clientMinorVersion": 562100,
            "carrier": "T-Mobile",
            "model": "Google_Pixel 8",
            "displayDensity": 2.625,
            "displayWidth": 1080,
            "displayHeight": 2400,
            "dpi": "xxhdpi",
            "deviceType": "android",
            "appId": "com.linkedin.android",
            "deviceId": device,
            "timezoneOffset": 0,
            "timezone": "UTC",
            "storeId": "com.linkedin.android",
            "advertiserId": "00000000-0000-0000-0000-000000000000",
            "isAdTrackingLimited": True,
            "mpName": "voyager-android",
            "mpVersion": "4.2.1058",
        }
        jar = httpx.Cookies()
        for name, value in cookies.items():
            jar.set(name, value, domain=".linkedin.com", path="/")
        self.http = httpx.Client(
            cookies=jar,
            timeout=configuration.timeout_seconds,
            transport=transport,
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "ANDROID OS",
                "X-RestLi-Protocol-Version": "2.0.0",
                "Csrf-Token": csrf,
                "X-LI-Lang": "en_US",
                "Accept-Language": "en-US",
                "X-UDID": device,
                "X-LI-Track": json.dumps(track),
            },
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http.close()

    def get(self, path, **kwargs):
        return request_json(self.http, "GET", BASE + path, **kwargs)

    def post(self, path, body):
        return request_json(self.http, "POST", BASE + path, json=body)

    def query(self, key, variables):
        query_id, name = QUERIES[key]
        # Rest.li values are already escaped. Passing them via params would double-encode them.
        return self.get(
            f"graphql?variables={variables}&queryId={query_id}&queryName={name}",
            headers={"x-li-graphql-pegasus-client": "true"},
        )

    def mutation(self, key, variables):
        query_id, name = QUERIES[key]
        return request_json(
            self.http,
            "POST",
            BASE + "graphql",
            params={"action": "execute", "queryId": query_id, "queryName": name},
            headers={"x-li-graphql-pegasus-client": "true"},
            json={"queryId": query_id, "queryName": name, "variables": variables},
        )

    def me(self):
        return self.get("me")

    def own_urn(self):
        value = self.me().get("miniProfile", {}).get("dashEntityUrn")
        if not isinstance(value, str) or not value:
            raise ConnectorError("Profile response is missing the account URN.")
        return value

    def profile(self, public_id, visit=False):
        key = "visit" if visit else "profile"
        field = "vanityName" if visit else "memberIdentity"
        return self.query(key, f"({field}:{restli(public_id)})")

    def resolve(self, identifier):
        if identifier.startswith(
            ("urn:li:fsd_profile:", "urn:li:member:", "urn:li:fs_miniProfile:")
        ):
            return identifier
        candidates = [
            ("identity/miniprofiles", {"q": "memberIdentity", "memberIdentity": identifier}),
            ("identity/profiles/" + quote(identifier, safe=""), None),
        ]
        for path, params in candidates:
            try:
                result = self.get(path, params=params)
            except AuthenticationError:
                raise
            except ConnectorError:
                continue
            entries = result.get("elements", [])
            entity = entries[0] if entries else result
            value = (
                entity.get("dashEntityUrn")
                or entity.get("miniProfile", {}).get("dashEntityUrn")
                or entity.get("entityUrn")
            )
            if isinstance(value, str):
                return value.replace("fs_miniProfile", "fsd_profile").replace(
                    "fs_profile", "fsd_profile"
                )
        result = self.profile(identifier)
        entries = (
            result.get("data", {})
            .get("identityDashProfilesByMemberIdentity", {})
            .get("elements", [])
        )
        if entries and isinstance(entries[0].get("entityUrn"), str):
            return entries[0]["entityUrn"]
        raise ConnectorError("Could not resolve the profile identifier.")

    def feed(self, start, count):
        return self.get("feed/updates", params={"q": "findFeed", "start": start, "count": count})

    def connections(self, start, count):
        return self.get(
            "relationships/connections",
            params={"start": start, "count": count, "sortType": "RECENTLY_ADDED"},
        )

    def search(self, kind, keywords, start, count):
        text = restli(keywords)
        if kind == "people":
            variables = (
                f"(count:{count},origin:GLOBAL_SEARCH_HEADER,"
                f"query:(flagshipSearchIntent:SEARCH_SRP,keywords:{text},"
                f"queryParameters:(resultType:List(PEOPLE))),start:{start})"
            )
        else:
            variables = (
                f"(count:{count},includeJobState:true,"
                f"query:(keywords:{text},origin:FACETED_SEARCH),start:{start})"
            )
        return self.query(kind, variables)

    def conversations(self, count, before):
        cursor = f",lastActivityBefore:{before}" if before is not None else ""
        return self.query(
            "conversations",
            f"(mailboxUrn:{restli(self.own_urn())},category:PRIMARY_INBOX,count:{count}{cursor})",
        )

    def messages(self, conversation, before):
        if not conversation.startswith("urn:li:msg_conversation:"):
            thread = conversation.removeprefix("urn:li:messagingThread:")
            conversation = f"urn:li:msg_conversation:({self.own_urn()},{thread})"
        cursor = f",deliveredBefore:{before}" if before is not None else ""
        return self.query("messages", f"(conversationUrn:{restli(conversation)}{cursor})")

    def send_message(self, recipient, text):
        recipient_urn = self.resolve(recipient)
        return self.post(
            "voyagerMessagingDashMessengerMessages?action=createMessage",
            {
                "message": {
                    "body": {"attributes": [], "text": text},
                    "originToken": str(uuid.uuid4()),
                    "renderContentUnions": [],
                },
                "mailboxUrn": self.own_urn(),
                "trackingId": secrets.token_bytes(16).decode("latin1"),
                "dedupeByClientGeneratedToken": False,
                "hostRecipientUrns": [recipient_urn],
            },
        )

    def reaction(self, post, reaction, remove=False):
        values = {"threadUrn": activity(post), "reactionType": reaction}
        if not remove:
            values["entity"] = dict(values)
        return self.mutation("unreact" if remove else "react", values)

    def comment(self, post, text):
        return self.mutation(
            "comment",
            {
                "entity": {
                    "commentary": {"text": text},
                    "threadUrn": activity(post),
                    "origin": "FEED",
                }
            },
        )

    def create_post(self, text, visibility):
        return request_json(
            self.http,
            "POST",
            BASE + "graphql",
            params={"action": "execute", "queryId": POST_QUERY},
            headers={"x-li-graphql-pegasus-client": "true"},
            json={
                "queryId": POST_QUERY,
                "includeWebMetadata": True,
                "variables": {
                    "post": {
                        "allowedCommentersScope": "ALL",
                        "intendedShareLifeCycleState": "PUBLISHED",
                        "origin": "FEED",
                        "visibilityDataUnion": {"visibilityType": visibility},
                        "commentary": {"text": text, "attributesV2": []},
                    }
                },
            },
        )

    def invite(self, recipient, message):
        profile = recipient if recipient.startswith("urn:li:") else self.resolve(recipient)
        body = {
            "trackingId": base64.b64encode(secrets.token_bytes(16)).decode(),
            "invitee": {
                "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                    "profileId": profile.rsplit(":", 1)[-1]
                }
            },
        }
        if message is not None:
            body["message"] = message
        return self.post("voyagerGrowthNormInvitations", body)

    def accept(self, invitation, shared_secret):
        if not invitation.startswith("urn:li:"):
            invitation = f"urn:li:fsd_invitation:{invitation}"
        return self.post(
            "voyagerRelationshipsDashInvitations/" + quote(invitation, safe="") + "?action=accept",
            {"invitationUrn": invitation, "sharedSecret": shared_secret},
        )
