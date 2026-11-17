# HTTP API

Base URL: `https://gateway.baalebo.xyz/webhook`

## POST `/baalebos-ai`

Headers: `Content-Type: application/json`, `x-api-key: <key>`

```json
{ "message": "your prompt", "mode": "auto" }
```

| Field | Required | Notes |
|---|---|---|
| `message` | yes | non-empty string, at most 8,000 characters |
| `mode` | no | `auto` (default): try providers in order. `manual`: only `model`. `fanout`: ask all (or the ones in `models`) in parallel. `fallback`: try the providers in `models`, in that order |
| `model` | with `manual` | a provider id, e.g. `groq-llama-3.3-70b` |
| `models` | no | list of provider ids, for `fanout` / `fallback` |
| `temperature` | no | number, clamped to 0 to 1 and forwarded to every provider; anything else is ignored |
| `debug` | no | admin key only: include raw provider errors in `routingSummary` |

Provider ids, in default order: `groq-llama-3.3-70b`, `cerebras-llama3.1-8b`, `openrouter-llama3.3-70b-free`,
`gemini-flash`, `mistral-small`, `cohere-command`, `github-gpt-4o-mini`, `sambanova-llama3.1-8b`, `hf-mistral-7b`.

### Success (200)

```json
{
  "success": true,
  "text": "the answer",
  "output": "the answer",
  "usedModel": "groq-llama-3.3-70b",
  "provider": "groq",
  "classification": "general",
  "mode": "auto",
  "routingSummary": [{ "provider": "groq", "model": "groq-llama-3.3-70b", "ok": true }]
}
```

`routingSummary` lists each provider that was tried. In `fanout` mode each successful entry also carries its `text`.
Responses to messages that look sensitive include a `warning`.

### Errors

Always JSON with `error` and `message`.

| Status | `error` | Meaning |
|---|---|---|
| 400 | `bad_request`, `unknown_model` | missing/empty message, or a model id that doesn't exist |
| 401 | `unauthorized` | missing or unknown `x-api-key` |
| 413 | `message_too_long` | over 8,000 characters |
| 429 | `rate_limited` | your key's daily limit, or the shared public cap, is reached; resets 00:00 UTC |
| 502 | `all_providers_failed` | every provider failed or timed out |
| 503 | `service_unavailable` | the key database is temporarily unreachable; retry shortly |

## POST `/baalebos-ai-signup`

No body, no key. Returns `{"api_key": "..."}` (64 hex characters). Rate limited per network (default 10 keys per
IP per day); over the limit it returns `429 too_many_signups`.

## GET `/baalebos-ai-health`

Returns `{"status": "ok", "service": "baalebos-ai"}`. Needs no key and touches no database or provider; use it for
uptime monitoring.

## Example

```bash
KEY=$(curl -s -X POST https://gateway.baalebo.xyz/webhook/baalebos-ai-signup | python3 -c "import sys,json;print(json.load(sys.stdin)['api_key'])")

curl -s -X POST https://gateway.baalebo.xyz/webhook/baalebos-ai \
  -H "Content-Type: application/json" -H "x-api-key: $KEY" \
  -d '{"message": "say hello", "mode": "auto"}'
```
