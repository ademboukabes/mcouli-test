-- name: UpsertStaffDriveConnection :one
INSERT INTO staff_drive_connections (
    staff_user_id,
    provider,
    google_email,
    google_account_id,
    access_token,
    refresh_token,
    token_expires_at,
    scopes,
    connected_at,
    revoked_at,
    updated_at
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, NOW(), NULL, NOW()
)
ON CONFLICT (staff_user_id, provider)
DO UPDATE SET
    google_email = EXCLUDED.google_email,
    google_account_id = EXCLUDED.google_account_id,
    access_token = EXCLUDED.access_token,
    refresh_token = EXCLUDED.refresh_token,
    token_expires_at = EXCLUDED.token_expires_at,
    scopes = EXCLUDED.scopes,
    connected_at = NOW(),
    revoked_at = NULL,
    updated_at = NOW()
RETURNING *;

-- name: GetActiveStaffDriveConnectionByStaffUserID :one
SELECT *
FROM staff_drive_connections
WHERE staff_user_id = $1
  AND provider = $2
  AND revoked_at IS NULL;

-- name: RevokeStaffDriveConnectionByStaffUserID :exec
UPDATE staff_drive_connections
SET revoked_at = NOW(),
    updated_at = NOW()
WHERE staff_user_id = $1
  AND provider = $2
  AND revoked_at IS NULL;
