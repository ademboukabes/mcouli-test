ALTER TABLE upload_request_groups
    ADD COLUMN source character varying(16) DEFAULT 'drive'::character varying NOT NULL,
    ALTER COLUMN folder_id DROP NOT NULL;

ALTER TABLE upload_requests
    ADD COLUMN source character varying(16) DEFAULT 'drive'::character varying NOT NULL;

ALTER TABLE upload_request_photos
    ADD COLUMN source character varying(16) DEFAULT 'drive'::character varying NOT NULL,
    ADD COLUMN transfer_status character varying(16) DEFAULT 'uploaded'::character varying NOT NULL,
    ALTER COLUMN drive_file_id DROP NOT NULL;
