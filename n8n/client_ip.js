// Works out the caller's IP for signup rate limiting.
// Order: Cloudflare's header (if the domain is proxied) -> x-real-ip ->
// last x-forwarded-for entry (the one appended by the trusted proxy) ->
// a random value, so an unknown IP never lumps every caller into one bucket.
const h = $input.first().json.headers || {};
const first = (v) => (v || '').toString().split(',')[0].trim();
const last = (v) => (v || '').toString().split(',').pop().trim();
const ip = first(h['cf-connecting-ip']) || first(h['x-real-ip']) || last(h['x-forwarded-for'])
  || ('unknown-' + Math.random().toString(36).slice(2));
return [{ json: { ip } }];
