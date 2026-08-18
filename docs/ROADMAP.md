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

## Phase 1 — Foundation (implemented; deployment validation pending)

**Exit criteria:** reproducible local environment; registry and routing tests pass;
all agent prompts/specs are reviewed; traces contain required run metadata.

- Complete policy gateway and typed output validation.
- Add a durable API/service boundary and authenticated user context.
- Add model/prompt version registry, structured logging, usage budgets, and tracing.
- Implement evaluation harness for routing, citations, injection, and approvals.

Implementation now includes a read-only authenticated FastAPI boundary, centralized
fail-closed runtime authorization, correlated audit traces, rate limits, usage budgets,
DLP redaction, encrypted retained artifacts, legal holds, tenant-scoped backup, locked
dependencies, and hardened CI. Production exit still requires real identity-provider
configuration, managed keys and storage, administrator-enforced repository controls,
restore and incident exercises, and representative human pilot acceptance.

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

## Phase 3B — Contract and Due Diligence document workflows (implemented; pilot validation pending)

**Recommended agents:** Contract and Due Diligence Managers.

**Exit criteria:** reviewer time reduction demonstrated; issue-recall and unsupported-
claim targets met; every outbound artifact passes human approval.

- Implemented versioned, approved clause playbooks, exact clause citations, risk
  comparison, fallback language, and mandatory legal-review queues.
- Implemented reproducible diligence reports separating verified facts, allegations,
  and open items, with material-fact corroboration and protected-trait controls.
- Added two-client synthetic fixtures and legal/commercial, diligence, isolation,
  stale evidence, injection, citation, and approval-bypass evaluation coverage.

Production exit criteria still require representative counsel and diligence-reviewer
acceptance testing, approved production playbooks and taxonomies, retention controls,
and measured issue-recall, unsupported-claim, latency, cost, and reviewer-time targets.

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

## Phase 4B — Construction and capital controls (implemented; pilot validation pending)

**Recommended agents:** Construction and Capital Managers.

**Exit criteria:** reconciled project/model data; forecast lineage; professional
review controls; zero autonomous safety, contractual, or financial actions.

- Implemented typed construction schedule, cost, RFI/submittal, change, and safety
  controls with deterministic exception calculations and urgent human escalation.
- Implemented reconciled, versioned capital models with deterministic DSCR, LTV,
  equity multiple, covenant, and sensitivity calculations.
- Added internal construction and investment review queues; field directives, change
  approvals, notices, external communications, term acceptance, forecast publication,
  and funds movement remain disabled.
- Added two-client synthetic fixtures and isolation, reconciliation, citation,
  injection, calculation, safety, and approval-bypass evaluation coverage.

Production exit criteria still require authoritative read-only adapter design,
qualified construction and investment-review acceptance testing, production identity
and audit controls, and measured quality, latency, cost, and reviewer-time targets.

## Phase 5 — Gated actions and automation (sandbox foundation implemented; production blocked)

**Recommended agents:** Automation Manager and approved write paths for other agents.

**Exit criteria:** scoped approvals, idempotency, rollback, kill switches, audit
reconstruction, and incident exercises all pass in a sandbox and limited production.

- Implemented a durable exact-action approval store with separation of duties,
  expiring signed tokens, exact payload/target binding, and single-use nonces.
- Enabled one versioned, reversible, low-risk synthetic record-tag workflow against
  an in-memory sandbox adapter; no production adapter or credential path exists.
- Implemented idempotency binding, optimistic preconditions, separately approved
  rollback actions, tenant/action kill switches, dead-letter capture, monitoring
  metrics, and tenant-scoped hash-chained audit reconstruction.
- Added two-client synthetic workflow fixtures and tests for cross-scope access,
  over-permission, expiry, tampering, replay, approval bypass, payload substitution,
  prompt injection, state conflicts, rollback, kill switches, dead letters, and audit
  tampering.

The sandbox portion of the exit criteria passes. Limited-production validation is
blocked pending completion of prior-phase pilot gates, approved production identity
and secret management, authoritative adapter design, retention and recovery controls,
operational ownership, incident exercises in an approved environment, and a separate
authorization decision for each proposed low-risk production workflow.

## Phase 6 — Intelligence and engineering scale (offline foundation implemented; production blocked)

**Recommended agents:** Intelligence Agent and Codex Engineering Agent.

**Exit criteria:** approved source and license governance; isolated CI infrastructure
and repository identity/permission design reviewed separately from this codebase;
measured quality, cost, and latency targets per artifact kind; zero autonomous
intelligence retrieval, repository writes, releases, or assurance-gated activation.

- Implemented tenant/client/project-scoped monitored source lists restricted to
  approved `offline://` sources, with license approval, content digests, per-source
  freshness policies, source diversity, corroboration, cited briefs, and internal alerts.
- Implemented isolated engineering workspace definitions, traversal-free allowed paths,
  CI evidence, deterministic PR-readiness gates, and blocked dependency, production
  configuration, destructive, direct-main, secret, and deployment actions.
- Implemented deterministic recurring comparison gates for prompt, model, integration,
  and policy candidates across accuracy, citation correctness, unsupported claims,
  latency, cost, cross-project isolation, prompt injection, approval bypass, and
  over-permission tests.
- Added two-client synthetic fixtures and adversarial tests for scope isolation,
  freshness, source integrity and licensing, source diversity, injection, path escape,
  unsafe changes, failed CI, release bypass, evaluation regression, cadence, citations,
  and activation bypass.

Production intelligence retrieval, source purchasing, alert delivery, repository writes,
pull-request creation, release/deployment, and artifact activation remain disabled.
Production exit requires representative acceptance testing, approved source and license
governance, isolated CI infrastructure, repository identity and permission design,
measured quality/cost/latency targets, and separate approval for every external action.

## Initial backlog

1. Completed: define `tenant_id` and project ACL contracts across shared schemas.
2. Completed: implement policy decisions, qualified review, and approval packets.
3. Completed in code: add a read-only FastAPI service with an OIDC-ready boundary.
4. Completed: add structured output types for each specialist.
5. Completed: add multi-client synthetic fixtures, adversarial evaluations, and CI.
6. Completed in code: implement the GET-only, ACL-preserving SharePoint boundary.
7. Pending external validation: pilot cited project-status generation with an approved
   project team and record measured quality, latency, cost, and reviewer acceptance.
