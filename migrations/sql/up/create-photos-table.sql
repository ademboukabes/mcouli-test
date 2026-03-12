CREATE TYPE photo_status AS ENUM ('pending', 'approved', 'rejected');

CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    storage_key TEXT NOT NULL,
    taken_at TIMESTAMPTZ,
    day_number INT,
    visibility VARCHAR(32) NOT NULL DEFAULT 'private',
    status photo_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_photos_event_id ON photos(event_id);
CREATE INDEX IF NOT EXISTS idx_photos_uploaded_by ON photos(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
