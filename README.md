# Tessera OS

Tessera OS is an AI operating system for development, construction management,
capital, advisory, and internal operations. This repository includes the Phase 2
read-only pilot and the Phase 3 and Phase 4 manager foundations: a policy-aware
orchestrator, thirteen specialist agents, ACL-preserving retrieval, human review
workflows, shared schemas, and offline document drafting.

## Status

**Stage:** Phase 6 complete; production-readiness hardening implemented

**Current milestone:** Phase 7C single-user private portal deployment and validation

**Safety posture:** Offline by default; production pilot is read-only and external delivery is disabled

## What is included

- A deterministic routing layer and OpenAI Agents SDK adapter
- Specifications and prompts for 13 core agents
- Shared request, response, evidence, and approval schemas
- Central model, routing, security, and integration configuration
- A local CLI and smoke tests that run without API credentials
- Read-only Microsoft Graph/SharePoint adapter, ACL-preserving knowledge index,
  and durable review queue for morning briefing and project-status drafts
- Client/project-scoped approved proposal language, versioned templates, and
  versioned approved fee schedules
- Structured proposal scope, deliverables, exclusions, assumptions, schedule,
  staffing, and pricing with source-linked citations
- Proposal version comparison, review-queue submission, and deterministic DOCX
  generation suitable for Word
- Synthetic proposal fixtures for two fictional clients and multiple projects,
  plus isolation, hallucination, pricing, injection, citation, and delivery tests
- Structured development projects, milestones, stage gates, approvals, constraints,
  consultants, deliverables, schedules, budgets, and RAID registers
- Immutable approved baselines with versioned schedule and budget forecasts and
  deterministic schedule/budget variance calculations
- Entitlement, permit, utility, and agency matrices; consultant responsibility
  tracking; and freshness-aware, cited stage-gate readiness recommendations
- Internal human-review and baseline-change queues with external submissions,
  consultant direction, gate approvals, and baseline mutation disabled
- Synthetic development fixtures for two fictional clients and three projects,
  plus Phase 4A policy and calculation regression tests
- Cited Contract Manager clause comparison against approved playbooks, with exact
  clause locations, legal-uncertainty labels, and counsel review queues
- Reproducible Due Diligence Manager reports that separate verified facts,
  allegations, and open items; corroborate material facts; and prohibit
  protected-trait inference
- Construction Manager exception dashboards for safety, quality, schedule, cost,
  RFIs, submittals, and change exposure, including urgent human safety escalation
- Capital Manager model reconciliation, deterministic underwriting metrics,
  covenant tests, and downside/base/upside sensitivities
- Synthetic Phase 3B and 4B fixtures for two clients and multiple projects, with
  cross-scope, citation, injection, version, calculation, and approval-bypass tests
- Versioned low-risk sandbox workflows with exact-action approval packets,
  separation of duties, expiring signed tokens, and single-use replay protection
- Deterministic idempotency and precondition checks, reversible action receipts,
  tenant-scoped kill switches, dead-letter handling, control metrics, and
  hash-chained audit reconstruction
- A synthetic in-memory record adapter for one reversible tag workflow; production
  targets, credentials, external actions, and irreversible writes remain disabled
- Allowlisted offline intelligence sources with approved licenses, content digests,
  per-source freshness policies, source diversity, corroboration, cited briefs, and
  internal human-reviewed alerts
- Isolated engineering workspace definitions, path controls, cited CI evidence,
  deterministic PR-readiness gates, and blocked dependency, production-config,
  destructive, direct-main, and deployment actions
- Deterministic recurring evaluation gates for prompt, model, integration, and policy
  candidates across quality, citations, unsupported claims, latency, cost, isolation,
  injection, approvals, and permissions
- A read-only FastAPI boundary with OIDC JWT validation, authenticated tenant/project
  scope, a fail-closed runtime policy gateway, rate limiting, and trace correlation
- A localhost-only synthetic operator console API and browser UI for scoped projects,
  agent discovery, policy visibility, deterministic routing, and durable human review
- A persistent interactive pilot workspace that runs deterministic project workflows,
  creates cited draft artifacts with quality metrics and audit history, and submits them
  to qualified human review without model calls or external actions
- A synthetic Structure Manager that produces cited entity/governance recommendations,
  blocks stale or unresolved inputs, and permits agreement drafting only from the exact
  qualified-counsel-approved recommendation version
- Qualified reviewer roles, DLP redaction, deterministic usage budgets, encrypted
  artifact retention/legal hold, and tenant-scoped backup primitives
- Locked dependencies, SHA-pinned CI actions, dependency auditing, secret-pattern
  scanning, CODEOWNERS, Dependabot configuration, and Python 3.11/3.12 CI coverage
- Architecture, governance, and phased implementation documentation

## Quick start

Prerequisites: Python 3.11+.

```bash
/opt/homebrew/bin/python3.12 -m venv .venv  # macOS; any Python 3.11+ works
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.lock
pip install --no-deps --no-build-isolation .
cp .env.example .env
python -m tessera_os.cli list
python -m tessera_os.cli route "Prepare my morning briefing"
python -m tessera_os.cli policy
python -m tessera_os.cli integrations
pytest
```

`policy` and `integrations` read `config/security.yaml` and
`config/integrations.yaml` respectively, so an operator can see the active
security posture and integration status without opening a YAML file.

To use the synthetic browser console:

```bash
export TESSERA_ENV=sandbox
tessera serve
```

Open `http://127.0.0.1:8000`. The console serves its own API, uses only the
versioned synthetic fixture, persists review decisions under ignored
`data/runtime/`, refuses bearer credentials, and fails closed in production. Use
**Projects** to run a defined synthetic workflow, use **Ask** only to preview routing,
inspect cited or insufficient-evidence results under **Drafts**, and submit them to
**Review Queue** for acceptance, rejection, or recorded amendment and acceptance.
Offline API guidance is available at `http://127.0.0.1:8000/api/docs`; the OpenAPI
contract is at `http://127.0.0.1:8000/api/openapi.json`.

The Microsoft 365 pilot connection is implemented but disabled by default. It requests
only delegated `User.Read` and `Sites.Selected`, stores its MSAL cache encrypted, and
resolves SharePoint locations only through approved project mappings. Complete the
[Microsoft 365 connection plan](docs/MICROSOFT_365_CONNECTION_PLAN.md) before enabling it.

A deployment package for a single-user, invite-only production pilot is also included:
the static private portal in `web/tessera-portal.html`, its locked-down FastAPI layer in
`src/tessera_os/portal.py`, a Render Blueprint and Docker image, and a separate Netlify
site definition. It is intentionally not connected or deployed from the repository.
Follow the [portal deployment guide](docs/PORTAL_DEPLOYMENT.md) for the required
administrator-controlled setup in Entra, SharePoint, Render, Netlify, and Porkbun.

Run Tessera commands from the repository checkout. A normal local install is used
because some Homebrew Python builds ignore hidden editable-install path files. Set
`TESSERA_ROOT` only when deliberately launching from another directory.

To execute a live model call, set `OPENAI_API_KEY` and run:

```bash
python -m tessera_os.cli run "Summarize the current project risks" \
  --tenant-id synthetic-tenant --project-id synthetic-project --user-id local-user
```

The starter uses `gpt-5.6-terra` as the balanced default and reserves
`gpt-5.6-sol` for complex legal, diligence, and engineering work, both defined
in `config/models.yaml`. Override either with the `TESSERA_MODEL_DEFAULT` /
`TESSERA_MODEL_HIGH_REASONING` environment variables; validate quality and cost
on representative Tessera tasks before production use.

## Repository map

```text
config/              Runtime, routing, integration, and policy configuration
docs/                Architecture, governance, roadmap, and integration contracts
prompts/             Versioned orchestrator and specialist instructions
specs/agents/        Human-readable agent charters and acceptance criteria
src/tessera_os/      Runnable Python package
tests/               Offline routing and registry tests
fixtures/proposals/  Synthetic Phase 3A clients, language, templates, and fees
fixtures/development/ Synthetic Phase 4A development project-control records
fixtures/phase3b/    Synthetic contract and diligence records
fixtures/phase4b/    Synthetic construction and capital records
fixtures/automation/ Synthetic Phase 5 workflows, targets, and records
fixtures/phase6/     Synthetic intelligence, engineering, and assurance records
fixtures/console/    Synthetic operator-console clients, projects, and review items
fixtures/clause_library/ Synthetic drafting clauses and Structure Manager samples
web/                 Local operator console served by FastAPI
```

## Design principles

1. The orchestrator owns the final answer and calls specialists as tools.
2. Agents recommend; humans authorize external or high-impact changes.
3. Every material claim carries evidence or an explicit uncertainty label.
4. Tenant, project, and client boundaries are enforced before retrieval.
5. Prompts and policies are versioned; runs are traceable and auditable.
6. Legal, investment, and safety outputs are decision support—not autonomous decisions.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Governance and safety](docs/GOVERNANCE.md)
- [Implementation roadmap](docs/ROADMAP.md)
- [Integration contracts](docs/INTEGRATIONS.md)
- [Pilot operations](docs/PILOT_OPERATIONS.md)
- [Phase 3A readiness report](docs/PHASE_3A_READINESS_REPORT.md)
- [Phase 4A readiness report](docs/PHASE_4A_READINESS_REPORT.md)
- [Phase 3B readiness report](docs/PHASE_3B_READINESS_REPORT.md)
- [Phase 4B readiness report](docs/PHASE_4B_READINESS_REPORT.md)
- [Phase 0–4 foundation audit](docs/PHASE_0_4_FOUNDATION_AUDIT.md)
- [Phase 5 readiness report](docs/PHASE_5_READINESS_REPORT.md)
- [Phase 6 readiness report](docs/PHASE_6_READINESS_REPORT.md)
- [Phase 7A readiness report](docs/PHASE_7A_READINESS_REPORT.md)
- [Phase 7B readiness report](docs/PHASE_7B_READINESS_REPORT.md)
- [Production readiness report](docs/PRODUCTION_READINESS_REPORT.md)
- [Production gate checklist](docs/PRODUCTION_GATE_CHECKLIST.md)
- [Incident exercise runbook](docs/INCIDENT_EXERCISE_RUNBOOK.md)
- [Console API](docs/CONSOLE_API.md)
- [Microsoft 365 and SharePoint connection plan](docs/MICROSOFT_365_CONNECTION_PLAN.md)
- [Private portal deployment](docs/PORTAL_DEPLOYMENT.md)
- [Private portal readiness report](docs/PORTAL_READINESS_REPORT.md)
- [Contributing](CONTRIBUTING.md)

## License

Proprietary. Copyright Tessera. See [LICENSE](LICENSE).
