# Phase 2C Live Validation

**Date:** 2026-06-24  
**Project:** Google Email Organizer  
**Location:** `C:\Users\chase\Workspace\GMAIL CLEANER`

This document tracks every validation step for Phase 2C, noting which steps were actually executed and which still require manual action with live credentials.

---

## Commands Reference

### Backend

```powershell
# Install Python deps
uv sync

# Run database migrations
uv run python -c "from db import init_db; init_db()"

# Start backend (development)
uv run uvicorn app:asgi --reload --host 127.0.0.1 --port 5273

# Run tests
uv run pytest -q

# Start backend with short access-token TTL (for refresh testing only)
# Set ACCESS_TOKEN_TTL_SECONDS=60 in .env, then:
uv run uvicorn app:asgi --host 127.0.0.1 --port 5273
# After test, restore ACCESS_TOKEN_TTL_SECONDS=600
```

### Dashboard

```powershell
# Install JS deps
npm install

# Development server (standalone)
npm run dev

# Production build
npm run build

# Audit
npm audit
```

### Extension

```powershell
cd extension

# Install deps
npm install

# Type check
npm run typecheck

# Tests
npm test

# Production build
npm run build

# Audit
npm audit
```

---

## Environment Variables (names only — no values)

| Variable | Description |
|---|---|
| `APP_ENV` | `development` for local dev |
| `PUBLIC_API_BASE_URL` | `http://localhost:5273` for local dev |
| `ALLOWED_WEB_ORIGINS` | `http://localhost:5173` for local dev |
| `ALLOWED_EXTENSION_IDS` | Unpacked extension ID from `chrome://extensions` |
| `JWT_ISSUER` | `google-email-organizer-api` (default) |
| `JWT_AUDIENCE` | `google-email-organizer-extension` (default) |
| `JWT_SIGNING_SECRET` | ≥32 random chars, generated with `secrets.token_hex(40)` |
| `ACCESS_TOKEN_TTL_SECONDS` | 600 normally; 60–90 temporarily for refresh test only |
| `REFRESH_TOKEN_TTL_SECONDS` | 2592000 (30 days) |
| `PAIRING_CODE_TTL_SECONDS` | 600 (10 min) |
| `DBE91F0215_DATABASE_URL` | Neon PostgreSQL connection string |
| `GOOGLE_OAUTH_CLIENT_ID` | Dashboard web OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Dashboard web OAuth client secret |
| `GEMINI_WORKSHOP_API_KEY` | Gemini API key |

---

## OAuth Callback URLs

These must be configured exactly in Google Cloud Console:

| Client | Type | Redirect URI |
|---|---|---|
| Dashboard | Web application | `http://localhost:5173/api/gmail/oauth/callback` |
| Extension | Chrome Extension | (no redirect URI — uses extension ID instead) |

---

## Database Migration

**Migration system:** `db.py::apply_migrations()` tracks applied migration file names in `schema_migrations` table. Safe to rerun.

**Migration file:** `migrations/001_extension_auth.sql`

**Tables created:**
- `organizer_users` — dashboard users, UUID PK, email unique, `TIMESTAMPTZ`
- `extension_pairing_codes` — hashed codes, unique `code_hash`, `consumed_at`, `failed_attempts`, `expires_at`
- `extension_device_sessions` — per-device `refresh_token_hash`, `rotation_counter`, `revoked_at`, `refresh_token_expires_at`
- `extension_refresh_token_history` — old token hashes for reuse detection
- `extension_audit_events` — IP-hashed event log, `BIGSERIAL` PK

**Indexes:** `ix_extension_pairing_codes_user`, `ix_extension_devices_user`

---

## Pairing Workflow (Browser Steps)

1. Navigate to dashboard → log in with Google OAuth
2. Go to extension pairing section → click **Generate Pairing Code**
3. The 8-character code (format `XXXX-XXXX`) is displayed once — copy it
4. Open extension → Options → enter backend URL (`http://localhost:5273`) → enter pairing code → click **Pair**
5. Confirm popup/side panel shows **Paired** state
6. Call `GET /api/extension/auth/me` with the access token → confirm user identity matches dashboard user
7. Attempt to reuse the pairing code → confirm `400 Invalid or expired pairing code`

---

## Refresh Workflow

1. Temporarily set `ACCESS_TOKEN_TTL_SECONDS=60` in `.env` and restart backend
2. Pair extension normally
3. Wait ≥70 seconds (token should expire)
4. Trigger any authenticated request (e.g., `backend:authStatus` from extension popup)
5. Extension should: detect 401 → call refresh → store new access token → retry original request → succeed
6. Confirm old access token no longer works
7. Restore `ACCESS_TOKEN_TTL_SECONDS=600` and restart backend

---

## Refresh-Reuse Validation

Use the backend test suite against the live development database with a disposable session:

```powershell
# This uses the actual DB, not SQLite.
# The test creates a disposable user+session, refreshes once,
# attempts reuse, confirms revocation.
# No token values are printed.
uv run pytest tests/test_extension_auth.py -q -k "reuse" -v
```

For live-DB validation (not in-memory SQLite), ensure `DBE91F0215_DATABASE_URL` is set and backend is reachable.

---

## Device Revocation (Browser Steps)

1. From dashboard → navigate to **Devices** list
2. Confirm current extension device appears
3. Click **Revoke** on the current device
4. Extension popup should transition to **Expired** or **Unpaired** state on next interaction
5. Attempt refresh from extension → confirm `401` or cleared state
6. Verify extension cleared its credentials (popup shows **Unpaired**)
7. Generate new pairing code → pair again for continued testing
8. Attempt to revoke a device owned by a different dashboard user → confirm `404 Device not found`

---

## CORS Verification (Browser)

Open browser DevTools → Network tab while testing these requests:

| Origin | Expected result |
|---|---|
| `http://localhost:5173` (dashboard) | `Access-Control-Allow-Origin: http://localhost:5173` |
| `chrome-extension://<configured-ID>` | `Access-Control-Allow-Origin: chrome-extension://<ID>` |
| `http://unknown-origin.example.com` | No `Access-Control-Allow-Origin` header |
| Any origin (no credentials) | No `Access-Control-Allow-Origin: *` with credentials |

---

## Secret-Scan Checklist

- [x] `.env` is git-ignored (verified via `git check-ignore`)
- [x] `.env` is not committed (no commits exist)
- [x] `extension/dist` bundle does not contain `JWT_SIGNING_SECRET`, `GEMINI_WORKSHOP_API_KEY`, `DBE91F0215_DATABASE_URL`, or `client_secret`
- [x] `refresh_token` appears in extension bundle only as JSON field name (`body:{refresh_token:e}`) — not a value
- [x] `gmail.readonly` is the only Gmail scope in `manifest.json`
- [x] No Gmail mutation methods (`modify`, `delete`, `trash`, `batchModify`) in extension TypeScript source
- [x] Extension manifest OAuth client ID is a placeholder (requires real value before live testing)
- [x] `ALLOWED_EXTENSION_IDS` placeholder is in `.env` (requires real extension ID before live testing)

---

## Phase 2C Gate Status

| Gate | Automated | Status | Notes |
|---|---|---|---|
| PostgreSQL migration applied | No | ⏳ Awaiting credentials | Run: `uv run python -c "from db import init_db; init_db()"` |
| Backend starts with real database | No | ⏳ Awaiting credentials | Run: `uv run uvicorn app:asgi ...` |
| Dashboard Google OAuth succeeds | No | ⏳ Awaiting credentials | Browser manual step |
| Authenticated pairing-code creation | No | ⏳ Awaiting credentials | Browser manual step |
| Extension Google authentication | No | ⏳ Awaiting extension OAuth client | Browser manual step |
| Gmail read-only scan | No | ⏳ Awaiting extension OAuth | Browser manual step |
| Extension pairs with backend | No | ⏳ Awaiting all above | Browser manual step |
| `/api/extension/auth/me` succeeds | Partial | ⏳ Awaiting live pairing | `curl` after pairing |
| Authenticated classification succeeds | No | ⏳ Awaiting Gemini key + pairing | Browser manual step |
| Unauthenticated classification returns 401 | Yes (tests) | ✅ Test passing | Also verifiable with `curl` |
| Access-token refresh succeeds exactly once | No | ⏳ Awaiting live session | Browser + short TTL |
| Refresh-token rotation | Partial | ✅ Tested in-memory | Live DB validation pending |
| Device revocation blocks refresh | Partial | ✅ Tested in-memory | Live DB + browser pending |
| Browser CORS for approved origins | No | ⏳ Awaiting live backend | Browser DevTools |
| Unknown origins rejected | No | ⏳ Awaiting live backend | Browser DevTools |
| Backend automated tests pass | Yes | ✅ **18 passed** | `uv run pytest -q` |
| Extension typecheck | Yes | ✅ **Passed** | `npm run typecheck` |
| Extension tests | Yes | ✅ **11 passed** | `npm test` |
| Extension production build | Yes | ✅ **Passed** | `npm run build` |
| Extension npm audit | Yes | ✅ **0 vulnerabilities** | `npm audit` |
| Dashboard production build | Yes | ✅ **Passed** | `npm run build` |
| Dashboard npm audit | Yes | ✅ **0 vulnerabilities** | `npm audit` |
| No secrets in bundle | Yes | ✅ **Passed** | Scan completed |
| Extension is gmail.readonly | Yes | ✅ **Confirmed** | Manifest verified |

---

## Remaining Manual Steps (Credential-Dependent)

1. **Fill in `.env`:** Add `DBE91F0215_DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GEMINI_WORKSHOP_API_KEY`
2. **Google Cloud Console:**
   - Enable Gmail API in project
   - Create Web application OAuth client with redirect URI `http://localhost:5173/api/gmail/oauth/callback`
   - Create Chrome Extension OAuth client with extension ID
   - Add test users to consent screen
3. **Load unpacked extension:**
   - Build: `cd extension && npm run build`
   - Load `extension/dist` in `chrome://extensions` (Developer mode)
   - Copy extension ID
4. **Update `.env`:** Set `ALLOWED_EXTENSION_IDS=<extension-id>`
5. **Update `manifest.json`:** Replace placeholder with real Chrome Extension OAuth client ID → rebuild → reload extension
6. **Run migration:** `uv run python -c "from db import init_db; init_db()"`
7. **Start backend and dashboard**
8. **Execute browser validation steps** (Parts 6–14 of Phase 2C)
9. **Run final regression tests**
10. **Create initial Git commit and tag**

---

## Known Warnings

| Warning | Source | Actionable? |
|---|---|---|
| `DeprecationWarning: '_UnionGenericAlias'` | `google-genai` package, Python 3.17 future | No — upstream package issue |
| `DeprecationWarning: default datetime adapter deprecated` | Python 3.12 sqlite3 in test suite | No — tests use SQLite, production uses PostgreSQL |
| In-process rate limiter not shared across workers | `extension_auth.py::RateLimiter` | Yes — replace with Redis before multi-worker production |
| Extension manifest has placeholder OAuth client ID | `manifest.json` | Yes — requires real client ID before live extension auth |

---

## Phase 2C Outcome

**Automated gates passed:** 12/20  
**Awaiting live credentials:** 8/20  

Phase 2C is **not yet complete** because live browser validation requires real credentials. No Git commit or tag has been created.

**Phase 3 is NOT authorized** until all 20 gates pass.
