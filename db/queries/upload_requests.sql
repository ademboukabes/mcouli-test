-- name: CreateUploadRequest :one
INSERT INTO upload_requests (
    event_id,
    drive_file_id,
    requested_by,
    photo_count
) VALUES (
    $1, $2, $3, $4
)
RETURNING *;

-- name: GetUploadRequestByID :one
SELECT *
FROM upload_requests
WHERE id = $1;

-- name: ListUploadRequests :many
SELECT *
FROM upload_requests
WHERE ($1::uuid IS NULL OR requested_by = $1)
  AND ($2::upload_request_status IS NULL OR status = $2)
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
