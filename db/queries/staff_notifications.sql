-- name: CreateStaffNotification :one
INSERT INTO staff_notifications (
    staff_user_id,
    type,
    payload
) VALUES (
    $1, $2, $3
)
RETURNING *;

-- name: ListStaffNotificationsByStaffUserID :many
SELECT *
FROM staff_notifications
WHERE staff_user_id = $1
ORDER BY created_at DESC;

-- name: MarkStaffNotificationAsRead :one
UPDATE staff_notifications
SET read_at = NOW()
WHERE id = $1
  AND staff_user_id = $2
  AND read_at IS NULL
RETURNING *;
