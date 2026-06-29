CREATE TABLE IF NOT EXISTS organizer_users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS extension_pairing_codes (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES organizer_users(id) ON DELETE CASCADE,
    code_hash VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    created_ip_hash VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS ix_extension_pairing_codes_user ON extension_pairing_codes(user_id);

CREATE TABLE IF NOT EXISTS extension_device_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES organizer_users(id) ON DELETE CASCADE,
    device_name VARCHAR(100) NOT NULL,
    extension_version VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    refresh_token_hash VARCHAR(64) NOT NULL,
    refresh_token_expires_at TIMESTAMPTZ NOT NULL,
    rotation_counter INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_extension_devices_user ON extension_device_sessions(user_id);

CREATE TABLE IF NOT EXISTS extension_refresh_token_history (
    token_hash VARCHAR(64) PRIMARY KEY,
    device_session_id VARCHAR(36) NOT NULL REFERENCES extension_device_sessions(id) ON DELETE CASCADE,
    rotated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS extension_audit_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(80) NOT NULL,
    user_id VARCHAR(36),
    device_session_id VARCHAR(36),
    ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
