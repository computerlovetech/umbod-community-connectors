# Architecture

Each connector has four modules: SDK configuration, an HTTP client, a configuration check, and SDK tool declarations. HTTP clients implement provider protocols independently of the reference CLIs; neither Rust nor the reference executables are required.

`server.py` translates the public SDK `connector.definition()` tool declarations into MCP stdio tools. Configuration is validated once from `UMBOD_CONNECTOR_CONFIG` and injected by the launcher. The public function signature excludes configuration, so agents cannot read or override credentials through tool arguments. The same definitions remain discoverable as native SDK plugins through Python entry points.

```text
Agent → Umbod Desktop permissions → MCP stdio → SDK tool → provider HTTP
```

The connector process exposes all its tools. Umbod is the permission enforcement point. Directly connecting a different MCP client to the process bypasses Umbod's policies. There is no generic request/dispatch tool that could bypass individual tool permissions.

The installed connector runs in uv's tool environment, separate from Umbod's application bundle. Umbod persists connection settings in its own profile and secrets in Keychain; this package persists no credentials or account data. `catalog/*.json` is descriptive metadata for contributors, not an existing Desktop import format.

## Versioning

- Package: `0.1.0`, tagged `v0.1.0`.
- Umbod SDK: `0.1.0` from public commit `7e761248cf45ae157201e30ce7b49c1c25afba91`.
- Python: 3.14 or newer.
- MCP Python SDK: 2.3 series API (`MCPServer`), constrained below 3.
- `uv.lock` captures the development/CI resolution. A Git-based `uv tool install` uses dependency constraints and the pinned Umbod source, not a promise to reproduce every lockfile version.

The SDK's offline `connectors check` validates package entry-point metadata. Its `--target` version-range checker does not support this direct Git dependency. SDK loading, schema generation, and MCP startup are checked separately by tests. Enterprise deployment requires bundling the plugins with a compatible SDK supplied by the host; it is not verified by Desktop stdio tests.

## Failures

Requests have bounded timeouts, verify TLS, and do not follow redirects. Error messages omit provider bodies, credential values and full request URLs. Empty success responses map to JSON null; GraphQL errors in HTTP 200 responses are failures. Writes are never automatically retried. A failed or interrupted write may still have completed at the provider; inspect current state before repeating it.

SDK configuration checks cannot establish compatibility of every endpoint. Private provider protocols require periodic live validation with the operator's own account; this initial release has only offline protocol and stdio verification.
