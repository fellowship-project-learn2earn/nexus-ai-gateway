# baalebos-ai

Official Python client and terminal CLI for the **Baalebos AI Gateway** — a single endpoint that
routes across 9 free-tier LLM providers with automatic failover.

## Install

```bash
cd clients/python
pip install -e .
```

This installs the `baalebos-ai` package and registers the `ai` terminal command.

## Configuration

The client needs two values: the gateway URL and your API key. Set them as environment
variables so you never have to hardcode secrets in code:

```bash
export BAALEBOS_API_URL="https://<your-instance>.app.n8n.cloud/webhook/baalebos-ai"
export BAALEBOS_API_KEY="your-gateway-key"
```

Add those two lines to `~/.bashrc` (or `~/.zshrc`) and run `source ~/.bashrc` so they persist
across terminal sessions.

Alternatively, pass them directly when creating a client — useful for scripts that manage
multiple keys or don't want to rely on the environment:

```python
client = BaalebosAI(api_url="...", api_key="...")
```

## Terminal CLI

Once installed, call the gateway directly from any terminal:

```bash
ai "Explain Kubernetes architecture in 2 simple sentences"
```

Optional flags:

```bash
ai "Summarize this" --mode fast
```

## Python usage — synchronous

```python
from baalebos_ai import BaalebosAI

client = BaalebosAI()  # reads BAALEBOS_API_URL / BAALEBOS_API_KEY from the environment
response = client.chat("What is the capital of Nigeria?")
print(response)
```

## Python usage — asynchronous

For async codebases (FastAPI, asyncio scripts), use `AsyncBaalebosAI` instead — same
methods, same behavior, just non-blocking:

```python
import asyncio
from baalebos_ai import AsyncBaalebosAI

async def main():
    client = AsyncBaalebosAI()
    response = await client.chat("What is the capital of Nigeria?")
    print(response)

asyncio.run(main())
```

## Error handling

The SDK raises specific, catchable exception types instead of generic errors, so calling
code can handle each failure differently:

| Exception | Raised when |
|---|---|
| `BaalebosConfigError` | `BAALEBOS_API_URL` or `BAALEBOS_API_KEY` is missing |
| `BaalebosAuthError` | the gateway rejected the API key (401) |
| `BaalebosConnectionError` | the request timed out or couldn't reach the gateway |
| `BaalebosAPIError` | the gateway returned any other error status |

All of them inherit from `BaalebosError`, so you can catch that alone if you just want to
handle "something went wrong" generically:

```python
from baalebos_ai import BaalebosAI, BaalebosAuthError, BaalebosError

client = BaalebosAI()
try:
    print(client.chat("Hello"))
except BaalebosAuthError:
    print("Your API key looks wrong — check BAALEBOS_API_KEY.")
except BaalebosError as e:
    print(f"Something else went wrong: {e}")
```

## `chat()` parameters

| Parameter | Default | Description |
|---|---|---|
| `prompt` | — | the text to send to the gateway |
| `mode` | `"auto"` | routing mode: `"auto"`, `"fast"`, or `"smart"` |
| `temperature` | `0.7` | sampling temperature passed through to the underlying model |

## Package structure

```
clients/python/
├── setup.py
└── baalebos_ai/
    ├── __init__.py
    ├── client.py       # BaalebosAI (sync) and AsyncBaalebosAI
    ├── cli.py           # `ai` command entrypoint
    └── exceptions.py    # custom error types
```
