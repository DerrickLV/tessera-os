# Contributing

1. Create a focused branch and keep changes small.
2. Never commit credentials, client data, contracts, or production exports.
3. Update the relevant agent specification and prompt together.
4. Add or update tests for routing, schemas, tools, and policies.
5. Run `ruff check .` and `pytest` before opening a pull request.
6. Document any new external permission and default it to read-only.
7. Never add a duplicate `.json`/`.yaml` copy of a config or manifest file.
   `agents/*.json` and `config/routing.json` are canonical; `config/models.yaml`,
   `config/security.yaml`, and `config/integrations.yaml` are canonical and
   loaded via `settings.py`. See "Configuration" in `docs/ARCHITECTURE.md`.

Changes to approval policy, tenant isolation, retention, or legal/investment
guardrails require an owner review recorded in the pull request.
