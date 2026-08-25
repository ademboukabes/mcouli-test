ALTER TABLE upload_request_photos
    ALTER COLUMN drive_file_id SET NOT NULL,
    DROP COLUMN transfer_status,
    DROP COLUMN source;

ALTER TABLE upload_requests
    DROP COLUMN source;

ALTER TABLE upload_request_groups
    ALTER COLUMN folder_id SET NOT NULL,
    DROP COLUMN source;
