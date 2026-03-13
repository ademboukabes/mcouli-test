-- name: CreateDevice :one
INSERT INTO user_devices (
    id,
    user_id,
    device_name,
    device_type,
    totp_secret
) VALUES (
    COALESCE($1, uuid_generate_v4()), $2, $3, $4, $5
)
RETURNING *;

-- name: ListUserDevices :many
SELECT *
FROM user_devices
WHERE user_id = $1
ORDER BY last_active DESC;

-- name: UpdateDeviceLastActive :exec
UPDATE user_devices
SET last_active = NOW()
WHERE id = $1;


-- name: RevokeDevice :exec
DELETE FROM user_devices
WHERE id = $1
AND user_id = $2;

-- name: EnableDevice2FA :exec
UPDATE user_devices
SET is_2fa_enabled = TRUE
WHERE id = $1
AND user_id = $2
AND is_2fa_enabled = FALSE;

-- name: Get_device_By_id :one
SELECT * from user_devices
WHERE id =$1;

-- name: Count_User_Devices :one
SELECT COUNT(*) 
FROM user_devices
WHERE user_id = $1;
