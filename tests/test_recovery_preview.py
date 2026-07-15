import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import gmail_service as gs
from tests.test_extension_api import make_app, session_cookie


def test_recovery_preview_unauthenticated(monkeypatch, engine, settings):
    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    # No session cookie
    response = client.post("/api/recovery/preview", json={"operation_batch_id": 1})
    assert response.status_code == 401
    assert "Dashboard authentication required" in response.json()["detail"]


def test_recovery_preview_by_batch_id_and_run_id(monkeypatch, engine, settings):
    # Setup test DB data
    with engine.connect() as conn:
        # Create scan_run for user-a
        run_a = conn.execute(text("""
            INSERT INTO scan_runs (user_email, status, dry_run)
            VALUES ('a@example.test', 'completed', 0)
            RETURNING id
        """)).fetchone()
        run_id_a = run_a[0]

        # Create batch for user-a
        batch_a = conn.execute(text("""
            INSERT INTO operation_batches (user_email, scan_run_id, dry_run, status)
            VALUES ('a@example.test', :run_id, 0, 'completed')
            RETURNING id
        """), {"run_id": run_id_a}).fetchone()
        batch_id_a = batch_a[0]

        # Insert email_action_logs for user-a
        conn.execute(text("""
            INSERT INTO email_action_logs (
                operation_batch_id, scan_run_id, user_email, gmail_message_id,
                planned_action, executed_action, category, confidence, pre_label_ids
            ) VALUES
            (:batch_id, :run_id, 'a@example.test', 'msg_lbl', 'label', 'labeled', 'work', 0.95, '["INBOX"]'),
            (:batch_id, :run_id, 'a@example.test', 'msg_trsh', 'trash', 'trashed', NULL, 0.99, '["INBOX"]'),
            (:batch_id, :run_id, 'a@example.test', 'msg_arch', 'archive', 'archived', NULL, 0.85, '["INBOX"]'),
            (:batch_id, :run_id, 'a@example.test', 'msg_skip', 'none', 'no_action', NULL, 0.70, '["INBOX"]')
        """), {"batch_id": batch_id_a, "run_id": run_id_a})

        # Insert a failed log row
        conn.execute(text("""
            INSERT INTO email_action_logs (
                operation_batch_id, scan_run_id, user_email, gmail_message_id,
                planned_action, executed_action, category, confidence, pre_label_ids, error_message
            ) VALUES
            (:batch_id, :run_id, 'a@example.test', 'msg_fail', 'trash', 'trash_failed', NULL, 0.90, '["INBOX"]', 'Gmail API error')
        """), {"batch_id": batch_id_a, "run_id": run_id_a})

        conn.commit()

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # Test preview by operation_batch_id
    resp = client.post("/api/recovery/preview", json={"operation_batch_id": batch_id_a})
    assert resp.status_code == 200
    data = resp.json()
    assert data["operation_batch_id"] == batch_id_a
    assert data["scan_run_id"] == run_id_a
    assert data["dry_run"] is False
    assert data["total_actions"] == 5
    assert data["recoverable_count"] == 3
    assert data["skipped_count"] == 2
    assert data["high_risk_count"] == 1
    assert len(data["warning_list"]) == 1
    assert "Gmail auto-deletes trash" in data["warning_list"][0]

    # Verify per-message rows
    rows = {r["gmail_message_id"]: r for r in data["per_message_preview"]}
    
    # Labeled action
    assert rows["msg_lbl"]["planned_recovery_action"] == "remove_label"
    assert rows["msg_lbl"]["recoverable"] is True
    assert rows["msg_lbl"]["risk_level"] == "low"

    # Trashed action
    assert rows["msg_trsh"]["planned_recovery_action"] == "untrash"
    assert rows["msg_trsh"]["recoverable"] is True
    assert rows["msg_trsh"]["risk_level"] == "high"

    # Archived action
    assert rows["msg_arch"]["planned_recovery_action"] == "restore_inbox"
    assert rows["msg_arch"]["recoverable"] is True
    assert rows["msg_arch"]["risk_level"] == "low"

    # No mutation action
    assert rows["msg_skip"]["planned_recovery_action"] == "none"
    assert rows["msg_skip"]["recoverable"] is False
    assert rows["msg_skip"]["risk_level"] == "low"

    # Failed action
    assert rows["msg_fail"]["planned_recovery_action"] == "none"
    assert rows["msg_fail"]["recoverable"] is False
    assert rows["msg_fail"]["risk_level"] == "low"
    assert "original action failure" in rows["msg_fail"]["reason"]


    # Test preview by scan_run_id
    resp_run = client.post("/api/recovery/preview", json={"scan_run_id": run_id_a})
    assert resp_run.status_code == 200
    assert resp_run.json()["operation_batch_id"] == batch_id_a


def test_recovery_preview_denies_cross_user(monkeypatch, engine, settings):
    with engine.connect() as conn:
        # Create scan_run and batch for user-b
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
    # Authenticate as user-a
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    # Request user-b's batch -> 404
    resp = client.post("/api/recovery/preview", json={"operation_batch_id": batch_id_b})
    assert resp.status_code == 404

    # Request user-b's run -> 404
    resp_run = client.post("/api/recovery/preview", json={"scan_run_id": run_id_b})
    assert resp_run.status_code == 404


def test_recovery_preview_dry_run_batch(monkeypatch, engine, settings):
    with engine.connect() as conn:
        run_dry = conn.execute(text("""
            INSERT INTO scan_runs (user_email, status, dry_run)
            VALUES ('a@example.test', 'completed', 1)
            RETURNING id
        """)).fetchone()
        run_id_dry = run_dry[0]

        batch_dry = conn.execute(text("""
            INSERT INTO operation_batches (user_email, scan_run_id, dry_run, status)
            VALUES ('a@example.test', :run_id, 1, 'completed')
            RETURNING id
        """), {"run_id": run_id_dry}).fetchone()
        batch_id_dry = batch_dry[0]

        conn.execute(text("""
            INSERT INTO email_action_logs (
                operation_batch_id, scan_run_id, user_email, gmail_message_id,
                planned_action, executed_action, category, confidence, pre_label_ids
            ) VALUES
            (:batch_id, :run_id, 'a@example.test', 'msg_dry', 'trash', 'preview', NULL, 0.95, '["INBOX"]')
        """), {"batch_id": batch_id_dry, "run_id": run_id_dry})
        conn.commit()

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    resp = client.post("/api/recovery/preview", json={"operation_batch_id": batch_id_dry})
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["total_actions"] == 1
    assert data["recoverable_count"] == 0
    assert data["skipped_count"] == 1
    assert data["per_message_preview"][0]["planned_recovery_action"] == "none"
    assert data["per_message_preview"][0]["recoverable"] is False


def test_recovery_preview_no_gmail_mutations_called(monkeypatch, engine, settings):
    # Guard to verify no Gmail mutation functions are called
    def fail_mutation(*args, **kwargs):
        pytest.fail("Gmail mutation was called during recovery preview!")

    monkeypatch.setattr(gs, "trash_message", fail_mutation)
    monkeypatch.setattr(gs, "add_label_to_message", fail_mutation)

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
        conn.commit()

    app = make_app(monkeypatch, engine, settings)
    client = TestClient(app)
    client.cookies.set("session", session_cookie(settings, "user-a", "a@example.test"))

    resp = client.post("/api/recovery/preview", json={"operation_batch_id": batch_id})
    assert resp.status_code == 200
