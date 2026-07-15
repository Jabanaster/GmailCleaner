# Neon Production Database Guide — GmailCleaner

> **Status**: Pre-production beta.  
> **Last updated**: 2026-07-15

---

## Why Neon

Neon is a serverless PostgreSQL provider offering:
- **Branching** — create isolated database branches for staging/testing without copying data.
- **Autoscaling** — scales to zero when idle; no charges for idle time on free tier.
- **Point-in-time restore** — roll back to any point within the retention window.
- **Connection pooling** — via PgBouncer endpoint (recommended for production).

---

## Connection Setup

### Environment Variable

```
DBE91F0215_DATABASE_URL=postgresql://<user>:<password>@<host>/<database>?sslmode=require
```

> [!IMPORTANT]
> Always use `sslmode=require` for Neon connections. Neon enforces TLS.

### Pooled vs. Direct Connection

| Endpoint type | When to use |
|---|---|
| **Pooled** (`-pooler` suffix in host) | Production FastAPI app (many short-lived connections) |
| **Direct** | Alembic migrations, one-off admin queries |

Use the **pooled endpoint** for `DBE91F0215_DATABASE_URL` in the running app.  
Use the **direct endpoint** for migration runs:

```bash
DBE91F0215_DATABASE_URL=<direct-url> uv run alembic upgrade head
```

---

## Database Branching Workflow

```
main branch (production)
  └── staging branch  ← test migrations here first
        └── feature branches (optional)
```

### Create a staging branch

1. Go to **Neon Console → Branches → New Branch**.
2. Branch from `main` at the current head.
3. Copy the connection string for the staging branch.
4. Run migrations against staging branch.
5. Verify application against staging.
6. Apply same migration to `main` branch in production.

---

## Backup and Restore

### Point-in-Time Restore (PITR)

1. Neon Console → Project → **Restore**.
2. Select timestamp.
3. Creates a new branch at that point — does not overwrite `main`.
4. Test the restored branch, then promote if needed.

### Manual Snapshot (before risky migrations)

```bash
pg_dump "<direct-neon-url>" > backup_$(date +%Y%m%d_%H%M%S).sql
```

Store backups in a secure location (not in the repository).

---

## Connection Limits

| Neon plan | Max connections |
|---|---|
| Free | 100 (pooled) |
| Launch | 300 (pooled) |
| Scale | Configurable |

GmailCleaner's default `uvicorn --workers 2` uses a small SQLAlchemy connection pool.
Default pool size: 5 per worker. Adjust `SQLALCHEMY_POOL_SIZE` if scaling workers.

---

## Monitoring

- Neon Console → **Monitoring** tab: query volume, CPU, memory.
- Enable **query insights** to catch slow queries.
- Set up alerts for connection limit thresholds.

---

## Security Notes

- Rotate database credentials before production launch (see `SECRET_ROTATION_RUNBOOK.md`).
- Use role-based access: create a read-only role for analytics/monitoring.
- Never share the production connection string outside of the hosting environment's secret manager.
