"""Production configuration validation tests.

Verifies that load_settings() fails closed on unsafe production configs
and that error messages never include secret values.
"""
import pytest

from config import load_settings

# ── Shared helpers ────────────────────────────────────────────────────────────

VALID_KEY = "m1y6C2fHWhlS9v_P7r7Y1T3Nf8u_k3zL0d3J-5s3o9o="  # 32-byte b64
STRONG_SECRET = "a-production-secret-that-is-at-least-32-characters-long"


def _prod_base(monkeypatch):
    """Set a minimal valid production environment."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SIGNING_SECRET", STRONG_SECRET)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("ALLOWED_EXTENSION_IDS", "abcdefghijklmnopqrstuvwxyzabcdef")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", VALID_KEY)
    monkeypatch.setenv("DBE91F0215_DATABASE_URL", "postgresql://user:pass@host/db")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "123.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "GOCSPX-placeholder")
    monkeypatch.delenv("DEBUG", raising=False)


# ── Existing tests (must continue to pass) ────────────────────────────────────

def test_production_rejects_http_and_missing_extension_ids(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SIGNING_SECRET", STRONG_SECRET)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://api.example.test")
    monkeypatch.setenv("ALLOWED_EXTENSION_IDS", "")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", VALID_KEY)
    with pytest.raises(RuntimeError):
        load_settings()


def test_localhost_http_is_allowed_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SIGNING_SECRET", STRONG_SECRET)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", VALID_KEY)
    assert load_settings().public_api_base_url == "http://localhost:8000"


# ── New Batch 6C tests ────────────────────────────────────────────────────────

def test_production_missing_encryption_key_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "OAUTH_TOKEN_ENCRYPTION_KEY" in str(exc.value)


def test_production_invalid_encryption_key_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", "not-a-valid-base64-key!!")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "OAUTH_TOKEN_ENCRYPTION_KEY" in str(exc.value)


def test_production_weak_session_secret_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("JWT_SIGNING_SECRET", "tooshort")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "JWT_SIGNING_SECRET" in str(exc.value)


def test_production_placeholder_secret_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("JWT_SIGNING_SECRET", "changeme")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "JWT_SIGNING_SECRET" in str(exc.value)


def test_production_wildcard_cors_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", "*")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "Wildcard" in str(exc.value)


def test_wildcard_cors_fails_in_development_too(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SIGNING_SECRET", STRONG_SECRET)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", VALID_KEY)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", "*")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "Wildcard" in str(exc.value)


def test_production_http_web_origin_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", "http://app.example.com")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    msg = str(exc.value)
    assert "HTTPS" in msg
    # Must not expose the origin value as a raw secret (URL is not sensitive,
    # but the error count pattern confirms it's the origin check not the secret check)
    assert "non-HTTPS origin" in msg


def test_production_http_public_api_url_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://api.example.com")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "PUBLIC_API_BASE_URL" in str(exc.value)


def test_production_missing_database_url_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("DBE91F0215_DATABASE_URL", "")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "DATABASE_URL" in str(exc.value)


def test_production_missing_oauth_client_id_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "GOOGLE_OAUTH_CLIENT_ID" in str(exc.value)


def test_production_missing_oauth_client_secret_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    # Error must name the var but must NOT include the word "secret value" literally
    msg = str(exc.value)
    assert "GOOGLE_OAUTH_CLIENT_SECRET" in msg
    # Confirm error says "(value not shown)" to prevent secret leakage
    assert "not shown" in msg


def test_production_debug_mode_fails(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    assert "DEBUG" in str(exc.value)


def test_production_valid_minimal_config_passes(monkeypatch):
    _prod_base(monkeypatch)
    settings = load_settings()
    assert settings.app_env == "production"
    assert settings.public_api_base_url == "https://api.example.com"


def test_development_config_remains_usable(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SIGNING_SECRET", STRONG_SECRET)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", VALID_KEY)
    monkeypatch.delenv("DBE91F0215_DATABASE_URL", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    settings = load_settings()
    assert settings.app_env == "development"


def test_errors_do_not_include_secret_values(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv("JWT_SIGNING_SECRET", "tooshort")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", "bad-key")
    with pytest.raises(RuntimeError) as exc:
        load_settings()
    msg = str(exc.value)
    # Must not contain the actual bad values
    assert "tooshort" not in msg
    assert "bad-key" not in msg
    # Must contain the sanitized description
    assert "JWT_SIGNING_SECRET" in msg
    assert "OAUTH_TOKEN_ENCRYPTION_KEY" in msg
    # Must have the "secret values omitted" header
    assert "omitted" in msg
