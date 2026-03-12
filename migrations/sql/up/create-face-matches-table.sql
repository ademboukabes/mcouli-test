CREATE TABLE IF NOT EXISTS face_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    photo_face_id UUID NOT NULL REFERENCES photo_faces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_face_matches_face_id ON face_matches(photo_face_id);
CREATE INDEX IF NOT EXISTS idx_face_matches_user_id ON face_matches(user_id);
