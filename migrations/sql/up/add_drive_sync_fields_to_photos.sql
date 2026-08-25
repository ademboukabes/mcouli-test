ALTER TABLE photos
    ADD COLUMN drive_file_id text,
    ADD COLUMN drive_synced_at timestamp with time zone;
