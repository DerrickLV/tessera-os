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
| GET | `/v1/console/bootstrap` | UI session, configuration, reviews, and pilot artifacts |
| GET | `/v1/integrations/microsoft/status` | Read connection state without exposing tokens |
| POST | `/v1/integrations/microsoft/connect` | Start the state-bound delegated authorization flow |
| POST | `/v1/integrations/microsoft/disconnect` | Remove accounts and the encrypted local token cache |
| GET | `/v1/session` | Fixed synthetic operator identity and scope |
| GET | `/v1/clients` | Clients visible through scoped projects |
| GET | `/v1/projects` | Projects in the synthetic identity scope |
| GET | `/v1/projects/{project_id}` | One scope-checked project |
| GET | `/v1/agents` | Versioned agent manifest summaries |
| GET | `/v1/policy` | Validated `config/security.yaml` |
| GET | `/v1/integrations` | Validated `config/integrations.yaml` |
| POST | `/v1/route` | Deterministic, policy-checked routing preview |
| POST | `/v1/workspace/run` | Run one fixture-backed project workflow and persist a cited draft |
| POST | `/v1/workspace/compare` | Compare deterministic and flag-gated live contract drafts |
| GET | `/v1/projects/{project_id}/workflows` | List defined workflows for a scoped project |
| GET | `/v1/projects/{project_id}/controls` | Read synthetic RAID and variance state |
| GET | `/v1/artifacts` | List scoped pilot artifacts, optionally by project |
| GET | `/v1/artifacts/{artifact_id}` | Read one scoped artifact and synchronized review state |
| POST | `/v1/artifacts/{artifact_id}/submit` | Idempotently create an internal human-review item |
| POST | `/v1/workspace/reset` | Reset local synthetic artifacts and fixture reviews with exact confirmation |
| POST | `/v1/reviews/{id}/amend-and-accept` | Preserve the original and record a human-approved amendment |
| GET | `/v1/pilot/export` | Export finalized, categorized review labels as JSON |
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
- Pilot artifacts are deterministic fixture outputs; no model or Microsoft API is called.
- Content from API records is escaped before insertion into the UI.
- There are no external send, publish, filing/application submission, deploy, funds,
  baseline-mutation, or production-write endpoints. Artifact submission is internal
  and creates only a review-queue record.

## Verification

The console and Phase 7A integration are covered by the offline repository suite. Coverage
includes bootstrap shapes, scope denial, prompt injection, absent external-action
routes, qualified decisions, final-transition enforcement, fixture reseeding,
credential refusal, invalid input, production startup denial, offline locators, artifact
persistence, idempotent review submission, reset confirmation, audit synchronization,
CLI startup, and the UI/API contract.
