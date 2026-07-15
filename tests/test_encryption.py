import pytest
from datetime import datetime, timezone
import os
from sqlalchemy import text
from cryptography.fernet import Fernet

import db
import gmail_service
from config import Settings


def setup_test_env(monkeypatch, settings):
    monkeypatch.setenv("APP_ENV", settings.app_env)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", settings.public_api_base_url)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", ",".join(settings.allowed_web_origins))
    monkeypatch.setenv("ALLOWED_EXTENSION_IDS", ",".join(settings.allowed_extension_ids))
    monkeypatch.setenv("JWT_SIGNING_SECRET", settings.jwt_signing_secret)
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", settings.oauth_token_encryption_key)


def test_tokens_are_stored_encrypted(engine, monkeypatch, settings):
    setup_test_env(monkeypatch, settings)
    monkeypatch.setattr(db, "_engine", engine)
    
    # Store token using standard store_tokens
    user_email = "test_enc@example.test"
    tokens = {
        "access_token": "mock_access",
        "refresh_token": "my_secret_refresh_token_xyz",
        "expires_in": 3600
    }
    
    gmail_service.store_tokens(user_email, tokens)
    
    # Verify the stored value directly in DB is encrypted
    with engine.connect() as conn:
        row = conn.execute(text("SELECT refresh_token FROM gmail_oauth_tokens WHERE email = :email"), {"email": user_email}).fetchone()
    
    db_val = row[0]
    assert db_val != "my_secret_refresh_token_xyz"
    assert "my_secret_refresh_token_xyz" not in db_val
    assert db_val.startswith("gAAAAA")  # Standard Fernet prefix


def test_tokens_are_decrypted_on_retrieve(engine, monkeypatch, settings):
    setup_test_env(monkeypatch, settings)
    monkeypatch.setattr(db, "_engine", engine)
    
    user_email = "test_dec@example.test"
    tokens = {
        "access_token": "mock_access",
        "refresh_token": "my_secret_refresh_token_123",
        "expires_in": 3600
    }
    
    gmail_service.store_tokens(user_email, tokens)
    
    # Retrieve and verify it is decrypted transparently
    retrieved = gmail_service.get_stored_tokens(user_email)
    assert retrieved["refresh_token"] == "my_secret_refresh_token_123"


def test_legacy_plaintext_is_rejected_and_fails_closed(engine, monkeypatch, settings):
    setup_test_env(monkeypatch, settings)
    monkeypatch.setattr(db, "_engine", engine)
    
    from datetime import timedelta
    # Manually insert a legacy plaintext token row into database
    user_email = "legacy@example.test"
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO gmail_oauth_tokens (email, access_token, refresh_token, token_expiry, scopes)
            VALUES (:email, 'mock_access', 'raw_legacy_refresh_token_123', :expiry, 'scopes')
        """), {"email": user_email, "expiry": datetime.now(timezone.utc) + timedelta(hours=1)})
    
    # Retrieve it — should return None (failing closed) since plaintext is rejected
    retrieved = gmail_service.get_stored_tokens(user_email)
    assert retrieved is None



def test_invalid_encryption_key_fails(engine, monkeypatch, settings):
    setup_test_env(monkeypatch, settings)
    monkeypatch.setattr(db, "_engine", engine)
    
    user_email = "bad_key@example.test"
    tokens = {
        "access_token": "mock_access",
        "refresh_token": "some_refresh",
        "expires_in": 3600
    }
    gmail_service.store_tokens(user_email, tokens)
    
    # Try retrieving with a different encryption key
    bad_settings = Settings(
        app_env=settings.app_env,
        public_api_base_url=settings.public_api_base_url,
        allowed_web_origins=settings.allowed_web_origins,
        allowed_extension_ids=settings.allowed_extension_ids,
        jwt_issuer=settings.jwt_issuer,
        jwt_audience=settings.jwt_audience,
        jwt_signing_secret=settings.jwt_signing_secret,
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_token_ttl_seconds=settings.refresh_token_ttl_seconds,
        pairing_code_ttl_seconds=settings.pairing_code_ttl_seconds,
        oauth_token_encryption_key=Fernet.generate_key().decode(),  # Random bad key
        scan_batch_size=settings.scan_batch_size,
        scan_batch_delay_ms=settings.scan_batch_delay_ms,
        gmail_quota_backoff_ms=settings.gmail_quota_backoff_ms,
        gmail_max_retry_attempts=settings.gmail_max_retry_attempts,
        min_classification_confidence=0.80,
    )

    
    # We monkeypatch the settings returned by routes or config to return bad_settings
    import config
    monkeypatch.setattr(config, "load_settings", lambda: bad_settings)

    
    # Retrieval should fail closed and return None because decryption fails
    retrieved = gmail_service.get_stored_tokens(user_email)
    assert retrieved is None

