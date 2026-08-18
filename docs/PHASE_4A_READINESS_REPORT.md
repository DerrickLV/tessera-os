# Phase 4A readiness report

**Assessment date:** 2026-08-18

**Verdict:** Ready as an offline, synthetic, read-only, draft-only foundation.
Not ready for production data, external actions, or autonomous approvals.

## Delivered scope

Phase 4A adds a Development Manager control plane covering structured development
projects, milestones, stage gates, approval matrices, constraints, consultants,
deliverables, schedules, budgets, and risk, issue, decision, and dependency
registers. Schedules and budgets are versioned, approved baselines are immutable,
and forecast variance is calculated in deterministic Python using dates and
`Decimal` values.

The approval matrix distinguishes entitlement, permit, utility, and agency records.
Consultants have explicit disciplines, responsibilities, owners, and tracked
deliverables. Stage-gate evaluation checks exact record statuses, citation presence,
and evidence age before returning `ready`, `not_ready`, or
`insufficient_evidence`. Every result remains a draft requiring human review.

## Control evidence

- Authorization fails closed on tenant, client, and project before returning data.
- Completed and approved status claims require source evidence.
- Missing or evidence older than the configured freshness window cannot support a
  ready gate recommendation.
- Conflicting schedule/budget versions and incompatible baseline/current record sets
  fail closed.
- Approved baselines cannot be replaced. Requested changes create internal pending
  review items and do not mutate a baseline.
- Retrieved prompt-injection text is treated as untrusted data, omitted from rendered
  output, and flagged.
- Application submission, consultant direction, gate approval, and every other
  external development action are disabled.
- Review records retain project scope, creator, workflow, evidence, and disposition
  metadata through the existing durable SQLite queue.

## Synthetic evaluation coverage

The fixture set contains two fictional clients and three fictional projects:
Northstar / Aurora, Northstar / Solstice, and Harbor / Tidepool. No production or
real-project information is included.

The Phase 4A suite covers cross-project and cross-client isolation, unsupported
status claims, stale evidence, conflicting schedules, unauthorized baseline
changes, prompt injection, citation rendering, deterministic date and monetary
variance, human review, and approval-bypass attempts.

## Verification

Executed with the bundled Python 3.12 runtime required by the repository:

```text
python -m ruff check src tests
All checks passed!

python -m pytest -q
30 passed in 0.15s
```

## Remaining gates before production

1. Define authoritative systems and design separately approved, least-privilege,
   read-only adapters; Phase 4A includes no production connection.
2. Establish record-specific freshness standards with accountable development,
   permitting, finance, and professional reviewers.
3. Run representative human acceptance tests and measure reviewer time, correctness,
   citation quality, latency, and cost.
4. Add durable production identity, encryption, retention, backup, observability,
   incident response, and audit reconstruction controls.
5. Design and test any future action path separately with scoped approvals,
   idempotency, rollback, and explicit authority. Phase 4A does not authorize one.
6. Keep Construction and Capital Managers out of scope until Phase 4B is separately
   designed, implemented, and approved.
