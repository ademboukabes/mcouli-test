-- name: CreateEvent :one
INSERT INTO events (name, event_code, event_date, status, created_by)
VALUES ($1, $2, $3, $4, $5)
RETURNING *;

-- name: GetEventById :one
SELECT * FROM events 
WHERE id = $1;

-- name: GetEventByCode :one
SELECT * FROM events 
WHERE event_code = $1;

-- name: GetEventsByName :many
SELECT * FROM events 
WHERE name ILIKE '%' || $1 || '%'
ORDER BY event_date DESC;

-- name: GetEventsByStatus :many
SELECT * FROM events 
WHERE status = $1
ORDER BY event_date DESC;

-- name: GetEventsByDateRange :many
SELECT * FROM events 
WHERE event_date >= sqlc.arg('start_date') 
AND event_date <= sqlc.arg('end_date')
ORDER BY event_date ASC;

-- name: ListEvents :many
SELECT * FROM events 
ORDER BY event_date DESC 
LIMIT $1 OFFSET $2;

-- name: UpdateEventStatus :one
UPDATE events 
SET status = $2, 
    archived_at = CASE WHEN $2 = 'archived'::event_status THEN NOW() ELSE archived_at END
WHERE id = $1
RETURNING *;

-- name: DeleteEvent :exec
DELETE FROM events 
WHERE id = $1;