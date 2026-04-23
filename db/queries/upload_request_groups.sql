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

-- name: GetUploadRequestGroupById :one
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

-- name: StartUploadRequestGroupProcessing :one
UPDATE upload_request_groups
SET processing_status = 'running',
    error_message = NULL
WHERE id = $1
  AND processing_status = 'pending'
RETURNING *;

-- name: UpdateUploadRequestGroupImportProgress :one
UPDATE upload_request_groups
SET total_photo_count = $2,
    batch_count = $3,
    processed_photo_count = $4,
    failed_photo_count = $5
WHERE id = $1
RETURNING *;

-- name: CompleteUploadRequestGroupProcessing :one
UPDATE upload_request_groups
SET processing_status = 'completed',
    total_photo_count = $2,
    batch_count = $3,
    processed_photo_count = $4,
    failed_photo_count = $5,
    error_message = NULL
WHERE id = $1
RETURNING *;

-- name: FailUploadRequestGroupProcessing :one
UPDATE upload_request_groups
SET processing_status = 'failed',
    total_photo_count = $2,
    batch_count = $3,
    processed_photo_count = $4,
    failed_photo_count = $5,
    error_message = $6
WHERE id = $1
RETURNING *;

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
