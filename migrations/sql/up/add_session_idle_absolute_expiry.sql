ALTER TABLE user_sessions
    RENAME COLUMN expires_at TO idle_expires_at;

ALTER TABLE user_sessions
    ADD COLUMN absolute_expires_at timestamp with time zone NOT NULL DEFAULT (now() + interval '30 days');

ALTER TABLE user_sessions
    ALTER COLUMN absolute_expires_at DROP DEFAULT;