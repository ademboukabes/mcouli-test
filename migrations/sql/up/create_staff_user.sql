CREATE TYPE staff_role AS ENUM ('admin','multi_team_lead', 'multi');

CREATE TABLE IF NOT EXISTS staff_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discord_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    role staff_role NOT NULL DEFAULT 'admin', 
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_staff_users_discord_id ON staff_users(discord_id);

