-- name: CreateAdmin :one
INSERT INTO staff_users (email, password, role)
VALUES ($1, $2, 'admin')
RETURNING *;

-- name: CreateMulti :one
INSERT INTO staff_users (email, password, role)
VALUES ($1, $2, $3)
RETURNING *;

-- name: GetStaffUserById :one
SELECT *
FROM staff_users
WHERE id = $1;

-- name: GetStaffUserByEmail :one
SELECT *
FROM staff_users
WHERE email = $1;

-- name: ListStaffUsers :many
SELECT *
FROM staff_users
WHERE (COALESCE($1, '') = '' OR email ILIKE '%' || $1 || '%')
  AND (COALESCE($2, '') = '' OR role::text = $2)
ORDER BY
  CASE WHEN $3 = 'email' AND $4 = 'asc' THEN email END ASC,
  CASE WHEN $3 = 'created_at' AND $4 = 'asc' THEN created_at END ASC,
  CASE WHEN $3 = 'email' AND $4 = 'desc' THEN email END DESC,
  CASE WHEN $3 = 'created_at' AND $4 = 'desc' THEN created_at END DESC,
  created_at DESC
LIMIT $5 OFFSET $6;

-- name: UpdateStaffUser :one
UPDATE staff_users
SET email = $2,  role = $3, updated_at = NOW()
WHERE id = $1
RETURNING *;

-- name: DeleteStaffUser :one
DELETE FROM staff_users
WHERE id = $1
RETURNING *;
