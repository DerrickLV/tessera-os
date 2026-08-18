# Synthetic console API

The operator console is an offline sandbox for evaluating Tessera workflows with
versioned synthetic data. It is not a production server and has no external-action
endpoints.

## Start

Use Python 3.11 or newer. From the repository checkout, install and run:

```bash
pip install -r requirements.lock
pip install --no-deps --no-build-isolation .
export TESSERA_ENV=sandbox
tessera serve
```

Open `http://127.0.0.1:8000`. Offline API guidance is at `/api/docs`, and the machine-
readable OpenAPI contract is at `/api/openapi.json`. No external documentation assets
are loaded.

## Contract

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Sandbox mode and disabled-write status |
| GET | `/v1/console/bootstrap` | UI session, dashboard, projects, agents, policy, integrations, and reviews |
| GET | `/v1/session` | Fixed synthetic operator identity and scope |
| GET | `/v1/clients` | Clients visible through scoped projects |
| GET | `/v1/projects` | Projects in the synthetic identity scope |
| GET | `/v1/projects/{project_id}` | One scope-checked project |
| GET | `/v1/agents` | Versioned agent manifest summaries |
| GET | `/v1/policy` | Validated `config/security.yaml` |
| GET | `/v1/integrations` | Validated `config/integrations.yaml` |
| POST | `/v1/route` | Deterministic, policy-checked routing preview |
| GET | `/v1/reviews` | Scoped queue, optionally filtered by `status` |
| GET | `/v1/reviews/{item_id}` | One scope-checked review item |
| POST | `/v1/reviews/{item_id}/accept` | Internal qualified decision with required reason |
| POST | `/v1/reviews/{item_id}/reject` | Internal qualified decision with required reason |

Decision bodies use `{"reason": "..."}`. Accepted and rejected transitions are final.
Qualified workflow groups and separation of duties are enforced by `ReviewQueue`.

## Boundaries

- The server binds to `127.0.0.1` by default and trusts only localhost/test hosts.
- The console refuses to start in production and refuses bearer credentials.
- All evidence locators are `offline://`; no production connector is called.
- Review decisions write only to ignored local SQLite state under `data/runtime/`.
- Content from API records is escaped before insertion into the UI.
- There are no send, publish, submit, deploy, funds, baseline-mutation, or external-write
  endpoints.

## Verification

The console integration raises the repository suite to 131 offline tests. Coverage
includes bootstrap shapes, scope denial, prompt injection, absent external-action
routes, qualified decisions, final-transition enforcement, fixture reseeding,
credential refusal, invalid input, production startup denial, offline locators, CLI
startup, and the UI/API contract. Browser verification covers initial load, backend
routing, and a persisted review decision.
