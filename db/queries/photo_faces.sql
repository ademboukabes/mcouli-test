-- name: UpsertPhotoFace :one
INSERT INTO photo_faces (
    photo_id,
    face_index,
    embedding,
    bbox
) VALUES (
    $1, $2, $3::vector, $4
)
ON CONFLICT (photo_id, face_index)
DO UPDATE SET embedding = EXCLUDED.embedding,
              bbox = EXCLUDED.bbox
RETURNING *;
