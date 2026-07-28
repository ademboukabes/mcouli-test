ALTER TABLE user_devices
    ADD COLUMN physical_device_id UUID;

UPDATE user_devices SET physical_device_id = id WHERE physical_device_id IS NULL;

ALTER TABLE user_devices
    ALTER COLUMN physical_device_id SET NOT NULL;

CREATE UNIQUE INDEX idx_user_devices_user_physical
    ON user_devices (user_id, physical_device_id);