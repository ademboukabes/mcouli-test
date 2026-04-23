-- name: UpsertSession :one
INSERT INTO user_sessions (
    user_id,
    device_id,
    expires_at
) VALUES (
    $1, $2, $3
)
ON CONFLICT (user_id, device_id)
DO UPDATE SET
    last_active = NOW(),
    expires_at = EXCLUDED.expires_at
RETURNING
    id,
    user_id,
    device_id,
    last_active,
    expires_at,
    created_at;

-- name: GetSessionByDevice :one
SELECT *
FROM user_sessions
WHERE device_id = $1;

-- name: GetSessionById :one
SELECT *
FROM user_sessions
WHERE id = $1;

-- name: ListSessionsByUser :many
SELECT *
FROM user_sessions
WHERE user_id = $1;

-- name: UpdateSessionActivity :exec
UPDATE user_sessions
SET last_active = NOW()
WHERE id = $1;


-- name: DeleteSessionByDevice :exec
DELETE FROM user_sessions
WHERE device_id = $1
AND user_id = $2;

-- name: DeleteAllUserSessions :exec
DELETE FROM user_sessions
WHERE user_id = $1;

-- name: DeleteExpiredSessions :exec
DELETE FROM user_sessions
WHERE expires_at < NOW();

-- name: CountUserSessions :one
SELECT COUNT(*) FROM user_sessions WHERE user_id = $1;
