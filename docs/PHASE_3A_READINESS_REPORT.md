# Phase 3A Proposal Manager readiness report

**Run date:** 2026-08-18

**Environment:** Local repository, offline synthetic execution

**Decision:** **READY WITH CONDITIONS** for controlled internal evaluation

## Executive summary

Phase 3A establishes an offline, draft-only Proposal Manager and shared document
foundation. It uses typed records and deterministic policy checks rather than a
live model or external service. Proposal language, templates, and fee schedules
are versioned and checked against tenant, client, and project access before use.
Unsupported qualifications, unapproved or expired pricing, and out-of-scope
records fail closed.

Generated drafts contain structured scope, deliverables, exclusions, assumptions,
schedule, staffing, and pricing. Their source IDs appear inline and in attached
evidence. Drafts can be compared, submitted to the existing durable human review
queue, and exported as valid Word OOXML. External delivery is explicitly disabled,
including after an internal reviewer accepts an item.

## Synthetic coverage

The fixture catalog contains two fictional clients (`client-northstar` and
`client-harbor`) and multiple fictional projects, including project-specific and
client-wide grants. It includes two versions of one proposal template, approved
qualifications and general language, separate approved fee schedules, and negative
records for an unapproved qualification and fee schedule. No real client, project,
person, account, credential, or price is present.

## Verification results

| Control | Result | Evidence |
|---|---|---|
| Tenant/client/project isolation | PASS | Unauthorized projects and client mismatches raise `ScopeDenied` before proposal content is returned. |
| Approved language only | PASS | Missing and unapproved qualification IDs cannot enter a draft. |
| Approved pricing only | PASS | Unapproved, expired, and unknown fee entries are rejected. |
| Structured proposal schema | PASS | All seven requested commercial/document sections have typed models. |
| Source citations | PASS | Structured items, approved language, qualifications, and price lines reference evidence IDs; dangling citations fail validation. |
| Prompt-injection handling | PASS | Retrieved instruction-like text is excluded from output and produces a safety warning. |
| Version comparison | PASS | Recursive structured changes are returned with before/after values. |
| Human review integration | PASS | Proposal drafts enter the SQLite queue as pending, project-scoped internal items. |
| External-delivery control | PASS | Delivery raises `ExternalDeliveryDisabled` even after review acceptance. |
| Word-ready generation | PASS | DOCX package integrity test passed; LibreOffice rendered both pages successfully and visual inspection found no clipping, overlap, or missing content. |
| Ruff | PASS | `ruff check .` completed with no findings. |
| Automated tests | PASS | 21 tests passed, including all Phase 2 regressions and eight Phase 3A tests. |

## Boundaries and conditions

- All workflows remain offline and draft-only.
- No external accounts, APIs, delivery channels, or real client information were used.
- Review acceptance is an internal content disposition, not authorization to send,
  publish, sign, or commit pricing.
- Contract Manager and Due Diligence Manager work has not begun.
- The deterministic generator proves policy and artifact mechanics. Before adding
  model-authored prose, add representative golden-set quality evaluation and verify
  citation entailment, unsupported-claim rate, latency, and cost.
- Before production use, add durable catalog storage, authenticated role/approver
  policy, retention and backup, audit reconstruction, and controlled outbound design.

## Readiness decision

Phase 3A is ready for internal, synthetic user evaluation under the stated
conditions. It is not approved for production data or external proposal delivery.
