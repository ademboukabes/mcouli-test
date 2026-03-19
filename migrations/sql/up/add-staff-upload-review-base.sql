CREATE TABLE IF NOT EXISTS staff_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_user_id UUID NOT NULL REFERENCES staff_users(id) ON DELETE CASCADE,
    type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staff_notifications_staff_user_id
ON staff_notifications(staff_user_id);

CREATE INDEX IF NOT EXISTS idx_staff_notifications_read_at
ON staff_notifications(read_at);

ALTER TABLE upload_requests
    ALTER COLUMN drive_file_id DROP NOT NULL;

ALTER TABLE upload_requests
    ADD COLUMN IF NOT EXISTS photo_count INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

CREATE TABLE IF NOT EXISTS upload_request_photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_request_id UUID NOT NULL REFERENCES upload_requests(id) ON DELETE CASCADE,
    drive_file_id TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL DEFAULT 'unknown',
    mime_type VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    staging_storage_key TEXT NOT NULL,
    final_storage_key TEXT,
    taken_at TIMESTAMPTZ,
    day_number INT,
    visibility VARCHAR(32) NOT NULL DEFAULT 'private',
    status VARCHAR(32) NOT NULL DEFAULT 'staged',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(upload_request_id, drive_file_id)
);

CREATE INDEX IF NOT EXISTS idx_upload_request_photos_upload_request_id
ON upload_request_photos(upload_request_id);

CREATE INDEX IF NOT EXISTS idx_upload_request_photos_status
ON upload_request_photos(status);
