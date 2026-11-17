# Contributing

Issues and pull requests are welcome.

```bash
git clone https://github.com/baalebos-cloud/nexus-ai-gateway.git
cd nexus-ai-gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .
cd tests/node && npm install && npm test     # SQL + gateway engine tests
```

- The workflow JSON in `n8n/*.workflow.json` is generated. Edit `n8n/gateway_engine.js`, `n8n/client_ip.js`,
  `n8n/build_error.js` or `sql/*.sql`, then run `python3 n8n/build_workflows.py`. The tests fail if the JSON is stale.
- Never put real keys in the repo, in tests or in issues. Never build SQL by string interpolation; use `$1`-style
  parameters (a test enforces this).
- Add an entry under "Unreleased" in `CHANGELOG.md`.
- Security problems: please open a private security advisory on GitHub rather than a public issue.
