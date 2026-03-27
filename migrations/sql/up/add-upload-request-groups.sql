CREATE TABLE IF NOT EXISTS upload_request_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    folder_id TEXT NOT NULL,
    requested_by UUID NOT NULL REFERENCES staff_users(id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES staff_users(id) ON DELETE SET NULL,
    status upload_request_status NOT NULL DEFAULT 'pending',
    total_photo_count INT NOT NULL DEFAULT 0,
    batch_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_upload_request_groups_event_id
ON upload_request_groups(event_id);

CREATE INDEX IF NOT EXISTS idx_upload_request_groups_requested_by
ON upload_request_groups(requested_by);

CREATE INDEX IF NOT EXISTS idx_upload_request_groups_status
ON upload_request_groups(status);

ALTER TABLE upload_requests
    ADD COLUMN IF NOT EXISTS group_id UUID REFERENCES upload_request_groups(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_upload_requests_group_id
ON upload_requests(group_id);
