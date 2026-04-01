-- name: CreatePhotoApproval :one
INSERT INTO photo_approvals (
    photo_id,
    user_id,
    decision
) VALUES (
    $1, $2, $3
)
RETURNING *;

-- name: UpdatePhotoApprovalDecision :one
UPDATE photo_approvals
SET decision = $2, decided_at = now()
WHERE photo_id = $1 AND user_id = $3
RETURNING *;

-- name: GetPhotoApprovalsByPhotoId :many
SELECT * FROM photo_approvals WHERE photo_id = $1;

-- name: ListApprovalsByUserAndStatus :many
SELECT * FROM photo_approvals
WHERE user_id = $1
  AND ($2::varchar IS NULL OR decision = $2)
ORDER BY decided_at DESC
LIMIT $3 OFFSET $4;