import fs from 'fs';
const src = fs.readFileSync(new URL('../../n8n/gateway_engine.js', import.meta.url).pathname, 'utf8');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const engine = new AsyncFunction('$', '$env', src);

let pass = 0, fail = 0;
const ok = (c, n) => { c ? (pass++, console.log('PASS', n)) : (fail++, console.log('FAIL', n)); };

const ALL_KEYS = { GROQ_API_KEY:'k1', CEREBRAS_API_KEY:'k2', OPENROUTER_API_KEY:'k3', GOOGLE_API_KEY:'k4',
  MISTRAL_API_KEY:'k5', COHERE_API_KEY:'k6', GITHUB_TOKEN:'k7', SAMBANOVA_API_KEY:'k8', HF_API_KEY:'k9' };

// route(optsUrlSubstring -> handler) ; returns {calls, run}
function harness({ env = ALL_KEYS, body, headers = {}, handlers = {} }) {
  const calls = [];
  const ctx = { helpers: { httpRequest: async (opts) => {
    calls.push(opts);
    for (const [frag, h] of Object.entries(handlers)) if (opts.url.includes(frag)) return h(opts);
    return { choices: [{ message: { content: 'default-answer' } }] };
  } } };
  const $ = () => ({ first: () => ({ json: { headers, body } }) });
  return { calls, run: async () => (await engine.call(ctx, $, env))[0].json };
}
const boom = (m) => () => { throw new Error(m); };

// 1. failover + no secret leakage
let h = harness({ body: { message: 'hi' }, handlers: {
  'groq.com': boom('401 Unauthorized secret-token-123'), 'cerebras.ai': boom('rate limited secret-token-123') } });
let r = await h.run();
ok(r.statusCode === 200 && r.success && r.usedModel === 'openrouter-llama3.3-70b-free', 'auto: falls through failed providers to the first working one');
ok(r.routingSummary.length === 3 && r.routingSummary.filter(x => x.ok).length === 1, 'routing summary lists each attempt');
ok(!JSON.stringify(r).includes('secret-token-123'), 'raw provider error text never reaches the caller');
ok(r.text === 'default-answer' && r.output === r.text, 'text and output both populated (SDK/CLI compatible)');

// 2. unconfigured providers are skipped without network calls
h = harness({ env: { MISTRAL_API_KEY: 'k5' }, body: { message: 'hi' } });
r = await h.run();
ok(r.usedModel === 'mistral-small' && h.calls.length === 1, 'unconfigured providers skipped with zero HTTP calls');

// 3. everything fails -> real 502
h = harness({ body: { message: 'hi' }, handlers: Object.fromEntries(['groq','cerebras','openrouter','googleapis','mistral','cohere','azure','sambanova','huggingface'].map(f => [f, boom('down')])) });
r = await h.run();
ok(r.statusCode === 502 && r.success === false && r.error === 'all_providers_failed' && r.text === null, 'all providers failing -> statusCode 502');
h = harness({ env: {}, body: { message: 'hi' } });
r = await h.run();
ok(r.statusCode === 502, 'no providers configured -> 502 (not a fake 200)');

// 4. input validation
for (const [label, b] of [['missing', {}], ['non-string', { message: 123 }], ['blank', { message: '   ' }]]) {
  r = await harness({ body: b }).run();
  ok(r.statusCode === 400, `bad message (${label}) -> 400`);
}
r = await harness({ body: { message: 'x'.repeat(8001) } }).run();
ok(r.statusCode === 413, 'message over 8000 chars -> 413');
r = await harness({ body: { message: 'x'.repeat(8000) } }).run();
ok(r.statusCode === 200, 'message of exactly 8000 chars is accepted');

// 5. manual mode
r = await harness({ body: { message: 'hi', mode: 'manual', model: 'nope' } }).run();
ok(r.statusCode === 400 && r.message.includes('groq-llama-3.3-70b'), 'manual with unknown model -> 400 listing valid ids');
h = harness({ body: { message: 'hi', mode: 'manual', model: 'mistral-small' } });
r = await h.run();
ok(r.success && h.calls.length === 1 && h.calls[0].url.includes('mistral'), 'manual calls only the requested provider');

// 6. fanout
h = harness({ body: { message: 'hi', mode: 'fanout' }, handlers: {
  'groq.com': boom('x'),
  googleapis: () => ({ candidates: [{ content: { parts: [{ text: 'g' }] } }] }),
  cohere: () => ({ message: { content: [{ text: 'c' }] } }) } });
r = await h.run();
ok(h.calls.length === 9, 'fanout calls every configured provider');
ok(r.routingSummary.filter(x => x.ok && typeof x.text === 'string').length === 8, 'fanout returns each successful answer');
ok(r.usedModel === 'cerebras-llama3.1-8b', 'fanout primary text is the first success in provider order');
h = harness({ body: { message: 'hi', mode: 'fanout', models: ['mistral-small', 'groq-llama-3.3-70b'] } });
await h.run();
ok(h.calls.length === 2, 'fanout honours an explicit models list');

// 7. admin debug
const failingGroq = { 'groq.com': boom('quota exceeded for org') };
r = await harness({ env: { ...ALL_KEYS, GATEWAY_API_KEY: 'master' }, headers: { 'x-api-key': 'master' }, body: { message: 'hi', debug: true }, handlers: failingGroq }).run();
ok(r.routingSummary[0].error === 'quota exceeded for org', 'admin + debug:true sees raw provider errors');
r = await harness({ env: { ...ALL_KEYS, GATEWAY_API_KEY: 'master' }, headers: { 'x-api-key': 'someone-else' }, body: { message: 'hi', debug: true }, handlers: failingGroq }).run();
ok(!('error' in r.routingSummary[0]), 'non-admin cannot enable debug');
r = await harness({ env: ALL_KEYS, headers: {}, body: { message: 'hi', debug: true }, handlers: failingGroq }).run();
ok(!('error' in r.routingSummary[0]), 'unset master key never makes an anonymous caller admin');

// 8. classification
r = await harness({ body: { message: 'my password is hunter2' } }).run();
ok(r.classification === 'sensitive' && !!r.warning, 'sensitive messages get a warning');

// 9. provider request shapes + overrides
h = harness({ env: { GOOGLE_API_KEY: 'gkey', GEMINI_MODEL: 'gemini-9-test' }, body: { message: 'hi' },
  handlers: { googleapis: () => ({ candidates: [{ content: { parts: [{ text: 'from gemini' }] } }] }) } });
r = await h.run();
ok(r.text === 'from gemini' && h.calls[0].url.includes('gemini-9-test:generateContent'), 'gemini model comes from GEMINI_MODEL');
ok(h.calls[0].headers['x-goog-api-key'] === 'gkey' && !h.calls[0].url.includes('gkey'), 'gemini key sent in a header, never in the URL');
h = harness({ env: { GROQ_API_KEY: 'k', GROQ_MODEL: 'llama-next' }, body: { message: 'hi' } });
await h.run();
ok(h.calls[0].body.model === 'llama-next', 'OpenAI-style model overridable via <PREFIX>_MODEL');
h = harness({ env: { COHERE_API_KEY: 'k' }, body: { message: 'hi' }, handlers: { cohere: () => ({ message: { content: [{ text: 'from cohere v2' }] } }) } });
r = await h.run();
ok(r.text === 'from cohere v2', 'cohere v2 response shape parsed');
h = harness({ env: { GROQ_API_KEY: 'k' }, body: { message: 'hi' }, handlers: { groq: () => ({ choices: [] }) } });
r = await h.run();
ok(r.statusCode === 502, 'a provider returning an empty body counts as a failure, not a blank answer');

// 10. overall deadline stops the cascade early
{
  const calls = [];
  const ctx = { helpers: { httpRequest: async (o) => { calls.push(o); await new Promise(r => setTimeout(r, 40)); throw new Error('slow fail'); } } };
  const $ = () => ({ first: () => ({ json: { headers: {}, body: { message: 'hi' } } }) });
  const out = (await engine.call(ctx, $, { ...ALL_KEYS, GATEWAY_DEADLINE_MS: '60' }))[0].json;
  ok(calls.length >= 2 && calls.length < 9, `deadline halts the cascade early (${calls.length} of 9 providers tried)`);
  ok(out.statusCode === 502 && out.error === 'all_providers_failed', 'deadline exhaustion returns a clean 502 JSON error');
}

// 11. temperature
const temps = async (body, env = { GROQ_API_KEY: 'k', GOOGLE_API_KEY: 'g', COHERE_API_KEY: 'c', HF_API_KEY: 'h' }) => {
  const h = harness({ env, body: { message: 'hi', mode: 'fanout', ...body }, handlers: {
    googleapis: () => ({ candidates: [{ content: { parts: [{ text: 'g' }] } }] }),
    cohere: () => ({ message: { content: [{ text: 'c' }] } }) } });
  await h.run();
  return h.calls;
};
let calls = await temps({ temperature: 0.3 });
ok(calls.find(c => c.url.includes('groq')).body.temperature === 0.3, 'temperature forwarded to OpenAI-style providers');
ok(calls.find(c => c.url.includes('googleapis')).body.generationConfig.temperature === 0.3, 'temperature forwarded to Gemini as generationConfig');
ok(calls.find(c => c.url.includes('cohere')).body.temperature === 0.3, 'temperature forwarded to Cohere');
ok(calls.find(c => c.url.includes('huggingface')).body.temperature === 0.3, 'temperature forwarded to Hugging Face');
calls = await temps({ temperature: 5 });
ok(calls.every(c => (c.body.temperature ?? c.body.generationConfig?.temperature) === 1), 'temperature above 1 is clamped to 1');
calls = await temps({ temperature: -2 });
ok(calls.every(c => (c.body.temperature ?? c.body.generationConfig?.temperature) === 0), 'negative temperature is clamped to 0');
calls = await temps({ temperature: '0.5' });
ok(calls.every(c => c.body.temperature === undefined && c.body.generationConfig === undefined), 'a non-numeric temperature is ignored, not forwarded');
calls = await temps({});
ok(calls.every(c => !('temperature' in c.body) && !('generationConfig' in c.body)), 'no temperature requested -> none sent');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
