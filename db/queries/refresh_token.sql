-- name: create_refresh_token :one
INSERT INTO refresh_tokens (
    session_id,
    family_id,
    token_hash
) VALUES (
    $1, $2, $3
)
RETURNING *;

-- name: get_refresh_token_by_hash :one
SELECT *
FROM refresh_tokens
WHERE token_hash = $1;

-- name: mark_refresh_token_used :one
UPDATE refresh_tokens
SET used = TRUE, used_at = NOW()
WHERE id = $1 AND used = FALSE
RETURNING *;

-- name: get_refresh_token_by_hash_for_update :one
SELECT id, session_id, family_id, token_hash, used, created_at, used_at
FROM refresh_tokens
WHERE token_hash = $1
FOR UPDATE;