// Code node: "Check Rate Limit" -- place after a Postgres node that
// looks up the presented x-api-key (SELECT * FROM api_keys WHERE
// api_key = {{ $json.headers['x-api-key'] }}).
//
// This node decides: valid & under limit -> proceed; invalid -> 401;
// over limit -> 429. It also computes whether today's counter needs
// resetting (new day since last request).

const lookupResult = $input.first().json;

// Postgres node returns no rows (empty result) if the key doesn't exist
// at all -- n8n represents "no match" as either an empty item or a
// specific shape depending on node version, so check defensively.
const keyRecord = lookupResult && lookupResult.id ? lookupResult : null;

if (!keyRecord) {
  return [{
    json: {
      valid: false,
      statusCode: 401,
      error: 'invalid or unregistered api key',
    },
  }];
}

const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
const lastRequestDate = keyRecord.last_request_date
  ? new Date(keyRecord.last_request_date).toISOString().slice(0, 10)
  : null;

const isNewDay = lastRequestDate !== today;
const currentCount = isNewDay ? 0 : keyRecord.daily_request_count;

if (currentCount >= keyRecord.daily_limit) {
  return [{
    json: {
      valid: false,
      statusCode: 429,
      error: `daily limit of ${keyRecord.daily_limit} requests reached, resets tomorrow`,
    },
  }];
}

return [{
  json: {
    valid: true,
    api_key: keyRecord.api_key,
    newDailyCount: currentCount + 1,
    isNewDay,
  },
}];
