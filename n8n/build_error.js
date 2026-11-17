// Runs when a database-backed key was refused. The quota query returns one
// row: allowed (0/1) and known (does the key exist at all).
//   unknown key  -> 401
//   known key    -> 429 (its own daily limit, or the global public cap)
const r = $input.first().json;
const known = r.known === true || r.known === 't' || r.known === 'true';
return [{ json: known
  ? { error: 'rate_limited', message: 'daily request limit reached; it resets at 00:00 UTC', statusCode: 429 }
  : { error: 'unauthorized', message: 'missing or invalid x-api-key header', statusCode: 401 } }];
