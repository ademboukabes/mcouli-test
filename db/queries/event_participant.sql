-- name: JoinEvent :one
-- Records when a user scans a QR code to join an event
INSERT INTO event_participants (event_id, user_id)
VALUES ($1, $2)
RETURNING *;

-- name: GetUserEvents :many
-- Retrieves all events a specific user has successfully joined
SELECT 
    e.id, 
    e.name, 
    e.event_date, 
    e.status,
    ep.joined_at
FROM events e
JOIN event_participants ep ON e.id = ep.event_id
WHERE ep.user_id = $1
ORDER BY ep.joined_at DESC;

-- name: ListUserEvents :many
SELECT 
    e.id, 
    e.name, 
    e.event_date, 
    e.status,
    ep.joined_at
FROM events e
JOIN event_participants ep ON e.id = ep.event_id
WHERE ep.user_id = $1
    -- Optional Status Filter
    AND (sqlc.narg('status')::text IS NULL OR e.status = sqlc.narg('status'))
    -- Optional Date Range Filters
    AND (sqlc.narg('start_date')::timestamptz IS NULL OR e.event_date >= sqlc.narg('start_date'))
    AND (sqlc.narg('end_date')::timestamptz IS NULL OR e.event_date <= sqlc.narg('end_date'))
ORDER BY 
    -- Sort by joined_at
    CASE WHEN sqlc.arg('sort_field')::text = 'joined_at' AND sqlc.arg('sort_desc')::boolean THEN ep.joined_at END DESC,
    CASE WHEN sqlc.arg('sort_field')::text = 'joined_at' AND NOT sqlc.arg('sort_desc')::boolean THEN ep.joined_at END ASC,
    
    -- Sort by event_date
    CASE WHEN sqlc.arg('sort_field')::text = 'event_date' AND sqlc.arg('sort_desc')::boolean THEN e.event_date END DESC,
    CASE WHEN sqlc.arg('sort_field')::text = 'event_date' AND NOT sqlc.arg('sort_desc')::boolean THEN e.event_date END ASC,
    
    -- Sort by name
    CASE WHEN sqlc.arg('sort_field')::text = 'name' AND sqlc.arg('sort_desc')::boolean THEN e.name END DESC,
    CASE WHEN sqlc.arg('sort_field')::text = 'name' AND NOT sqlc.arg('sort_desc')::boolean THEN e.name END ASC,

    -- Default fallback if no sort matches
    ep.joined_at DESC
LIMIT $2 OFFSET $3;

-- name: GetEventParticipants :many
-- Retrieves all users who joined a specific event
SELECT 
    u.id as user_id,
    u.email as user_email,
    ep.joined_at
FROM users u
JOIN event_participants ep ON u.id = ep.user_id
WHERE ep.event_id = $1
ORDER BY ep.joined_at ASC;

-- name: LeaveEvent :exec
-- Allows a user to unregister or leave an event
DELETE FROM event_participants 
WHERE event_id = $1 AND user_id = $2;

-- name: CountEventParticipants :one
-- Gets the total number of people joined for an event
SELECT COUNT(*) 
FROM event_participants 
WHERE event_id = $1;

-- name: IsUserInEvent :one
-- Checks if a specific user has already joined an event
SELECT EXISTS (
    SELECT 1 FROM event_participants 
    WHERE event_id = $1 AND user_id = $2
);