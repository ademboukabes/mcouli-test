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
