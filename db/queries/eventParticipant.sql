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