# Umbod community connectors

Community-built **LinkedIn** and **Nemlig** connectors using the [Umbod Python SDK](https://github.com/computerlovetech/umbod/tree/main/packages/umbod-sdk). Each operation is a separate tool, so you choose permissions in Umbod.

**Shout-out to Mark Ruvald ([@eisbaw](https://github.com/eisbaw))** for the inspiration and protocol research in [linkedin-rs](https://github.com/eisbaw/linkedin-rs) and [nemlig_cli](https://github.com/eisbaw/nemlig_cli). These are independent Python implementations informed by his CLIs. Thank you, Mark!

| Connector | Tools | Functionality |
| --- | ---: | --- |
| [LinkedIn](docs/linkedin.md) | 20 | Profiles, visits/viewers, feed, posts, comments/reactions, connections/invitations, people/jobs search, messaging, notifications |
| [Nemlig](docs/nemlig.md) | 7 | Account check, product search/details, basket viewing/quantity changes, order history/details |

## Status

Initial implementation with mocked provider request tests and real local MCP stdio discovery tests. **Not yet verified against live LinkedIn or Nemlig accounts.** The providers' private endpoints can change; source parity does not guarantee current provider compatibility. [Exact scope and source revisions](docs/parity.md).

Nemlig's meal planner, fridge/camera, local grocery lists, budgets, and Google Sheets import are intentionally excluded. Neither this connector nor the reference Nemlig CLI implements checkout.

## Install for Umbod Desktop on macOS

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git. uv installs Python 3.14 and the connector dependencies in an isolated tool environment; it does not modify Umbod's bundled runtime.

```sh
uv tool install --python 3.14 \
  'git+https://github.com/computerlovetech/umbod-community-connectors.git@v0.1.0'
uv tool dir --bin
```

In Umbod Desktop, choose **Add connector → Local process (stdio)**:

| Field | LinkedIn | Nemlig |
| --- | --- | --- |
| Name | LinkedIn Community | Nemlig Community |
| Executable | Absolute path to `umbod-community` inside the bin directory printed above | Same executable |
| Arguments (one per line) | `linkedin` | `nemlig` |
| Authentication: environment variable name | `UMBOD_CONNECTOR_CONFIG` | `UMBOD_CONNECTOR_CONFIG` |
| Authentication: secret value | Configuration JSON from [LinkedIn setup](docs/linkedin.md) | Configuration JSON from [Nemlig setup](docs/nemlig.md) |

Save the connector, check its account-status tool, and enable the tools you want. Umbod stores the secret environment value in Keychain and passes it to the local connector process. Configuration is never part of the model's tool arguments. There is no automatic browser sign-in in these connectors: they use session cookies for LinkedIn and an account login for Nemlig.

Write tools are present alongside read tools. There is no blanket read-only switch or generic HTTP tool. Use Umbod's per-tool permissions; enabling a write tool authorizes that capability within Umbod's policy. Tool annotations describe side effects but are not authorization checks. `profile_visit` registers a profile view even though its upstream request uses GET.

Each account should be a separate connector entry with its own configuration. No connector credentials, account content, or tokens are written by this package to files. Nemlig sessions last for one tool call; LinkedIn cookies come from the saved configuration. Provider requests are not automatically retried, avoiding duplicate writes after uncertain failures.

## SDK use

The distribution also publishes `linkedin` and `nemlig` in the standard `umbod.connectors` entry-point group. The plugin objects use the public SDK `Connector` interface, configuration models, configuration checks, and tool decorators. An SDK-compatible Umbod backend can discover the installed package through these entry points. For Enterprise, follow Umbod's [plugin bundle deployment guide](https://umbod.ai/docs/plugins/build-a-connector/); installing this tool environment does not install a plugin in an Enterprise backend.

Desktop uses a small stdio launcher over the **same SDK tool definitions**. It requires no Desktop changes, catalog support, or custom plugin loader.

The current PyPI package named `umbod` does not provide this SDK release. We therefore pin the SDK to a public Umbod commit in `pyproject.toml`, and commit `uv.lock`. See [architecture](docs/architecture.md) for the compatibility contract.

## Development

```sh
git clone https://github.com/computerlovetech/umbod-community-connectors.git
cd umbod-community-connectors
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run umbod connectors check
uv build
```

Tests use synthetic credentials and deny live HTTP. See [CONTRIBUTING.md](CONTRIBUTING.md) to add or update a connector.

Code in this repository is MIT licensed. No upstream source files are bundled. Attribution and inspected source revisions are recorded in [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).
