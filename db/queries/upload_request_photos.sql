-- name: CreateUploadRequestPhoto :one
INSERT INTO upload_request_photos (
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    taken_at,
    day_number,
    visibility,
    status
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
)
RETURNING *;

-- name: ListUploadRequestPhotosByUploadRequestId :many
SELECT *
FROM upload_request_photos
WHERE upload_request_id = $1
ORDER BY created_at ASC;

-- name: ListUploadRequestPhotosByUploadRequestIds :many
SELECT *
FROM upload_request_photos
WHERE upload_request_id = ANY($1::uuid[])
ORDER BY created_at ASC;

-- name: GetUploadRequestPhotoById :one
SELECT *
FROM upload_request_photos
WHERE id = $1;

-- name: UpdateUploadRequestPhotoApproval :one
UPDATE upload_request_photos
SET status = $2,
    final_storage_key = $3
WHERE id = $1
RETURNING *;

-- name: UpdateUploadRequestPhotoStatusByUploadRequestId :many
UPDATE upload_request_photos
SET status = $2
WHERE upload_request_id = $1
RETURNING *;

-- name: DeleteUploadRequestPhotosByUploadRequestId :exec
DELETE FROM upload_request_photos
WHERE upload_request_id = $1;

-- name: CreateDirectUploadRequestPhoto :one
INSERT INTO upload_request_photos (
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    source,
    transfer_status
) VALUES (
    $1, NULL, $2, $3, $4, $5, $6, $7, $8, 'staged', 'direct', 'pending_upload'
)
RETURNING *;

-- name: ConfirmUploadRequestPhotoTransfer :one
UPDATE upload_request_photos
SET transfer_status = 'uploaded',
    size_bytes = $2,
    mime_type = $3
WHERE id = $1
  AND transfer_status IN ('pending_upload', 'failed')
RETURNING *;

-- name: FailUploadRequestPhotoTransfer :one
UPDATE upload_request_photos
SET transfer_status = 'failed'
WHERE id = $1
  AND transfer_status IN ('pending_upload', 'failed')
RETURNING *;

-- name: ResetUploadRequestPhotoTransferToPending :one
UPDATE upload_request_photos
SET transfer_status = 'pending_upload'
WHERE id = $1
  AND transfer_status IN ('pending_upload', 'failed')
RETURNING *;

-- name: ListStalePendingTransferPhotos :many
SELECT *
FROM upload_request_photos
WHERE source = 'direct'
  AND transfer_status = 'pending_upload'
  AND created_at <= NOW() - ($1 || ' minutes')::interval
ORDER BY created_at ASC
LIMIT 500;
