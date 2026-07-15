"""OAuth redirect URI resolution and callback session behavior."""
from unittest.mock import MagicMock

import httpx
from starlette.testclient import TestClient

import gmail_service as gs
from tests.test_extension_api import make_app


class DummyRequest:
    def __init__(self, headers: dict | None = None, scheme: str = "http"):
        self.headers = headers or {}
        self.url = MagicMock(scheme=scheme)


def test_redirect_uri_uses_origin_on_oauth_start(monkeypatch):
    monkeypatch.delenv("WORKSHOP_CUSTOM_DOMAIN", raising=False)
    monkeypatch.delenv("OAUTH_REDIRECT_BASE", raising=False)
    request = DummyRequest({"origin": "http://localhost:5173"})
    assert gs.get_redirect_uri(request) == "http://localhost:5173/api/gmail/oauth/callback"


def test_redirect_uri_ignores_google_referer_on_callback(monkeypatch):
    monkeypatch.delenv("WORKSHOP_CUSTOM_DOMAIN", raising=False)
    monkeypatch.delenv("OAUTH_REDIRECT_BASE", raising=False)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", "http://localhost:5173")
    request = DummyRequest(
        {
            "referer": "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc",
            "host": "localhost:6173",
        }
    )
    assert gs.get_redirect_uri(request) == "http://localhost:5173/api/gmail/oauth/callback"


def test_redirect_uri_prefers_forwarded_host_over_google_referer(monkeypatch):
    monkeypatch.delenv("WORKSHOP_CUSTOM_DOMAIN", raising=False)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", "http://localhost:5173,https://app.example.test")
    request = DummyRequest(
        {
            "referer": "https://accounts.google.com/",
            "x-forwarded-host": "app.example.test",
            "x-forwarded-proto": "https",
        }
    )
    assert gs.get_redirect_uri(request) == "https://app.example.test/api/gmail/oauth/callback"


def test_oauth_callback_uses_session_redirect_uri(monkeypatch, engine, settings):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")

    captured: dict[str, str] = {}

    def fake_exchange(code, request, redirect_uri=None):
        captured["redirect_uri"] = redirect_uri or ""
        return {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }

    def fake_userinfo(*_args, **_kwargs):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"email": "user@example.test", "name": "User"}
        return response

    monkeypatch.setattr(gs, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(gs, "store_tokens", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gs, "ensure_labels_exist", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("routes.upsert_dashboard_user", lambda *_args, **_kwargs: "user-1")
    monkeypatch.setattr(httpx, "get", fake_userinfo)

    client = TestClient(make_app(monkeypatch, engine, settings))

    start = client.get(
        "/api/gmail/oauth/start",
        headers={"origin": "http://localhost:5173"},
    )
    assert start.status_code == 200
    session_cookie_value = start.cookies.get("session")
    assert session_cookie_value

    state = start.json()["auth_url"].split("state=")[1].split("&")[0]

    callback = client.get(
        f"/api/gmail/oauth/callback?code=test-code&state={state}",
        cookies={"session": session_cookie_value},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert captured["redirect_uri"] == "http://localhost:5173/api/gmail/oauth/callback"


def test_oauth_callback_invalid_state_redirects_home(monkeypatch, engine, settings):
    client = TestClient(make_app(monkeypatch, engine, settings))

    response = client.get(
        "/api/gmail/oauth/callback?code=test-code&state=wrong",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/?oauth_error=invalid_state"
