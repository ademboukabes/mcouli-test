CREATE TABLE IF NOT EXISTS staff_drive_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_user_id UUID NOT NULL REFERENCES staff_users(id) ON DELETE CASCADE,
    provider VARCHAR(64) NOT NULL DEFAULT 'google_drive',
    google_email VARCHAR(255) NOT NULL,
    google_account_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    scopes TEXT NOT NULL,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (staff_user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_staff_drive_connections_staff_user_id
ON staff_drive_connections(staff_user_id);

CREATE INDEX IF NOT EXISTS idx_staff_drive_connections_revoked_at
ON staff_drive_connections(revoked_at);
