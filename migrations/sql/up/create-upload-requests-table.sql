CREATE TYPE upload_request_status AS ENUM ('pending', 'approved', 'rejected');

CREATE TABLE IF NOT EXISTS upload_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    drive_file_id TEXT NOT NULL,
    requested_by UUID NOT NULL REFERENCES staff_users(id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES staff_users(id) ON DELETE SET NULL,
    status upload_request_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_upload_requests_event_id ON upload_requests(event_id);
CREATE INDEX IF NOT EXISTS idx_upload_requests_requested_by ON upload_requests(requested_by);
CREATE INDEX IF NOT EXISTS idx_upload_requests_status ON upload_requests(status);
