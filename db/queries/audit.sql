-- name: CreateAuditEvent :one
INSERT INTO audit_events (
    event_type,
    user_id,
    metadata
) VALUES (
    $1, $2, $3
)
RETURNING id, event_type, user_id, metadata, created_at;

-- name: ListAuditEvents :many
SELECT id, event_type, user_id, metadata, created_at
FROM audit_events
WHERE event_type = COALESCE($1, event_type)
  AND user_id = COALESCE($2, user_id)
  AND created_at >= COALESCE($3, created_at)
  AND created_at <= COALESCE($4, created_at)
ORDER BY created_at DESC
LIMIT $5
OFFSET $6;
