# Google Email Organizer

A standalone Gmail organizer with React/Vite, FastAPI, SQLAlchemy/PostgreSQL, server-side Gemini classification, and a Manifest V3 Chrome companion extension.

## Architecture

```
React/Vite dashboard  ──► FastAPI backend  ──► Neon/PostgreSQL
Chrome MV3 extension  ──► FastAPI backend  ──► Gemini (server-side)
                              │
                              └── Gmail API (dashboard only, gmail.modify)
Extension ──► Gmail API (gmail.readonly, via chrome.identity, NOT forwarded to backend)
```

## Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with npm (or bun)
- A Neon (or other PostgreSQL) database
- A Google Cloud project with Gmail API enabled
- A Gemini API key

## Quick Start

### 1. Environment setup

```powershell
Copy-Item .env.example .env
# Edit .env — fill in all credentials (see Environment Variables below)
```

Generate a strong `JWT_SIGNING_SECRET` (must be ≥32 random characters):

```powershell
python -c "import secrets; print(secrets.token_hex(40))"
```

Paste the output into `.env` as the `JWT_SIGNING_SECRET` value. Do not commit it.

### 2. Start the development servers

```powershell
.\start.ps1
```

This installs Python and JavaScript dependencies, then starts:
- FastAPI backend on `http://localhost:5273`
- Vite dev server on `http://localhost:5173` (proxies `/api` to backend)

Or start them separately:

```powershell
# Backend only
uv run uvicorn app:asgi --reload --host 127.0.0.1 --port 5273

# Dashboard only (separate terminal)
npm install
npm run dev
```

### 3. Database migration

Migrations run automatically on startup via `db.py::init_db()`. To run manually:

```powershell
uv run python -c "from db import init_db; init_db()"
```

Migrations are idempotent — safe to run multiple times.

### 4. Extension setup

See [extension/README.md](extension/README.md) for full OAuth and loading instructions.

```powershell
cd extension
npm install
npm run typecheck
npm test
npm run build
# Load extension/dist as unpacked in chrome://extensions
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | Yes | `development` or `production` |
| `PUBLIC_API_BASE_URL` | Yes | Backend public URL (HTTPS required outside loopback dev) |
| `ALLOWED_WEB_ORIGINS` | Yes | Dashboard origin(s) for CORS, comma-separated |
| `ALLOWED_EXTENSION_IDS` | Yes (prod) | Chrome extension ID(s), comma-separated |
| `JWT_ISSUER` | No | Defaults to `google-email-organizer-api` |
| `JWT_AUDIENCE` | No | Defaults to `google-email-organizer-extension` |
| `JWT_SIGNING_SECRET` | Yes | ≥32 random chars, never a placeholder |
| `ACCESS_TOKEN_TTL_SECONDS` | No | Default 600 (10 min) |
| `REFRESH_TOKEN_TTL_SECONDS` | No | Default 2592000 (30 days) |
| `PAIRING_CODE_TTL_SECONDS` | No | Default 600 (10 min) |
| `DBE91F0215_DATABASE_URL` | Yes | PostgreSQL connection string |
| `GOOGLE_OAUTH_CLIENT_ID` | Yes | Dashboard Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Yes | Dashboard Google OAuth client secret |
| `GEMINI_WORKSHOP_API_KEY` | Yes | Gemini API key for classification |

Do not add credentials to `.env.example`. Do not commit `.env`. `.gitignore` excludes all `.env.*` files except `.env.example`.

## Project Structure

```
├── src/                   # React dashboard frontend
│   ├── components/ui/     # shadcn/ui components
│   └── App.tsx            # Main app component
├── app.py                 # FastAPI ASGI entry point
├── routes.py              # Dashboard API routes + SPA fallback
├── extension_routes.py    # Authenticated extension API (/api/extension/*)
├── extension_auth.py      # Pairing codes, JWT issuance, refresh rotation
├── config.py              # Fail-closed settings loader
├── db.py                  # Database engine + migration runner
├── classifier.py          # Server-side Gemini classification
├── gmail_service.py       # Gmail API utilities (dashboard)
├── migrations/            # Idempotent SQL migration files
│   └── 001_extension_auth.sql
├── extension/             # MV3 Chrome companion extension
│   ├── src/               # TypeScript source
│   ├── manifest.json      # Extension manifest (gmail.readonly only)
│   ├── docs/              # Extension-specific documentation
│   └── README.md
├── tests/                 # Backend test suite (SQLite in-memory)
├── start.ps1              # Windows combined dev launcher
├── start.sh               # Unix combined dev launcher
└── .env.example           # Environment variable template
```

## Development

### Backend tests

```powershell
uv run pytest -q
```

### Extension checks

```powershell
cd extension
npm run typecheck   # TypeScript type check
npm test            # Vitest unit tests
npm run build       # Production bundle
npm audit           # Dependency vulnerability scan
```

### Dashboard checks

```powershell
npm run build   # Production bundle (from root)
npm audit       # Dependency vulnerability scan
```

## Extension Pairing Workflow

1. Log in to the dashboard via Google OAuth
2. Navigate to the extension pairing section
3. Click **Generate Pairing Code** — a 10-minute one-time code is displayed
4. Open the extension options page and enter the backend URL + pairing code
5. The extension stores an organizer refresh token in `chrome.storage.local`
6. Subsequent requests use short-lived access tokens refreshed automatically

The extension uses only `gmail.readonly` for its own Gmail access. Gmail tokens stay in Chrome Identity and are never forwarded to the backend.

## Security Notes

- The backend refuses to start with a weak `JWT_SIGNING_SECRET`
- Wildcard CORS origins are forbidden at the config level
- Non-loopback HTTP backend URLs are rejected in production and by the extension
- Pairing codes are single-use, hashed at rest, and expire after 10 minutes
- Refresh tokens rotate on each `/auth/refresh` call; reuse of a superseded token triggers immediate device revocation. Ordinary authenticated requests consume the current access token and do not rotate credentials.
- Access tokens are session-scoped (`chrome.storage.session`) and expire with the browser session
- Classification happens server-side — Gemini is never called from the extension

## Phase Status

* **Phase 1 — Dashboard, Backend, Gmail API**: Complete
* **Phase 2A — Extension skeleton + Gmail readonly**: Complete
* **Phase 2B automated security gate**: Complete (25 tests passing)
* **Review-fix reconciliation**: Complete
* **Dry-run preview feature**: Implemented and reconciled, but not live-validated
* **Phase 2C live environment validation**: Pending
* **Phase 3 overall**: Not authorized as complete

> [!IMPORTANT]
> The application is not yet production-ready. Several live Phase 2C validation blockers (such as Neon migration, live OAuth credentials, HTTPS, and live pairing) must be resolved.

## Reliability Improvements (Phase 2C)

- **Retry logic**: All Gmail API calls (`fetch_messages`, `fetch_message_detail`, `trash_message`, `add_label_to_message`, `remove_from_inbox`, `get_user_profile`, `ensure_labels_exist`) use exponential backoff (up to 3 retries, doubling delay starting at 1s).
- **Scan progress tracking**: The `scan_runs` table stores `total_emails` so the dashboard can display a real percentage progress bar during active scans.
- **Toast notifications**: All user-facing actions (connect, disconnect, scan start/fail, device revoke) show toast notifications.

## Phase 2C Live-Validation Checklist

Complete every item below in order before committing or tagging.

- [ ] 1. Apply migrations `001`, `002`, and `003` to the real Neon database and confirm each row in `schema_migrations`.
- [ ] 2. Start the backend with the real `DBE91F0215_DATABASE_URL` and confirm a clean startup log.
- [ ] 3. Validate the dashboard Google OAuth callback end-to-end: connect an account, confirm session cookie, confirm token row in `gmail_oauth_tokens`.
- [ ] 4. Load the extension with the actual published extension ID; confirm `ALLOWED_EXTENSION_IDS` matches and pairing completes.
- [ ] 5. Run a live dry-run (preview) Gmail scan through the dashboard; confirm no Gmail mutations and `dry_run = true` in `scan_runs`.
- [ ] 6. Pair the extension with the backend using a live pairing code.
- [ ] 7. Call `/api/extension/auth/me` with a valid bearer token and confirm the correct user and device are returned.
- [ ] 8. Run a live Gemini classification request from the extension (`/api/extension/classify-preview`) and verify structured JSON output.
- [ ] 9. Let the access token expire naturally (or advance the clock); perform one refresh and confirm the new token is accepted and the old token is rejected.
- [ ] 10. Reuse the superseded refresh token and confirm the session is immediately revoked.
- [ ] 11. Revoke the device from the dashboard and confirm subsequent refresh attempts fail with `401`.
- [ ] 12. Verify browser CORS: an approved origin receives the correct headers; an unknown origin is rejected.
- [ ] 13. Re-run all 25 backend tests, dashboard build, and extension typecheck/test/build/audit — all must pass.
- [ ] 14. Commit and tag only after every item above is checked off.

> [!CAUTION]
> No further Phase 3 feature development should occur before Phase 2C live validation is complete.
