-- n8n Postgres node query, placed after "Check Rate Limit" on its
-- TRUE/valid branch. Use n8n's expression syntax to fill in the values
-- from the previous Code node's output.

UPDATE api_keys
SET
  daily_request_count = {{ $json.newDailyCount }},
  last_request_date = CURRENT_DATE,
  total_request_count = total_request_count + 1
WHERE api_key = '{{ $json.api_key }}';
