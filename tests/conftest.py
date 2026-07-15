from dataclasses import replace
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from config import Settings


SCHEMA = """
CREATE TABLE organizer_users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, display_name TEXT, created_at TIMESTAMP, last_login_at TIMESTAMP);
CREATE TABLE extension_pairing_codes (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, code_hash TEXT UNIQUE NOT NULL, created_at TIMESTAMP NOT NULL, expires_at TIMESTAMP NOT NULL, consumed_at TIMESTAMP, failed_attempts INTEGER NOT NULL DEFAULT 0, created_ip_hash TEXT);
CREATE TABLE extension_device_sessions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, device_name TEXT NOT NULL, extension_version TEXT NOT NULL, created_at TIMESTAMP NOT NULL, last_seen_at TIMESTAMP NOT NULL, revoked_at TIMESTAMP, refresh_token_hash TEXT NOT NULL, refresh_token_expires_at TIMESTAMP NOT NULL, rotation_counter INTEGER NOT NULL DEFAULT 0);
CREATE TABLE extension_refresh_token_history (token_hash TEXT PRIMARY KEY, device_session_id TEXT NOT NULL, rotated_at TIMESTAMP NOT NULL);
CREATE TABLE extension_audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, user_id TEXT, device_session_id TEXT, ip_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE scan_runs (id INTEGER PRIMARY KEY, user_email TEXT NOT NULL, started_at TIMESTAMP, completed_at TIMESTAMP, status TEXT, total_scanned INTEGER DEFAULT 0, total_emails INTEGER DEFAULT 0, total_crap INTEGER DEFAULT 0, total_categorized INTEGER DEFAULT 0, total_trashed INTEGER DEFAULT 0, total_labeled INTEGER DEFAULT 0, dry_run BOOLEAN DEFAULT FALSE, error_message TEXT);
CREATE TABLE email_classifications (id INTEGER PRIMARY KEY, run_id INTEGER, user_email TEXT NOT NULL, gmail_message_id TEXT, subject TEXT, sender TEXT, category TEXT, is_crap BOOLEAN, crap_reason TEXT, confidence REAL, action_taken TEXT, classified_at TIMESTAMP);
CREATE TABLE gmail_oauth_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, access_token TEXT, refresh_token TEXT, token_expiry TIMESTAMP, scopes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE gmail_labels (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT NOT NULL, label_name TEXT NOT NULL, gmail_label_id TEXT, category TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_email, label_name));
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""


@pytest.fixture
def settings():
    os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"] = "m1y6C2fHWhlS9v_P7r7Y1T3Nf8u_k3zL0d3J-5s3o9o="
    return Settings(
        app_env="development", public_api_base_url="http://localhost:8000", allowed_web_origins=("http://localhost:5173",),
        allowed_extension_ids=("abcdefghijklmnopabcdefghijklmnop",), jwt_issuer="google-email-organizer-api",
        jwt_audience="google-email-organizer-extension", jwt_signing_secret="test-signing-secret-that-is-at-least-32-characters",
        access_token_ttl_seconds=600, refresh_token_ttl_seconds=2_592_000, pairing_code_ttl_seconds=600,
        oauth_token_encryption_key="m1y6C2fHWhlS9v_P7r7Y1T3Nf8u_k3zL0d3J-5s3o9o=",
        scan_batch_size=10,
        scan_batch_delay_ms=0,
        gmail_quota_backoff_ms=0,
        gmail_max_retry_attempts=3,
        min_classification_confidence=0.80,
    )





@pytest.fixture
def engine():
    from sqlalchemy import event
    import datetime
    value = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(value, "connect")
    def register_sqlite_funcs(dbapi_connection, connection_record):
        dbapi_connection.create_function("now", 0, lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
        dbapi_connection.create_function("to_timestamp", 1, lambda val: datetime.datetime.fromtimestamp(val, datetime.timezone.utc).isoformat() if val is not None else None)


    with value.begin() as conn:
        for statement in SCHEMA.split(";"):
            if statement.strip(): conn.execute(text(statement))
        conn.execute(text("INSERT INTO organizer_users (id, email) VALUES ('user-a', 'a@example.test'), ('user-b', 'b@example.test')"))
    return value


@pytest.fixture(autouse=True)
def clear_rate_limits():
    from extension_auth import rate_limiter
    rate_limiter._events.clear()
