# LinkedIn

Inspired by Mark Ruvald's [linkedin-rs](https://github.com/eisbaw/linkedin-rs).

## Configuration

Connector ID and Desktop launch argument: `linkedin`.

Log into LinkedIn yourself. In browser developer tools, find cookies for `https://www.linkedin.com` and copy `li_at` and, preferably, `JSESSIONID`. Enter this JSON as the secret `UMBOD_CONNECTOR_CONFIG` environment variable in Umbod:

```json
{"li_at":"YOUR_SESSION_COOKIE","jsessionid":"ajax:YOUR_CSRF_VALUE"}
```

For operations that require additional browser cookies, add `browser_cookies`, a JSON **string** containing a name-to-value object:

```json
{"li_at":"YOUR_SESSION_COOKIE","jsessionid":"ajax:YOUR_CSRF_VALUE","browser_cookies":"{\"liap\":\"true\",\"bcookie\":\"YOUR_COOKIE_VALUE\"}"}
```

`li_at` and an explicitly supplied `jsessionid` take precedence over the browser cookie map. Cookie values are stored as SDK `SecretStr` fields. An optional `timeout_seconds` (default 30, maximum 120) controls requests. With no JSESSIONID supplied, the connector generates a CSRF value as the reference CLI does. There is no automatic cookie extraction or OAuth login.

Enable and call `auth_status` first. Replace expired cookies through Umbod's connector configuration. Disconnect/remove the connector through Umbod to revoke its local use; removing a connector does not invalidate the session at LinkedIn itself.

## Tools

| Domain | Read tools | Tools with side effects |
| --- | --- | --- |
| Session | `auth_status` | Credentials managed in Umbod |
| Profiles | `profile_me`, `profile_view`, `profile_viewers` | `profile_visit` |
| Feed | `feed_list` | `feed_post`, `feed_comment`, `feed_react`, `feed_unreact` |
| Connections | `connections_list`, `connections_invitations` | `connections_invite`, `connections_accept` |
| Search | `search_people`, `search_jobs` | — |
| Messages | `messages_list`, `messages_read` | `messages_send` |
| Notifications | `notifications_list` | — |

Profile identifiers are public URL slugs. Message recipients also accept `urn:li:fsd_profile:...`, `urn:li:member:...`, and `urn:li:fs_miniProfile:...`. Invitations accept a profile URN directly. Post operations accept a complete post URN or numeric activity ID. Invitation acceptance takes the identifier and shared secret returned by `connections_invitations`.

Offset-based tools accept `start` and `count`. Messaging uses an optional `before` epoch-milliseconds cursor. Responses preserve the upstream JSON, including GraphQL envelopes and pagination metadata; the account check returns a validity summary.

Reactions: `LIKE`, `PRAISE`, `EMPATHY`, `INTEREST`, `APPRECIATION`, `ENTERTAINMENT`, `CELEBRATION`. Post audiences: `ANYONE` and `CONNECTIONS_ONLY`.

## Compatibility

This uses the same unofficial Voyager endpoints and captured query IDs as the inspected CLI. No live account has been tested for this release. HTTP success with GraphQL errors is treated as failure, and ambiguous writes are never retried automatically. The configuration check reads `/voyager/api/me`; it does not send messages, visit other profiles, or publish content.
