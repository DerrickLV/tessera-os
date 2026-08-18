# Production readiness report

**Assessment date:** 2026-08-18

**Verdict:** The repository-owned hardening foundation is implemented and verified for
offline, synthetic, read-only, and draft-only use. Tessera OS is not approved for a
production deployment or for external actions.

## Implemented controls

- A FastAPI `/v1/route` boundary validates issuer, audience, signature algorithm,
  expiration, subject, tenant, project, and group claims. Production rejects symmetric
  JWT algorithms and API documentation endpoints are disabled.
- A central fail-closed gateway authorizes the authenticated tenant, project, user,
  routed agent, environment, and action. Safe read/draft actions are allowlisted;
  production writes and prohibited actions are denied. Supplying an approval ID alone
  never authorizes execution.
- Live orchestrator calls require an authenticated context and pass through the same
  policy gateway before any model call.
- Review items can require workflow-specific qualified groups, and the queue enforces
  the group at disposition time.
- Runtime controls provide per-tenant/user rate limits, tenant/workflow/day token and
  cost budgets, DLP-redacted errors, correlation traces, AES-GCM artifact encryption,
  retention, records-administrator legal hold, and tenant-scoped backup.
- CI uses immutable action revisions, Python 3.11 and 3.12, a compiled dependency lock,
  Ruff, all tests, a local secret-pattern scan, wheel construction, and dependency audit.
  Dependabot, CODEOWNERS, a security policy, and contribution rules are included.

## Verification evidence

The clean Python 3.12 environment passed Ruff, the repository secret-pattern scan, and
all 121 offline tests on 2026-08-18. The connected dependency audit reported no known
vulnerabilities after upgrading `cryptography` to 50.0.0. A later repeat could not
reach PyPI from the sandbox; CI repeats the audit with network access.

Tests cover scope and tenant isolation, unsupported claims, stale and conflicting
evidence, baseline protection, prompt injection, citations, approval bypass, reviewer
roles, JWT and project authorization, rate limits, usage budgets, DLP, trace isolation,
encrypted retention, legal hold, and tenant backup.

## Blocking gates

The following cannot be completed truthfully from source code and remain blockers:

1. Configure and test a real OIDC identity provider, groups, lifecycle, and emergency
   access process.
2. Select managed compute, database, key/secret storage, monitoring, and backup services;
   perform restore and key-rotation tests with named owners.
3. Enable repository branch/ruleset protection and security scanning in GitHub. The
   current private-repository plan rejected ruleset configuration during the audit.
4. Run representative Phase 2–6 pilots with accountable proposal, counsel, diligence,
   development, construction, investment, security, records, and engineering reviewers.
5. Approve measurable quality, citation, unsupported-claim, issue-recall, latency, cost,
   recovery, and reviewer-time thresholds and record results.
6. Review source licenses, retention schedules, data processing obligations, threat
   model, incident process, and each proposed external or write action.

Until every applicable checklist item has owner, evidence, date, and approval, keep the
system offline/synthetic and all external delivery, submissions, consultant direction,
baseline mutation, repository writes, deployments, and financial/contractual actions
disabled.
