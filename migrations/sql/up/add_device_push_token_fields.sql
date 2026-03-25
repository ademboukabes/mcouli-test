ALTER TABLE user_devices
    ADD COLUMN push_token TEXT,
    ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL,
    ADD COLUMN is_invalid_token BOOLEAN DEFAULT FALSE NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_devices_push_token ON user_devices (push_token) WHERE push_token IS NOT NULL;
