# Deployment Runbook — GmailCleaner

> **Status**: Pre-production beta.  
> **Last updated**: 2026-07-15

---

## Overview

GmailCleaner is a FastAPI backend + Vite dashboard served as a single ASGI process.
The extension is a standalone Chrome/MV3 package distributed separately.

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Python | 3.12 |
| Node.js | 20 LTS |
| PostgreSQL (Neon or Render Postgres) | 15 |
| Chrome Extension manifest version | 3 |

---

## 1. Environment Variables

Copy `.env.example` to `.env` (never commit `.env`).  
Set **all** required production values — see
`docs/Production/ENVIRONMENT_AND_SECRET_MANAGEMENT.md`.

Required production env vars:

```
APP_ENV=production
PUBLIC_API_BASE_URL=https://<your-domain>
ALLOWED_WEB_ORIGINS=https://<your-dashboard-domain>
ALLOWED_EXTENSION_IDS=<chrome-extension-id>
JWT_SIGNING_SECRET=<32+ char random secret>
OAUTH_TOKEN_ENCRYPTION_KEY=<32-byte base64 key>
DBE91F0215_DATABASE_URL=postgresql://<user>:<pass>@<host>/<db>
GOOGLE_OAUTH_CLIENT_ID=<client-id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=<client-secret>
```

Generate secrets:

```bash
# JWT signing secret
python -c "import secrets; print(secrets.token_hex(32))"

# Encryption key (Fernet 32-byte base64)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 2. Build Dashboard

```bash
npm ci
npm run build
# Output: dist/
```

---

## 3. Run Database Migrations

```bash
# Apply all pending Alembic migrations
uv run alembic upgrade head
```

Verify migrations completed:

```bash
uv run alembic current
```

---

## 4. Start Server

### Option A — Render / Cloud Run (recommended)

See `docs/Production/HOSTED_BACKEND_OPTIONS.md`.

### Option B — Local/Self-Hosted

```bash
uv run uvicorn app:asgi --host 0.0.0.0 --port 8000 --workers 2
```

---

## 5. Health Check Verification

After deployment, confirm:

```bash
curl -sf https://<your-domain>/api/health
# Expected: {"ok": true}
```

Also verify:

- Dashboard loads at `https://<your-domain>/`
- OAuth login redirects correctly
- `/api/scan/status` returns 200 (unauthenticated → no session, not 500)

---

## 6. Post-Deploy Checks

- [ ] `APP_ENV=production` confirmed via healthcheck log
- [ ] Session cookies marked `Secure` and `SameSite=Lax`
- [ ] No `DEBUG=true` in environment
- [ ] Extension connects successfully via pairing flow
- [ ] Dry-run scan completes without Gmail mutations
- [ ] OAuth token encryption verified (see `test_encryption.py`)

---

## 7. Rollback

See `docs/Production/ROLLBACK_RUNBOOK.md`.
