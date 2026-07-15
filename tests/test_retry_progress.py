import time
import threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from googleapiclient.errors import HttpError

import db
import routes
import gmail_service as gs
import classifier as clf
from extension_auth import AuthFailure
from tests.test_extension_api import make_app, session_cookie


# ──────────────────────────────────────────────────────────────────────
# 1. Retry Logic Tests
# ──────────────────────────────────────────────────────────────────────

def test_retry_api_call_success_immediately():
    calls = 0
    def target():
        nonlocal calls
        calls += 1
        return "ok"

    result = gs.retry_api_call(target, max_retries=3, delay=0.01)
    assert result == "ok"
    assert calls == 1


def test_retry_api_call_transient_failure(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda x: sleeps.append(x))

    calls = 0
    def target():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("transient error")
        return "success"

    result = gs.retry_api_call(target, max_retries=3, delay=0.1)
    assert result == "success"
    assert calls == 3
    assert sleeps == [0.1, 0.2]  # exponential backoff: 0.1 * 2^0, 0.1 * 2^1


def test_retry_api_call_continuous_failure(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda x: sleeps.append(x))

    calls = 0
    def target():
        nonlocal calls
        calls += 1
        raise ValueError("persistent error")

    with pytest.raises(ValueError, match="persistent error"):
        gs.retry_api_call(target, max_retries=3, delay=0.1)

    assert calls == 3
    assert len(sleeps) == 2


class MockResp:
    def __init__(self, status, reason="Conflict"):
        self.status = status
        self.reason = reason


def test_ensure_labels_exist_handles_409(monkeypatch, engine):
    # Test that ensure_labels_exist handles 409 conflict when creating labels
    class MockLabels:
        def list(self, userId):
            class Executable:
                def execute(self):
                    return {"labels": [{"id": "Sorter", "name": "Sorter"}]}
            return Executable()

        def create(self, userId, body):
            resp = MockResp(409)
            raise HttpError(resp, b"Label already exists")

    class MockUsers:
        def labels(self):
            return MockLabels()

    class MockService:
        def users(self):
            return MockUsers()

    monkeypatch.setattr(gs, "build_gmail_service", lambda email: MockService())
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setattr(time, "sleep", lambda x: None)

    # Let's run ensure_labels_exist. It will hit HttpError(409) on the first label Sorter/Work,
    # then catch it and re-list labels. To prevent infinite loop, we provide a stateful mock:
    labels_list = [{"id": "Sorter", "name": "Sorter"}]

    class MockLabelsWithState:
        def list(self, userId):
            class Executable:
                def execute(self):
                    return {"labels": labels_list}
            return Executable()

        def create(self, userId, body):
            name = f"Sorter/{body['name']}" if "Sorter/" not in body["name"] else body["name"]
            labels_list.append({"id": f"id-{name}", "name": name})
            resp = MockResp(409)
            raise HttpError(resp, b"Label already exists")

    class MockUsersWithState:
        def labels(self):
            return MockLabelsWithState()

    class MockServiceWithState:
        def users(self):
            return MockUsersWithState()

    monkeypatch.setattr(gs, "build_gmail_service", lambda email: MockServiceWithState())

    # Call it
    result = gs.ensure_labels_exist("a@example.test")
    assert "Sorter/Work" in result


# ──────────────────────────────────────────────────────────────────────
# 2. Scan Progress Tracking & Sync Thread Tests
# ──────────────────────────────────────────────────────────────────────

class MockUsers:
    def __init__(self, service):
        self.service = service
    def getProfile(self, userId):
        outer = self
        class ExecutableProfile:
            def execute(self):
                return {"emailAddress": "a@example.test", "messagesTotal": len(outer.service._messages), "threadsTotal": 0}
        return ExecutableProfile()
    def labels(self):
        return MockLabels(self.service)
    def messages(self):
        return MockMessages(self.service)

class MockLabels:
    def __init__(self, service):
        self.service = service
    def list(self, userId):
        outer = self
        class ExecutableLabels:
            def execute(self):
                return {"labels": outer.service._labels}
        return ExecutableLabels()
    def create(self, userId, body):
        outer = self
        new_id = f"label-{body['name'].lower()}"
        new_label = {"id": new_id, "name": body["name"]}
        outer.service._labels.append(new_label)
        class ExecutableCreate:
            def execute(self):
                return new_label
        return ExecutableCreate()

class MockMessages:
    def __init__(self, service):
        self.service = service
    def list(self, userId, q=None, pageToken=None):
        outer = self
        class ExecutableMessagesList:
            def execute(self):
                return {"messages": [{"id": m["id"], "threadId": m["thread_id"]} for m in outer.service._messages]}
        return ExecutableMessagesList()
    def get(self, userId, id, format=None, metadataHeaders=None):
        outer = self
        msg = next((m for m in outer.service._messages if m["id"] == id), None)
        class ExecutableMessageGet:
            def execute(self):
                if not msg:
                    raise Exception("Message not found")
                return {
                    "id": msg["id"],
                    "threadId": msg["thread_id"],
                    "snippet": msg.get("snippet", ""),
                    "labelIds": msg.get("label_ids", []),
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": msg.get("subject", "")},
                            {"name": "From", "value": msg.get("from", "")},
                            {"name": "Date", "value": msg.get("date", "")},
                        ]
                    }
                }
        return ExecutableMessageGet()
    def trash(self, userId, id):
        outer = self
        outer.service.trash_calls.append(id)
        class ExecutableTrash:
            def execute(self):
                return {"id": id, "status": "trashed"}
        return ExecutableTrash()
    def modify(self, userId, id, body):
        outer = self
        outer.service.modify_calls.append((id, body))
        class ExecutableModify:
            def execute(self):
                return {"id": id}
        return ExecutableModify()

class MockService:
    def __init__(self, messages=None, labels=None):
        self._messages = messages or []
        self._labels = labels or [
            {"id": "Sorter", "name": "Sorter"},
            {"id": "label-work", "name": "Sorter/Work"},
            {"id": "label-promotions", "name": "Sorter/Promotions"},
        ]
        self.create_label_calls = []
        self.trash_calls = []
        self.modify_calls = []
    def users(self):
        return MockUsers(self)


def mock_classify_batch(emails):
    results = []
    for email in emails:
        if "crap" in email.get("subject", "").lower():
            results.append({
                "message_id": email["id"],
                "subject": email.get("subject", ""),
                "from": email.get("from", ""),
                "category": None,
                "is_crap": True,
                "crap_reason": "Contains crap in subject",
                "confidence": 0.95
            })
        else:
            results.append({
                "message_id": email["id"],
                "subject": email.get("subject", ""),
                "from": email.get("from", ""),
                "category": "work",
                "is_crap": False,
                "crap_reason": None,
                "confidence": 0.88
            })
    return results


class MockSyncThread:
    def __init__(self, target, args=(), kwargs={}, daemon=True):
        self.target = target
        self.args = args
        self.kwargs = kwargs
    def start(self):
        # Run synchronously in the test main thread for deterministic assertions
        self.target(*self.args, **self.kwargs)


def test_scan_progress_tracking(monkeypatch, engine, settings):
    # Setup test messages: 1 crap message, 1 work message
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "This is total crap", "from": "spam@spam.com", "snippet": "Buy now!", "label_ids": ["INBOX"]},
        {"id": "msg2", "thread_id": "t2", "subject": "Meeting notes", "from": "boss@work.com", "snippet": "Please review", "label_ids": ["INBOX"]},
    ]
    service = MockService(messages=messages)

    # Monkeypatch the Gmail builder, classifier, and OAuth configuration
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch)

    # Make the background thread synchronous
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    # Create app and client
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # Assert no scan runs yet
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM scan_runs")).scalar() == 0

    # Start the scan
    response = client.post("/api/scan/start")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify that the scan run completed and progress columns were updated
    with engine.connect() as conn:
        run = conn.execute(text("SELECT status, total_emails, total_scanned, total_crap, total_categorized, total_trashed, total_labeled, error_message FROM scan_runs WHERE id = :id"), {"id": run_id}).fetchone()
        assert run is not None
        assert run[0] == "completed"       # status
        assert run[1] == 2                  # total_emails
        assert run[2] == 2                  # total_scanned
        assert run[3] == 1                  # total_crap
        assert run[4] == 1                  # total_categorized
        assert run[5] == 1                  # total_trashed
        assert run[6] == 1                  # total_labeled
        assert run[7] is None               # error_message

        # Verify classifications stored
        classes = conn.execute(text("SELECT gmail_message_id, is_crap, category, action_taken FROM email_classifications WHERE run_id = :id ORDER BY gmail_message_id"), {"id": run_id}).fetchall()
        assert len(classes) == 2
        assert classes[0] == ("msg1", True, None, "trashed")
        assert classes[1] == ("msg2", False, "work", "labeled")

    # Verify that Gmail API mutation calls were actually made
    assert service.trash_calls == ["msg1"]
    assert len(service.modify_calls) == 1
    assert service.modify_calls[0] == ("msg2", {"addLabelIds": ["label-work"]})


def test_scan_dry_run(monkeypatch, engine, settings):
    # Setup test messages: 1 crap message, 1 work message
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "This is total crap", "from": "spam@spam.com", "snippet": "Buy now!", "label_ids": ["INBOX"]},
        {"id": "msg2", "thread_id": "t2", "subject": "Meeting notes", "from": "boss@work.com", "snippet": "Please review", "label_ids": ["INBOX"]},
    ]
    service = MockService(messages=messages)

    # Monkeypatch the Gmail builder, classifier, and OAuth configuration
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch)

    # Make the background thread synchronous
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    # Create app and client
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # Start the dry-run scan
    response = client.post("/api/scan/start?dry_run=true")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify that the scan run completed and progress columns were updated
    with engine.connect() as conn:
        run = conn.execute(text("SELECT status, dry_run, total_emails, total_scanned, total_crap, total_categorized FROM scan_runs WHERE id = :id"), {"id": run_id}).fetchone()
        assert run is not None
        assert run[0] == "completed"       # status
        assert bool(run[1]) is True        # dry_run
        assert run[2] == 2                  # total_emails
        assert run[3] == 2                  # total_scanned
        assert run[4] == 1                  # total_crap
        assert run[5] == 1                  # total_categorized

        # Verify classifications stored with action_taken = 'preview'
        classes = conn.execute(text("SELECT gmail_message_id, is_crap, category, action_taken FROM email_classifications WHERE run_id = :id ORDER BY gmail_message_id"), {"id": run_id}).fetchall()
        assert len(classes) == 2
        assert classes[0] == ("msg1", True, None, "preview")
        assert classes[1] == ("msg2", False, "work", "preview")

    # Verify that NO Gmail API mutation calls were made
    assert len(service.trash_calls) == 0
    assert len(service.modify_calls) == 0

    # Verify scan status endpoint includes dry_run
    status_resp = client.get("/api/scan/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["last_run"]["dry_run"] is True

    # Verify scan history endpoint includes dry_run
    history_resp = client.get("/api/scan/history")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["history"][0]["dry_run"] is True


def test_scan_dry_run_no_mutations_called(monkeypatch, engine, settings):
    # Setup test messages: 1 crap message, 1 work message
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "This is total crap", "from": "spam@spam.com", "snippet": "Buy now!", "label_ids": ["INBOX"]},
        {"id": "msg2", "thread_id": "t2", "subject": "Meeting notes", "from": "boss@work.com", "snippet": "Please review", "label_ids": ["INBOX"]},
    ]

    # Explicitly fail if any mutation function is called
    def fail_mutation(*args, **kwargs):
        pytest.fail("Gmail mutation function was called during dry-run!")

    monkeypatch.setattr(gs, "trash_message", fail_mutation)
    monkeypatch.setattr(gs, "add_label_to_message", fail_mutation)
    monkeypatch.setattr(gs, "remove_from_inbox", fail_mutation)
    monkeypatch.setattr(gs, "ensure_labels_exist", fail_mutation)

    service = MockService(messages=messages)
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start?dry_run=true")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify that the scan run completed and progress columns were updated
    with engine.connect() as conn:
        run = conn.execute(text("SELECT status, dry_run, total_emails, total_scanned, total_crap, total_categorized FROM scan_runs WHERE id = :id"), {"id": run_id}).fetchone()
        assert run is not None
        assert run[0] == "completed"
        assert bool(run[1]) is True
        assert run[2] == 2
        assert run[3] == 2

        # Verify classifications stored with action_taken = 'preview'
        classes = conn.execute(text("SELECT gmail_message_id, is_crap, category, action_taken FROM email_classifications WHERE run_id = :id ORDER BY gmail_message_id"), {"id": run_id}).fetchall()
        assert len(classes) == 2
        assert classes[0] == ("msg1", True, None, "preview")
        assert classes[1] == ("msg2", False, "work", "preview")


def test_scan_pause_and_resume(monkeypatch, engine, settings):
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # 1. Create a scan run with status 'running'
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO scan_runs (user_email, status) VALUES ('a@example.test', 'running')"))
        conn.commit()
        run_id = conn.execute(text("SELECT id FROM scan_runs ORDER BY id DESC LIMIT 1")).scalar()

    # 2. Call pause endpoint
    response_pause = client.post("/api/scan/pause")
    assert response_pause.status_code == 200
    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM scan_runs WHERE id = :id"), {"id": run_id}).scalar()
        assert status == "paused"

    # 3. Call resume endpoint
    response_resume = client.post("/api/scan/resume")
    assert response_resume.status_code == 200
    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM scan_runs WHERE id = :id"), {"id": run_id}).scalar()
        assert status == "running"


def test_scan_stop_endpoint(monkeypatch, engine, settings):
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # 1. Create a scan run with status 'running'
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO scan_runs (user_email, status) VALUES ('a@example.test', 'running')"))
        conn.commit()
        run_id = conn.execute(text("SELECT id FROM scan_runs ORDER BY id DESC LIMIT 1")).scalar()

    # 2. Call stop endpoint
    response_stop = client.post("/api/scan/stop")
    assert response_stop.status_code == 200
    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM scan_runs WHERE id = :id"), {"id": run_id}).scalar()
        assert status == "stopping"


def test_scan_stop_execution(monkeypatch, engine, settings):
    messages = [
        {"id": "msg1", "thread_id": "t1", "subject": "First message", "from": "boss@work.com", "snippet": "Notes", "label_ids": ["INBOX"]},
        {"id": "msg2", "thread_id": "t2", "subject": "Second message", "from": "boss@work.com", "snippet": "Notes", "label_ids": ["INBOX"]},
    ]
    service = MockService(messages=messages)
    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})
    monkeypatch.setattr(clf, "classify_batch", mock_classify_batch)
    monkeypatch.setattr(threading, "Thread", MockSyncThread)

    # We want to trigger a stop mid-scan. We can intercept in fetch_message_detail
    def mock_fetch_detail(email, msg_id):
        # Trigger stop in DB
        with engine.connect() as conn:
            conn.execute(text("UPDATE scan_runs SET status = 'stopping'"))
            conn.commit()
        return {"id": msg_id, "thread_id": "t1", "subject": "test", "from": "test", "snippet": "test", "label_ids": []}

    monkeypatch.setattr(gs, "fetch_message_detail", mock_fetch_detail)

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    response = client.post("/api/scan/start")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Verify status is stopped
    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM scan_runs WHERE id = :id"), {"id": run_id}).scalar()
        assert status == "stopped"


def test_active_scan_guard_with_paused_states(monkeypatch, engine, settings):
    monkeypatch.setattr(gs, "get_oauth_config", lambda: {"client_id": "fake_id", "client_secret": "fake_secret", "configured": True})

    # Setup scan_runs with a 'paused' scan
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO scan_runs (user_email, status) VALUES ('a@example.test', 'paused')"))
        conn.commit()

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # Trying to start a scan should return conflict (409)
    response = client.post("/api/scan/start")
    assert response.status_code == 409
    assert "A scan is already running" in response.json()["detail"]


