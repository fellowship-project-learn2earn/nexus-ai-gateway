# Baalebos AI

A zero-cost, multi-provider AI gateway. One API, one CLI command, cascading
across 9 free-tier LLM providers so you never have to manage individual
provider keys or pay for API access.

## Why use this?

Instead of signing up for and paying for OpenAI, Anthropic, or another
provider directly, `baalebos-ai` routes your request through a gateway
that automatically falls back across Groq, Cerebras, OpenRouter, Gemini,
Mistral, Cohere, GitHub Models, SambaNova, and HuggingFace -- all free
tier. If one is rate-limited or down, the next one picks up the request
automatically. You get a working answer; which provider actually
generated it is invisible to you.

## Install

```bash
pip install baalebos-ai
```

## Authentication

**Nothing to set up.** The first time you run the CLI or use the SDK, it
automatically registers a unique key for your installation and saves it
locally (`~/.config/baalebos_ai/credentials.json`, permissions restricted
to your user only). No signup form, no manual key request.

If you're a team member with an existing key, it still works exactly as
before:

```bash
export BAALEBOS_API_KEY=your_existing_key
```

(environment variable always takes priority over the auto-registered one)

## CLI usage

```bash
ai "explain what a race condition is in one sentence"
```

With a specific mode:

```bash
ai --mode fanout "compare answers across providers"
```

## Python SDK usage

```python
from baalebos_ai import BaalebosAI

client = BaalebosAI()  # auto-registers a key on first use, same as the CLI
answer = client.chat("explain what a race condition is")
print(answer)
```

## Architecture

```
Your request
    │
    ▼
Gateway webhook (auth-checked, individually rate-limited per key)
    │
    ▼
Cascading fallback: Groq → Cerebras → OpenRouter → Gemini → Mistral
                   → Cohere → GitHub Models → SambaNova → HuggingFace
    │
    ▼
First provider that responds successfully wins
```

## Provider list & failover behavior

| Order | Provider | Model |
|---|---|---|
| 1 | Groq | llama-3.3-70b-versatile |
| 2 | Cerebras | llama3.1-8b |
| 3 | OpenRouter | llama-3.3-70b-instruct:free |
| 4 | Gemini | gemini-2.5-flash |
| 5 | Mistral | mistral-small-latest |
| 6 | Cohere | command-r |
| 7 | GitHub Models | gpt-4o-mini |
| 8 | SambaNova | Meta-Llama-3.1-8B-Instruct |
| 9 | HuggingFace | Mistral-7B-Instruct |

Any provider that's unavailable is skipped automatically -- you'll only
ever notice if literally all 9 fail at once.

## Configuration

| Environment variable | Purpose | Required? |
|---|---|---|
| `BAALEBOS_API_KEY` | Your gateway key | No -- auto-registered if not set |
| `BAALEBOS_API_URL` | Gateway endpoint | No -- has a sensible default |

## Source code

https://github.com/baalebos-cloud/nexus-ai-gateway

## Contributing

Issues and pull requests welcome. See
[CONTRIBUTING.md](https://github.com/baalebos-cloud/nexus-ai-gateway/blob/main/CONTRIBUTING.md).

## License

MIT -- see [LICENSE](https://github.com/baalebos-cloud/nexus-ai-gateway/blob/main/LICENSE).
