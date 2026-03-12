CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    qr_code_hash VARCHAR(64) NOT NULL UNIQUE, 
    event_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_qr_code_hash ON events(qr_code_hash);
CREATE INDEX idx_events_event_date ON events(event_date DESC);