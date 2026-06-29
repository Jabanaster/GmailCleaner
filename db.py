"""Database initialization and schema for the Gmail sorter app."""
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Neon database connection (pooled URL for app queries)
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("DBE91F0215_DATABASE_URL")
        if not db_url:
            raise RuntimeError("DBE91F0215_DATABASE_URL not set — database connector not configured")
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def init_db():
    """Create tables if they don't exist."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gmail_oauth_tokens (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                access_token TEXT,
                refresh_token TEXT,
                token_expiry TIMESTAMP,
                scopes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gmail_labels (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                label_name VARCHAR(100) NOT NULL,
                gmail_label_id VARCHAR(255),
                category VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_email, label_name)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scan_runs (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                status VARCHAR(20) DEFAULT 'running',
                total_scanned INTEGER DEFAULT 0,
                total_emails INTEGER DEFAULT 0,
                total_crap INTEGER DEFAULT 0,
                total_categorized INTEGER DEFAULT 0,
                total_trashed INTEGER DEFAULT 0,
                total_labeled INTEGER DEFAULT 0,
                error_message TEXT
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS email_classifications (
                id SERIAL PRIMARY KEY,
                run_id INTEGER REFERENCES scan_runs(id),
                user_email VARCHAR(255) NOT NULL,
                gmail_message_id VARCHAR(255) NOT NULL,
                subject TEXT,
                sender TEXT,
                category VARCHAR(50),
                is_crap BOOLEAN DEFAULT FALSE,
                crap_reason TEXT,
                confidence REAL DEFAULT 0.0,
                action_taken VARCHAR(50),
                classified_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.commit()
    apply_migrations()


def apply_migrations():
    """Apply checked-in idempotent SQL migrations without recreating data."""
    migrations_dir = Path(__file__).with_name("migrations")
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (name VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
        applied = {row[0] for row in conn.execute(text("SELECT name FROM schema_migrations"))}
        for migration in sorted(migrations_dir.glob("*.sql")):
            if migration.name in applied:
                continue
            for statement in migration.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.execute(text("INSERT INTO schema_migrations (name) VALUES (:name)"), {"name": migration.name})


def get_setting(key: str, default: str = None) -> str:
    """Get a setting from the app_settings table."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT value FROM app_settings WHERE key = :key"),
            {"key": key}
        ).fetchone()
        return result[0] if result else default


def set_setting(key: str, value: str):
    """Set a setting in the app_settings table."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (:key, :value, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = :value, updated_at = NOW()
        """), {"key": key, "value": value})
        conn.commit()
