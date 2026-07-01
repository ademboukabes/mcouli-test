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

-- name: ExpireStaleApprovals :many
WITH stale_photos AS (
SELECT id FROM photos
WHERE status = 'pending'
AND created_at < now() - make_interval(days => sqlc.arg('timeout_days')::int)
),
_update_approvals AS (
UPDATE photo_approvals
SET decision = 'approved', decided_at = now()
WHERE photo_id IN (SELECT id FROM stale_photos)
AND decision = 'pending'
)
UPDATE photos
SET status = 'approved'
WHERE id IN (SELECT id FROM stale_photos)
RETURNING id;

-- name: ListApprovalsByUserAndStatus :many
SELECT * FROM photo_approvals
WHERE user_id = $1
  AND (sqlc.narg('status')::varchar IS NULL OR decision = sqlc.narg('status'))
ORDER BY decided_at DESC
LIMIT $2 OFFSET $3;
