-- name: CreateEvent :one
INSERT INTO events (name, qr_code_hash, event_date)
VALUES ($1, $2, $3)
RETURNING *;

-- name: GetEventById :one
SELECT * FROM events 
WHERE id = $1;

-- name: GetEventByHash :one
SELECT * FROM events 
WHERE qr_code_hash = $1;

-- name: ListEvents :many
SELECT * FROM events 
ORDER BY event_date DESC 
LIMIT $1 OFFSET $2;

-- name: DeleteEvent :exec
DELETE FROM events 
WHERE id = $1;