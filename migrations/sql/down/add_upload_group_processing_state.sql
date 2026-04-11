ALTER TABLE upload_request_groups
    DROP CONSTRAINT IF EXISTS chk_upload_request_groups_processing_status;

ALTER TABLE upload_request_groups
    DROP COLUMN IF EXISTS error_message,
    DROP COLUMN IF EXISTS failed_photo_count,
    DROP COLUMN IF EXISTS processed_photo_count,
    DROP COLUMN IF EXISTS processing_status;
