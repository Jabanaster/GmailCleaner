import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.test_extension_api import make_app, session_cookie


def test_unauthenticated_deletion_is_rejected(monkeypatch, engine, settings):
    client = TestClient(make_app(monkeypatch, engine, settings))
    response = client.delete("/api/user/account")
    assert response.status_code == 401


def test_authenticated_deletion_purges_user_data_and_leaves_others_alone(monkeypatch, engine, settings):
    # Clear tables first for clean state
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM email_action_logs"))
        conn.execute(text("DELETE FROM recovery_action_logs"))
        conn.execute(text("DELETE FROM operation_batches"))
        conn.execute(text("DELETE FROM email_classifications"))
        conn.execute(text("DELETE FROM scan_runs"))
        conn.execute(text("DELETE FROM extension_refresh_token_history"))
        conn.execute(text("DELETE FROM extension_device_sessions"))
        conn.execute(text("DELETE FROM extension_pairing_codes"))
        conn.execute(text("DELETE FROM organizer_users"))
        conn.execute(text("DELETE FROM gmail_oauth_tokens"))
        conn.execute(text("DELETE FROM gmail_labels"))
        conn.execute(text("DELETE FROM extension_audit_events"))

    # Setup two users
    user_a_email = "user.a@example.com"
    user_b_email = "user.b@example.com"

    with engine.begin() as conn:
        # User A
        conn.execute(text("INSERT INTO organizer_users (id, email) VALUES (:id, :email)"), {"id": "user-a", "email": user_a_email})
        conn.execute(text("INSERT INTO gmail_oauth_tokens (email, access_token) VALUES (:email, 'token-a')"), {"email": user_a_email})
        conn.execute(text("""
            INSERT INTO extension_device_sessions 
            (id, user_id, device_name, extension_version, refresh_token_hash, refresh_token_expires_at, created_at, last_seen_at) 
            VALUES ('session-a', 'user-a', 'dev-a', '1.0', 'hash', '2030-01-01', '2026-07-15', '2026-07-15')
        """))
        conn.execute(text("""
            INSERT INTO extension_pairing_codes 
            (id, user_id, code_hash, created_at, expires_at) 
            VALUES ('code-a', 'user-a', 'hash-code', '2026-07-15', '2030-01-01')
        """))
        conn.execute(text("INSERT INTO scan_runs (id, user_email, status) VALUES (10, :email, 'completed')"), {"email": user_a_email})
        conn.execute(text("INSERT INTO email_classifications (id, run_id, user_email, gmail_message_id) VALUES (100, 10, :email, 'msg-a')"), {"email": user_a_email})
        conn.execute(text("INSERT INTO operation_batches (id, user_email, scan_run_id) VALUES (1000, :email, 10)"), {"email": user_a_email})
        conn.execute(text("INSERT INTO email_action_logs (id, operation_batch_id, scan_run_id, user_email, gmail_message_id) VALUES (10000, 1000, 10, :email, 'msg-a')"), {"email": user_a_email})
        conn.execute(text("INSERT INTO recovery_action_logs (id, operation_batch_id, scan_run_id, user_email, gmail_message_id, recovery_action, status) VALUES (100000, 1000, 10, :email, 'msg-a', 'untrash', 'pending')"), {"email": user_a_email})
        conn.execute(text("INSERT INTO extension_audit_events (id, event_type, user_id) VALUES (1, 'test-event', 'user-a')"))

        # User B (should NOT be deleted)
        conn.execute(text("INSERT INTO organizer_users (id, email) VALUES (:id, :email)"), {"id": "user-b", "email": user_b_email})
        conn.execute(text("INSERT INTO gmail_oauth_tokens (email, access_token) VALUES (:email, 'token-b')"), {"email": user_b_email})
        conn.execute(text("""
            INSERT INTO extension_device_sessions 
            (id, user_id, device_name, extension_version, refresh_token_hash, refresh_token_expires_at, created_at, last_seen_at) 
            VALUES ('session-b', 'user-b', 'dev-b', '1.0', 'hash', '2030-01-01', '2026-07-15', '2026-07-15')
        """))
        conn.execute(text("INSERT INTO scan_runs (id, user_email, status) VALUES (20, :email, 'completed')"), {"email": user_b_email})
        conn.execute(text("INSERT INTO email_classifications (id, run_id, user_email, gmail_message_id) VALUES (200, 20, :email, 'msg-b')"), {"email": user_b_email})
        conn.execute(text("INSERT INTO extension_audit_events (id, event_type, user_id) VALUES (2, 'test-event', 'user-b')"))

    client = TestClient(make_app(monkeypatch, engine, settings))
    client.cookies.set("session", session_cookie(settings, "user-a", user_a_email))

    response = client.delete("/api/user/account")
    assert response.status_code == 200

    data = response.json()
    assert data["deleted_user_metadata"] is True
    assert data["deleted_tokens"] is True
    assert data["deleted_device_sessions"] == 1
    assert data["deleted_scan_recovery_records"] == 2  # scan_run and operation_batch
    assert data["deleted_classifications_logs"] == 4   # classification + action log + recovery log + audit event

    # Now verify database state
    with engine.connect() as conn:
        # Check User A data is gone
        assert conn.execute(text("SELECT COUNT(*) FROM organizer_users WHERE id = 'user-a'")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM gmail_oauth_tokens WHERE email = :email"), {"email": user_a_email}).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM extension_device_sessions WHERE user_id = 'user-a'")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM extension_pairing_codes WHERE user_id = 'user-a'")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM scan_runs WHERE user_email = :email"), {"email": user_a_email}).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM email_classifications WHERE user_email = :email"), {"email": user_a_email}).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM operation_batches WHERE user_email = :email"), {"email": user_a_email}).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM email_action_logs WHERE user_email = :email"), {"email": user_a_email}).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM recovery_action_logs WHERE user_email = :email"), {"email": user_a_email}).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM extension_audit_events WHERE user_id = 'user-a'")).scalar() == 0

        # Check User B data is still intact
        assert conn.execute(text("SELECT COUNT(*) FROM organizer_users WHERE id = 'user-b'")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM gmail_oauth_tokens WHERE email = :email"), {"email": user_b_email}).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM extension_device_sessions WHERE user_id = 'user-b'")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM scan_runs WHERE user_email = :email"), {"email": user_b_email}).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM email_classifications WHERE user_email = :email"), {"email": user_b_email}).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM extension_audit_events WHERE user_id = 'user-b'")).scalar() == 1
