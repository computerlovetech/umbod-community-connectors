# Contributing

This repository welcomes connectors for any app or service that people want to use through Umbod. You can contribute a new integration, improve an existing connector, or help with documentation and compatibility testing.

Add a connector directory under `src/umbod_community_connectors/`, documentation under `docs/`, and a descriptive entry under `catalog/`. Register the SDK plugin through `umbod.connectors` in `pyproject.toml` and add the desktop launcher entry in `server.py`.

Use the public Umbod SDK configuration model, configuration check, and tool decorators. Every tool must have a specific operation and documented parameters, with an injected `configuration` parameter. Do not expose a generic HTTP request or arbitrary dispatch tool. Keep side effects separately permissionable and describe them clearly, including GET requests that change provider state.

Keep HTTP and protocol handling in the client module. Return raw provider JSON where practical. Declare credentials as `SecretStr`; never commit credentials, session cookies, captured private responses, or local configuration files. Use synthetic test fixtures, bounded timeouts, redacted errors, and no automatic retries for writes.

Record the reference source, immutable revision, command-to-tool mapping, and any deliberate scope differences in `docs/parity.md`. Preserve required notices when reusing licensed code. Contributions based on unlicensed sources must not copy their implementation.

Run `uv sync --locked`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run umbod connectors check`, and `uv build`. Tests must exercise request shapes, response passthrough, failure behavior, SDK discovery, hidden credential injection, and the MCP stdio contract. Label live provider verification separately from mocked checks.

Open a pull request explaining the user workflow, permissionable operations, authentication requirements, and validation performed. Changes to endpoints, launch commands, credentials, or dependencies need explicit review. Catalog entries are documentation today; there is no automatic installation or execution from this repository's catalog.
