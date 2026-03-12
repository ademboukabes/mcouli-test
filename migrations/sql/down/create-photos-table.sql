DROP INDEX IF EXISTS idx_photos_status;
DROP INDEX IF EXISTS idx_photos_uploaded_by;
DROP INDEX IF EXISTS idx_photos_event_id;

DROP TABLE IF EXISTS photos;
DROP TYPE IF EXISTS photo_status;
