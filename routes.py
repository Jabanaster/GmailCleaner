import os
import json
import time
import threading
import hashlib
import hmac
import secrets
from datetime import datetime

from fastapi import FastAPI, APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from db import init_db, get_engine, get_setting, set_setting
import gmail_service as gs
import classifier as clf
from config import load_settings
from extension_auth import upsert_dashboard_user
from extension_routes import create_extension_router
from recovery_utils import generate_recovery_preview, execute_recovery

class RecoveryPreviewRequest(BaseModel):
    operation_batch_id: int | None = None
    scan_run_id: int | None = None

class RecoveryExecuteRequest(BaseModel):
    operation_batch_id: int | None = None
    scan_run_id: int | None = None
    confirm_execute: bool
    handle_high_risk: bool = False




def create_app(static_dir: str) -> FastAPI:
    settings = load_settings()
    init_db()

    api = APIRouter()

    # ─── Health ───
    @api.get("/health")
    def health():
        return {"ok": True}

    # ─── Gmail OAuth status ───
    @api.get("/gmail/status")
    def gmail_status(request: Request):
        oauth_config = gs.get_oauth_config()
        connected_email = request.session.get("email")
        return {
            "oauth_configured": oauth_config["configured"],
            "connected": connected_email is not None,
            "email": connected_email,
        }

    # ─── Start OAuth flow ───
    @api.get("/gmail/oauth/start")
    def gmail_oauth_start(request: Request):
        try:
            state = secrets.token_urlsafe(32)
            redirect_uri = gs.get_redirect_uri(request)
            request.session["oauth_state"] = state
            request.session["oauth_redirect_uri"] = redirect_uri
            auth_url = gs.get_auth_url(request, state, redirect_uri=redirect_uri)
            return {"auth_url": auth_url}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ─── OAuth callback ───
    @api.get("/gmail/oauth/callback")
    async def gmail_oauth_callback(request: Request):
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        returned_state = request.query_params.get("state", "")
        expected_state = request.session.pop("oauth_state", "")

        if error:
            return RedirectResponse(url=f"/?oauth_error={error}", status_code=302)
        if not code:
            raise HTTPException(status_code=400, detail="No authorization code received")
        if not expected_state or not hmac.compare_digest(returned_state, expected_state):
            return RedirectResponse(url="/?oauth_error=invalid_state", status_code=302)

        redirect_uri = request.session.pop("oauth_redirect_uri", None)

        try:
            tokens = gs.exchange_code_for_tokens(code, request, redirect_uri=redirect_uri)

            # Get user email from token info
            access_token = tokens.get("access_token")
            userinfo_resp = __import__("httpx").get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            userinfo_resp.raise_for_status()
            user_email = userinfo_resp.json()["email"]
            display_name = userinfo_resp.json().get("name")

            gs.store_tokens(user_email, tokens)
            user_id = upsert_dashboard_user(get_engine(), user_email, display_name)
            request.session["user_id"] = user_id
            request.session["email"] = user_email.lower()

            # Ensure labels exist
            gs.ensure_labels_exist(user_email)

            return RedirectResponse(url=f"/?oauth_success=true&email={user_email}", status_code=302)
        except Exception as e:
            return RedirectResponse(url=f"/?oauth_error={str(e)[:200]}", status_code=302)

    # ─── Get Gmail profile ───
    @api.get("/gmail/profile")
    def gmail_profile(request: Request):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")
        try:
            return gs.get_user_profile(email)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ─── Disconnect Gmail ───
    @api.post("/gmail/disconnect")
    def gmail_disconnect(request: Request):
        email = request.session.get("email")
        if email:
            gs.disconnect_gmail(email)
        request.session.clear()
        return {"ok": True}

    # ─── Delete Account & Purge Data ───
    @api.delete("/user/account")
    def delete_user_account(request: Request):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        user_id = None
        user_deleted = False
        tokens_deleted = 0
        device_sessions_deleted = 0
        scan_records_deleted = 0
        logs_deleted = 0

        engine = get_engine()
        with engine.begin() as conn:
            # 1. Get user_id if any
            user = conn.execute(text("""
                SELECT id FROM organizer_users WHERE LOWER(email) = LOWER(:email)
            """), {"email": email}).fetchone()
            if user:
                user_id = user[0]

            # 2. Fetch tokens first so we can revoke them remotely after deletion
            token_row = conn.execute(text("""
                SELECT refresh_token FROM gmail_oauth_tokens WHERE LOWER(email) = LOWER(:email)
            """), {"email": email}).fetchone()
            refresh_token = token_row[0] if token_row else None

            # 3. Perform cascading deletes in correct FK order
            logs_deleted += conn.execute(text("""
                DELETE FROM recovery_action_logs WHERE LOWER(user_email) = LOWER(:email)
            """), {"email": email}).rowcount or 0

            logs_deleted += conn.execute(text("""
                DELETE FROM email_action_logs WHERE LOWER(user_email) = LOWER(:email)
            """), {"email": email}).rowcount or 0

            scan_records_deleted += conn.execute(text("""
                DELETE FROM operation_batches WHERE LOWER(user_email) = LOWER(:email)
            """), {"email": email}).rowcount or 0

            logs_deleted += conn.execute(text("""
                DELETE FROM email_classifications WHERE LOWER(user_email) = LOWER(:email)
            """), {"email": email}).rowcount or 0

            scan_records_deleted += conn.execute(text("""
                DELETE FROM scan_runs WHERE LOWER(user_email) = LOWER(:email)
            """), {"email": email}).rowcount or 0

            conn.execute(text("""
                DELETE FROM gmail_labels WHERE LOWER(user_email) = LOWER(:email)
            """), {"email": email})

            tokens_deleted = conn.execute(text("""
                DELETE FROM gmail_oauth_tokens WHERE LOWER(email) = LOWER(:email)
            """), {"email": email}).rowcount or 0

            if user_id:
                logs_deleted += conn.execute(text("""
                    DELETE FROM extension_audit_events WHERE user_id = :user_id
                """), {"user_id": user_id}).rowcount or 0

            # Delete extension sessions and pairing codes before user row
            if user_id:
                device_sessions_deleted = conn.execute(text("""
                    DELETE FROM extension_device_sessions WHERE user_id = :user_id
                """), {"user_id": user_id}).rowcount or 0

                conn.execute(text("""
                    DELETE FROM extension_pairing_codes WHERE user_id = :user_id
                """), {"user_id": user_id})

            if user_id:
                user_deleted = (conn.execute(text("""
                    DELETE FROM organizer_users WHERE id = :user_id
                """), {"user_id": user_id}).rowcount or 0) > 0

        # 5. Revoke tokens remotely
        if refresh_token:
            try:
                import httpx
                httpx.post(
                    f"https://oauth2.googleapis.com/revoke?token={refresh_token}",
                    timeout=10.0,
                )
            except Exception:
                pass

        request.session.clear()

        return {
            "deleted_user_metadata": user_deleted,
            "deleted_tokens": tokens_deleted > 0,
            "deleted_device_sessions": device_sessions_deleted,
            "deleted_scan_recovery_records": scan_records_deleted,
            "deleted_classifications_logs": logs_deleted,
        }


    # ─── Scan status ───
    @api.get("/scan/status")
    def scan_status(request: Request):
        email = request.session.get("email")
        if not email:
            return {"running": False, "email": None}

        engine = get_engine()
        with engine.connect() as conn:
            latest = conn.execute(text("""
                SELECT id, status, started_at, completed_at, total_scanned,
                       total_crap, total_categorized, total_trashed, total_labeled,
                       COALESCE(total_emails, 0) AS total_emails, error_message,
                       COALESCE(dry_run, FALSE) AS dry_run
                FROM scan_runs WHERE user_email = :email
                ORDER BY started_at DESC LIMIT 1
            """), {"email": email}).fetchone()

            # Get classifications for latest run
            recent_classes = []
            if latest:
                recent_classes = conn.execute(text("""
                    SELECT gmail_message_id, subject, sender, category, is_crap, crap_reason, confidence, action_taken
                    FROM email_classifications WHERE run_id = :run_id
                    ORDER BY classified_at DESC LIMIT 100
                """), {"run_id": latest[0]}).fetchall()

        if not latest:
            return {"running": False, "email": email, "last_run": None, "classifications": []}

        return {
            "running": latest[1] in ("running", "paused", "stopping"),
            "email": email,
            "last_run": {
                "id": latest[0],
                "status": latest[1],
                "started_at": str(latest[2]) if latest[2] else None,
                "completed_at": str(latest[3]) if latest[3] else None,
                "total_scanned": latest[4],
                "total_crap": latest[5],
                "total_categorized": latest[6],
                "total_trashed": latest[7],
                "total_labeled": latest[8],
                "total_emails": latest[9],
                "error_message": latest[10],
                "dry_run": bool(latest[11]),
            },
            "classifications": [
                {
                    "message_id": r[0],
                    "subject": r[1],
                    "sender": r[2],
                    "category": r[3],
                    "is_crap": r[4],
                    "crap_reason": r[5],
                    "confidence": r[6],
                    "action_taken": r[7],
                }
                for r in recent_classes
            ],
        }

    # ─── Start scan (background task) ───
    @api.post("/scan/start")
    def scan_start(request: Request, max_results: int | None = None, dry_run: bool = False):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        oauth_ok = gs.get_oauth_config()
        if not oauth_ok["configured"]:
            raise HTTPException(status_code=400, detail="Google OAuth not configured")

        # Check if a scan is already running
        engine = get_engine()
        with engine.connect() as conn:
            running = conn.execute(text("""
                SELECT id FROM scan_runs WHERE user_email = :email AND status IN ('running', 'paused', 'stopping')
            """), {"email": email}).fetchone()

        if running:
            raise HTTPException(status_code=409, detail="A scan is already running")

        # Create a scan run record
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO scan_runs (user_email, status, dry_run) VALUES (:email, 'running', :dry_run)
                RETURNING id
            """), {"email": email, "dry_run": dry_run}).fetchone()
            conn.commit()
            run_id = result[0]

        # Start background scan
        thread = threading.Thread(
            target=_run_scan,
            args=(email, run_id, max_results, dry_run),
            daemon=True,
        )
        thread.start()

        return {"run_id": run_id, "status": "running", "message": "Scan started"}

    @api.post("/scan/pause")
    def scan_pause(request: Request):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        engine = get_engine()
        with engine.connect() as conn:
            active_run = conn.execute(text("""
                SELECT id FROM scan_runs WHERE user_email = :email AND status = 'running'
            """), {"email": email}).fetchone()

            if not active_run:
                raise HTTPException(status_code=400, detail="No active running scan to pause")

            conn.execute(text("""
                UPDATE scan_runs SET status = 'paused' WHERE id = :id
            """), {"id": active_run[0]})
            conn.commit()

        return {"ok": True, "message": "Scan paused"}

    @api.post("/scan/resume")
    def scan_resume(request: Request):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        engine = get_engine()
        with engine.connect() as conn:
            paused_run = conn.execute(text("""
                SELECT id FROM scan_runs WHERE user_email = :email AND status = 'paused'
            """), {"email": email}).fetchone()

            if not paused_run:
                raise HTTPException(status_code=400, detail="No paused scan to resume")

            conn.execute(text("""
                UPDATE scan_runs SET status = 'running' WHERE id = :id
            """), {"id": paused_run[0]})
            conn.commit()

        return {"ok": True, "message": "Scan resumed"}

    @api.post("/scan/stop")
    def scan_stop(request: Request):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        engine = get_engine()
        with engine.connect() as conn:
            active_run = conn.execute(text("""
                SELECT id FROM scan_runs 
                WHERE user_email = :email AND status IN ('running', 'paused')
            """), {"email": email}).fetchone()

            if not active_run:
                raise HTTPException(status_code=400, detail="No active scan to stop")

            conn.execute(text("""
                UPDATE scan_runs SET status = 'stopping' WHERE id = :id
            """), {"id": active_run[0]})
            conn.commit()

        return {"ok": True, "message": "Scan stop initiated"}

    @api.post("/recovery/preview")
    def recovery_preview(request: Request, body: RecoveryPreviewRequest):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        if body.operation_batch_id is None and body.scan_run_id is None:
            raise HTTPException(status_code=400, detail="Either operation_batch_id or scan_run_id must be provided")

        engine = get_engine()
        val = body.operation_batch_id if body.operation_batch_id is not None else body.scan_run_id
        preview = generate_recovery_preview(email, val, engine)
        if not preview:
            raise HTTPException(status_code=404, detail="Operation batch or scan run not found")

        return preview

    @api.post("/recovery/execute")
    def recovery_execute(request: Request, body: RecoveryExecuteRequest):
        email = request.session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Dashboard authentication required")

        if not body.confirm_execute:
            raise HTTPException(status_code=400, detail="Missing explicit confirmation (confirm_execute: true)")

        if body.operation_batch_id is None and body.scan_run_id is None:
            raise HTTPException(status_code=400, detail="Either operation_batch_id or scan_run_id must be provided")

        engine = get_engine()
        val = body.operation_batch_id if body.operation_batch_id is not None else body.scan_run_id
        summary = execute_recovery(
            user_email=email,
            batch_id_or_run_id=val,
            confirm_execute=body.confirm_execute,
            handle_high_risk=body.handle_high_risk,
            engine=engine
        )

        if not summary:
            raise HTTPException(status_code=404, detail="Operation batch or scan run not found")

        return summary




    # ─── Get run history ───
    @api.get("/scan/history")
    def scan_history(request: Request):
        email = request.session.get("email")
        if not email:
            return {"history": []}

        engine = get_engine()
        with engine.connect() as conn:
            runs = conn.execute(text("""
                SELECT id, status, started_at, completed_at, total_scanned,
                       total_crap, total_categorized, total_trashed, total_labeled, error_message,
                       COALESCE(dry_run, FALSE) AS dry_run
                FROM scan_runs WHERE user_email = :email
                ORDER BY started_at DESC LIMIT 20
            """), {"email": email}).fetchall()

        return {
            "history": [
                {
                    "id": r[0],
                    "status": r[1],
                    "started_at": str(r[2]) if r[2] else None,
                    "completed_at": str(r[3]) if r[3] else None,
                    "total_scanned": r[4],
                    "total_crap": r[5],
                    "total_categorized": r[6],
                    "total_trashed": r[7],
                    "total_labeled": r[8],
                    "error_message": r[9],
                    "dry_run": bool(r[10]),
                }
                for r in runs
            ]
        }

    # ─── Category breakdown for charts ───
    @api.get("/scan/categories")
    def scan_categories(request: Request):
        email = request.session.get("email")
        if not email:
            return {"categories": [], "crap_count": 0}

        engine = get_engine()
        with engine.connect() as conn:
            cats = conn.execute(text("""
                SELECT category, COUNT(*) as count
                FROM email_classifications
                WHERE user_email = :email AND category IS NOT NULL AND is_crap = FALSE
                GROUP BY category ORDER BY count DESC
            """), {"email": email}).fetchall()

            crap_count = conn.execute(text("""
                SELECT COUNT(*) FROM email_classifications
                WHERE user_email = :email AND is_crap = TRUE
            """), {"email": email}).fetchone()

        return {
            "categories": [{"category": r[0], "count": r[1]} for r in cats],
            "crap_count": crap_count[0] if crap_count else 0,
        }

    def _run_scan(user_email: str, run_id: int, max_results: int | None, dry_run: bool = False):
        """Background scan: fetch, classify, trash crap, label others."""
        engine = get_engine()
        total_scanned = 0
        total_crap = 0
        total_categorized = 0
        total_trashed = 0
        total_labeled = 0

        # Load settings
        settings = load_settings()
        batch_size = settings.scan_batch_size
        batch_delay = settings.scan_batch_delay_ms / 1000.0
        quota_backoff = settings.gmail_quota_backoff_ms / 1000.0
        max_retries = settings.gmail_max_retry_attempts

        def execute_gmail_api_with_quota_backoff(api_func):
            attempts = 0
            while True:
                try:
                    return api_func()
                except Exception as e:
                    # Check if status code is 429 or 403 (standard Google rate limit/quota status codes)
                    is_quota = False
                    if hasattr(e, "resp") and getattr(e.resp, "status", None) in {429, 403}:
                        is_quota = True
                    
                    if is_quota:
                        attempts += 1
                        if attempts <= max_retries:
                            if quota_backoff > 0:
                                time.sleep(quota_backoff * (2 ** (attempts - 1)))
                            continue
                        else:
                            raise RuntimeError("Gmail API quota exceeded or rate limit hit. Scan stopped to prevent abuse.") from e
                    raise e

        def fail(msg):
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE scan_runs SET status = 'failed', completed_at = NOW(), error_message = :msg
                    WHERE id = :id
                """), {"id": run_id, "msg": msg})
                conn.commit()

        def get_current_status():
            with engine.connect() as conn:
                row = conn.execute(text("SELECT status FROM scan_runs WHERE id = :id"), {"id": run_id}).fetchone()
                return row[0] if row else "failed"

        batch_id = None
        try:
            # Create operation batch
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO operation_batches (user_email, scan_run_id, dry_run, status)
                    VALUES (:email, :scan_run_id, :dry_run, 'running')
                """), {
                    "email": user_email,
                    "scan_run_id": run_id,
                    "dry_run": dry_run
                })
                conn.commit()
                # Query for batch ID
                batch_id = conn.execute(text("""
                    SELECT id FROM operation_batches WHERE scan_run_id = :scan_run_id
                """), {"scan_run_id": run_id}).scalar()

            # Ensure labels exist
            if not dry_run:
                execute_gmail_api_with_quota_backoff(lambda: gs.ensure_labels_exist(user_email))

            # Fetch all message IDs
            message_ids = execute_gmail_api_with_quota_backoff(lambda: gs.fetch_messages(user_email, max_results=max_results))
            total = len(message_ids)

            # Store total email count for progress tracking
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE scan_runs SET total_emails = :total WHERE id = :id
                """), {"total": total, "id": run_id})
                conn.commit()

            # Process in batches
            i = 0
            while i < total:
                # Check status
                status = get_current_status()
                if status in ("stopping", "stopped"):
                    break
                if status == "paused":
                    time.sleep(1)
                    continue

                # Batch pacing delay (except before first batch)
                if i > 0 and batch_delay > 0:
                    time.sleep(batch_delay)

                batch = message_ids[i:i + batch_size]

                # Fetch message details
                email_details = []
                for msg_ref in batch:
                    if get_current_status() in ("stopping", "stopped"):
                        break
                    try:
                        detail = execute_gmail_api_with_quota_backoff(lambda ref=msg_ref: gs.fetch_message_detail(user_email, ref["id"]))
                        email_details.append(detail)
                    except RuntimeError as re:
                        raise re
                    except Exception:
                        continue

                if get_current_status() in ("stopping", "stopped"):
                    break

                # Classify with AI
                classifications = clf.classify_batch(email_details)

                # Build details map for quick lookup of pre-action metadata
                details_map = {d["id"]: d for d in email_details}

                # Process each classification
                for cls in classifications:
                    if get_current_status() in ("stopping", "stopped"):
                        break
                    msg_id = cls["message_id"]
                    action_taken = "none"
                    planned_action = "none"
                    error_msg = None

                    # Extract pre-action labels
                    detail = details_map.get(msg_id, {})
                    label_ids = detail.get("label_ids", [])
                    archived_before = "INBOX" not in label_ids
                    trashed_before = "TRASH" in label_ids

                    if cls["is_crap"]:
                        planned_action = "trash"
                        if dry_run:
                            action_taken = "preview"
                            total_trashed += 1
                            total_crap += 1
                        else:
                            # Move to trash
                            try:
                                execute_gmail_api_with_quota_backoff(lambda: gs.trash_message(user_email, msg_id))
                                action_taken = "trashed"
                                total_trashed += 1
                                total_crap += 1
                            except RuntimeError as re:
                                raise re
                            except Exception as e:
                                action_taken = "trash_failed"
                                error_msg = str(e)[:500]
                    elif cls["category"]:
                        planned_action = "label"
                        if dry_run:
                            action_taken = "preview"
                            total_labeled += 1
                            total_categorized += 1
                        else:
                            # Add category label
                            label_id = gs.get_label_id(user_email, cls["category"])
                            if label_id:
                                try:
                                    execute_gmail_api_with_quota_backoff(lambda lid=label_id: gs.add_label_to_message(user_email, msg_id, lid))
                                    action_taken = "labeled"
                                    total_labeled += 1
                                    total_categorized += 1
                                except RuntimeError as re:
                                    raise re
                                except Exception as e:
                                    action_taken = "label_failed"
                                    error_msg = str(e)[:500]

                    # Determine post-action labels if applicable
                    post_label_ids = None
                    if not dry_run and action_taken == "labeled":
                        post_labels = list(label_ids)
                        label_id = gs.get_label_id(user_email, cls["category"])
                        if label_id and label_id not in post_labels:
                            post_labels.append(label_id)
                        post_label_ids = json.dumps(post_labels)
                    elif not dry_run and action_taken == "trashed":
                        post_labels = list(label_ids)
                        if "TRASH" not in post_labels:
                            post_labels.append("TRASH")
                        post_label_ids = json.dumps(post_labels)

                    # Store classification
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO email_classifications
                                (run_id, user_email, gmail_message_id, subject, sender,
                                 category, is_crap, crap_reason, confidence, action_taken)
                            VALUES (:run_id, :email, :msg_id, :subject, :sender,
                                    :category, :is_crap, :crap_reason, :confidence, :action)
                        """), {
                            "run_id": run_id,
                            "email": user_email,
                            "msg_id": msg_id,
                            "subject": cls.get("subject", ""),
                            "sender": cls.get("from", ""),
                            "category": cls.get("category"),
                            "is_crap": cls.get("is_crap", False),
                            "crap_reason": cls.get("crap_reason"),
                            "confidence": cls.get("confidence", 0.0),
                            "action": action_taken,
                        })

                        # Log email action in email_action_logs
                        conn.execute(text("""
                            INSERT INTO email_action_logs
                                (operation_batch_id, scan_run_id, user_email, gmail_message_id,
                                 planned_action, executed_action, category, confidence,
                                 pre_label_ids, post_label_ids, archived_before, trashed_before, error_message)
                            VALUES (:batch_id, :run_id, :email, :msg_id,
                                    :planned, :executed, :category, :confidence,
                                    :pre_labels, :post_labels, :archived, :trashed, :error)
                        """), {
                            "batch_id": batch_id,
                            "run_id": run_id,
                            "email": user_email,
                            "msg_id": msg_id,
                            "planned": planned_action,
                            "executed": "preview" if dry_run else (action_taken if action_taken != "none" else "no_mutation"),
                            "category": cls.get("category"),
                            "confidence": cls.get("confidence", 0.0),
                            "pre_labels": json.dumps(label_ids),
                            "post_labels": post_label_ids,
                            "archived": archived_before,
                            "trashed": trashed_before,
                            "error": error_msg,
                        })
                        conn.commit()

                    total_scanned += 1

                if get_current_status() in ("stopping", "stopped"):
                    break

                # Update progress periodically
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE scan_runs SET total_scanned = :scanned WHERE id = :id
                    """), {"scanned": total_scanned, "id": run_id})
                    conn.commit()

                i += batch_size

            # Mark completed or stopped
            final_status = get_current_status()
            if final_status in ("stopping", "stopped"):
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE scan_runs
                        SET status = 'stopped', completed_at = NOW(),
                            total_scanned = :scanned, total_crap = :crap,
                            total_categorized = :categorized, total_trashed = :trashed,
                            total_labeled = :labeled
                        WHERE id = :id
                    """), {
                        "id": run_id,
                        "scanned": total_scanned,
                        "crap": total_crap,
                        "categorized": total_categorized,
                        "trashed": total_trashed,
                        "labeled": total_labeled,
                    })
                    if batch_id is not None:
                        conn.execute(text("""
                            UPDATE operation_batches
                            SET status = 'stopped', completed_at = NOW(),
                                total_processed = :scanned
                            WHERE id = :batch_id
                        """), {"batch_id": batch_id, "scanned": total_scanned})
                    conn.commit()
            else:
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE scan_runs
                        SET status = 'completed', completed_at = NOW(),
                            total_scanned = :scanned, total_crap = :crap,
                            total_categorized = :categorized, total_trashed = :trashed,
                            total_labeled = :labeled
                        WHERE id = :id
                    """), {
                        "id": run_id,
                        "scanned": total_scanned,
                        "crap": total_crap,
                        "categorized": total_categorized,
                        "trashed": total_trashed,
                        "labeled": total_labeled,
                    })
                    if batch_id is not None:
                        conn.execute(text("""
                            UPDATE operation_batches
                            SET status = 'completed', completed_at = NOW(),
                                total_processed = :scanned
                            WHERE id = :batch_id
                        """), {"batch_id": batch_id, "scanned": total_scanned})
                    conn.commit()

        except Exception as e:
            if batch_id is not None:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("""
                            UPDATE operation_batches
                            SET status = 'failed', completed_at = NOW()
                            WHERE id = :batch_id
                        """), {"batch_id": batch_id})
                        conn.commit()
                except Exception:
                    pass
            fail(str(e)[:500])


    # ─── Build FastAPI app ───
    app = FastAPI(debug=False)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    cookie_secret = hashlib.sha256(f"{settings.jwt_signing_secret}:dashboard-session".encode()).hexdigest()
    app.add_middleware(SessionMiddleware, secret_key=cookie_secret, same_site="lax", https_only=settings.app_env == "production")

    @app.middleware("http")
    async def extension_request_guard(request: Request, call_next):
        if request.url.path.startswith("/api/extension/") and request.method in {"POST", "PUT", "PATCH"}:
            length = int(request.headers.get("content-length", "0") or 0)
            if length > 1_048_576:
                return __import__("fastapi").responses.JSONResponse(status_code=413, content={"detail": "Request body too large"})
            if not request.headers.get("content-length") and len(await request.body()) > 1_048_576:
                return __import__("fastapi").responses.JSONResponse(status_code=413, content={"detail": "Request body too large"})
            body_required = request.url.path not in {"/api/extension/auth/revoke", "/api/extension/pairing-codes"}
            if body_required and request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return __import__("fastapi").responses.JSONResponse(status_code=415, content={"detail": "application/json required"})
        return await call_next(request)

    app.include_router(api, prefix="/api")
    app.include_router(create_extension_router(), prefix="/api")

    if os.path.isdir(static_dir):
        assets_dir = os.path.join(static_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}")
        async def spa_fallback(request: Request, path: str):
            file_path = os.path.join(static_dir, path)
            if path and os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(
                os.path.join(static_dir, "index.html"),
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

    return app
