DROP INDEX IF EXISTS idx_upload_requests_group_id;

ALTER TABLE upload_requests
    DROP COLUMN IF EXISTS group_id;

DROP INDEX IF EXISTS idx_upload_request_groups_status;
DROP INDEX IF EXISTS idx_upload_request_groups_requested_by;
DROP INDEX IF EXISTS idx_upload_request_groups_event_id;

DROP TABLE IF EXISTS upload_request_groups;
