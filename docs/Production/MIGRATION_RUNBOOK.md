# Migration Runbook — GmailCleaner

> **Status**: Pre-production beta.  
> **Last updated**: 2026-07-15

---

## Overview

GmailCleaner uses **Alembic** for schema migrations against a PostgreSQL database (Neon or Render Postgres).

---

## Before Any Migration

1. **Back up the database** — see your hosting provider's snapshot docs.
2. **Test the migration against a staging database first.**
3. Confirm you have the correct `DBE91F0215_DATABASE_URL` in your `.env`.

---

## Running Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Check current migration state
uv run alembic current

# Show pending migrations
uv run alembic history --verbose
```

---

## Creating a New Migration

```bash
# Auto-detect schema changes from SQLAlchemy models (review the output!)
uv run alembic revision --autogenerate -m "describe the change"

# Or create a blank migration template
uv run alembic revision -m "describe the change"
```

Always **review the generated migration file** before applying. Auto-generation can produce incorrect downgrade steps.

---

## Downgrading

```bash
# Downgrade one step
uv run alembic downgrade -1

# Downgrade to a specific revision
uv run alembic downgrade <revision_id>

# Downgrade to base (empty schema — destructive!)
uv run alembic downgrade base
```

> [!CAUTION]
> `downgrade base` drops all managed tables. Confirm this is intended and that a backup exists.

---

## Table Order (for manual reference)

If manually restoring or scripting deletes, respect FK order:

1. `recovery_action_logs`
2. `email_action_logs`
3. `operation_batches`
4. `email_classifications`
5. `scan_runs`
6. `gmail_labels`
7. `gmail_oauth_tokens`
8. `extension_audit_events`
9. `extension_refresh_token_history`
10. `extension_device_sessions`
11. `extension_pairing_codes`
12. `organizer_users`

---

## Neon-Specific Notes

- Neon supports **branching** — create a branch from production before running migrations.
- Use branch URL for staging tests, then merge/apply to production branch.
- See `docs/Production/NEON_PRODUCTION_DATABASE.md`.

---

## Troubleshooting

| Problem | Resolution |
|---|---|
| `alembic.util.exc.CommandError: Can't locate revision` | Run `alembic history` to find the current head; resolve conflicts manually |
| FK constraint violation on migration | Apply deletions in FK order before dropping tables |
| Migration applied but schema still wrong | Check `alembic_version` table; manual `UPDATE alembic_version SET version_num = '<target>'` as last resort |
