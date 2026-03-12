DROP INDEX IF EXISTS idx_upload_requests_status;
DROP INDEX IF EXISTS idx_upload_requests_requested_by;
DROP INDEX IF EXISTS idx_upload_requests_event_id;

DROP TABLE IF EXISTS upload_requests;
DROP TYPE IF EXISTS upload_request_status;
