import os
from base64 import b64encode
import hashlib
import json
from itsdangerous import TimestampSigner

from fastapi.testclient import TestClient

import db
import routes


def make_app(monkeypatch, engine, settings):
    monkeypatch.setenv("APP_ENV", settings.app_env)
    monkeypatch.setenv("PUBLIC_API_BASE_URL", settings.public_api_base_url)
    monkeypatch.setenv("ALLOWED_WEB_ORIGINS", ",".join(settings.allowed_web_origins))
    monkeypatch.setenv("ALLOWED_EXTENSION_IDS", ",".join(settings.allowed_extension_ids))
    monkeypatch.setenv("JWT_SIGNING_SECRET", settings.jwt_signing_secret)
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", settings.oauth_token_encryption_key)
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setattr(routes, "init_db", lambda: None)
    return routes.create_app("does-not-exist")



def session_cookie(settings, user_id: str, email: str) -> str:
    secret = hashlib.sha256(f"{settings.jwt_signing_secret}:dashboard-session".encode()).hexdigest()
    payload = b64encode(json.dumps({"user_id": user_id, "email": email}).encode())
    return TimestampSigner(secret).sign(payload).decode()


def test_unauthenticated_classification_is_rejected(monkeypatch, engine, settings):
    client = TestClient(make_app(monkeypatch, engine, settings))
    response = client.post("/api/extension/classify-preview", json={"messages": [{"id": "m1", "threadId": "t1", "subject": "s", "from": "a@example.test", "snippet": "x", "labelIds": []}]})
    assert response.status_code == 401


def test_user_supplied_identity_is_rejected(monkeypatch, engine, settings):
    from extension_auth import _issue_access_token
    token, _ = _issue_access_token(settings, "user-a", "session-a")
    client = TestClient(make_app(monkeypatch, engine, settings))
    response = client.post("/api/extension/classify-preview", headers={"Authorization": f"Bearer {token}"}, json={
        "user_id": "user-b",
        "messages": [{"id": "m1", "threadId": "t1", "subject": "s", "from": "a@example.test", "snippet": "x", "labelIds": []}],
    })
    assert response.status_code == 422


def test_pairing_code_requires_dashboard_auth(monkeypatch, engine, settings):
    client = TestClient(make_app(monkeypatch, engine, settings))
    assert client.post("/api/extension/pairing-codes").status_code == 401


def test_authenticated_dashboard_user_can_create_pairing_code(monkeypatch, engine, settings):
    client = TestClient(make_app(monkeypatch, engine, settings))
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))
    response = client.post("/api/extension/pairing-codes")
    assert response.status_code == 200
    assert len(response.json()["pairing_code"]) == 9


def test_cors_allowlist(monkeypatch, engine, settings):
    client = TestClient(make_app(monkeypatch, engine, settings))
    approved = client.options("/api/extension/pair", headers={"Origin": settings.allowed_web_origins[0], "Access-Control-Request-Method": "POST"})
    unknown = client.options("/api/extension/pair", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert approved.headers.get("access-control-allow-origin") == settings.allowed_web_origins[0]
    assert unknown.headers.get("access-control-allow-origin") is None


def test_user_cannot_revoke_another_users_device(monkeypatch, engine, settings):
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO extension_device_sessions
            (id,user_id,device_name,extension_version,created_at,last_seen_at,refresh_token_hash,refresh_token_expires_at)
            VALUES ('00000000-0000-0000-0000-000000000002','user-b','B device','0.2.0',:now,:now,'hash',:expires)"""),
            {"now": now, "expires": now + timedelta(days=30)})
    app = make_app(monkeypatch, engine, settings)
    from extension_routes import dashboard_user
    app.dependency_overrides[dashboard_user] = lambda: {"id": "user-a", "email": "a@example.test"}
    response = TestClient(app).delete("/api/extension/devices/00000000-0000-0000-0000-000000000002")
    assert response.status_code == 404
    with engine.connect() as conn:
        assert conn.execute(text("SELECT revoked_at FROM extension_device_sessions WHERE user_id='user-b'")).scalar_one() is None


def test_user_a_cannot_read_user_b_scan_or_classification(monkeypatch, engine, settings):
    from sqlalchemy import text
    from datetime import datetime, timezone
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO scan_runs (id,user_email,started_at,status,total_scanned) VALUES (22,'b@example.test',:now,'completed',1)"), {"now": datetime.now(timezone.utc)})
        conn.execute(text("""INSERT INTO email_classifications
            (id,run_id,user_email,gmail_message_id,subject,sender,category,is_crap,confidence,classified_at)
            VALUES (33,22,'b@example.test','private-message','private-subject','private-sender','work',0,0.9,:now)"""), {"now": datetime.now(timezone.utc)})
    client = TestClient(make_app(monkeypatch, engine, settings))
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))
    payload = client.get("/api/scan/status").json()
    assert payload["last_run"] is None
    assert payload["classifications"] == []
