# Implementation roadmap

The roadmap prioritizes trust and repeatable value before breadth. Dates should be
set after owners, data access, and pilot projects are confirmed.

## Phase 0 — Decisions and controls

**Exit criteria:** named product owner and approvers; selected pilot project;
approved data classification, retention, identity, and audit design; baseline evals.

- Confirm authoritative systems, users, roles, and tenant/project boundaries.
- Select three pilot workflows and quantify current time, quality, and risk.
- Approve action tiers and human review responsibilities.
- Create golden datasets using sanitized or synthetic content.

## Phase 1 — Foundation (this repository)

**Exit criteria:** reproducible local environment; registry and routing tests pass;
all agent prompts/specs are reviewed; traces contain required run metadata.

- Complete policy gateway and typed output validation.
- Add a durable API/service boundary and authenticated user context.
- Add model/prompt version registry, structured logging, usage budgets, and tracing.
- Implement evaluation harness for routing, citations, injection, and approvals.

## Phase 2 — Read-only pilot (implemented; deployment validation pending)

**Recommended agents:** Knowledge Manager, Executive Assistant, Project Manager.

**Exit criteria:** no scope leaks; citation target met; pilot users accept outputs;
cost and latency within agreed budgets; documented support and incident process.

- Connect SharePoint and Microsoft Graph with read-only delegated scopes.
- Ingest authorized documents with ACL-preserving retrieval.
- Deliver morning briefings and project status drafts to a review queue.

Implementation includes a delegated, GET-only Microsoft Graph boundary, a
fail-closed ACL-preserving knowledge index, cited draft workflows, and a durable
SQLite review queue. Production exit criteria still require tenant-specific app
registration, approved SharePoint sites, pilot acceptance, and measured budgets.

## Phase 3A — Proposal Manager foundation (implemented; pilot validation pending)

**Recommended agent:** Proposal Manager.

**Exit criteria:** reviewer time reduction demonstrated; unsupported-claim and
citation targets met; every proposal remains internal until a future delivery
control is separately designed, approved, and tested.

- Implemented approved proposal-language records with tenant, client, and project access controls.
- Implemented versioned proposal templates and approved, effective-dated fee schedules.
- Added typed scope, deliverable, exclusion, assumption, schedule, staffing, and pricing models.
- Added deterministic cited draft generation, version comparison, human review submission,
  and Word-ready DOCX artifacts.
- Added two-client, multiple-project synthetic fixtures and policy regression tests.
- External delivery remains disabled; all outputs are draft-only and offline.

Production exit criteria still require representative human acceptance testing,
measured reviewer-time savings, model-quality evaluation if model drafting is added,
retention/backup controls, and a separately approved outbound-delivery design.

## Phase 3B — Contract and Due Diligence document workflows (not started)

**Recommended agents:** Contract and Due Diligence Managers.

**Exit criteria:** reviewer time reduction demonstrated; issue-recall and unsupported-
claim targets met; every outbound artifact passes human approval.

- Version clause playbooks and diligence taxonomies.
- Add document comparison, structured extraction, and source-linked reports.
- Add legal/commercial and diligence-specific evaluation suites.

## Phase 4A — Development Manager and shared project controls (implemented; pilot validation pending)

**Recommended agent:** Development Manager.

**Exit criteria:** reconciled project-control data; cited and current stage-gate
evidence; immutable approved baselines; deterministic variance calculations; zero
autonomous submissions, consultant direction, approvals, or baseline changes.

- Implemented structured projects, milestones, stage gates, approvals, constraints,
  consultants, deliverables, schedules, budgets, and RAID registers.
- Implemented versioned schedules and budgets with immutable approved baselines.
- Added entitlement, permit, utility, and agency approval matrices and consultant
  responsibility/deliverable tracking.
- Added freshness-aware, cited stage-gate readiness and deterministic schedule and
  budget variance calculations.
- Integrated development drafts and baseline-change requests with the durable human
  review queue; all external and approval actions remain disabled.
- Added two-client, three-project synthetic fixtures and policy regression tests.

Production exit criteria still require authoritative read-only adapter design,
representative human acceptance testing, defined freshness policies by record class,
retention/backup controls, and measured quality, latency, and reviewer-time targets.

## Phase 4B — Construction and capital controls (not started)

**Recommended agents:** Construction and Capital Managers.

**Exit criteria:** reconciled project/model data; forecast lineage; professional
review controls; zero autonomous safety, contractual, or financial actions.

- Add construction schedule, cost, RFI/submittal, underwriting, and covenant adapters.
- Build exception dashboards and decision packets.
- Validate quantitative calculations outside the model where possible.

## Phase 5 — Gated actions and automation

**Recommended agents:** Automation Manager and approved write paths for other agents.

**Exit criteria:** scoped approvals, idempotency, rollback, kill switches, audit
reconstruction, and incident exercises all pass in a sandbox and limited production.

- Introduce a durable approval queue and signed action tokens.
- Enable one reversible, low-risk write workflow at a time.
- Add monitoring, dead-letter queues, replay protection, and change management.

## Phase 6 — Intelligence and engineering scale

**Recommended agents:** Intelligence Agent and Codex Engineering Agent.

- Add monitored source lists, freshness policies, and intelligence alerts.
- Add isolated engineering workspaces, CI checks, PR-only changes, and release gates.
- Continuously re-evaluate prompts, models, integrations, and policy attacks.

## Initial backlog

1. Define `tenant_id` and project ACL contract across every schema.
2. Implement policy decision and approval packet schemas.
3. Add FastAPI service with SSO-ready authentication boundary.
4. Add structured output types for each specialist.
5. Add synthetic eval fixtures and CI.
6. Implement read-only SharePoint retrieval adapter.
7. Pilot cited project-status generation with one project team.
