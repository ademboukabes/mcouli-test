-- name: UpsertStaffSession :one
INSERT INTO staff_sessions (
    staff_id,
    device_id,
    expires_at
) VALUES (
    $1, $2, $3
)
ON CONFLICT (staff_id, device_id)
DO UPDATE SET
    last_active = NOW(),
    expires_at = EXCLUDED.expires_at
RETURNING
    id,
    staff_id,
    device_id,
    last_active,
    expires_at,
    created_at;

-- name: GetStaffSessionByDevice :one
SELECT *
FROM staff_sessions
WHERE device_id = $1;

-- name: GetStaffSessionByID :one
SELECT *
FROM staff_sessions
WHERE id = $1;

-- name: UpdateStaffSessionActivity :exec
UPDATE staff_sessions
SET last_active = NOW()
WHERE id = $1;

-- name: DeleteStaffSessionByDevice :exec
DELETE FROM staff_sessions
WHERE device_id = $1
AND staff_id = $2;

-- name: DeleteAllStaffSessions :exec
DELETE FROM staff_sessions
WHERE staff_id = $1;

-- name: DeleteExpiredStaffSessions :exec
DELETE FROM staff_sessions
WHERE expires_at < NOW();

-- name: CountStaffSessions :one
SELECT COUNT(*) FROM staff_sessions WHERE staff_id = $1;