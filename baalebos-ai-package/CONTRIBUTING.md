# Contributing to Baalebos AI

Thanks for considering a contribution.

## Reporting issues

Open a GitHub Issue with: what you expected, what actually happened,
and steps to reproduce. Include your Python version and OS.

## Development setup

```bash
git clone https://github.com/baalebos-cloud/nexus-ai-gateway.git
cd nexus-ai-gateway
pip install -e .
```

## Pull requests

- Keep changes focused -- one logical change per PR.
- Update `CHANGELOG.md` under an "Unreleased" section.
- Never commit real API keys, tokens, or `.env` files. If you're testing
  against the live gateway, use your own auto-registered key.

## Security

If you find a security issue (e.g. a way to bypass rate limiting, or an
exposed secret), please open a private security advisory on GitHub
rather than a public issue.
