ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS display_name character varying(255) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS face_embedding vector(512) DEFAULT NULL, 
    ADD COLUMN IF NOT EXISTS deleted_at timestamp with time zone DEFAULT NULL;