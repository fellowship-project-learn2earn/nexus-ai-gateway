-- $1 = client IP, $2 = max signups per IP per 24h, $3 = hash salt.
-- Generates the key inside Postgres (no JS crypto module needed in n8n),
-- and refuses to mint more than $2 keys per network per day.
-- Always returns exactly one row; api_key is NULL when the limit is hit.
WITH h AS (
  SELECT encode(sha256(convert_to($1::text || $3::text, 'UTF8')), 'hex') AS ip
),
ins AS (
  INSERT INTO api_keys (api_key, signup_ip_hash)
  SELECT replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', ''),
         h.ip
  FROM h
  WHERE (SELECT COUNT(*) FROM api_keys
         WHERE signup_ip_hash = h.ip
           AND created_at > NOW() - INTERVAL '24 hours') < $2::int
  RETURNING api_key
)
SELECT (SELECT api_key FROM ins) AS api_key;
