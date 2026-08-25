ALTER TABLE photos
    ADD COLUMN source character varying(16) DEFAULT 'drive'::character varying NOT NULL,
    ADD COLUMN storage_cleaned_at timestamp with time zone;
