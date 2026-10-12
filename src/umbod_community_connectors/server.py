"""Expose the same SDK tool definitions over stdio for Umbod Desktop."""

import argparse
import inspect
import json
import os
import sys
from functools import wraps

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError, validate_call

from .linkedin import connector as linkedin
from .nemlig import connector as nemlig

CONNECTORS = {"linkedin": linkedin, "nemlig": nemlig}
WRITES = {
    "linkedin": {
        "profile_visit",
        "feed_react",
        "feed_unreact",
        "feed_comment",
        "feed_post",
        "connections_invite",
        "connections_accept",
        "messages_send",
    },
    "nemlig": {"basket_set_quantity"},
}


def bind_tool(function, configuration):
    """Inject configuration without exposing it as a model-controllable argument."""
    signature = inspect.signature(function)
    public = signature.replace(
        parameters=[p for p in signature.parameters.values() if p.name != "configuration"]
    )
    checked = validate_call(function)

    @wraps(function)
    def invoke(*args, **kwargs):
        bound = public.bind(*args, **kwargs)
        bound.apply_defaults()
        return checked(**bound.arguments, configuration=configuration)

    invoke.__signature__ = public
    invoke.__annotations__ = {
        name: annotation
        for name, annotation in function.__annotations__.items()
        if name != "configuration"
    }
    return invoke


def build_server(connector, configuration):
    connector.registration()  # Fail early if SDK contracts or parameter metadata are invalid.
    server = MCPServer(name=f"umbod-community-{connector.id}", version="0.1.0")
    for tool in connector.definition().tools:
        writes = tool.operation_name in WRITES[connector.id]
        server.add_tool(
            bind_tool(tool.function, configuration),
            name=tool.operation_name,
            description=tool.description,
            annotations=ToolAnnotations(
                readOnlyHint=not writes, destructiveHint=writes, openWorldHint=True
            ),
        )
    return server


def main():
    parser = argparse.ArgumentParser(
        description="Run an Umbod SDK community connector over MCP stdio."
    )
    parser.add_argument("connector", choices=CONNECTORS)
    parser.add_argument(
        "--check", action="store_true", help="Check provider credentials, then exit."
    )
    args = parser.parse_args()
    connector = CONNECTORS[args.connector]
    raw = os.environ.get("UMBOD_CONNECTOR_CONFIG")
    if raw is None:
        parser.exit(2, "Set UMBOD_CONNECTOR_CONFIG to the connector configuration JSON.\n")
    try:
        config = connector.configuration.model_validate_json(raw)
    except ValidationError, ValueError:
        # Pydantic errors can contain input values. Do not print them for secret configuration.
        parser.exit(2, "Invalid UMBOD_CONNECTOR_CONFIG; check the connector's documented fields.\n")
    if args.check:
        result = connector.registration()["configuration_check"](config)
        print(json.dumps({"valid": result.valid, "message": result.message}), file=sys.stderr)
        raise SystemExit(0 if result.valid else 1)
    build_server(connector, config).run(transport="stdio")


if __name__ == "__main__":
    main()
