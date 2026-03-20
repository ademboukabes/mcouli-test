-- name: CreateNotification :one
INSERT INTO notifications (
    user_id,
    type,
    payload
) VALUES (
    $1, $2, $3
)
RETURNING id, user_id, type, payload, read_at, created_at;

-- name: ListNotificationsByUserID :many
SELECT id, user_id, type, payload, read_at, created_at
FROM notifications
WHERE user_id = $1
ORDER BY created_at DESC;

-- name: MarkNotificationAsRead :one
UPDATE notifications
SET read_at = NOW()
WHERE id = $1
  AND user_id = $2
  AND read_at IS NULL
RETURNING id, user_id, type, payload, read_at, created_at;
