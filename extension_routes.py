"""Authenticated organizer extension API."""
from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

import classifier as clf
from config import Settings
from db import get_engine
from extension_auth import (AuthFailure, SCOPES, create_pairing_code, decode_access_token,
                            pair_extension, privacy_hash, rate_limiter, refresh_session)

bearer = HTTPBearer(auto_error=False)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PairRequest(StrictModel):
    pairing_code: str = Field(min_length=9, max_length=9)
    device_name: str = Field(min_length=1, max_length=100)
    extension_version: str = Field(min_length=1, max_length=30)


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=40, max_length=512)


class MessageSummary(StrictModel):
    id: str = Field(min_length=1, max_length=255)
    threadId: str = Field(min_length=1, max_length=255)
    subject: str = Field(max_length=500)
    from_: str = Field(alias="from", max_length=500)
    receivedAt: str | None = Field(default=None, max_length=100)
    snippet: str = Field(max_length=1000)
    labelIds: list[str] = Field(default_factory=list, max_length=100)


class ClassificationRequest(StrictModel):
    messages: list[MessageSummary] = Field(min_length=1, max_length=50)


def _remote_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def dashboard_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    email = request.session.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Dashboard authentication required")
    return {"id": str(user_id), "email": str(email)}


def access_claims(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    settings: Settings = request.app.state.settings
    ip_key = privacy_hash(_remote_ip(request), settings)
    if not credentials or credentials.scheme.lower() != "bearer":
        try: rate_limiter.check(f"auth-failure:{ip_key}", 30, 600)
        except AuthFailure as exc: raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
        with get_engine().begin() as conn:
            conn.execute(text("INSERT INTO extension_audit_events (event_type, ip_hash) VALUES ('extension_auth_failed', :ip)"), {"ip": ip_key})
        raise HTTPException(status_code=401, detail="Bearer authentication required")
    try:
        return decode_access_token(credentials.credentials, settings)
    except AuthFailure as exc:
        with get_engine().begin() as conn:
            conn.execute(text("INSERT INTO extension_audit_events (event_type, ip_hash) VALUES ('extension_auth_failed', :ip)"), {"ip": ip_key})
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None


def create_extension_router() -> APIRouter:
    router = APIRouter(prefix="/extension", tags=["extension"])

    @router.post("/pairing-codes")
    def pairing_codes(request: Request, user: Annotated[dict, Depends(dashboard_user)]):
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM extension_pairing_codes WHERE expires_at < :now OR consumed_at IS NOT NULL"), {"now": datetime.now(timezone.utc)})
        try:
            return create_pairing_code(engine, request.app.state.settings, user["id"], _remote_ip(request))
        except AuthFailure as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None

    @router.post("/pair")
    def pair(body: PairRequest, request: Request):
        try:
            return pair_extension(get_engine(), request.app.state.settings, body.pairing_code, body.device_name, body.extension_version, _remote_ip(request))
        except AuthFailure as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None

    @router.post("/auth/refresh")
    def refresh(body: RefreshRequest, request: Request):
        try:
            return refresh_session(get_engine(), request.app.state.settings, body.refresh_token, _remote_ip(request))
        except AuthFailure as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None

    @router.get("/auth/me")
    def me(request: Request, claims: Annotated[dict, Depends(access_claims)]):
        with get_engine().begin() as conn:
            row = conn.execute(text("""SELECT u.id, u.email, u.display_name, d.id, d.device_name, d.revoked_at
                FROM extension_device_sessions d JOIN organizer_users u ON u.id = d.user_id
                WHERE d.id = :sid AND d.user_id = :uid"""), {"sid": claims["sid"], "uid": claims["user_id"]}).fetchone()
            if not row or row[5] is not None:
                raise HTTPException(status_code=401, detail="Device session unavailable")
            conn.execute(text("UPDATE extension_device_sessions SET last_seen_at = :now WHERE id = :sid"), {"now": datetime.now(timezone.utc), "sid": claims["sid"]})
        return {"user": {"id": str(row[0]), "displayName": row[2] or row[1]}, "deviceSessionId": str(row[3]),
                "deviceName": row[4], "scopes": claims["scope"], "accessTokenExpiresAt": datetime.fromtimestamp(claims["exp"], timezone.utc).isoformat(),
                "environment": request.app.state.settings.app_env}

    @router.post("/auth/revoke", status_code=204)
    def revoke_current(request: Request, claims: Annotated[dict, Depends(access_claims)]):
        now = datetime.now(timezone.utc)
        with get_engine().begin() as conn:
            conn.execute(text("UPDATE extension_device_sessions SET revoked_at = :now WHERE id = :sid AND user_id = :uid"),
                         {"now": now, "sid": claims["sid"], "uid": claims["user_id"]})
            conn.execute(text("INSERT INTO extension_audit_events (event_type, user_id, device_session_id) VALUES ('extension_device_revoked', :uid, :sid)"),
                         {"uid": claims["user_id"], "sid": claims["sid"]})

    @router.get("/devices")
    def devices(user: Annotated[dict, Depends(dashboard_user)]):
        with get_engine().connect() as conn:
            rows = conn.execute(text("""SELECT id, device_name, extension_version, created_at, last_seen_at, revoked_at
                FROM extension_device_sessions WHERE user_id = :uid ORDER BY created_at DESC"""), {"uid": user["id"]}).fetchall()
        return {"devices": [{"id": str(row[0]), "device_name": row[1], "extension_version": row[2], "created_at": row[3],
                             "last_seen_at": row[4], "revoked": row[5] is not None} for row in rows]}

    @router.delete("/devices/{device_session_id}", status_code=204)
    def revoke_device(device_session_id: str, user: Annotated[dict, Depends(dashboard_user)]):
        try: uuid.UUID(device_session_id)
        except ValueError: raise HTTPException(status_code=404, detail="Device not found") from None
        with get_engine().begin() as conn:
            row = conn.execute(text("""UPDATE extension_device_sessions SET revoked_at = :now
                WHERE id = :sid AND user_id = :uid RETURNING id"""),
                {"now": datetime.now(timezone.utc), "sid": device_session_id, "uid": user["id"]}).fetchone()
            if not row: raise HTTPException(status_code=404, detail="Device not found")

    @router.post("/classify-preview")
    def classify_preview(body: ClassificationRequest, claims: Annotated[dict, Depends(access_claims)]):
        if "classify:submit" not in claims["scope"]:
            raise HTTPException(status_code=403, detail="Insufficient scope")
        emails = [{"id": item.id, "subject": item.subject, "from": item.from_, "date": item.receivedAt or "", "snippet": item.snippet} for item in body.messages]
        results = clf.classify_batch(emails)
        proposals = [{"messageId": item["message_id"], "proposedLabel": item.get("category") or ("trash-review" if item.get("is_crap") else "uncategorized"),
                      "confidence": item.get("confidence", 0.0), "reason": item.get("crap_reason")} for item in results]
        return {"proposals": proposals}

    return router
