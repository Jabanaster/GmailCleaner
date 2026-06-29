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
            request.session["oauth_state"] = state
            auth_url = gs.get_auth_url(request, state)
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
            raise HTTPException(status_code=400, detail="Invalid OAuth state")

        try:
            tokens = gs.exchange_code_for_tokens(code, request)

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
            "running": latest[1] == "running",
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
                SELECT id FROM scan_runs WHERE user_email = :email AND status = 'running'
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

        def fail(msg):
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE scan_runs SET status = 'failed', completed_at = NOW(), error_message = :msg
                    WHERE id = :id
                """), {"id": run_id, "msg": msg})
                conn.commit()

        try:
            # Ensure labels exist
            if not dry_run:
                gs.ensure_labels_exist(user_email)

            # Fetch all message IDs
            message_ids = gs.fetch_messages(user_email, max_results=max_results)
            total = len(message_ids)

            # Store total email count for progress tracking
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE scan_runs SET total_emails = :total WHERE id = :id
                """), {"total": total, "id": run_id})
                conn.commit()

            # Process in batches
            batch_size = 10
            for i in range(0, total, batch_size):
                batch = message_ids[i:i + batch_size]

                # Fetch message details
                email_details = []
                for msg_ref in batch:
                    try:
                        detail = gs.fetch_message_detail(user_email, msg_ref["id"])
                        email_details.append(detail)
                    except Exception:
                        continue

                # Classify with AI
                classifications = clf.classify_batch(email_details)

                # Process each classification
                for cls in classifications:
                    msg_id = cls["message_id"]
                    action_taken = "none"

                    if cls["is_crap"]:
                        if dry_run:
                            action_taken = "preview"
                            total_trashed += 1
                            total_crap += 1
                        else:
                            # Move to trash
                            try:
                                gs.trash_message(user_email, msg_id)
                                action_taken = "trashed"
                                total_trashed += 1
                                total_crap += 1
                            except Exception:
                                action_taken = "trash_failed"
                    elif cls["category"]:
                        if dry_run:
                            action_taken = "preview"
                            total_labeled += 1
                            total_categorized += 1
                        else:
                            # Add category label
                            label_id = gs.get_label_id(user_email, cls["category"])
                            if label_id:
                                try:
                                    gs.add_label_to_message(user_email, msg_id, label_id)
                                    action_taken = "labeled"
                                    total_labeled += 1
                                    total_categorized += 1
                                except Exception:
                                    action_taken = "label_failed"

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
                        conn.commit()

                    total_scanned += 1

                # Update progress periodically
                with engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE scan_runs SET total_scanned = :scanned WHERE id = :id
                    """), {"scanned": total_scanned, "id": run_id})
                    conn.commit()

            # Mark complete
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
                conn.commit()

        except Exception as e:
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
