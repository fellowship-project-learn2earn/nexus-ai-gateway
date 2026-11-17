import { PGlite } from '@electric-sql/pglite';
import fs from 'fs';
const D = new URL('../../sql/', import.meta.url).pathname;
const schema = fs.readFileSync(D + 'schema.sql', 'utf8');
const checkSql = fs.readFileSync(D + 'check_key_and_quota.sql', 'utf8');
const createSql = fs.readFileSync(D + 'create_key.sql', 'utf8');

let pass = 0, fail = 0;
const ok = (cond, name) => { cond ? (pass++, console.log('PASS', name)) : (fail++, console.log('FAIL', name)); };

const db = new PGlite();

// Simulate the EARLIER deployed table (no is_team / signup_ip_hash / label) then upgrade it.
await db.exec(`CREATE TABLE api_keys (
  id SERIAL PRIMARY KEY, api_key TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), daily_limit INTEGER NOT NULL DEFAULT 50,
  daily_request_count INTEGER NOT NULL DEFAULT 0, last_request_date DATE NOT NULL DEFAULT CURRENT_DATE,
  total_request_count INTEGER NOT NULL DEFAULT 0);
  INSERT INTO api_keys (api_key) VALUES ('legacy-key-from-before');`);
await db.exec(schema);
await db.exec(schema); // idempotent: second run must not fail
const cols = (await db.query(`SELECT column_name FROM information_schema.columns WHERE table_name='api_keys'`)).rows.map(r => r.column_name);
ok(['is_team','signup_ip_hash','label'].every(c => cols.includes(c)), 'schema upgrades an existing table and is idempotent');
ok((await db.query(`SELECT COUNT(*)::int n FROM api_keys WHERE api_key='legacy-key-from-before'`)).rows[0].n === 1, 'existing rows survive the upgrade');

// ---- create_key ----
const mint = async (ip, max='3') => (await db.query(createSql, [ip, max, 'salt'])).rows[0].api_key;
const k1 = await mint('1.2.3.4');
ok(/^[0-9a-f]{64}$/.test(k1), 'minted key is 64 hex chars');
const k2 = await mint('1.2.3.4'); const k3 = await mint('1.2.3.4');
ok(new Set([k1,k2,k3]).size === 3, 'minted keys are unique');
ok((await mint('1.2.3.4')) === null, '4th signup from the same IP is refused (api_key NULL)');
ok(/^[0-9a-f]{64}$/.test(await mint('9.9.9.9')), 'a different IP can still sign up');
const stored = (await db.query(`SELECT signup_ip_hash FROM api_keys WHERE api_key=$1`, [k1])).rows[0].signup_ip_hash;
ok(/^[0-9a-f]{64}$/.test(stored) && !stored.includes('1.2.3.4'), 'only a salted hash of the IP is stored, never the raw IP');
// the 24h window: backdate the 3 keys, the IP can sign up again
await db.query(`UPDATE api_keys SET created_at = NOW() - INTERVAL '25 hours' WHERE signup_ip_hash IS NOT NULL AND api_key IN ($1,$2,$3)`, [k1,k2,k3]);
ok(/^[0-9a-f]{64}$/.test(await mint('1.2.3.4')), 'signup limit window rolls over after 24h');

// ---- check_key_and_quota ----
const check = async (key, cap='5000') => (await db.query(checkSql, [key, cap])).rows[0];
let r = await check('does-not-exist');
ok(r.allowed === 0 && r.known === false, 'unknown key -> allowed 0, known false (=> 401)');
r = await check("x' OR '1'='1");
ok(r.allowed === 0 && r.known === false, 'SQL injection string is treated as a plain (unknown) key');
r = await check('');
ok(r.allowed === 0 && r.known === false, 'empty key -> 401 path');

await db.query(`INSERT INTO api_keys (api_key, daily_limit) VALUES ('quota-key', 2)`);
ok((await check('quota-key')).allowed === 1, 'request 1 allowed');
ok((await check('quota-key')).allowed === 1, 'request 2 allowed');
r = await check('quota-key');
ok(r.allowed === 0 && r.known === true, 'request 3 denied, key known (=> 429)');
const row = (await db.query(`SELECT daily_request_count d, total_request_count t FROM api_keys WHERE api_key='quota-key'`)).rows[0];
ok(row.d === 2 && row.t === 2, 'denied requests are not counted');

await db.query(`UPDATE api_keys SET last_request_date = CURRENT_DATE - 1 WHERE api_key='quota-key'`);
ok((await check('quota-key')).allowed === 1, 'quota resets on a new day');
const row2 = (await db.query(`SELECT daily_request_count d, total_request_count t FROM api_keys WHERE api_key='quota-key'`)).rows[0];
ok(row2.d === 1 && row2.t === 3, 'daily counter restarts at 1, lifetime total keeps growing');

// ---- global cap + team keys ----
await db.exec(`DELETE FROM api_keys; INSERT INTO api_keys (api_key, daily_limit) VALUES ('a',100),('b',100);
               INSERT INTO api_keys (api_key, daily_limit, is_team) VALUES ('team',1000000,TRUE);`);
let allowed = 0;
for (const k of ['a','b','a','b','a','b']) allowed += (await check(k, '3')).allowed;
ok(allowed === 3, 'global cap of 3 stops public traffic after 3 requests total');
r = await check('a','3');
ok(r.allowed === 0 && r.known === true, 'over the global cap -> 429, not 401');
ok((await check('team','3')).allowed === 1, 'team keys bypass the global cap');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
