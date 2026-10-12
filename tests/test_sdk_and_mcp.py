import asyncio
import inspect
import json
import os
import subprocess
import sys
from importlib.metadata import entry_points

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import ValidationError

from umbod_community_connectors.server import CONNECTORS, WRITES, bind_tool, build_server

EXPECTED = {
    "linkedin": {
        "auth_status",
        "profile_me",
        "profile_view",
        "profile_visit",
        "profile_viewers",
        "feed_list",
        "feed_react",
        "feed_unreact",
        "feed_comment",
        "feed_post",
        "connections_list",
        "connections_invite",
        "connections_invitations",
        "connections_accept",
        "search_people",
        "search_jobs",
        "messages_list",
        "messages_read",
        "messages_send",
        "notifications_list",
    },
    "nemlig": {
        "account_status",
        "search_products",
        "product_details",
        "basket_get",
        "basket_set_quantity",
        "order_history",
        "order_details",
    },
}


def fixture_config(name):
    return (
        {"li_at": "not-a-real-cookie"}
        if name == "linkedin"
        else {"username": "fixture", "password": "not-a-real-password"}
    )


@pytest.mark.parametrize("name", CONNECTORS)
def test_sdk_discovery_and_mcp_contract(name):
    connector = CONNECTORS[name]
    found = [ep for ep in entry_points(group="umbod.connectors") if ep.name == name]
    assert len(found) == 1
    assert found[0].load() is connector
    registration = connector.registration()
    assert registration["id"] == name
    config = connector.configuration.model_validate(fixture_config(name))
    server = build_server(connector, config)
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == EXPECTED[name]
    for tool in tools:
        assert "configuration" not in tool.input_schema.get("properties", {})
        assert "not-a-real" not in json.dumps(tool.model_dump())
        assert tool.annotations.read_only_hint is (tool.name not in WRITES[name])
        function = next(
            t.function for t in connector.definition().tools if t.operation_name == tool.name
        )
        assert "configuration" not in inspect.signature(bind_tool(function, config)).parameters


@pytest.mark.parametrize(
    "name,tool,args",
    [
        ("linkedin", "feed_react", {"post": "123", "reaction": "INVALID"}),
        ("linkedin", "feed_post", {"text": "hello", "visibility": "PUBLIC"}),
        ("linkedin", "feed_list", {"start": -1}),
        ("nemlig", "basket_set_quantity", {"product_id": "123", "quantity": -1}),
        ("nemlig", "order_details", {"order_id": 0}),
    ],
)
def test_validation_happens_before_network(name, tool, args):
    connector = CONNECTORS[name]
    config = connector.configuration.model_validate(fixture_config(name))
    function = next(t.function for t in connector.definition().tools if t.operation_name == tool)
    with pytest.raises(ValidationError):
        bind_tool(function, config)(**args)


def test_agent_cannot_override_credentials():
    connector = CONNECTORS["linkedin"]
    function = next(
        t.function for t in connector.definition().tools if t.operation_name == "profile_me"
    )
    bound = bind_tool(function, connector.configuration.model_validate(fixture_config("linkedin")))
    with pytest.raises(TypeError):
        bound(configuration={"li_at": "injected"})


@pytest.mark.parametrize("name", CONNECTORS)
def test_real_stdio_discovery(name):
    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "umbod_community_connectors.server", name],
            env={"UMBOD_CONNECTOR_CONFIG": json.dumps(fixture_config(name))},
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                assert {t.name for t in result.tools} == EXPECTED[name]
                # Invalid input is rejected locally; no provider request is made.
                result = await session.call_tool(
                    "feed_react" if name == "linkedin" else "basket_set_quantity",
                    {"post": "123", "reaction": "INVALID"}
                    if name == "linkedin"
                    else {"product_id": "123", "quantity": -1},
                )
                assert result.is_error

    asyncio.run(run())


def test_bad_config_does_not_print_secrets():
    result = subprocess.run(
        [sys.executable, "-m", "umbod_community_connectors.server", "linkedin"],
        env={
            **os.environ,
            "UMBOD_CONNECTOR_CONFIG": '{"li_at":"private-value","unexpected":"private-value"}',
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "private-value" not in result.stderr
    assert not result.stdout


def test_mcp_invocation_runs_sdk_tool_with_injected_configuration(monkeypatch):
    import httpx

    from umbod_community_connectors import linkedin
    from umbod_community_connectors.linkedin.api_client import LinkedInClient

    def handler(request):
        assert request.url.path == "/voyager/api/me"
        assert "li_at=not-a-real-cookie" in request.headers["cookie"]
        return httpx.Response(200, json={"miniProfile": {"firstName": "Fixture"}})

    monkeypatch.setattr(
        linkedin, "LinkedInClient", lambda cfg: LinkedInClient(cfg, httpx.MockTransport(handler))
    )
    config = linkedin.connector.configuration.model_validate(fixture_config("linkedin"))
    server = build_server(linkedin.connector, config)
    result = asyncio.run(server.call_tool("profile_me", {}))
    assert not result.is_error
    assert "Fixture" in result.content[0].text
