"""Gmail OAuth2 and API service layer."""
import os
import time
from datetime import datetime, timezone
import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from db import get_engine, get_setting, set_setting
from sqlalchemy import text

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Category labels we'll create in the user's Gmail
CATEGORY_LABELS = {
    "work": "Sorter/Work",
    "finance": "Sorter/Finance",
    "personal": "Sorter/Personal",
    "travel": "Sorter/Travel",
    "receipts": "Sorter/Receipts",
    "social": "Sorter/Social",
    "newsletters": "Sorter/Newsletters",
    "promotions": "Sorter/Promotions",
}


def get_oauth_config() -> dict:
    """Get Google OAuth client config from environment."""
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "configured": bool(client_id and client_secret),
    }


def retry_api_call(func, max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    """Retry an API call with exponential backoff.

    Args:
        func: Callable to invoke (no arguments).
        max_retries: Maximum number of attempts.
        delay: Initial delay in seconds (doubles each attempt).

    Returns:
        Result of the first successful call.

    Raises:
        Exception: Re-raises the last exception if all retries fail.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
    raise last_exception


def _is_google_host(host: str) -> bool:
    hostname = host.lower().split(":")[0]
    return hostname == "google.com" or hostname.endswith(".google.com")


def _resolve_app_origin(request) -> str:
    """Resolve the public dashboard origin used for OAuth redirect URIs."""
    try:
        settings = request.app.state.settings
    except AttributeError:
        from config import load_settings, Settings
        try:
            settings = load_settings()
        except Exception:
            web_origins = tuple(
                value.strip()
                for value in os.environ.get("ALLOWED_WEB_ORIGINS", "").split(",")
                if value.strip()
            )
            if not web_origins:
                web_origins = ("http://localhost:5173",)
            settings = Settings(
                app_env="development",
                public_api_base_url=os.environ.get("PUBLIC_API_BASE_URL", "http://localhost:5273"),
                allowed_web_origins=web_origins,
                allowed_extension_ids=(),
                jwt_issuer="google-email-organizer-api",
                jwt_audience="google-email-organizer-extension",
                jwt_signing_secret="dummy-signing-secret-at-least-32-characters-long",
                access_token_ttl_seconds=600,
                refresh_token_ttl_seconds=2592000,
                pairing_code_ttl_seconds=600,
                oauth_token_encryption_key="m1y6C2fHWhlS9v_P7r7Y1T3Nf8u_k3zL0d3J-5s3o9o=",
                scan_batch_size=10,
                scan_batch_delay_ms=1000,
                gmail_quota_backoff_ms=5000,
                gmail_max_retry_attempts=3,
            )


    
    # Whitelist of allowed origins
    allowed = [origin.rstrip("/") for origin in settings.allowed_web_origins]
    if settings.public_api_base_url:
        allowed.append(settings.public_api_base_url.rstrip("/"))
        
    custom_domain = os.environ.get("WORKSHOP_CUSTOM_DOMAIN")
    if custom_domain:
        allowed.append(f"https://{custom_domain.strip()}")
        
    # Build list of potential candidates from request headers
    candidates = []
    
    origin = request.headers.get("origin")
    if origin:
        candidates.append(origin.rstrip("/"))
        
    referer = request.headers.get("referer")
    if referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            candidates.append(f"{parsed.scheme}://{parsed.netloc}".rstrip("/"))
            
    xfh = request.headers.get("x-forwarded-host")
    if xfh:
        xfh = xfh.split(",")[0].strip()
        xfp = request.headers.get("x-forwarded-proto") or request.url.scheme
        candidates.append(f"{xfp}://{xfh}".rstrip("/"))
        
    host = request.headers.get("host")
    if host:
        host = host.split(",")[0].strip()
        xfp = request.headers.get("x-forwarded-proto") or request.url.scheme
        candidates.append(f"{xfp}://{host}".rstrip("/"))

    # Match candidates against whitelisted allowed origins
    for c in candidates:
        if c in allowed:
            return c

    if allowed:
        return allowed[0]
        
    raise ValueError(
        "Cannot determine redirect URI — no trusted origin found in ALLOWED_WEB_ORIGINS"
    )


def get_redirect_uri(request) -> str:
    """Build the OAuth redirect URI from the request origin."""
    return f"{_resolve_app_origin(request)}/api/gmail/oauth/callback"


def get_auth_url(request, state: str, redirect_uri: str | None = None) -> str:
    """Generate the Google OAuth consent URL."""
    config = get_oauth_config()
    if not config["configured"]:
        raise ValueError("Google OAuth client ID/secret not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET secrets.")

    redirect_uri = redirect_uri or get_redirect_uri(request)

    params = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    import urllib.parse
    query = "&".join(f"{k}={urllib.parse.quote(v, safe='')}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"



def exchange_code_for_tokens(code: str, request, redirect_uri: str | None = None) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    config = get_oauth_config()
    redirect_uri = redirect_uri or get_redirect_uri(request)

    data = {
        "code": code,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    resp = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token using a stored refresh token."""
    config = get_oauth_config()
    data = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    resp = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=30.0)
    resp.raise_for_status()
    tokens = resp.json()
    tokens["refresh_token"] = refresh_token  # keep the refresh token
    return tokens


def store_tokens(user_email: str, tokens: dict):
    """Store OAuth tokens in the database."""
    from config import load_settings
    from encryption_utils import encrypt_token

    settings = load_settings()
    engine = get_engine()
    expiry_ts = tokens.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc).timestamp() + expiry_ts

    raw_refresh = tokens.get("refresh_token")
    enc_refresh = encrypt_token(raw_refresh, settings.oauth_token_encryption_key) if raw_refresh else None

    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO gmail_oauth_tokens (email, access_token, refresh_token, token_expiry, scopes, updated_at)
            VALUES (:email, :access_token, :refresh_token, to_timestamp(:expiry), :scopes, NOW())
            ON CONFLICT (email) DO UPDATE
            SET access_token = :access_token,
                refresh_token = COALESCE(:refresh_token, gmail_oauth_tokens.refresh_token),
                token_expiry = to_timestamp(:expiry),
                scopes = :scopes,
                updated_at = NOW()
        """), {
            "email": user_email,
            "access_token": tokens.get("access_token"),
            "refresh_token": enc_refresh,
            "expiry": expiry,
            "scopes": " ".join(GMAIL_SCOPES),
        })
        conn.commit()


def get_stored_tokens(user_email: str) -> dict | None:
    """Retrieve stored OAuth tokens for a user, refreshing if needed."""
    from config import load_settings
    from encryption_utils import decrypt_token
    from cryptography.fernet import InvalidToken

    settings = load_settings()
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT email, access_token, refresh_token, token_expiry
            FROM gmail_oauth_tokens WHERE email = :email
        """), {"email": user_email}).fetchone()

    if not result:
        return None

    email, access_token, refresh_token, expiry = result

    if expiry and isinstance(expiry, str):
        try:
            if expiry.endswith("Z"):
                expiry = expiry[:-1] + "+00:00"
            expiry = datetime.fromisoformat(expiry)
        except ValueError:
            expiry = None


    decrypted_refresh = None
    if refresh_token:
        try:
            decrypted_refresh = decrypt_token(refresh_token, settings.oauth_token_encryption_key)
        except InvalidToken:
            # Stored token is plaintext (or key mismatch). Fail closed for safety.
            import logging
            logging.warning("Failed to decrypt stored Gmail refresh token; invalid or unencrypted token format.")
            return None


    # Check if token is expired (with 60s buffer)
    now_ts = datetime.now(timezone.utc).timestamp()
    if expiry and expiry.timestamp() <= now_ts + 60:
        if decrypted_refresh:
            try:
                new_tokens = refresh_access_token(decrypted_refresh)
                store_tokens(email, new_tokens)
                return {
                    "access_token": new_tokens["access_token"],
                    "refresh_token": decrypted_refresh,
                }
            except Exception:
                return None
        return None

    return {"access_token": access_token, "refresh_token": decrypted_refresh}



def get_connected_email() -> str | None:
    """Get the email of the currently connected Gmail account."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT email FROM gmail_oauth_tokens ORDER BY updated_at DESC LIMIT 1"
        )).fetchone()
    return result[0] if result else None


def build_gmail_service(user_email: str):
    """Build an authenticated Gmail API service for the given user."""
    tokens = get_stored_tokens(user_email)
    if not tokens:
        raise ValueError(f"No valid OAuth tokens for {user_email}")

    creds = Credentials(
        token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
        scopes=GMAIL_SCOPES,
    )

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_user_profile(user_email: str) -> dict:
    """Get Gmail user profile (email address, message count)."""
    service = build_gmail_service(user_email)
    profile = retry_api_call(lambda: service.users().getProfile(userId="me").execute())
    return {
        "email": profile.get("emailAddress"),
        "messages_total": profile.get("messagesTotal", 0),
        "threads_total": profile.get("threadsTotal", 0),
    }


def ensure_labels_exist(user_email: str) -> dict:
    """Ensure all category labels exist in Gmail; return name->labelId mapping."""
    service = build_gmail_service(user_email)
    existing_labels = retry_api_call(lambda: service.users().labels().list(userId="me").execute())
    label_map = {lbl["name"]: lbl["id"] for lbl in existing_labels.get("labels", [])}

    # Ensure top-level "Sorter" label exists
    if "Sorter" not in label_map:
        body = {"name": "Sorter", "messageListVisibility": "show", "labelListVisibility": "labelShow"}
        try:
            result = retry_api_call(lambda: service.users().labels().create(userId="me", body=body).execute())
            label_map["Sorter"] = result["id"]
        except HttpError as e:
            print(f"Failed to create Sorter label: {e}")
            raise

    for cat, label_name in CATEGORY_LABELS.items():
        if label_name not in label_map:
            body = {
                "name": label_name.split("/", 1)[1],
                "messageListVisibility": "show",
                "labelListVisibility": "labelShow",
            }
            try:
                result = retry_api_call(lambda: service.users().labels().create(userId="me", body=body).execute())
                label_map[label_name] = result["id"]
            except HttpError as e:
                if e.resp.status == 409:
                    # Already exists — re-fetch
                    labels = retry_api_call(lambda: service.users().labels().list(userId="me").execute())
                    label_map = {lbl["name"]: lbl["id"] for lbl in labels.get("labels", [])}
                else:
                    raise

    # Store label mapping in DB
    engine = get_engine()
    with engine.connect() as conn:
        for cat, label_name in CATEGORY_LABELS.items():
            conn.execute(text("""
                INSERT INTO gmail_labels (user_email, label_name, gmail_label_id, category)
                VALUES (:email, :label_name, :label_id, :category)
                ON CONFLICT (user_email, label_name) DO UPDATE
                SET gmail_label_id = :label_id
            """), {
                "email": user_email,
                "label_name": label_name,
                "label_id": label_map.get(label_name),
                "category": cat,
            })
        conn.commit()

    return label_map


def get_label_id(user_email: str, category: str) -> str | None:
    """Get the Gmail label ID for a category."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT gmail_label_id FROM gmail_labels
            WHERE user_email = :email AND category = :category
        """), {"email": user_email, "category": category}).fetchone()
    return result[0] if result else None


def fetch_messages(user_email: str, max_results: int | None = None) -> list[dict]:
    """Fetch messages from inbox. If max_results is None, fetch everything (paginated)."""
    service = build_gmail_service(user_email)
    all_message_ids = []
    page_token = None

    while True:
        params = {"userId": "me", "q": "in:inbox"}
        if page_token:
            params["pageToken"] = page_token
        if max_results and len(all_message_ids) >= max_results:
            break

        results = retry_api_call(lambda: service.users().messages().list(**params).execute())
        messages = results.get("messages", [])
        all_message_ids.extend(messages)
        page_token = results.get("nextPageToken")

        if not page_token:
            break
        if max_results and len(all_message_ids) >= max_results:
            all_message_ids = all_message_ids[:max_results]
            break

    return all_message_ids


def fetch_message_detail(user_email: str, message_id: str) -> dict:
    """Fetch full message details (headers + snippet)."""
    service = build_gmail_service(user_email)
    msg = retry_api_call(lambda: service.users().messages().get(
        userId="me", id=message_id, format="metadata", metadataHeaders=["Subject", "From", "Date"]
    ).execute())

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "subject": headers.get("Subject", "(no subject)"),
        "from": headers.get("From", ""),
        "date": headers.get("Date", ""),
        "snippet": msg.get("snippet", ""),
        "label_ids": msg.get("labelIds", []),
    }


def trash_message(user_email: str, message_id: str):
    """Move a message to trash (recoverable for 30 days)."""
    service = build_gmail_service(user_email)
    retry_api_call(lambda: service.users().messages().trash(userId="me", id=message_id).execute())


def add_label_to_message(user_email: str, message_id: str, label_id: str):
    """Add a label to a message."""
    service = build_gmail_service(user_email)
    retry_api_call(lambda: service.users().messages().modify(
        userId="me", id=message_id, body={"addLabelIds": [label_id]}
    ).execute())


def remove_from_inbox(user_email: str, message_id: str):
    """Archive a message (remove from inbox)."""
    service = build_gmail_service(user_email)
    retry_api_call(lambda: service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
    ).execute())


def disconnect_gmail(user_email: str):
    """Revoke OAuth tokens and remove from database."""
    engine = get_engine()
    tokens = get_stored_tokens(user_email)
    if tokens and tokens.get("refresh_token"):
        try:
            httpx.post(
                f"https://oauth2.googleapis.com/revoke?token={tokens['refresh_token']}",
                timeout=10.0,
            )
        except Exception:
            pass

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM gmail_oauth_tokens WHERE email = :email"), {"email": user_email})
        conn.execute(text("DELETE FROM gmail_labels WHERE user_email = :email"), {"email": user_email})
        conn.commit()
