CREATE TABLE IF NOT EXISTS join_events (
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, user_id)
);

-- Index for performance when checking a user's history
CREATE INDEX IF NOT EXISTS idx_join_events_user_id ON join_events(user_id);