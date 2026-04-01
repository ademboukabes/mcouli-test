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
