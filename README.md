# Tessera OS

Tessera OS is an AI operating system for development, construction management,
capital, advisory, and internal operations. This repository includes the Phase 2
read-only pilot and the Phase 3 and Phase 4 manager foundations: a policy-aware
orchestrator, twelve specialist agents, ACL-preserving retrieval, human review
workflows, shared schemas, and offline document drafting.

## Status

**Stage:** Phase 6 — Intelligence and engineering scale foundation

**Current milestone:** Offline intelligence, PR-only engineering, and continuous assurance

**Safety posture:** Offline and draft-only; external delivery is disabled

## What is included

- A deterministic routing layer and OpenAI Agents SDK adapter
- Specifications and prompts for 12 core agents
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
- Architecture, governance, and phased implementation documentation

## Quick start

Prerequisites: Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m tessera_os.cli list
python -m tessera_os.cli route "Prepare my morning briefing"
pytest
```

To execute a live model call, set `OPENAI_API_KEY` and run:

```bash
python -m tessera_os.cli run "Summarize the current project risks"
```

The starter uses `gpt-5.6-terra` as the balanced default and reserves
`gpt-5.6-sol` for complex legal, diligence, and engineering work. Override either
with environment variables; validate quality and cost on representative Tessera
tasks before production use.

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
- [Contributing](CONTRIBUTING.md)

## License

Proprietary. Copyright Tessera. See [LICENSE](LICENSE).
