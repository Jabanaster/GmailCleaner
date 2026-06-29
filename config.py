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

    @property
    def allowed_origins(self) -> list[str]:
        return [*self.allowed_web_origins, *(f"chrome-extension://{value}" for value in self.allowed_extension_ids)]


def load_settings() -> Settings:
    env = os.getenv("APP_ENV", "development").lower()
    public_url = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:5273").rstrip("/")
    secret = os.getenv("JWT_SIGNING_SECRET", "")
    web_origins = _csv("ALLOWED_WEB_ORIGINS")
    extension_ids = _csv("ALLOWED_EXTENSION_IDS")
    if len(secret) < 32 or secret.lower() in {"changeme", "change-me", "placeholder", "secret"}:
        raise RuntimeError("JWT_SIGNING_SECRET must be a non-placeholder secret of at least 32 characters")
    if "*" in web_origins:
        raise RuntimeError("Wildcard CORS origins are forbidden")
    parsed = urlparse(public_url)
    is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (env == "development" and parsed.scheme == "http" and is_loopback):
        raise RuntimeError("PUBLIC_API_BASE_URL must use HTTPS outside loopback development")
    if env == "production":
        if not extension_ids:
            raise RuntimeError("ALLOWED_EXTENSION_IDS must not be empty in production")
        if os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}:
            raise RuntimeError("Debug mode is forbidden in production")
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
    )
