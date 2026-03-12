CREATE TABLE IF NOT EXISTS photo_approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    photo_id UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision VARCHAR(32) NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_photo_approvals_photo_id ON photo_approvals(photo_id);
CREATE INDEX IF NOT EXISTS idx_photo_approvals_user_id ON photo_approvals(user_id);
