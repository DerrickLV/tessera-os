# Contributing

1. Create a focused branch and keep changes small.
2. Never commit credentials, client data, contracts, or production exports.
3. Update the relevant agent specification and prompt together.
4. Add or update tests for routing, schemas, tools, and policies.
5. Run `ruff check .` and `pytest` before opening a pull request.
6. Document any new external permission and default it to read-only.

Changes to approval policy, tenant isolation, retention, or legal/investment
guardrails require an owner review recorded in the pull request.
