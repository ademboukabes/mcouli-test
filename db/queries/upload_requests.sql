-- name: CreateUploadRequest :one
INSERT INTO upload_requests (
    event_id,
    group_id,
    drive_file_id,
    requested_by,
    photo_count
) VALUES (
    $1, $2, $3, $4, $5
)
RETURNING *;

-- name: GetUploadRequestById :one
SELECT *
FROM upload_requests
WHERE id = $1;

-- name: ListUploadRequestsByGroupId :many
SELECT *
FROM upload_requests
WHERE group_id = $1
ORDER BY created_at ASC;

-- name: ListUploadRequests :many
SELECT *
FROM upload_requests
ORDER BY created_at DESC;

-- name: ListUploadRequestsByStatus :many
SELECT *
FROM upload_requests
WHERE status = $1
ORDER BY created_at DESC;

-- name: ListUploadRequestsByRequester :many
SELECT *
FROM upload_requests
WHERE requested_by = $1
ORDER BY created_at DESC;

-- name: ListUploadRequestsByRequesterAndStatus :many
SELECT *
FROM upload_requests
WHERE requested_by = $1
  AND status = $2
ORDER BY created_at DESC;

-- name: ApproveUploadRequest :one
UPDATE upload_requests
SET status = 'approved',
    approved_by = $2,
    approved_at = NOW(),
    rejection_reason = NULL
WHERE id = $1
  AND status = 'pending'
RETURNING *;

-- name: RejectUploadRequest :one
UPDATE upload_requests
SET status = 'rejected',
    approved_by = $2,
    approved_at = NOW(),
    rejection_reason = $3
WHERE id = $1
  AND status = 'pending'
RETURNING *;

-- name: DeleteUploadRequest :exec
DELETE FROM upload_requests
WHERE id = $1;
