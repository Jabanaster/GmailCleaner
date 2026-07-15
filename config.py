"""Fail-closed application configuration."""
from dataclasses import dataclass
import os
from urllib.parse import urlparse


def _csv(name: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, "").split(",") if value.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    public_api_base_url: str
    allowed_web_origins: tuple[str, ...]
    allowed_extension_ids: tuple[str, ...]
    jwt_issuer: str
    jwt_audience: str
    jwt_signing_secret: str
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    pairing_code_ttl_seconds: int
    oauth_token_encryption_key: str
    scan_batch_size: int
    scan_batch_delay_ms: int
    gmail_quota_backoff_ms: int
    gmail_max_retry_attempts: int
    min_classification_confidence: float

    @property
    def allowed_origins(self) -> list[str]:
        return [*self.allowed_web_origins, *(f"chrome-extension://{value}" for value in self.allowed_extension_ids)]


def load_settings() -> Settings:
    env = os.getenv("APP_ENV", "development").lower()
    public_url = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:5273").rstrip("/")
    secret = os.getenv("JWT_SIGNING_SECRET", "")
    web_origins = _csv("ALLOWED_WEB_ORIGINS")
    extension_ids = _csv("ALLOWED_EXTENSION_IDS")
    encryption_key = os.getenv("OAUTH_TOKEN_ENCRYPTION_KEY", "")
    errors: list[str] = []

    # ── JWT signing secret strength ──────────────────────────────────────────
    if len(secret) < 32 or secret.lower() in {"changeme", "change-me", "placeholder", "secret"}:
        errors.append("JWT_SIGNING_SECRET must be a non-placeholder secret of at least 32 characters")

    # ── Wildcard CORS origin is always forbidden ─────────────────────────────
    if "*" in web_origins:
        errors.append("Wildcard CORS origins are forbidden")

    # ── Token encryption key ─────────────────────────────────────────────────
    encryption_key_valid = False
    if not encryption_key:
        errors.append("OAUTH_TOKEN_ENCRYPTION_KEY is required and must be set in the environment")
    else:
        try:
            import base64
            key_bytes = base64.urlsafe_b64decode(encryption_key)
            if len(key_bytes) != 32:
                raise ValueError("key length")
            encryption_key_valid = True
        except Exception:
            errors.append("OAUTH_TOKEN_ENCRYPTION_KEY must be a valid 32-byte URL-safe base64-encoded key")

    # ── Public API base URL must use HTTPS outside loopback development ───────
    parsed = urlparse(public_url)
    is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (env == "development" and parsed.scheme == "http" and is_loopback):
        errors.append("PUBLIC_API_BASE_URL must use HTTPS outside loopback development")

    # ── Production-only guards ───────────────────────────────────────────────
    if env == "production":
        # Extension IDs must be explicit
        if not extension_ids:
            errors.append("ALLOWED_EXTENSION_IDS must not be empty in production")

        # Debug mode forbidden
        if os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}:
            errors.append("DEBUG mode is forbidden in production")

        # Database URL must be present
        if not os.getenv("DBE91F0215_DATABASE_URL", "").strip():
            errors.append("DBE91F0215_DATABASE_URL must be set in production")

        # Google OAuth client credentials must be present
        if not os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip():
            errors.append("GOOGLE_OAUTH_CLIENT_ID must be set in production")
        if not os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip():
            errors.append("GOOGLE_OAUTH_CLIENT_SECRET must be set in production (value not shown)")

        # All allowed web origins must use HTTPS in production
        non_https = [o for o in web_origins if not o.startswith("https://")]
        if non_https:
            errors.append(
                f"All ALLOWED_WEB_ORIGINS must use HTTPS in production "
                f"({len(non_https)} non-HTTPS origin(s) found)"
            )

    # ── Raise a single sanitized error (never prints secret values) ──────────
    if errors:
        raise RuntimeError(
            "Configuration error(s) — secret values omitted:\n" +
            "\n".join(f"  • {e}" for e in errors)
        )

    # ── Scan loop pacing settings ────────────────────────────────────────────
    try:
        scan_batch_size = int(os.getenv("SCAN_BATCH_SIZE", "10"))
        scan_batch_delay_ms = int(os.getenv("SCAN_BATCH_DELAY_MS", "1000"))
        gmail_quota_backoff_ms = int(os.getenv("GMAIL_QUOTA_BACKOFF_MS", "5000"))
        gmail_max_retry_attempts = int(os.getenv("GMAIL_MAX_RETRY_ATTEMPTS", "3"))
        min_classification_confidence = float(os.getenv("MIN_CLASSIFICATION_CONFIDENCE", "0.80"))
        if (
            scan_batch_size <= 0
            or scan_batch_delay_ms < 0
            or gmail_quota_backoff_ms < 0
            or gmail_max_retry_attempts < 0
            or not (0.0 <= min_classification_confidence <= 1.0)
        ):
            raise ValueError()
    except Exception:
        raise RuntimeError(
            "Scan pacing settings must be non-negative integers and confidence must be a float between 0.0 and 1.0"
        )

    return Settings(
        app_env=env,
        public_api_base_url=public_url,
        allowed_web_origins=web_origins,
        allowed_extension_ids=extension_ids,
        jwt_issuer=os.getenv("JWT_ISSUER", "google-email-organizer-api"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "google-email-organizer-extension"),
        jwt_signing_secret=secret,
        access_token_ttl_seconds=int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "600")),
        refresh_token_ttl_seconds=int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "2592000")),
        pairing_code_ttl_seconds=int(os.getenv("PAIRING_CODE_TTL_SECONDS", "600")),
        oauth_token_encryption_key=encryption_key,
        scan_batch_size=scan_batch_size,
        scan_batch_delay_ms=scan_batch_delay_ms,
        gmail_quota_backoff_ms=gmail_quota_backoff_ms,
        gmail_max_retry_attempts=gmail_max_retry_attempts,
        min_classification_confidence=min_classification_confidence,
    )
