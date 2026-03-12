CREATE TYPE event_status AS ENUM ('draft', 'scheduled', 'archived');

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    event_code VARCHAR(64) NOT NULL UNIQUE,
    event_date TIMESTAMPTZ NOT NULL,
    status event_status NOT NULL DEFAULT 'draft',
    created_by UUID NOT NULL REFERENCES staff_users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_events_created_by ON events(created_by);
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
