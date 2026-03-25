DROP INDEX IF EXISTS idx_user_devices_push_token;

ALTER TABLE user_devices
    DROP COLUMN IF EXISTS is_invalid_token,
    DROP COLUMN IF EXISTS is_active,
    DROP COLUMN IF EXISTS push_token;
