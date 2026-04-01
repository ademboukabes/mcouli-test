-- name: CreateProcessingJob :one
INSERT INTO processing_jobs (photo_id, job_type, status)
VALUES ($1, $2, 'pending')
RETURNING *;

-- name: UpdateProcessingJobStatus :one
UPDATE processing_jobs
SET status = $2,
    attempts = attempts + 1,
    completed_at = CASE WHEN $2 IN ('completed', 'failed') THEN now() ELSE completed_at END
WHERE id = $1
RETURNING *;

-- name: GetProcessingJobByPhotoId :one
SELECT * FROM processing_jobs
WHERE photo_id = $1
ORDER BY created_at DESC
LIMIT 1;
