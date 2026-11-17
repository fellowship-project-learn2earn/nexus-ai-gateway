# Operations runbook

The gateway is three n8n workflows plus one Postgres table. **This repository is the source of truth**: the
workflow JSON in `n8n/` is generated from tested sources (`python3 n8n/build_workflows.py`), so losing an n8n
instance never means losing the workflows.

`n8n/multi-llm-gateway-free.json` is the earlier single-key workflow. It is superseded by
`gateway.workflow.json` and kept only for reference; don't run both on the same webhook path.

Self-hosted n8n only. These workflows read secrets with `$env.*`, which n8n Cloud blocks, and the Variables
feature (`$vars`) is Enterprise-only on self-hosted n8n.

## Environment variables (on the n8n service)

| Variable | Purpose |
|---|---|
| `N8N_HOST` | bare hostname only, e.g. `gateway.baalebo.xyz` (no `https://`: a prefix here produces `https://https://...`) |
| `N8N_PROTOCOL` | `https` |
| `N8N_WEBHOOK_URL` | `https://gateway.baalebo.xyz/` (use this, not the deprecated `WEBHOOK_URL`) |
| `N8N_ENCRYPTION_KEY` | generate once, keep it, never change it after credentials exist: saved credentials become unreadable |
| `GATEWAY_API_KEY` | the master key. Bypasses quotas and the database, so it keeps working if Postgres is down. `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `COHERE_API_KEY`, `GITHUB_TOKEN`, `SAMBANOVA_API_KEY`, `HF_API_KEY` | provider keys; any can be omitted and that provider is skipped |
| `IP_HASH_SALT` | random string; signup IPs are stored only as a salted hash |
| `PUBLIC_DAILY_CAP` | optional, default `5000`: total requests per day across all non-master keys |
| `SIGNUPS_PER_IP_PER_DAY` | optional, default `10` (mobile carriers share IPs, so don't set it too low) |
| `GATEWAY_DEADLINE_MS` | optional, default `60000`: stop trying new providers after this long |
| `<PREFIX>_MODEL`, `<PREFIX>_URL` | optional overrides per provider, prefixes `GROQ`, `CEREBRAS`, `OPENROUTER`, `MISTRAL`, `COHERE`, `GITHUB`, `SAMBANOVA`, `HF`; plus `GEMINI_MODEL`. A retired model is fixed by changing a variable, not code |

Changing a variable redeploys the service. Use Postgres 17 or newer for new databases.

## First deployment

1. Create the Postgres database and run `sql/schema.sql` against it. It is idempotent and also upgrades the earlier
   version of the table in place.
2. Set the environment variables above and let n8n redeploy.
3. In n8n, create a credential of type **Postgres** for that database (SSL on for Railway).
4. Import `n8n/gateway.workflow.json`, `n8n/signup.workflow.json` and `n8n/health.workflow.json`.
5. Open **Check Key And Quota** (gateway workflow) and **Create Key** (signup workflow) and select the Postgres
   credential. Click *Execute step* once on each to confirm n8n accepts the parameters. They were written for the
   Postgres node v2.5; if your n8n version differs, re-select the named options (query, query parameters) in the UI.
6. **Publish all three workflows.** Each has its own Publish button; an unpublished workflow has no production URL.
7. Verify (below).

## Verify

```bash
GW=https://gateway.baalebo.xyz/webhook

curl -s $GW/baalebos-ai-health                                   # {"status":"ok",...}

KEY=$(curl -s -X POST $GW/baalebos-ai-signup | python3 -c "import sys,json;print(json.load(sys.stdin)['api_key'])")
curl -s -X POST $GW/baalebos-ai -H "Content-Type: application/json" -H "x-api-key: $KEY" \
  -d '{"message":"say hello"}'                                    # 200 with text

curl -s -X POST $GW/baalebos-ai -H "Content-Type: application/json" -H "x-api-key: wrong" \
  -d '{"message":"hi"}'                                           # 401
```

## Routine

**Uptime.** Point an uptime monitor at `/webhook/baalebos-ai-health`. It checks n8n only, not the database or providers.

**Provider health.** Providers retire models without notice. As the master key, ask every provider at once and
read the raw errors:

```bash
curl -s -X POST $GW/baalebos-ai -H "Content-Type: application/json" -H "x-api-key: $GATEWAY_API_KEY" \
  -d '{"message":"Reply with the single word OK","mode":"fanout","debug":true}' | python3 -m json.tool
```

Fix a failing provider by setting its `<PREFIX>_MODEL` variable.

**Backups.** Enable volume backups on the Postgres service in Railway, and keep an off-platform copy:

```bash
pg_dump "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" > backup-$(date +%F).sql
```

**Managing keys** (run in the database console):

```sql
-- usage today
SELECT COUNT(*) AS keys, SUM(daily_request_count) FILTER (WHERE last_request_date = CURRENT_DATE) AS requests_today
FROM api_keys;

-- raise one key's daily limit
UPDATE api_keys SET daily_limit = 500 WHERE api_key = '...';

-- revoke a key (the SDK registers a fresh one automatically on its next call)
DELETE FROM api_keys WHERE api_key = '...';

-- a key that should bypass the shared public cap
UPDATE api_keys SET is_team = TRUE, label = 'partner-x' WHERE api_key = '...';
```

## Recovery

**Hosting stopped after a Railway trial ended.** Subscribing to a paid plan redeploys the stopped services onto
their existing volumes, but volume data on a trial workspace is deleted 30 days after the trial credits run out.
Check that date first, and keep backups somewhere other than the platform you are backing up.

**Rebuild from scratch.** Follow *First deployment*. Users' saved keys don't need re-issuing: on the first 401 the SDK
registers a new key by itself. Holders of the master key are unaffected.

**Database down.** The master key keeps working. Other callers get `503 service_unavailable`, which the SDK retries.

## Capacity and known limits

- n8n runs in a single process by default. Past modest traffic, move to n8n's queue mode with worker processes.
- `PUBLIC_DAILY_CAP` is a soft circuit breaker: concurrent requests can overshoot it by a few.
- Signup limiting is per network and best-effort. Someone with many IPs can mint many keys; the public cap bounds
  the total damage.
- `api_keys` stores the keys themselves. They are random bearer tokens, but anyone who can read the table can use
  them, so treat the database as a secret. Hashing stored keys is a worthwhile next hardening step.
- Free-tier provider terms apply to everything routed through the gateway. Say so to your users.
