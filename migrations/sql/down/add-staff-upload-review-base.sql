DROP TABLE IF EXISTS upload_request_photos;

ALTER TABLE upload_requests
    DROP COLUMN IF EXISTS rejection_reason,
    DROP COLUMN IF EXISTS photo_count;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM upload_requests
        WHERE drive_file_id IS NULL
    ) THEN
        ALTER TABLE upload_requests
            ALTER COLUMN drive_file_id SET NOT NULL;
    END IF;
END $$;

DROP TABLE IF EXISTS staff_notifications;
