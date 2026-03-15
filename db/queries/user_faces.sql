-- name: CreateUserFace :one
INSERT INTO user_faces (
    user_id,
    embedding
) VALUES (
    $1, $2
)
RETURNING *;

-- name: GetUserFaceByUserId :one
SELECT *
FROM user_faces
WHERE user_id = $1;

-- name: DeleteUserFaceByUserId :exec
DELETE FROM user_faces
WHERE user_id = $1;
