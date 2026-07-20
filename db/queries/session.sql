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

-- name: GetSessionByDeviceForUser :one
SELECT *
FROM user_sessions
WHERE device_id = $1 AND user_id = $2;

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

-- name: DeleteSessionById :exec
DELETE FROM user_sessions
WHERE id = $1 AND user_id = $2;

-- name: DeleteAllUserSessions :exec
DELETE FROM user_sessions
WHERE user_id = $1;

-- name: DeleteExpiredSessions :exec
DELETE FROM user_sessions
WHERE expires_at < NOW();

-- name: CountUserSessions :one
SELECT COUNT(*) FROM user_sessions WHERE user_id = $1;

-- name: lock_user_sessions :exec
SELECT pg_advisory_xact_lock(hashtext(sqlc.arg(user_id)::text)::bigint);

-- name: evict_overflow_sessions :many
WITH overflow AS (
    SELECT GREATEST(0, COUNT(*) - sqlc.arg(session_limit)) AS n
    FROM user_sessions AS count_s
    WHERE count_s.user_id = sqlc.arg(user_id)
)
DELETE FROM user_sessions AS outer_s
WHERE outer_s.id IN (
    SELECT inner_s.id
    FROM user_sessions AS inner_s
    WHERE inner_s.user_id = sqlc.arg(user_id) AND inner_s.id != sqlc.arg(id)
    ORDER BY inner_s.last_active ASC, inner_s.created_at ASC
    LIMIT (SELECT n FROM overflow)
    FOR UPDATE SKIP LOCKED
)
RETURNING outer_s.id;