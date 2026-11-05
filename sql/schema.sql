-- Baalebos AI Gateway -- key store. Safe to run repeatedly (idempotent),
-- and safe to run on top of the earlier version of this table.

CREATE TABLE IF NOT EXISTS api_keys (
    id                  SERIAL PRIMARY KEY,
    api_key             TEXT UNIQUE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    daily_limit         INTEGER NOT NULL DEFAULT 50,
    daily_request_count INTEGER NOT NULL DEFAULT 0,
    last_request_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    total_request_count INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS is_team        BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS signup_ip_hash TEXT;
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS label          TEXT;

CREATE INDEX IF NOT EXISTS idx_api_keys_signup_ip ON api_keys (signup_ip_hash, created_at);
