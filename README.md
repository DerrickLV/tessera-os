# Tessera OS

Tessera OS is an AI operating system for development, construction management,
capital, advisory, and internal operations. This repository includes the Phase 2
read-only pilot and Phase 3A Proposal Manager foundation: a policy-aware
orchestrator, twelve specialist agents, ACL-preserving retrieval, human review
workflows, shared schemas, and offline document drafting.

## Status

**Stage:** Phase 3A — Proposal Manager foundation

**Current milestone:** Cited, versioned, Word-ready proposal drafts

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
- [Contributing](CONTRIBUTING.md)

## License

Proprietary. Copyright Tessera. See [LICENSE](LICENSE).
