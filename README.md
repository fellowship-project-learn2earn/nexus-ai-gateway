# Baalebos AI

Official Python client and terminal CLI for the **Baalebos AI Gateway**: one endpoint in front of nine free-tier LLM
providers (Groq, Cerebras, OpenRouter, Gemini, Mistral, Cohere, GitHub Models, SambaNova, HuggingFace) with automatic
failover. If a provider is rate-limited, retired or down, the next one answers. You never manage a provider key.

## Install

```bash
pip install baalebos-ai
```

Python 3.9 or newer.

## Use it

**Command line**

```bash
ai "explain what a race condition is in one sentence"
cat error.log | ai "what went wrong here?"     # piped text is appended to your prompt
ai "summarise this" --mode fast
ai --status                                    # is the gateway up?
```

**Python (synchronous)**

```python
from baalebos_ai import BaalebosAI

client = BaalebosAI()
print(client.chat("What is the capital of Nigeria?"))
```

**Python (asynchronous)**: for FastAPI, asyncio scripts and the like. Same methods, same errors:

```python
import asyncio
from baalebos_ai import AsyncBaalebosAI

async def main():
    client = AsyncBaalebosAI()
    print(await client.chat("What is the capital of Nigeria?"))

asyncio.run(main())
```

**Structured output**: you want a dict, not prose:

```python
data = client.chat_json(
    system_prompt='You are a code reviewer. Return {"severity": "low|medium|high", "summary": "..."}',
    user_prompt=open("diff.patch").read(),
    required_keys=["severity", "summary"],
)
print(data["severity"])
```

The gateway has no separate system-prompt field and can't guarantee that every fallback provider obeys "return only
JSON", so `chat_json` folds your instructions into the prompt, extracts the JSON object leniently (bare, in a code
fence, or buried in chatter), and asks again if it still can't parse it. `AsyncBaalebosAI` has the same method.

**Plain HTTP** (any language): see [docs/API.md](docs/API.md). A TypeScript client lives in
[`clients/typescript`](clients/typescript).

## Authentication

There is nothing to set up. On first use the SDK asks the gateway for its own key and saves it in
`~/.config/baalebos_ai/credentials.json` (owner-readable only), so every install has its own identity and its own
daily limit. No shared secret ships in the package.

If the gateway ever stops recognising a key it registered for you (for example after a database rebuild), the SDK
replaces it automatically. A key you supply yourself is never swapped silently.

Already have a key? Set it and it takes priority over everything:

```bash
export BAALEBOS_API_KEY="your-gateway-key"
export BAALEBOS_API_URL="https://gateway.baalebo.xyz/webhook/baalebos-ai"   # only needed for a self-hosted gateway
```

or pass them explicitly: `BaalebosAI(api_url="...", api_key="...")`.

## `chat()` parameters

| Parameter | Default | Description |
|---|---|---|
| `prompt` | (required) | the text to send |
| `mode` | `"auto"` | `auto` tries providers in order; `manual` uses only `model`; `fanout` asks several at once; `fallback` tries `models` in order. Other values (such as `fast`, `smart`) are accepted and behave like `auto` |
| `temperature` | `0.7` | sampling temperature, clamped to 0 to 1. `None` leaves it to the provider |
| `model` | `None` | keyword-only. A provider id, for `mode="manual"` |
| `models` | `None` | keyword-only. A list of provider ids, for `fanout` / `fallback` |

`chat_raw()` takes the same arguments and returns the gateway's full response (`usedModel`, `provider`,
`routingSummary`, ...) instead of just the text.

## Error handling

Everything the SDK raises inherits from `BaalebosError`:

| Exception | Raised when |
|---|---|
| `BaalebosConfigError` | the configured URL is malformed |
| `BaalebosConnectionError` | the request never reached the gateway (DNS, refused, timeout) |
| `BaalebosAPIError` | the gateway answered with an error status (`.status_code`); the classes below are subclasses |
| `BaalebosAuthError` | 401: the gateway rejected a key you supplied |
| `BaalebosRateLimitError` | 429: a daily limit was reached (yours, or the shared public pool) |
| `BaalebosRequestError` | 400/413/422: empty or oversized message, unknown model |
| `BaalebosUnavailableError` | 404/5xx: the gateway is down, mis-addressed, or every provider failed |
| `BaalebosStructuredOutputError` | `chat_json` could not get a valid JSON object |

```python
from baalebos_ai import BaalebosAI, BaalebosError, BaalebosRateLimitError

client = BaalebosAI()
try:
    print(client.chat("Hello"))
except BaalebosRateLimitError:
    print("Daily limit reached; it resets at 00:00 UTC.")
except BaalebosError as e:
    print(f"Something else went wrong: {e}")
```

Connection failures and 502/503/504 responses are retried automatically with backoff. Read timeouts are not, because
the request may already have been processed and counted.

## Limits and privacy

Read this before building on it.

- **It is a free service with no SLA.** Providers' free tiers change; the gateway can be slow or briefly down.
- **Daily limits.** Auto-registered keys get 50 requests a day, and a shared daily cap protects the free provider
  quotas for everyone. Messages are limited to 8,000 characters.
- **Your prompts go to third-party providers.** Free tiers may log or train on what you send. Don't send secrets,
  credentials or personal data. Messages that look sensitive are flagged in the response.
- The gateway is configured not to store successful requests. Failed requests may be logged for debugging.

## Self-hosting

The gateway is a set of n8n workflows plus a Postgres table. Everything needed to run your own is in
[docs/OPERATIONS.md](docs/OPERATIONS.md). Point the SDK at it with `BAALEBOS_API_URL`; the signup and health
endpoints are derived from it automatically.

## Development

```bash
pip install -e ".[dev]"
pytest                                       # SDK, async client, API-compatibility and workflow tests
cd tests/node && npm install && npm test     # SQL and gateway-engine tests (real Postgres engine, mocked providers)
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under MIT.
