-- name: JoinEvent :one
-- Records when a user scans a QR code to join an event
INSERT INTO join_events (event_id, user_id)
VALUES ($1, $2)
RETURNING *;

-- name: ListUserEvents :many
-- Retrieves all events a specific user has successfully joined
SELECT 
    e.id, 
    e.name, 
    e.event_date, 
    je.joined_at
FROM events e
JOIN join_events je ON e.id = je.event_id
WHERE je.user_id = $1
ORDER BY je.joined_at DESC;