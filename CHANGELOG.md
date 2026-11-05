# Changelog

## [1.1.0] - Unreleased

### Added
- **`AsyncBaalebosAI` now actually ships.** The 1.0.x README documented it, but the published wheel was built
  from a copy of the package that didn't contain it, so `from baalebos_ai import AsyncBaalebosAI` raised `ImportError`.
- Zero-setup authentication: the SDK registers its own key on first use. `BAALEBOS_API_URL` and `BAALEBOS_API_KEY`
  are no longer required, and still take priority when set.
- `chat_json()` (sync and async): structured output with lenient JSON extraction and re-asking.
- `chat_raw()`, `check_status()`, `ai --status`, `--raw`, `--model`, `--version`, and piped input
  (`cat error.log | ai "what went wrong?"`).
- New exceptions `BaalebosRateLimitError`, `BaalebosRequestError`, `BaalebosUnavailableError` and
  `BaalebosStructuredOutputError`. The first three subclass `BaalebosAPIError`, so existing `except` clauses keep working.
- Automatic retries with backoff on 502/503/504 and connection failures, and automatic replacement of an
  auto-registered key the gateway no longer recognises.
- Gateway: `fanout` mode (documented before, now implemented), `temperature` support (it was sent but ignored),
  admin-only `debug`, per-provider model/URL overrides by environment variable, an overall cascade deadline,
  a health endpoint.
- Gateway: database-backed API keys with per-key daily limits, a shared public daily cap and per-network signup limits.
- CI (lint, Python 3.9 to 3.12, SQL and gateway-engine tests, build check), HTTP API docs, an operations runbook,
  and a test suite that pins the 1.0.x public API.

### Changed
- Requires Python 3.9 or newer (was 3.8). Packaging moved from `setup.py` to `pyproject.toml`.
- The gateway returns a real `502` when every provider fails (it used to return `200` with `success: false`).
- Provider error text is no longer exposed to callers.
- Gateway provider ids `gemini-1.5-flash` and `cohere-command-r` are now `gemini-flash` and `cohere-command`, because
  their models are configurable. Anyone using `mode: "manual"` with the old ids must update them; the gateway answers
  400 and lists the valid ids.
- A response with none of the known answer fields now raises `BaalebosAPIError` instead of returning `str(data)`.
- `ai` with no prompt prints usage to stderr and exits 2 (it exited 1).
- Read timeouts are no longer retried; connection failures are.

### Security
- Database queries are parameterised; the `x-api-key` header is never interpolated into SQL.
- Signup IPs are stored only as a salted hash.
- The master-key check refuses an empty header, so an unset `GATEWAY_API_KEY` can't open the gateway.
- Successful gateway executions are not stored by the workflows.

## [1.0.1]
- README added to the PyPI project page.

## [1.0.0]
- Initial release: `BaalebosAI` client, `ai` CLI, typed exceptions.
