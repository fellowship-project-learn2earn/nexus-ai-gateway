// Baalebos AI Gateway engine -- n8n Code node ("Run Once for All Items").
// Reads the ORIGINAL request from the Webhook node, so it behaves the same
// whichever branch (master key / database key) let the request through.

const MAX_MESSAGE_CHARS = 8000;
const PROVIDER_TIMEOUT_MS = 20000;
// Overall budget for the whole cascade. Nine providers x 20s would outlast
// the proxy in front of n8n and turn into an opaque 502 -- stop trying new
// providers once this is spent and return a clean error instead.
const DEADLINE_MS = Number($env.GATEWAY_DEADLINE_MS) || 60000;

const request = $('Webhook').first().json;
const headers = request.headers || {};
const body = request.body || {};
const message = body.message;
const mode = String(body.mode || 'auto').toLowerCase();
const requestedModel = body.model;
const requestedModels = body.models;
// Optional sampling temperature. Clamped to 0-1, the range every provider here accepts (Cohere rejects
// more); anything that isn't a finite number is ignored and the provider's own default applies.
const temperature = typeof body.temperature === 'number' && Number.isFinite(body.temperature)
  ? Math.min(Math.max(body.temperature, 0), 1)
  : undefined;

// Admin = holder of the master key. Admins can ask for raw provider errors
// (debug: true); everyone else only ever sees ok/fail per provider.
const isAdmin = !!$env.GATEWAY_API_KEY && headers['x-api-key'] === $env.GATEWAY_API_KEY;
const wantDebug = isAdmin && body.debug === true;

if (typeof message !== 'string' || !message.trim()) {
  return [{ json: { error: 'bad_request', message: 'message (non-empty string) is required', statusCode: 400 } }];
}
if (message.length > MAX_MESSAGE_CHARS) {
  return [{ json: { error: 'message_too_long', message: `message must be at most ${MAX_MESSAGE_CHARS} characters`, statusCode: 413 } }];
}

// ---------------------------------------------------------------------------
// Provider registry, in fallback order. Every provider's model (and URL, for
// OpenAI-style ones) can be overridden with <PREFIX>_MODEL / <PREFIX>_URL
// environment variables, so a retired model is a config change, not a code
// change. Providers with no key configured are skipped.
// ---------------------------------------------------------------------------
function openAiStyle(id, provider, keyEnv, prefix, defaultUrl, defaultModel) {
  return {
    id, provider,
    call: async (ctx, msg) => {
      const key = $env[keyEnv];
      if (!key) throw new Error('not configured');
      const res = await ctx.helpers.httpRequest({
        method: 'POST',
        url: $env[`${prefix}_URL`] || defaultUrl,
        headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
        body: {
          model: $env[`${prefix}_MODEL`] || defaultModel,
          messages: [{ role: 'user', content: msg }],
          ...(temperature !== undefined && { temperature }),
        },
        json: true,
        timeout: PROVIDER_TIMEOUT_MS,
      });
      const text = res?.choices?.[0]?.message?.content;
      if (!text) throw new Error('empty response');
      return text;
    },
  };
}

const PROVIDERS = [
  openAiStyle('groq-llama-3.3-70b', 'groq', 'GROQ_API_KEY', 'GROQ',
    'https://api.groq.com/openai/v1/chat/completions', 'llama-3.3-70b-versatile'),
  openAiStyle('cerebras-llama3.1-8b', 'cerebras', 'CEREBRAS_API_KEY', 'CEREBRAS',
    'https://api.cerebras.ai/v1/chat/completions', 'llama3.1-8b'),
  openAiStyle('openrouter-llama3.3-70b-free', 'openrouter', 'OPENROUTER_API_KEY', 'OPENROUTER',
    'https://openrouter.ai/api/v1/chat/completions', 'meta-llama/llama-3.3-70b-instruct:free'),
  {
    id: 'gemini-flash', provider: 'gemini',
    call: async (ctx, msg) => {
      const key = $env.GOOGLE_API_KEY;
      if (!key) throw new Error('not configured');
      const model = $env.GEMINI_MODEL || 'gemini-2.5-flash';
      const res = await ctx.helpers.httpRequest({
        method: 'POST',
        url: `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
        headers: { 'x-goog-api-key': key, 'Content-Type': 'application/json' },
        body: {
          contents: [{ parts: [{ text: msg }] }],
          ...(temperature !== undefined && { generationConfig: { temperature } }),
        },
        json: true,
        timeout: PROVIDER_TIMEOUT_MS,
      });
      const text = res?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!text) throw new Error('empty response');
      return text;
    },
  },
  openAiStyle('mistral-small', 'mistral', 'MISTRAL_API_KEY', 'MISTRAL',
    'https://api.mistral.ai/v1/chat/completions', 'mistral-small-latest'),
  {
    id: 'cohere-command', provider: 'cohere',
    call: async (ctx, msg) => {
      const key = $env.COHERE_API_KEY;
      if (!key) throw new Error('not configured');
      const res = await ctx.helpers.httpRequest({
        method: 'POST',
        url: $env.COHERE_URL || 'https://api.cohere.com/v2/chat',
        headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
        body: {
          model: $env.COHERE_MODEL || 'command-r-08-2024',
          messages: [{ role: 'user', content: msg }],
          ...(temperature !== undefined && { temperature }),
        },
        json: true,
        timeout: PROVIDER_TIMEOUT_MS,
      });
      const text = res?.message?.content?.[0]?.text || res?.text;
      if (!text) throw new Error('empty response');
      return text;
    },
  },
  openAiStyle('github-gpt-4o-mini', 'github-models', 'GITHUB_TOKEN', 'GITHUB',
    'https://models.inference.ai.azure.com/chat/completions', 'gpt-4o-mini'),
  openAiStyle('sambanova-llama3.1-8b', 'sambanova', 'SAMBANOVA_API_KEY', 'SAMBANOVA',
    'https://api.sambanova.ai/v1/chat/completions', 'Meta-Llama-3.1-8B-Instruct'),
  {
    id: 'hf-mistral-7b', provider: 'huggingface',
    call: async (ctx, msg) => {
      const key = $env.HF_API_KEY;
      if (!key) throw new Error('not configured');
      const res = await ctx.helpers.httpRequest({
        method: 'POST',
        url: $env.HF_URL || 'https://router.huggingface.co/v1/chat/completions',
        headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
        body: {
          model: $env.HF_MODEL || 'Qwen/Qwen2.5-7B-Instruct',
          messages: [{ role: 'user', content: msg }],
          ...(temperature !== undefined && { temperature }),
        },
        json: true,
        timeout: PROVIDER_TIMEOUT_MS,
      });
      const text = res?.choices?.[0]?.message?.content;
      if (!text) throw new Error('empty response');
      return text;
    },
  },
];

function classify(msg) {
  const flags = ['ssn', 'bvn', 'nin', 'password', 'passport', 'salary', 'medical', 'diagnosis', 'bank account', 'credit card'];
  const lower = msg.toLowerCase();
  return flags.some((f) => lower.includes(f)) ? 'sensitive' : 'general';
}

async function runOne(ctx, entry, msg) {
  try {
    const text = await entry.call(ctx, msg);
    return { id: entry.id, provider: entry.provider, ok: true, text };
  } catch (err) {
    return { id: entry.id, provider: entry.provider, ok: false, error: (err && err.message) || String(err) };
  }
}

async function cascade(ctx, msg, chain) {
  const started = Date.now();
  const attempts = [];
  for (const entry of chain) {
    if (Date.now() - started > DEADLINE_MS) break;
    const r = await runOne(ctx, entry, msg);
    attempts.push(r);
    if (r.ok) return { winner: r, attempts };
  }
  return { winner: null, attempts };
}

// What callers see per provider: never raw error text (it can leak
// internals), except to admins who explicitly ask with debug:true.
function publicSummary(attempts, { includeText = false } = {}) {
  return attempts.map((a) => {
    const s = { provider: a.provider, model: a.id, ok: a.ok };
    if (includeText && a.ok) s.text = a.text;
    if (wantDebug && !a.ok) s.error = a.error;
    return s;
  });
}

const classification = classify(message);
let outcome;

if (mode === 'manual') {
  const selected = PROVIDERS.find((p) => p.id === requestedModel);
  if (!selected) {
    return [{ json: { error: 'unknown_model', message: `model '${requestedModel}' not found; valid ids: ${PROVIDERS.map((p) => p.id).join(', ')}`, statusCode: 400 } }];
  }
  outcome = await cascade(this, message, [selected]);
} else if (mode === 'fanout') {
  const chain = Array.isArray(requestedModels) && requestedModels.length
    ? requestedModels.map((id) => PROVIDERS.find((p) => p.id === id)).filter(Boolean)
    : PROVIDERS;
  if (!chain.length) {
    return [{ json: { error: 'unknown_model', message: 'none of the requested models were found', statusCode: 400 } }];
  }
  const attempts = await Promise.all(chain.map((entry) => runOne(this, entry, message)));
  outcome = { winner: attempts.find((a) => a.ok) || null, attempts };
  outcome.includeText = true;
} else if (mode === 'fallback' && Array.isArray(requestedModels) && requestedModels.length) {
  const chain = requestedModels.map((id) => PROVIDERS.find((p) => p.id === id)).filter(Boolean);
  if (!chain.length) {
    return [{ json: { error: 'unknown_model', message: 'none of the requested models were found', statusCode: 400 } }];
  }
  outcome = await cascade(this, message, chain);
} else {
  outcome = await cascade(this, message, PROVIDERS); // 'auto' and anything unrecognised
}

const ok = !!outcome.winner;
const result = {
  success: ok,
  text: ok ? outcome.winner.text : null,
  output: ok ? outcome.winner.text : null,
  usedModel: ok ? outcome.winner.id : null,
  provider: ok ? outcome.winner.provider : null,
  classification,
  mode: ['auto', 'manual', 'fanout', 'fallback'].includes(mode) ? mode : 'auto',
  routingSummary: publicSummary(outcome.attempts, { includeText: !!outcome.includeText }),
  statusCode: ok ? 200 : 502,
};
if (!ok) {
  result.error = 'all_providers_failed';
  result.message = 'every provider failed or is unconfigured; try again shortly';
}
if (classification === 'sensitive') {
  result.warning = 'message looks sensitive; it was sent to third-party free-tier providers';
}
return [{ json: result }];
