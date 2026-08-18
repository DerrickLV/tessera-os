# Architecture

## System context

Tessera OS is a control plane over business systems; it is not the system of
record. Microsoft 365, HubSpot, project systems, accounting systems, and GitHub
remain authoritative. Agents receive narrowly scoped context and propose actions
through typed tool interfaces.

```mermaid
flowchart LR
    U["Authorized user"] --> API["Tessera interface"]
    API --> O["Policy-aware orchestrator"]
    O --> R["Agent registry and router"]
    R --> S["Specialist agents"]
    S --> P["Permission and approval gateway"]
    P --> T["Typed integration tools"]
    T --> M["Systems of record"]
    O --> A["Trace, audit, and evaluation store"]
    P --> H["Human approver"]
    H --> P
```

## Runtime flow

1. Authenticate the user and resolve tenant, role, and project scope.
2. Normalize the request into `AgentRequest`; reject unauthorized scope early.
3. Route deterministically, with model-assisted classification added only after evals.
4. Give the selected specialist a bounded objective, evidence, and allowed actions.
5. Validate structured output, citations, policy, and proposed actions.
6. If an action is gated, pause with an approval packet. Otherwise synthesize.
7. Record trace, model/prompt versions, sources, decisions, usage, and approvals.

## Orchestration choice

The orchestrator uses the manager pattern: it owns the user interaction and calls
specialists. This prevents fragmented answers, centralizes policy, and makes
cross-functional work easier to audit. Direct agent-to-agent handoffs may be added
later only for workflows whose ownership truly transfers.

## Core components

- **Registry:** loads versioned agent manifests and prompt locations.
- **Router:** transparent keyword baseline suitable for offline tests.
- **Orchestrator:** chooses a specialist and controls live execution.
- **Policy boundaries:** evaluate identity, tenant/client/project scope, approval,
  approved proposal content, and fee authority before use.
- **Tool adapters (next):** typed read/write interfaces with idempotency and audit IDs.
- **Knowledge plane:** tenant/project-filtered retrieval with source ACLs.
- **Proposal plane:** access-controlled language, versioned templates, fee schedules,
  typed sections, citations, comparisons, internal review, and DOCX generation.
- **Contract and diligence plane:** approved clause playbooks, exact clause citations,
  claim classification, corroboration, source logs, and qualified-review queues.
- **Project-control plane:** development stage gates, construction exceptions, versioned
  schedules/costs, immutable baselines, safety escalation, and deterministic variance.
- **Capital plane:** reconciled model versions, deterministic underwriting metrics,
  covenant monitoring, sensitivities, and investment-review queues.
- **Sandbox action plane:** versioned low-risk workflows, exact approval packets,
  separation of duties, signed single-use tokens, idempotency and precondition checks,
  reversible receipts, kill switches, dead letters, monitoring, and tamper-evident audit.
- **Intelligence plane:** allowlisted offline sources, license and freshness policy,
  snapshot digests, corroborated findings, source diversity, cited briefs, and
  human-reviewed internal alerts.
- **Engineering plane:** isolated workspace definitions, repository-relative path
  boundaries, evidence-backed CI checks, PR-only change packets, and release gates.
- **Assurance plane:** versioned prompt, model, integration, and policy comparisons
  with deterministic quality, security, latency, cost, and evaluation-cadence gates.
- **Evaluation harness:** offline regression tests for routing, policy attacks,
  isolation, citations, approvals, and proposal commercial controls.

## Configuration

Two formats are in use, deliberately, and each is a single source of truth
loaded by exactly one place in the code — nothing here is duplicated across
formats:

- **JSON, loaded directly:** `agents/*.json` (`registry.py`) and
  `config/routing.json` (`router.py`). These define what the router and
  registry need at process start and stay simple key/value data.
- **YAML, loaded via `settings.py`:** `config/models.yaml`,
  `config/security.yaml`, and `config/integrations.yaml`. `settings.py`
  validates each against a Pydantic model and resolves any
  `${VAR:-default}` placeholder against the environment (used by
  `models.yaml` for `TESSERA_MODEL_DEFAULT` / `TESSERA_MODEL_HIGH_REASONING`).
  `orchestrator.py` reads `models.yaml` for model selection and run policy;
  `cli.py`'s `policy` and `integrations` commands surface `security.yaml` and
  `integrations.yaml` to an operator.

Do not add a second copy of either file in the other format — that was the
exact drift risk closed in the August 18, 2026 review. If a config value
needs to be both human-editable YAML and fast-loading JSON, generate one from
the other at build time rather than hand-maintaining both.

## Data model

Every run should carry `tenant_id`, `project_id`, `user_id`, role claims, correlation
ID, model and prompt versions, evidence IDs, allowed actions, proposed actions, and
approval state. These are security boundaries, not optional metadata.

## Production boundaries

The repository includes reference implementations for OIDC JWT validation, tenant and
project authorization, retrieval ACLs, exact-action approvals, rate limits, usage
budgets, DLP redaction, correlated audit traces, encrypted artifact retention, legal
holds, and tenant-scoped backup. They fail closed and keep production writes disabled.
They are not evidence that an actual deployment has configured a real identity provider,
managed key service, durable database, centralized monitoring, backups, or incident
ownership. Those administrator and human-validation gates are tracked in
`PRODUCTION_GATE_CHECKLIST.md`.

Phase 5 does not weaken this boundary. Its only executable adapter is an in-memory
synthetic record store whose targets must use `synthetic://`. Production action
adapters, credentials, and irreversible workflows are intentionally absent.
