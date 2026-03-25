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
WHERE ($1 IS NULL OR event_type = $1)
  AND ($2 IS NULL OR user_id = $2)
  AND ($3 IS NULL OR created_at >= $3)
  AND ($4 IS NULL OR created_at <= $4)
ORDER BY created_at DESC
LIMIT $5
OFFSET $6;
