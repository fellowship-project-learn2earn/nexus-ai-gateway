-- Run this once against your Railway Postgres database before wiring
-- up the signup/rate-limiting workflows.

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    api_key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    daily_limit INTEGER NOT NULL DEFAULT 50,
    daily_request_count INTEGER NOT NULL DEFAULT 0,
    last_request_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_request_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys (api_key);

-- One-time: preserve your existing team key with a much higher limit,
-- so current team members aren't affected by the new rate limiting.
-- Replace 'your-existing-gateway-api-key' with the real value.
INSERT INTO api_keys (api_key, daily_limit)
VALUES ('your-existing-gateway-api-key', 100000)
ON CONFLICT (api_key) DO NOTHING;
