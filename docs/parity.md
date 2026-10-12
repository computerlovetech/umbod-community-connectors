# Reference CLI coverage

Protocol observations were taken from these public revisions on 2026-10-12:

- Mark Ruvald's [linkedin-rs](https://github.com/eisbaw/linkedin-rs/tree/a7c8b40699d2cfa73aa3b1be665e505922070190), particularly `linkedin/linkedin-api/src/client.rs` and `linkedin/linkedin-cli/src/main.rs`.
- Mark Ruvald's [nemlig_cli](https://github.com/eisbaw/nemlig_cli/tree/de1c26d30f4fffb3db32aa11c00df0286a127e8c), particularly `nemlig_cli.py` and `nemlig_api.md`.

This is **implementation parity with the listed CLI operations**, not every feature of the providers' websites. Requests are covered by synthetic HTTP tests. No live provider verification has been performed, and copied protocol constants may change upstream.

## LinkedIn

| CLI operation | Connector equivalent | Protocol |
| --- | --- | --- |
| `auth login` | Configure `li_at`, optional JSESSIONID/browser cookies in Umbod | Cookies plus CSRF header |
| `auth status` | `auth_status` | GET `/voyager/api/me` |
| `auth logout` | Remove/disconnect configuration in Umbod | Local lifecycle; no provider session revocation |
| `profile me` | `profile_me` | GET `me` |
| `profile view` | `profile_view` | GraphQL ProfilesByMemberIdentity |
| `profile visit` | `profile_visit` | Separate web profile query registering a view |
| `profile viewers` | `profile_viewers` | GET `identity/wvmpCards` |
| `feed list` | `feed_list` | GET `feed/updates`, `q=findFeed` |
| `feed react` | `feed_react` | GraphQL CreateSocialDashReactions |
| `feed unreact` | `feed_unreact` | GraphQL DoDeleteReactionSocialDashReactions |
| `feed comment` | `feed_comment` | GraphQL CreateSocialDashNormComments |
| `feed post` | `feed_post` | GraphQL content-creation shares mutation |
| `connections list` | `connections_list` | GET `relationships/connections` |
| `connections invite` | `connections_invite` | POST `voyagerGrowthNormInvitations` |
| `connections invitations` | `connections_invitations` | GraphQL ReceivedInvitationViews |
| `connections accept` | `connections_accept` | POST `voyagerRelationshipsDashInvitations/{id}?action=accept` |
| `search people` | `search_people` | GraphQL SearchClusterCollection |
| `search jobs` | `search_jobs` | GraphQL JobCardsByJobSearch |
| `messages list` | `messages_list` | GraphQL MessengerConversationsByCategory |
| `messages read` | `messages_read` | GraphQL MessengerMessagesByConversation |
| `messages send` | `messages_send` | POST `voyagerMessagingDashMessengerMessages?action=createMessage` |
| `notifications list` | `notifications_list` | GraphQL NotificationsCardsByFilterVanityName |

The 22 CLI commands become 20 tools, with login/logout owned by Umbod configuration. CLI presentation flags (`--json`, table formatting), local-only status, terminal confirmation prompts, and session-file paths are replaced by structured responses, Umbod lifecycle, and per-tool permission controls. Authentication remains an admin action; it is not a model-facing credential tool.

Full browser-cookie input is supported for writes that need additional session cookies. GraphQL output keeps the original envelope rather than the Rust client's selected sub-object. Profile slug resolution follows the observed mini-profile → profile → GraphQL fallback. Each query or mutation uses the source-observed query ID and payload; message tracking uses 16 byte-to-character values, while invitation tracking uses base64.

## Nemlig account

| CLI operation | Connector equivalent | Protocol |
| --- | --- | --- |
| Login (`-u`/`-p` or local credentials) | Umbod configuration and `account_status` | AntiForgery → Token → login → refreshed Token/AntiForgery |
| `search` | `search_products` | AppSettings and page delivery context → search gateway |
| `details` | `product_details` | Product ID lookup → product page `GetAsJson` |
| `basket` | `basket_get` | GET `/webapi/basket/GetBasket` |
| `add --quantity N` | `basket_set_quantity` | POST `/webapi/basket/AddToBasket` |
| `history` | `order_history` | GET `/webapi/order/GetBasicOrderHistory` |
| `history ORDER_ID` | `order_details` | GET `/webapi/v2/order/GetOrderHistory/{id}` |

Quantity is absolute, not additive; zero removes the product. Search adds offset pagination to the CLI's limit. Search and product details preserve the full provider JSON. The source's historical fallback delivery slot is deliberately not reused: missing current slot information produces an actionable error.

Per the requested scope, **local grocery lists/budgets/sync, meal planning, recipe import/Google Sheets setup, barcode lookup, camera scanning, and fridge inventory/suggestions are excluded**. Checkout, order placement/cancellation, account-profile editing, and delivery-slot selection were not exposed by this CLI and are not invented here.

## Validation limits

- Every provider-facing tool is exercised with a mocked protocol response, including request shape and response passthrough.
- Credential checks cover accepted, rejected, and unreachable cases.
- Tests cover error redaction, no write retries, cookie/CSRF handling, query encoding, token refresh, product URL host isolation, and invalid input rejection.
- SDK package entry points and schemas are loaded against the pinned public SDK commit.
- Both MCP processes are started over real stdio and their tool catalogs are checked.
- This does not verify a live provider session, a complete Umbod Desktop GUI installation, or an Enterprise deployment.
