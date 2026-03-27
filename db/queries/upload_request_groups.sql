-- name: CreateUploadRequestGroup :one
INSERT INTO upload_request_groups (
    event_id,
    folder_id,
    requested_by,
    total_photo_count,
    batch_count
) VALUES (
    $1, $2, $3, $4, $5
)
RETURNING *;

-- name: GetUploadRequestGroupByID :one
SELECT *
FROM upload_request_groups
WHERE id = $1;

-- name: ListUploadRequestGroups :many
SELECT *
FROM upload_request_groups
ORDER BY created_at DESC;

-- name: ListUploadRequestGroupsByStatus :many
SELECT *
FROM upload_request_groups
WHERE status = $1
ORDER BY created_at DESC;

-- name: ListUploadRequestGroupsByRequester :many
SELECT *
FROM upload_request_groups
WHERE requested_by = $1
ORDER BY created_at DESC;

-- name: ListUploadRequestGroupsByRequesterAndStatus :many
SELECT *
FROM upload_request_groups
WHERE requested_by = $1
  AND status = $2
ORDER BY created_at DESC;

-- name: ApproveUploadRequestGroup :one
UPDATE upload_request_groups
SET status = 'approved',
    approved_by = $2,
    approved_at = NOW(),
    rejection_reason = NULL
WHERE id = $1
  AND status = 'pending'
RETURNING *;

-- name: RejectUploadRequestGroup :one
UPDATE upload_request_groups
SET status = 'rejected',
    approved_by = $2,
    approved_at = NOW(),
    rejection_reason = $3
WHERE id = $1
  AND status = 'pending'
RETURNING *;

-- name: DeleteUploadRequestGroup :exec
DELETE FROM upload_request_groups
WHERE id = $1;
