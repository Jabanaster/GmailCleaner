import pytest
import time
import threading
from fastapi.testclient import TestClient
from sqlalchemy import text
from googleapiclient.errors import HttpError

import db
import routes
import gmail_service as gs
import classifier as clf
from tests.test_extension_api import make_app, session_cookie


class MockResp:
    def __init__(self, status):
        self.status = status
        self.reason = "Quota exceeded or Rate limit"


class MockSyncThread:
    def __init__(self, target, args=(), kwargs=None, **extra):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)



def mock_classify_batch(batch):
    res = []
    for m in batch:
        is_crap = "crap" in m.get("subject", "").lower()
        res.append({
            "message_id": m["id"],
            "subject": m["subject"],
            "from": m["from"],
            "category": "work" if not is_crap else None,
            "is_crap": is_crap,
            "crap_reason": "spam" if is_crap else None,
            "confidence": 0.99,
        })
    return res


def test_batch_size_and_pacing_invoked(monkeypatch, engine, settings):
    # Mock settings with batch size 2 and non-zero delay
    from config import Settings
    # Set env vars so load_settings() reads our mocked test settings
    monkeypatch.setenv("SCAN_BATCH_SIZE", "2")
    monkeypatch.setenv("SCAN_BATCH_DELAY_MS", "250")
    monkeypatch.setenv("GMAIL_QUOTA_BACKOFF_MS", "0")
    monkeypatch.setenv("GMAIL_MAX_RETRY_ATTEMPTS", "3")

    custom_settings = Settings(
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
        oauth_token_encryption_key=settings.oauth_token_encryption_key,
        scan_batch_size=2,
        scan_batch_delay_ms=250,
        gmail_quota_backoff_ms=0,
        gmail_max_retry_attempts=3
    )


    # 4 messages -> should trigger 2 batches, meaning 1 delay call of 250ms (since i > 0 for 2nd batch)
    messages = [
        {"id": "m1", "thread_id": "t1", "subject": "Work 1", "from": "a@a.com", "snippet": "", "label_ids": ["INBOX"]},
        {"id": "m2", "thread_id": "t1", "subject": "Work 2", "from": "a@a.com", "snippet": "", "label_ids": ["INBOX"]},
        {"id": "m3", "thread_id": "t1", "subject": "Work 3", "from": "a@a.com", "snippet": "", "label_ids": ["INBOX"]},
        {"id": "m4", "thread_id": "t1", "subject": "Work 4", "from": "a@a.com", "snippet": "", "label_ids": ["INBOX"]},
    ]

    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda x: sleep_calls.append(x))

    class MockService:
        def users(self):
            class Labels:
                def list(self, userId):
                    class ListExec:
                        def execute(self):
                            return {"labels": []}
                    return ListExec()
            class Users:
                def labels(self):
                    return Labels()
            return Users()

    monkeypatch.setattr(gs, "build_gmail_service", lambda email: MockService())
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(gs, "fetch_messages", lambda email, max_results=None: [{"id": m["id"]} for m in messages])
    monkeypatch.setattr(gs, "fetch_message_detail", lambda email, msg_id: next(m for m in messages if m["id"] == msg_id))
    monkeypatch.setattr(gs, "ensure_labels_exist", lambda email: None)
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, custom_settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(custom_settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=true")
    assert response.status_code == 200

    # Pacing: 4 messages, batch size 2 -> 2 batches. Delay of 0.25s should be called once (between batch 1 and 2)
    assert 0.25 in sleep_calls


def test_quota_error_triggers_backoff_and_fails(monkeypatch, engine, settings):
    from config import Settings
    # Set env vars so load_settings() reads our mocked test settings
    monkeypatch.setenv("SCAN_BATCH_SIZE", "10")
    monkeypatch.setenv("SCAN_BATCH_DELAY_MS", "0")
    monkeypatch.setenv("GMAIL_QUOTA_BACKOFF_MS", "500")
    monkeypatch.setenv("GMAIL_MAX_RETRY_ATTEMPTS", "2")

    custom_settings = Settings(
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
        oauth_token_encryption_key=settings.oauth_token_encryption_key,
        scan_batch_size=10,
        scan_batch_delay_ms=0,
        gmail_quota_backoff_ms=500,
        gmail_max_retry_attempts=2
    )


    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda x: sleep_calls.append(x))

    # Raise quota error 429 HttpError
    def mock_fetch_messages(*args, **kwargs):
        raise HttpError(MockResp(429), b"Rate limit exceeded")

    monkeypatch.setattr(gs, "build_gmail_service", lambda email: None)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(gs, "fetch_messages", mock_fetch_messages)
    monkeypatch.setattr(gs, "ensure_labels_exist", lambda email: None)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, custom_settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(custom_settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=true")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify run failed with the correct error message
    with engine.connect() as conn:
        run = conn.execute(text("SELECT status, error_message FROM scan_runs WHERE id = :id"), {"id": run_id}).fetchone()
        assert run[0] == "failed"
        assert "Gmail API quota exceeded" in run[1]

    # Verify sleep was called for backoff.
    # Attempts: 1st (fail -> sleep 0.5), 2nd (fail -> sleep 1.0), 3rd (fail -> raise)
    # Since max_retries = 2, total attempts = 3. Sleep calls should be 0.5 and 1.0
    assert 0.5 in sleep_calls
    assert 1.0 in sleep_calls
