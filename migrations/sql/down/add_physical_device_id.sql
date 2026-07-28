DROP INDEX IF EXISTS idx_user_devices_user_physical;

ALTER TABLE user_devices
    DROP COLUMN IF EXISTS physical_device_id;