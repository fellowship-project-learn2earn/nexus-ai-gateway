-- $1 = presented x-api-key, $2 = global daily cap for non-team keys.
-- One atomic statement: validates the key, enforces the per-key and
-- global daily limits, and increments the counters. Always returns
-- exactly one row: allowed (0/1) and known (does the key exist at all,
-- used to tell 401 from 429).
WITH usage AS (
  SELECT COALESCE(SUM(daily_request_count), 0) AS used
  FROM api_keys
  WHERE last_request_date = CURRENT_DATE AND is_team = FALSE
),
bumped AS (
  UPDATE api_keys k
  SET daily_request_count = CASE WHEN k.last_request_date = CURRENT_DATE
                                 THEN k.daily_request_count + 1 ELSE 1 END,
      last_request_date   = CURRENT_DATE,
      total_request_count = k.total_request_count + 1
  FROM usage u
  WHERE k.api_key = $1
    AND (k.is_team OR u.used < $2)
    AND (k.last_request_date < CURRENT_DATE OR k.daily_request_count < k.daily_limit)
  RETURNING k.id
)
SELECT
  (SELECT COUNT(*) FROM bumped)::int AS allowed,
  EXISTS (SELECT 1 FROM api_keys WHERE api_key = $1) AS known;
