-- name: CreatePhoto :one
INSERT INTO photos (
    event_id,
    storage_key,
    taken_at,
    day_number,
    visibility
) VALUES (
    $1, $2, $3, $4, $5
)
RETURNING *;

-- name: GetPhotoById :one
SELECT * FROM photos WHERE id = $1;

-- name: UpdatePhotoStatus :one
UPDATE photos
SET status = $2
WHERE id = $1
RETURNING *;

-- name: ListUserPhotos :many
SELECT DISTINCT p.*
FROM photos p
LEFT JOIN photo_faces pf ON pf.photo_id = p.id
LEFT JOIN face_matches fm ON fm.photo_face_id = pf.id AND fm.user_id = $1
LEFT JOIN photo_approvals pa ON pa.photo_id = p.id AND pa.user_id = $1
WHERE (fm.user_id = $1 OR pa.user_id = $1)
  AND ($2::uuid IS NULL OR p.event_id = $2)
ORDER BY
  CASE WHEN $3 = 'asc' THEN p.created_at END ASC,
  CASE WHEN $3 != 'asc' THEN p.created_at END DESC
LIMIT $4 OFFSET $5;

-- name: ListEventPhotosForUser :many
SELECT DISTINCT p.*
FROM photos p
LEFT JOIN photo_faces pf ON pf.photo_id = p.id
LEFT JOIN face_matches fm ON fm.photo_face_id = pf.id AND fm.user_id = $1
LEFT JOIN photo_approvals pa ON pa.photo_id = p.id AND pa.user_id = $1
WHERE p.event_id = $2
  AND p.status = 'approved'
  AND (p.visibility = 'public' OR fm.user_id = $1 OR pa.user_id = $1)
ORDER BY
  CASE WHEN $3 = 'asc' THEN p.created_at END ASC,
  CASE WHEN $3 != 'asc' THEN p.created_at END DESC
LIMIT $4 OFFSET $5;

-- name: GetDriveFileIdForPhoto :one
SELECT urp.drive_file_id
FROM upload_request_photos urp
WHERE urp.final_storage_key = $1
LIMIT 1;
