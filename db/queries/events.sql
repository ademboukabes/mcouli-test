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

-- name: ListEvents :many
SELECT * FROM events 
WHERE 
    -- Filter by Status (Optional)
    (sqlc.narg('status')::event_status IS NULL OR status = sqlc.narg('status'))
    
    -- Filter by Date Range (Optional)
    AND (sqlc.narg('start_date')::timestamptz IS NULL OR event_date >= sqlc.narg('start_date'))
    AND (sqlc.narg('end_date')::timestamptz IS NULL OR event_date <= sqlc.narg('end_date'))
    
    -- Filter by Name Search (Optional - added for extra utility)
    AND (sqlc.narg('search_name')::text IS NULL OR name ILIKE '%' || sqlc.narg('search_name') || '%')

ORDER BY 
    -- Dynamic Sorting
    CASE WHEN sqlc.arg('sort_order')::text = 'date_asc' THEN event_date END ASC,
    CASE WHEN sqlc.arg('sort_order')::text = 'date_desc' THEN event_date END DESC,
    CASE WHEN sqlc.arg('sort_order')::text = 'name_asc' THEN name END ASC,
    -- Default fallback sorting
    event_date DESC

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