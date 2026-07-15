import threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import gmail_service as gs
import classifier as clf
from tests.test_extension_api import make_app, session_cookie


class MockSyncThread:
    def __init__(self, target, args=(), kwargs=None, **extra):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


def mock_classify_batch_mixed(batch):
    res = []
    for idx, m in enumerate(batch):
        subject = m.get("subject", "").lower()
        if "crap" in subject:
            res.append({
                "message_id": m["id"],
                "subject": m["subject"],
                "from": m["from"],
                "category": None,
                "is_crap": True,
                "crap_reason": "test spam",
                "confidence": 0.99,
            })
        elif "work" in subject:
            res.append({
                "message_id": m["id"],
                "subject": m["subject"],
                "from": m["from"],
                "category": "work",
                "is_crap": False,
                "crap_reason": None,
                "confidence": 0.95,
            })
        else:
            # NO_ACTION
            res.append({
                "message_id": m["id"],
                "subject": m["subject"],
                "from": m["from"],
                "category": None,
                "is_crap": False,
                "crap_reason": None,
                "confidence": 0.70,
            })
    return res
from tests.test_retry_progress import MockService



def test_dry_run_logging_behavior(monkeypatch, engine, settings):
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "Buy Crap Now!", "from": "spam@spam.com", "snippet": "cheap!", "label_ids": ["INBOX"]},
        {"id": "msg2", "thread_id": "t2", "subject": "Work meeting", "from": "boss@work.com", "snippet": "Notes", "label_ids": ["INBOX"]},
        {"id": "msg3", "thread_id": "t3", "subject": "Regular email", "from": "friend@email.com", "snippet": "Hi", "label_ids": ["INBOX"]},
    ]

    # Guard against mutations
    def fail_mutation(*args, **kwargs):
        pytest.fail("Gmail mutation was called in dry-run!")

    monkeypatch.setattr(gs, "trash_message", fail_mutation)
    monkeypatch.setattr(gs, "add_label_to_message", fail_mutation)

    service = MockService(messages=messages)
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch_mixed)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=true")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify operation_batches row
    with engine.connect() as conn:
        batch = conn.execute(text("SELECT id, dry_run, status, total_processed, total_failed FROM operation_batches WHERE scan_run_id = :id"), {"id": run_id}).fetchone()
        assert batch is not None
        assert bool(batch[1]) is True
        assert batch[2] == "completed"
        assert batch[3] == 3
        assert batch[4] == 0

        # Verify email_action_logs
        logs = conn.execute(text("SELECT gmail_message_id, planned_action, executed_action, category, pre_label_ids FROM email_action_logs WHERE scan_run_id = :id ORDER BY gmail_message_id"), {"id": run_id}).fetchall()
        assert len(logs) == 3

        # Crap email
        assert logs[0][0] == "msg1"
        assert logs[0][1] == "trash"
        assert logs[0][2] == "preview"
        assert logs[0][3] is None

        # Work email
        assert logs[1][0] == "msg2"
        assert logs[1][1] == "label"
        assert logs[1][2] == "preview"
        assert logs[1][3] == "work"

        # Regular email (NO_ACTION)
        assert logs[2][0] == "msg3"
        assert logs[2][1] == "none"
        assert logs[2][2] == "preview"
        assert logs[2][3] is None


def test_non_dry_run_logging_behavior(monkeypatch, engine, settings):
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "Buy Crap Now!", "from": "spam@spam.com", "snippet": "cheap!", "label_ids": ["INBOX"]},
        {"id": "msg2", "thread_id": "t2", "subject": "Work meeting", "from": "boss@work.com", "snippet": "Notes", "label_ids": ["INBOX"]},
    ]

    trashed_msgs = []
    labeled_msgs = []

    def mock_trash(email, msg_id):
        trashed_msgs.append(msg_id)

    def mock_add_label(email, msg_id, label_id):
        labeled_msgs.append((msg_id, label_id))

    monkeypatch.setattr(gs, "trash_message", mock_trash)
    monkeypatch.setattr(gs, "add_label_to_message", mock_add_label)
    monkeypatch.setattr(gs, "get_label_id", lambda email, cat: f"label_{cat}")

    service = MockService(messages=messages)
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch_mixed)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=false")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify executed mutations in logs
    with engine.connect() as conn:
        logs = conn.execute(text("SELECT gmail_message_id, planned_action, executed_action, post_label_ids FROM email_action_logs WHERE scan_run_id = :id ORDER BY gmail_message_id"), {"id": run_id}).fetchall()
        assert len(logs) == 2

        # Crap email
        assert logs[0][0] == "msg1"
        assert logs[0][1] == "trash"
        assert logs[0][2] == "trashed"
        assert "TRASH" in logs[0][3]

        # Work email
        assert logs[1][0] == "msg2"
        assert logs[1][1] == "label"
        assert logs[1][2] == "labeled"
        assert "label_work" in logs[1][3]


def test_failed_action_logging(monkeypatch, engine, settings):
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "Buy Crap Now!", "from": "spam@spam.com", "snippet": "cheap!", "label_ids": ["INBOX"]},
    ]

    def mock_trash_fail(email, msg_id):
        raise Exception("API connection timed out")

    monkeypatch.setattr(gs, "trash_message", mock_trash_fail)
    service = MockService(messages=messages)
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch_mixed)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=false")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify failed action logs sanitized error
    with engine.connect() as conn:
        log = conn.execute(text("SELECT executed_action, error_message FROM email_action_logs WHERE scan_run_id = :id"), {"id": run_id}).fetchone()
        assert log is not None
        assert log[0] == "trash_failed"
        assert "API connection timed out" in log[1]


def test_failed_scan_marks_batch_failed(monkeypatch, engine, settings):
    # Force a failure inside ensure_labels_exist to fail the entire scan run
    def mock_fail_ensure(*args, **kwargs):
        raise RuntimeError("Gmail credentials revoked")

    monkeypatch.setattr(gs, "ensure_labels_exist", mock_fail_ensure)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=false")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify operation_batches status is failed
    with engine.connect() as conn:
        batch = conn.execute(text("SELECT status FROM operation_batches WHERE scan_run_id = :id"), {"id": run_id}).scalar()
        assert batch == "failed"
