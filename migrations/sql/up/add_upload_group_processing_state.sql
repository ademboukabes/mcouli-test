ALTER TABLE upload_request_groups
    ADD COLUMN IF NOT EXISTS processing_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS processed_photo_count INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS failed_photo_count INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS error_message TEXT;

ALTER TABLE upload_request_groups
    DROP CONSTRAINT IF EXISTS chk_upload_request_groups_processing_status;

ALTER TABLE upload_request_groups
    ADD CONSTRAINT chk_upload_request_groups_processing_status
    CHECK (processing_status IN ('pending', 'running', 'completed', 'failed'));
