import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import gmail_service as gs
from tests.test_extension_api import make_app, session_cookie


class MockMessageGet:
    def __init__(self, msg):
        self.msg = msg

    def execute(self):
        return self.msg


class MockMessagesAPI:
    def __init__(self, service):
        self.service = service

    def get(self, userId, id, format=None, metadataHeaders=None):
        # find in service._messages
        msg = next((m for m in self.service._messages if m["id"] == id), None)
        if not msg:
            raise Exception("Message not found")
        # Return dict matching Gmail metadata payload
        payload = {
            "id": msg["id"],
            "threadId": msg["thread_id"],
            "snippet": msg.get("snippet", ""),
            "labelIds": msg.get("label_ids", []),
            "payload": {
                "headers": [
                    {"name": "Subject", "value": msg.get("subject", "")},
                    {"name": "From", "value": msg.get("from", "")},
                ]
            }
        }
        return MockMessageGet(payload)

    def modify(self, userId, id, body):
        self.service.modify_calls.append((id, body))
        class MockExec:
            def execute(self):
                return {"id": id}
        return MockExec()

    def untrash(self, userId, id):
        self.service.untrash_calls.append(id)
        class MockExec:
            def execute(self):
                return {"id": id}
        return MockExec()


class MockUsersAPI:
    def __init__(self, service):
        self.service = service

    def messages(self):
        return MockMessagesAPI(self.service)


class MockRecoveryService:
    def __init__(self, messages=None):
        self._messages = messages or []
        self.modify_calls = []
        self.untrash_calls = []

    def users(self):
        return MockUsersAPI(self)


def test_recovery_execute_unauthenticated(monkeypatch, engine, settings):
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    response = client.post("/api/recovery/execute", json={"operation_batch_id": 1, "confirm_execute": True})
    assert response.status_code == 401


def test_recovery_execute_missing_confirmation(monkeypatch, engine, settings):
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))
    response = client.post("/api/recovery/execute", json={"operation_batch_id": 1, "confirm_execute": False})
    assert response.status_code == 400
    assert "Missing explicit confirmation" in response.json()["detail"]


def test_recovery_execute_success_and_logs(monkeypatch, engine, settings):
    with engine.connect() as conn:
        run = conn.execute(text("""
            INSERT INTO scan_runs (user_email, status, dry_run)
            VALUES ('a@example.test', 'completed', 0)
            RETURNING id
        """)).fetchone()
        run_id = run[0]

        batch = conn.execute(text("""
            INSERT INTO operation_batches (user_email, scan_run_id, dry_run, status)
            VALUES ('a@example.test', :run_id, 0, 'completed')
            RETURNING id
        """), {"run_id": run_id}).fetchone()
        batch_id = batch[0]

        # Insert email action logs for:
        # 1. Labeled msg
        # 2. Trashed msg (high risk)
        # 3. Archived msg (INBOX in pre-labels)
        # 4. Skipped/no-op msg
        # 5. Failed msg
        conn.execute(text("""
            INSERT INTO email_action_logs (
                operation_batch_id, scan_run_id, user_email, gmail_message_id,
                planned_action, executed_action, category, confidence, pre_label_ids
            ) VALUES
            (:batch_id, :run_id, 'a@example.test', 'msg_lbl', 'label', 'labeled', 'work', 0.95, '["INBOX"]'),
            (:batch_id, :run_id, 'a@example.test', 'msg_trsh', 'trash', 'trashed', NULL, 0.99, '["INBOX"]'),
            (:batch_id, :run_id, 'a@example.test', 'msg_arch', 'archive', 'archived', NULL, 0.85, '["INBOX"]'),
            (:batch_id, :run_id, 'a@example.test', 'msg_skip', 'none', 'no_action', NULL, 0.70, '["INBOX"]')
        """), {"batch_id": batch_id, "run_id": run_id})

        conn.execute(text("""
            INSERT INTO email_action_logs (
                operation_batch_id, scan_run_id, user_email, gmail_message_id,
                planned_action, executed_action, category, confidence, pre_label_ids, error_message
            ) VALUES
            (:batch_id, :run_id, 'a@example.test', 'msg_fail', 'trash', 'trash_failed', NULL, 0.90, '["INBOX"]', 'Gmail API error')
        """), {"batch_id": batch_id, "run_id": run_id})

        # Insert mock category label mapping
        conn.execute(text("""
            INSERT INTO gmail_labels (user_email, label_name, gmail_label_id, category)
            VALUES ('a@example.test', 'Sorter/Work', 'label_work_id', 'work')
        """))

        conn.commit()

    service = MockRecoveryService(messages=[
        {"id": "msg_lbl", "thread_id": "t1", "label_ids": ["label_work_id"]},
        {"id": "msg_trsh", "thread_id": "t2", "label_ids": ["TRASH"]},
        {"id": "msg_arch", "thread_id": "t3", "label_ids": []},
    ])

    monkeypatch.setattr(gs, "build_gmail_service", lambda email: service)
    monkeypatch.setattr(gs, "get_stored_tokens", lambda email: {"access_token": "abc", "refresh_token": "xyz"})

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # Execute without handle_high_risk first -> high risk is skipped
    resp = client.post("/api/recovery/execute", json={
        "operation_batch_id": batch_id,
        "confirm_execute": True,
        "handle_high_risk": False
    })
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["operation_batch_id"] == batch_id
    assert summary["attempted"] == 2  # remove_label + restore_inbox
    assert summary["succeeded"] == 2
    assert summary["skipped"] == 2      # msg_skip + msg_fail
    assert summary["high_risk_skipped"] == 1  # msg_trsh

    # Confirm Gmail API calls
    assert len(service.untrash_calls) == 0
    # msg_lbl remove_label label_work_id, and msg_arch add INBOX
    assert len(service.modify_calls) == 2
    assert ("msg_lbl", {"removeLabelIds": ["label_work_id"]}) in service.modify_calls
    assert ("msg_arch", {"addLabelIds": ["INBOX"]}) in service.modify_calls

    # Now execute with handle_high_risk = True
    # Reset tracking lists
    service.modify_calls.clear()
    service.untrash_calls.clear()

    resp2 = client.post("/api/recovery/execute", json={
        "operation_batch_id": batch_id,
        "confirm_execute": True,
        "handle_high_risk": True
    })
    assert resp2.status_code == 200
    summary2 = resp2.json()
    assert summary2["attempted"] == 3  # remove_label + restore_inbox + untrash
    assert summary2["succeeded"] == 3
    assert summary2["high_risk_skipped"] == 0

    assert len(service.untrash_calls) == 1
    assert service.untrash_calls[0] == "msg_trsh"

    # Verify recovery_action_logs in DB
    with engine.connect() as conn:
        logs = conn.execute(text("""
            SELECT gmail_message_id, recovery_action, status, error_message
            FROM recovery_action_logs
            WHERE operation_batch_id = :batch_id
            ORDER BY gmail_message_id, id
        """), {"batch_id": batch_id}).fetchall()
        
        # We executed twice, so we will have logged rows for both runs.
        # Let's filter by the second run or inspect all:
        successes = {row[0]: row[2] for row in logs if row[2] == "success"}
        assert successes["msg_lbl"] == "success"
        assert successes["msg_trsh"] == "success"
        assert successes["msg_arch"] == "success"


def test_recovery_execute_cross_user_denied(monkeypatch, engine, settings):
    with engine.connect() as conn:
        run_b = conn.execute(text("""
            INSERT INTO scan_runs (user_email, status, dry_run)
            VALUES ('b@example.test', 'completed', 0)
            RETURNING id
        """)).fetchone()
        run_id_b = run_b[0]

        batch_b = conn.execute(text("""
            INSERT INTO operation_batches (user_email, scan_run_id, dry_run, status)
            VALUES ('b@example.test', :run_id, 0, 'completed')
            RETURNING id
        """), {"run_id": run_id_b}).fetchone()
        batch_id_b = batch_b[0]
        conn.commit()

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    resp = client.post("/api/recovery/execute", json={
        "operation_batch_id": batch_id_b,
        "confirm_execute": True
    })
    assert resp.status_code == 404
