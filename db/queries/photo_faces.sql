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

-- name: PhotoFacesPhotoExists :one
SELECT 1
FROM photos
WHERE id = $1
LIMIT 1;

-- name: PhotoFacesMatchExistsForPhoto :one
SELECT 1
FROM face_matches fm
JOIN photo_faces pf ON pf.id = fm.photo_face_id
WHERE pf.photo_id = $1
LIMIT 1;

-- name: PhotoFacesMatchExistsForPhotoFace :one
SELECT 1
FROM face_matches
WHERE photo_face_id = $1
LIMIT 1;

-- name: PhotoFacesFindClosestUser :one
SELECT id,
       (face_embedding <=> CAST($1 AS vector)) AS distance
FROM users
WHERE face_embedding IS NOT NULL
ORDER BY distance ASC
LIMIT 1;

-- name: PhotoFacesEnsureFaceMatch :one
WITH upserted_photo_face AS (
    INSERT INTO photo_faces (
        photo_id,
        face_index,
        embedding,
        bbox
    ) VALUES (
        $1,
        $2,
        CAST($3 AS vector),
        $4
    ) ON CONFLICT (photo_id, face_index)
    DO UPDATE SET embedding = EXCLUDED.embedding,
                  bbox = EXCLUDED.bbox
    RETURNING id, photo_id
),
existing_match AS (
    SELECT 1
    FROM face_matches fm
    JOIN photo_faces pf ON pf.id = fm.photo_face_id
    WHERE pf.photo_id = $1
    LIMIT 1
),
inserted_match AS (
    INSERT INTO face_matches (photo_face_id, user_id, confidence)
    SELECT upserted_photo_face.id, $5, $6
    WHERE NOT EXISTS (SELECT 1 FROM existing_match)
    RETURNING id
)
SELECT upserted_photo_face.id AS photo_face_id,
       inserted_match.id AS face_match_id
FROM upserted_photo_face
LEFT JOIN inserted_match ON TRUE;
