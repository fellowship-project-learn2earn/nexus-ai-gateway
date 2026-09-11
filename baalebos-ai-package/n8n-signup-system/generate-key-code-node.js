// Code node: "Generate Key" -- place after the Webhook trigger in the
// signup workflow, before the Postgres Insert node.
//
// Uses Node's built-in crypto module (no external package needed --
// this avoids the N8N_FUNCTION_ALLOW_EXTERNAL requirement that a
// database driver like `pg` would need, since n8n's native Postgres
// node handles the DB connection separately from this Code node).

const crypto = require('crypto');

const newKey = crypto.randomBytes(32).toString('hex');

return [{ json: { api_key: newKey } }];
