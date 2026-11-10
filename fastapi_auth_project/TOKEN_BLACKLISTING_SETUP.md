# Redis JWT Token Blacklisting Changes

This backend now uses a Redis blacklist for JWT revocation.

## What changed

- Access-token authentication checks `token-blacklist:<jti>` before accepting a token.
- Refresh-token requests check the same blacklist.
- Refresh rotation atomically blacklists/consumes the old refresh JTI with Redis `SET NX EX` before issuing replacement tokens. This prevents two concurrent refresh requests from both consuming the same refresh token.
- Logout blacklists the presented refresh token and the current access token supplied in the `Authorization: Bearer <access-token>` header.
- Blacklist entries expire automatically at the token's original `exp`; expired tokens do not leave permanent Redis entries.
- Token versioning remains enabled. Password changes still increment `token-version:<user_id>` and invalidate all older-version tokens.
- CSRF validation and the HttpOnly web refresh cookie remain unchanged.

## Redis session metadata is not an authorization allowlist

The old `hash-rt-for-user-<user_id>` key has been replaced by `sessions-for-user-<user_id>`. This hash stores refresh-session metadata only so the existing logout-all-devices Celery task can identify device IDs and send Socket.IO notifications. Refresh-token acceptance no longer depends on a JTI being present in this hash. The actual revocation check is the blacklist plus JWT signature/expiry/platform/version validation.

## Frontend logout requirement

For access-token blacklisting to work on logout, the frontend must send its current access token in the Authorization header:

`Authorization: Bearer <access-token>`

The existing Axios client should do this if its request interceptor attaches the access token to authenticated requests. The web logout request must continue sending the CSRF cookie/header as before.

## Redis keys

- `token-blacklist:<jti>` — value `1`, TTL equals the token's remaining lifetime.
- `token-version:<user_id>` — current token version, retained for global invalidation.
- `sessions-for-user-<user_id>` — device/session metadata for notifications only; not used to authorize tokens.

## Validation performed

Python bytecode compilation (`compileall`) completed successfully for the backend source. A live end-to-end test against the user's Redis/PostgreSQL/browser environment has not been run in this workspace.
