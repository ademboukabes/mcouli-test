-- name: CreateAuditEvent :one
INSERT INTO audit_events (
    event_type,
    user_id,
    metadata
) VALUES (
    $1, $2, $3
)
RETURNING id, event_type, user_id, metadata, created_at;
