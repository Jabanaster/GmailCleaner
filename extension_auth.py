"""Organizer-owned extension pairing and session credentials."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import threading
import uuid

import jwt
from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import Settings

SCOPES = ["classify:submit", "scan:create", "scan:read"]
PAIR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AuthFailure(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class RateLimiter:
    """Small-process limiter. Use a shared store when running multiple workers."""
    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int, now: float | None = None):
        timestamp = now if now is not None else datetime.now(timezone.utc).timestamp()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= timestamp - window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise AuthFailure("Too many requests", 429)
            events.append(timestamp)


rate_limiter = RateLimiter()


def _digest(value: str, settings: Settings) -> str:
    purpose_key = hashlib.sha256(f"{settings.jwt_signing_secret}:extension-credential-hash".encode()).digest()
    return hmac.new(purpose_key, value.encode(), hashlib.sha256).hexdigest()


def privacy_hash(value: str, settings: Settings) -> str:
    return _digest(f"privacy:{value}", settings)


def _audit(conn, event_type: str, *, user_id: str | None = None, session_id: str | None = None, ip_hash: str | None = None):
    conn.execute(text("""INSERT INTO extension_audit_events (event_type, user_id, device_session_id, ip_hash)
        VALUES (:event, :user_id, :session_id, :ip_hash)"""),
        {"event": event_type, "user_id": user_id, "session_id": session_id, "ip_hash": ip_hash})


def upsert_dashboard_user(engine: Engine, email: str, display_name: str | None = None) -> str:
    user_id = str(uuid.uuid4())
    with engine.begin() as conn:
        row = conn.execute(text("""INSERT INTO organizer_users (id, email, display_name)
            VALUES (:id, :email, :name)
            ON CONFLICT (email) DO UPDATE SET display_name = COALESCE(EXCLUDED.display_name, organizer_users.display_name), last_login_at = NOW()
            RETURNING id"""), {"id": user_id, "email": email.lower(), "name": display_name}).fetchone()
    return str(row[0])


def create_pairing_code(engine: Engine, settings: Settings, user_id: str, remote_ip: str) -> dict:
    ip_hash = privacy_hash(remote_ip, settings)
    rate_limiter.check(f"pair-create:user:{user_id}", 5, 3600)
    code = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(8))
    code = f"{code[:4]}-{code[4:]}"
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=settings.pairing_code_ttl_seconds)
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO extension_pairing_codes
            (id, user_id, code_hash, created_at, expires_at, created_ip_hash)
            VALUES (:id, :user_id, :code_hash, :now, :expires, :ip_hash)"""),
            {"id": str(uuid.uuid4()), "user_id": user_id, "code_hash": _digest(code, settings), "now": now, "expires": expires, "ip_hash": ip_hash})
        _audit(conn, "extension_pairing_code_created", user_id=user_id, ip_hash=ip_hash)
    return {"pairing_code": code, "expires_at": expires.isoformat()}


def _issue_access_token(settings: Settings, user_id: str, session_id: str, now: datetime | None = None) -> tuple[str, datetime]:
    issued = now or datetime.now(timezone.utc)
    expires = issued + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": f"user:{user_id}", "sid": session_id,
               "jti": str(uuid.uuid4()), "iat": issued, "nbf": issued, "exp": expires, "scope": SCOPES}
    return jwt.encode(payload, settings.jwt_signing_secret, algorithm="HS256"), expires


def _new_refresh_token(session_id: str) -> str:
    return f"{session_id}.{secrets.token_urlsafe(48)}"


def pair_extension(engine: Engine, settings: Settings, code: str, device_name: str, extension_version: str, remote_ip: str) -> dict:
    normalized = code.strip().upper()
    if not re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", normalized):
        raise AuthFailure("Invalid or expired pairing code", 400)
    ip_hash = privacy_hash(remote_ip, settings)
    rate_limiter.check(f"pair-attempt:ip:{ip_hash}", 10, 600)
    now = datetime.now(timezone.utc)
    session_id = str(uuid.uuid4())
    refresh = _new_refresh_token(session_id)
    code_hash = _digest(normalized, settings)
    pairing_failed = False
    with engine.begin() as conn:
        row = conn.execute(text("""UPDATE extension_pairing_codes
            SET consumed_at = :now WHERE code_hash = :code_hash AND consumed_at IS NULL
            AND expires_at > :now AND failed_attempts < 5 RETURNING user_id"""), {"now": now, "code_hash": code_hash}).fetchone()
        if not row:
            conn.execute(text("""UPDATE extension_pairing_codes SET failed_attempts = failed_attempts + 1
                WHERE code_hash = :code_hash AND consumed_at IS NULL"""), {"code_hash": code_hash})
            _audit(conn, "extension_pairing_failed", ip_hash=ip_hash)
            pairing_failed = True
        else:
            user_id = str(row[0])
            conn.execute(text("""INSERT INTO extension_device_sessions
            (id, user_id, device_name, extension_version, created_at, last_seen_at, refresh_token_hash, refresh_token_expires_at)
            VALUES (:id, :user_id, :name, :version, :now, :now, :token_hash, :expires)"""),
            {"id": session_id, "user_id": user_id, "name": device_name, "version": extension_version, "now": now,
             "token_hash": _digest(refresh, settings), "expires": now + timedelta(seconds=settings.refresh_token_ttl_seconds)})
            _audit(conn, "extension_pairing_succeeded", user_id=user_id, session_id=session_id, ip_hash=ip_hash)
    if pairing_failed:
        raise AuthFailure("Invalid or expired pairing code", 400)
    access, expires = _issue_access_token(settings, user_id, session_id, now)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_at": expires.isoformat()}


def refresh_session(engine: Engine, settings: Settings, refresh_token: str, remote_ip: str) -> dict:
    if "." not in refresh_token or len(refresh_token) > 512:
        raise AuthFailure("Invalid refresh credential")
    session_id = refresh_token.split(".", 1)[0]
    try: uuid.UUID(session_id)
    except ValueError: raise AuthFailure("Invalid refresh credential")
    ip_hash = privacy_hash(remote_ip, settings)
    rate_limiter.check(f"refresh:ip:{ip_hash}", 30, 600)
    supplied_hash = _digest(refresh_token, settings)
    now = datetime.now(timezone.utc)
    new_refresh = _new_refresh_token(session_id)
    auth_error: str | None = None
    with engine.begin() as conn:
        lock = " FOR UPDATE" if engine.dialect.name != "sqlite" else ""
        row = conn.execute(text("""SELECT user_id, refresh_token_hash, refresh_token_expires_at, revoked_at
            FROM extension_device_sessions WHERE id = :id""" + lock), {"id": session_id}).fetchone()
        if not row or row[3] is not None:
            auth_error = "Invalid refresh credential"
        elif not hmac.compare_digest(str(row[1]), supplied_hash):
            reused = conn.execute(text("SELECT 1 FROM extension_refresh_token_history WHERE token_hash = :hash AND device_session_id = :id"),
                                  {"hash": supplied_hash, "id": session_id}).fetchone()
            if reused:
                conn.execute(text("UPDATE extension_device_sessions SET revoked_at = :now WHERE id = :id"), {"now": now, "id": session_id})
                _audit(conn, "extension_refresh_reuse_detected", user_id=str(row[0]), session_id=session_id, ip_hash=ip_hash)
            auth_error = "Invalid refresh credential"
        else:
            expiry = row[2]
            if isinstance(expiry, str): expiry = datetime.fromisoformat(expiry)
            if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= now:
                auth_error = "Refresh credential expired"
            else:
                conn.execute(text("INSERT INTO extension_refresh_token_history (token_hash, device_session_id, rotated_at) VALUES (:hash, :id, :now)"),
                     {"hash": supplied_hash, "id": session_id, "now": now})
                conn.execute(text("""UPDATE extension_device_sessions SET refresh_token_hash = :hash, refresh_token_expires_at = :expires,
            rotation_counter = rotation_counter + 1, last_seen_at = :now WHERE id = :id"""),
            {"hash": _digest(new_refresh, settings), "expires": now + timedelta(seconds=settings.refresh_token_ttl_seconds), "now": now, "id": session_id})
                _audit(conn, "extension_session_refreshed", user_id=str(row[0]), session_id=session_id, ip_hash=ip_hash)
    if auth_error:
        raise AuthFailure(auth_error)
    access, expires = _issue_access_token(settings, str(row[0]), session_id, now)
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer", "expires_at": expires.isoformat()}


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_signing_secret, algorithms=["HS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer,
                            options={"require": ["iss", "aud", "sub", "sid", "jti", "iat", "nbf", "exp", "scope"]})
    except jwt.PyJWTError as exc:
        raise AuthFailure("Invalid or expired access token") from exc
    if not str(claims["sub"]).startswith("user:") or not isinstance(claims["scope"], list):
        raise AuthFailure("Invalid access token claims")
    claims["user_id"] = claims["sub"][5:]
    return claims
