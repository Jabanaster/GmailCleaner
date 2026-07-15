import pytest

from config import load_settings


def test_production_rejects_http_and_missing_extension_ids(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SIGNING_SECRET", "a-production-secret-that-is-at-least-32-characters")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://api.example.test")
    monkeypatch.setenv("ALLOWED_EXTENSION_IDS", "")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", "m1y6C2fHWhlS9v_P7r7Y1T3Nf8u_k3zL0d3J-5s3o9o=")
    with pytest.raises(RuntimeError): load_settings()


def test_localhost_http_is_allowed_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SIGNING_SECRET", "a-development-secret-that-is-at-least-32-characters")
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", "m1y6C2fHWhlS9v_P7r7Y1T3Nf8u_k3zL0d3J-5s3o9o=")
    assert load_settings().public_api_base_url == "http://localhost:8000"

