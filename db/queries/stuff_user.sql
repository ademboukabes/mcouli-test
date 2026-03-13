-- name: CreateAdmin :one
INSERT INTO staff_users (email, password, role)
VALUES ($1, $2, 'admin')
RETURNING *;

-- name: CreateMulti :one
INSERT INTO staff_users (email, password, role)
VALUES ($1, $2, $3)
RETURNING *;

-- name: GetStaffUserByID :one
SELECT *
FROM staff_users
WHERE id = $1;

-- name: GetStaffUserByEmail :one
SELECT *
FROM staff_users
WHERE email = $1;

-- name: GetAllStaffUsers :many
SELECT *
FROM staff_users
ORDER BY created_at DESC
LIMIT $1 OFFSET $2;

-- name: UpdateStaffUser :one
UPDATE staff_users
SET email = $2,  role = $3, updated_at = NOW()
WHERE id = $1
RETURNING *;

-- name: DeleteStaffUser :one
DELETE FROM staff_users
WHERE id = $1
RETURNING *;
