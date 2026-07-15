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

    if len(secret) < 32 or secret.lower() in {"changeme", "change-me", "placeholder", "secret"}:
        raise RuntimeError("JWT_SIGNING_SECRET must be a non-placeholder secret of at least 32 characters")
    if "*" in web_origins:
        raise RuntimeError("Wildcard CORS origins are forbidden")
    
    # Validate token encryption key
    if not encryption_key:
        raise RuntimeError("OAUTH_TOKEN_ENCRYPTION_KEY is required and must be set in the environment")
    try:
        import base64
        key_bytes = base64.urlsafe_b64decode(encryption_key)
        if len(key_bytes) != 32:
            raise ValueError()
    except Exception:
        raise RuntimeError("OAUTH_TOKEN_ENCRYPTION_KEY must be a valid 32-byte URL-safe base64-encoded key")

    parsed = urlparse(public_url)
    is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (env == "development" and parsed.scheme == "http" and is_loopback):
        raise RuntimeError("PUBLIC_API_BASE_URL must use HTTPS outside loopback development")
    if env == "production":
        if not extension_ids:
            raise RuntimeError("ALLOWED_EXTENSION_IDS must not be empty in production")
        if os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError("Debug mode is forbidden in production")

    # Load and validate scan loop batch/delay settings
    try:
        scan_batch_size = int(os.getenv("SCAN_BATCH_SIZE", "10"))
        scan_batch_delay_ms = int(os.getenv("SCAN_BATCH_DELAY_MS", "1000"))
        gmail_quota_backoff_ms = int(os.getenv("GMAIL_QUOTA_BACKOFF_MS", "5000"))
        gmail_max_retry_attempts = int(os.getenv("GMAIL_MAX_RETRY_ATTEMPTS", "3"))
        if scan_batch_size <= 0 or scan_batch_delay_ms < 0 or gmail_quota_backoff_ms < 0 or gmail_max_retry_attempts < 0:
            raise ValueError()
    except Exception:
        raise RuntimeError("Scan pacing settings (SCAN_BATCH_SIZE, SCAN_BATCH_DELAY_MS, GMAIL_QUOTA_BACKOFF_MS, GMAIL_MAX_RETRY_ATTEMPTS) must be non-negative integers (SCAN_BATCH_SIZE must be > 0)")

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
    )


