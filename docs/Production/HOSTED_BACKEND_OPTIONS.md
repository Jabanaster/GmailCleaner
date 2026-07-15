# Hosted Backend Options — GmailCleaner

> **Status**: Pre-production beta.  
> **Last updated**: 2026-07-15

---

## Overview

GmailCleaner's backend is a standard ASGI app (`uvicorn app:asgi`).
It can be deployed to any host that supports Python ASGI workloads and
environment variable configuration.

---

## Option A — Render (Recommended for Simplicity)

**Cost**: Free tier available; Starter plan $7/month for always-on.

### Setup

1. Connect your GitHub repository to Render.
2. Create a new **Web Service**.
3. Set:
   - **Build command**: `npm ci && npm run build && uv sync`
   - **Start command**: `uv run uvicorn app:asgi --host 0.0.0.0 --port $PORT`
   - **Environment**: Add all required env vars from `.env.example`.
4. Add a **PostgreSQL** database (Render Postgres) or use Neon via `DATABASE_URL`.
5. Deploy.

### Health Check

Set health check path to `/api/health` in Render service settings.

### Static Files

The Vite build output (`dist/`) is served directly by the FastAPI app via
`StaticFiles`. No separate CDN setup is needed for the beta.

---

## Option B — Google Cloud Run

**Cost**: Pay-per-request; free tier covers low traffic.

### Dockerfile (minimal)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

# Install Node.js for build step
RUN apt-get update && apt-get install -y nodejs npm
RUN npm ci && npm run build

# Install Python dependencies
RUN pip install uv && uv sync

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "app:asgi", "--host", "0.0.0.0", "--port", "8080"]
```

### Deploy

```bash
gcloud builds submit --tag gcr.io/<PROJECT_ID>/gmail-cleaner
gcloud run deploy gmail-cleaner \
  --image gcr.io/<PROJECT_ID>/gmail-cleaner \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars APP_ENV=production,...
```

### Notes

- Store secrets in **Secret Manager** and reference them via `--set-secrets`.
- Set `--min-instances 1` to avoid cold start on OAuth callbacks.
- Configure `--timeout 300` for scan operations.

---

## Option C — Railway

**Cost**: Starter $5/month credit.

1. Connect GitHub repo.
2. Railway auto-detects Python; override start command:
   ```
   uv run uvicorn app:asgi --host 0.0.0.0 --port $PORT
   ```
3. Add a PostgreSQL plugin or connect external Neon database.
4. Set environment variables in Railway dashboard.

---

## Option D — Self-Hosted (VPS)

Not recommended for beta. If required:

1. Set up a Linux server (Ubuntu 22.04+).
2. Install Python 3.12, Node.js 20, nginx.
3. Use `systemd` or `supervisor` to manage the uvicorn process.
4. Terminate TLS at nginx and proxy to uvicorn.
5. Use `certbot` for HTTPS certificates.

---

## Comparison

| Feature | Render | Cloud Run | Railway | Self-Hosted |
|---|---|---|---|---|
| Zero-config deploy | ✅ | Moderate | ✅ | ❌ |
| Always-on (no cold start) | ✅ Starter+ | ✅ min=1 | ✅ | ✅ |
| Managed TLS | ✅ | ✅ | ✅ | Manual |
| Persistent storage | Limited | ❌ | Limited | ✅ |
| Secret management | Env vars | Secret Manager | Env vars | Manual |
| Estimated cost (beta) | $7–$15/mo | $0–$5/mo | $5/mo | VPS cost |

**Recommended for beta**: Render (simplest) or Cloud Run (most scalable).

---

## Google OAuth Redirect URI

Regardless of host, register the redirect URI in **Google Cloud Console**:

```
https://<your-domain>/oauth/callback
```

Add this to **Authorized redirect URIs** in your OAuth 2.0 client configuration.
