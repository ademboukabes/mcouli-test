-- name: GetActiveEventsCount :one
SELECT COUNT(*) FROM events WHERE status = 'scheduled';

-- name: GetTotalPhotosUploaded :one
SELECT COUNT(*) FROM photos;

-- name: GetProcessingJobMetrics :one
SELECT 
    COUNT(*) FILTER (WHERE status = 'completed')::int AS completed_count,
    COUNT(*) FILTER (WHERE status = 'running')::int AS running_count,
    COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_count
FROM processing_jobs;

-- name: GetTotalStorageBytes :one
SELECT COALESCE(SUM(size_bytes), 0)::bigint FROM upload_request_photos;

-- name: GetRecentStaffAlerts :many
SELECT * FROM staff_notifications 
WHERE staff_user_id = $1 
ORDER BY created_at DESC LIMIT 10;

-- name: GetUnreadStaffAlertsCount :one
SELECT COUNT(*) FROM staff_notifications 
WHERE staff_user_id = $1 AND read_at IS NULL;
