# Phase 2 backend completion gate

## Implementation complete (Phase 2B)

The FastAPI/SQLAlchemy/PostgreSQL application at `C:\Users\chase\Workspace\GMAIL CLEANER` implements:

- **Pairing codes:** Dashboard-only creation, hashed with HMAC-SHA256, single-use, 10-minute expiry, consumed atomically with failed-attempt tracking
- **Access JWTs:** Short-lived (10-minute default), HS256, validated claims (`iss`, `aud`, `sub`, `sid`, `jti`, `iat`, `nbf`, `exp`, `scope`)
- **Rotating refresh tokens:** Hashed at rest, rotated on every use, reuse detected via history table, device session revoked on reuse
- **CORS:** Explicit allowlist (`ALLOWED_WEB_ORIGINS` + `ALLOWED_EXTENSION_IDS`), no wildcard, fail-closed config
- **Security gates:** Production startup rejects weak secrets, HTTP non-loopback URLs, wildcard CORS, missing extension IDs, debug mode
- **Request limits:** 1 MB body limit, `application/json` content type enforcement on extension POST routes
- **Rate limiting:** Per-user code creation, per-IP pairing attempts, per-IP refresh attempts (in-process limiter)
- **Audit events:** Hashed IPs, no raw credentials, recorded for pairing success/failure, refresh, reuse, revocation, auth failure
- **User ownership:** Scan and classification endpoints enforce user identity from session; `user_id` in request body is rejected
- **Device management:** List devices, revoke by ID (dashboard-only), self-revoke (extension bearer token)

## Automated test coverage (18 tests, SQLite in-memory)

- Concurrent one-time pairing (race condition prevention)
- Expired and reused pairing-code rejection
- Refresh-token rotation
- Refresh-token reuse revocation
- Unauthenticated classification rejection (401)
- Two-user scan ownership isolation
- Two-user classification ownership isolation
- Cross-user device revocation denial
- Caller-supplied `user_id` rejection
- Config: wildcard CORS rejection, placeholder secret rejection, production HTTP rejection

## Migration (001_extension_auth.sql)

Creates five tables tracked by `schema_migrations`:
- `organizer_users` — dashboard user identity (email-keyed, UUID PK)
- `extension_pairing_codes` — hashed, expiring, single-use codes
- `extension_device_sessions` — per-device refresh credential (hashed), rotation counter, revocation
- `extension_refresh_token_history` — old token hashes for reuse detection
- `extension_audit_events` — IP-hashed event log

All tables use `TIMESTAMPTZ`, `IF NOT EXISTS`, proper FK/index/unique constraints.

## Remaining gate: Live end-to-end validation (Phase 2C)

The following runtime values were not available during Phase 2B implementation and are required to complete Phase 2C:

| Required item | Status |
|---|---|
| `DBE91F0215_DATABASE_URL` — Neon/PostgreSQL URL | ⏳ Must be added to `.env` |
| `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` | ⏳ Must be added to `.env` |
| `GEMINI_WORKSHOP_API_KEY` | ⏳ Must be added to `.env` |
| Chrome Extension OAuth client ID | ⏳ Must be set in `manifest.json` |
| Unpacked extension ID | ⏳ Must be added to `ALLOWED_EXTENSION_IDS` |
| OAuth consent screen test users | ⏳ Must be configured in Google Cloud |
| Dashboard OAuth redirect URI configured | ⏳ `http://localhost:5173/api/gmail/oauth/callback` |

## Non-credential gates already passing

- `.gitignore` covers `.env`, `coverage/`, `venv/`
- Backend automated tests: **18 passed**
- Extension typecheck: **passed**
- Extension tests: **11 passed**
- Extension production build: **passed**
- Extension npm audit: **0 vulnerabilities**
- Dashboard production build: **passed**
- Dashboard npm audit: **0 vulnerabilities**
- Source scan: `gmail.readonly` only in manifest
- Source scan: no Gmail mutation methods in extension TypeScript
- Source scan: no embedded secrets in extension bundle
- Config gate: placeholder JWT secret rejected
- Config gate: wildcard CORS rejected

## Known warnings (non-actionable)

- `DeprecationWarning: '_UnionGenericAlias'` — from `google-genai` package internals, Python 3.17 future deprecation
- `DeprecationWarning: The default datetime adapter is deprecated` — SQLite sqlite3 adapter in Python 3.12, affects test suite only (production uses PostgreSQL)
- In-process rate limiter is not shared across multiple uvicorn workers — documented gap, acceptable for single-worker development

## API surface

| Method | Path | Auth |
|---|---|---|
| POST | `/api/extension/pairing-codes` | Dashboard session cookie |
| POST | `/api/extension/pair` | None (consumes pairing code) |
| POST | `/api/extension/auth/refresh` | None (consumes refresh token) |
| GET | `/api/extension/auth/me` | Bearer access token |
| POST | `/api/extension/auth/revoke` | Bearer access token |
| GET | `/api/extension/devices` | Dashboard session cookie |
| DELETE | `/api/extension/devices/{id}` | Dashboard session cookie |
| POST | `/api/extension/classify-preview` | Bearer access token |
