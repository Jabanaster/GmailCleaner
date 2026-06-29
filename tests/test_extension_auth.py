from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import text

from extension_auth import AuthFailure, create_pairing_code, decode_access_token, pair_extension, refresh_session


def create_and_pair(engine, settings):
    created = create_pairing_code(engine, settings, "user-a", "127.0.0.1")
    paired = pair_extension(engine, settings, created["pairing_code"], "Test Chrome", "0.2.0", "127.0.0.1")
    return created, paired


def test_pairing_code_is_hashed_single_use_and_claims_are_safe(engine, settings):
    created, paired = create_and_pair(engine, settings)
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT code_hash, consumed_at FROM extension_pairing_codes")).fetchone()
    assert stored[0] != created["pairing_code"]
    assert created["pairing_code"] not in stored[0]
    assert stored[1] is not None
    with pytest.raises(AuthFailure):
        pair_extension(engine, settings, created["pairing_code"], "Second", "0.2.0", "127.0.0.2")
    claims = decode_access_token(paired["access_token"], settings)
    assert claims["sub"] == "user:user-a"
    assert {"iss", "aud", "sub", "sid", "jti", "iat", "nbf", "exp", "scope"} <= claims.keys()
    assert "email" not in claims and "refresh_token" not in claims and "snippet" not in claims


def test_expired_and_wrong_pairing_codes_are_rejected(engine, settings):
    created = create_pairing_code(engine, settings, "user-a", "127.0.0.1")
    with engine.begin() as conn:
        conn.execute(text("UPDATE extension_pairing_codes SET expires_at = :past"), {"past": datetime.now(timezone.utc) - timedelta(seconds=1)})
    with pytest.raises(AuthFailure): pair_extension(engine, settings, created["pairing_code"], "Device", "0.2.0", "127.0.0.1")
    with pytest.raises(AuthFailure): pair_extension(engine, settings, "ZZZZ-ZZZZ", "Device", "0.2.0", "127.0.0.1")


def test_excessive_pairing_attempts_are_rate_limited(engine, settings):
    for _ in range(10):
        with pytest.raises(AuthFailure) as failure:
            pair_extension(engine, settings, "ZZZZ-ZZZZ", "Device", "0.2.0", "127.0.0.1")
        assert failure.value.status_code == 400
    with pytest.raises(AuthFailure) as limited:
        pair_extension(engine, settings, "ZZZZ-ZZZZ", "Device", "0.2.0", "127.0.0.1")
    assert limited.value.status_code == 429


def test_concurrent_pairing_consumes_code_once(engine, settings):
    created = create_pairing_code(engine, settings, "user-a", "127.0.0.1")
    def attempt(index):
        try:
            pair_extension(engine, settings, created["pairing_code"], f"Device {index}", "0.2.0", f"127.0.0.{index + 1}")
            return True
        except AuthFailure:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count(True) == 1


def test_refresh_rotates_and_reuse_revokes_device(engine, settings):
    _, paired = create_and_pair(engine, settings)
    rotated = refresh_session(engine, settings, paired["refresh_token"], "127.0.0.1")
    assert rotated["refresh_token"] != paired["refresh_token"]
    with pytest.raises(AuthFailure): refresh_session(engine, settings, paired["refresh_token"], "127.0.0.1")
    with pytest.raises(AuthFailure): refresh_session(engine, settings, rotated["refresh_token"], "127.0.0.1")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT revoked_at FROM extension_device_sessions")).scalar_one() is not None


@pytest.mark.parametrize("change", ["issuer", "audience", "signature", "expired"])
def test_rejects_invalid_access_tokens(settings, change):
    now = datetime.now(timezone.utc)
    payload = {"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": "user:user-a", "sid": "session",
               "jti": "token", "iat": now, "nbf": now, "exp": now + timedelta(minutes=10), "scope": ["scan:read"]}
    secret = settings.jwt_signing_secret
    if change == "issuer": payload["iss"] = "wrong"
    if change == "audience": payload["aud"] = "wrong"
    if change == "signature": secret = "different-signing-secret-that-is-long-enough"
    if change == "expired": payload["exp"] = now - timedelta(seconds=1)
    with pytest.raises(AuthFailure): decode_access_token(jwt.encode(payload, secret, algorithm="HS256"), settings)
