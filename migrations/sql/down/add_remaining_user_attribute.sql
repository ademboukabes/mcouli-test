ALTER TABLE users 
    DROP COLUMN IF EXISTS display_name,
    DROP COLUMN IF EXISTS face_embedding,
    DROP COLUMN IF EXISTS deleted_at;