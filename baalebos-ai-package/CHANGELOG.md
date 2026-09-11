# Changelog

All notable changes to this project are documented here.

## [1.1.0] - Unreleased

### Added
- Zero-setup authentication: the CLI/SDK now auto-registers a unique key
  on first use instead of requiring a manually-obtained shared key.
- Per-key daily rate limiting on the gateway, protecting underlying
  free-tier provider quotas as usage grows.
- Proper PyPI package metadata (project URLs, long description from
  README, classifiers, license).

### Changed
- `BAALEBOS_API_KEY` environment variable still works exactly as before
  for existing team members -- it takes priority over auto-registration.

### Security
- No shared secret is embedded in the package source anywhere. Each
  install gets its own individually-tracked, individually-limited key.

## [1.0.0] - Initial release

- Basic CLI (`ai` command) and Python SDK wrapping the gateway.
- Cascading fallback across 9 free-tier LLM providers.
