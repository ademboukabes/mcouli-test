ALTER TABLE user_sessions
    DROP COLUMN absolute_expires_at;

ALTER TABLE user_sessions
    RENAME COLUMN idle_expires_at TO expires_at;