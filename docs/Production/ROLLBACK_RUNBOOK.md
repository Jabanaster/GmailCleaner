# Rollback Runbook — GmailCleaner

> **Status**: Pre-production beta.  
> **Last updated**: 2026-07-15

---

## When to Roll Back

Roll back if any of the following occur after a deployment:

- Health check (`/api/health`) fails or returns non-200.
- OAuth login loop or token errors affecting more than 1 user.
- Extension pairing fails for all devices.
- Scan start endpoint returns 500 for all authenticated users.
- Database connection errors visible in logs.
- Any unhandled exception in a path that previously worked.

---

## Decision Tree

```
Is the database schema changed?
  YES → Schema rollback required (see Step 3)
  NO  → Code-only rollback (see Step 1)
```

---

## Step 1 — Code-Only Rollback (Render / Cloud Run)

### Render

1. Go to **Render Dashboard → GmailCleaner service → Deploys**.
2. Find the last known-good deploy.
3. Click **Re-deploy** on that commit.
4. Wait for health check to pass.

### Cloud Run

```bash
gcloud run services update-traffic gmail-cleaner \
  --to-revisions=<PREVIOUS_REVISION>=100
```

---

## Step 2 — Environment Variable Rollback

If the rollback is caused by a changed/missing env var:

1. Edit environment variables in Render dashboard or `gcloud run services update --set-env-vars`.
2. Re-deploy or roll traffic back.

---

## Step 3 — Schema Rollback (Alembic)

> [!WARNING]
> Always restore from a database backup before downgrading schema in production.

```bash
# Identify the revision to roll back to
uv run alembic history --verbose

# Downgrade one step
uv run alembic downgrade -1

# Or to a specific revision
uv run alembic downgrade <target_revision>
```

After schema rollback, redeploy the previous code version (Step 1).

---

## Step 4 — Verify Rollback

```bash
curl -sf https://<your-domain>/api/health
# Expected: {"ok": true}
```

Also verify:

- [ ] OAuth login completes successfully.
- [ ] Extension pairing code generation succeeds.
- [ ] Scan status endpoint returns 200.
- [ ] Dry-run scan starts and stops cleanly.

---

## Communication Checklist

- [ ] Notify affected users if downtime exceeded 5 minutes.
- [ ] Write internal incident note with: root cause, timeline, resolution, prevention.
- [ ] File a GitHub issue tagged `incident` with the post-mortem.

---

## Prevention Notes

- Always test migrations against a staging/branch database before production.
- Never deploy schema migrations and code changes simultaneously without a tested rollback plan.
- Keep the last 3 known-good deploy IDs documented after each release.
