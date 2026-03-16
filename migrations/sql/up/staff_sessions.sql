CREATE TABLE IF NOT EXISTS staff_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_id UUID NOT NULL REFERENCES staff_users(id) ON DELETE CASCADE,
    -- For web, device_id can be a browser fingerprint or a random UUID
    device_id UUID NOT NULL, 
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE(staff_id, device_id)
);

CREATE INDEX idx_staff_sessions_staff_id ON staff_sessions(staff_id);
