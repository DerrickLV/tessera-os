# Phase 2 synthetic pilot-readiness report

**Run date:** 2026-08-18

**Environment:** Local repository, offline synthetic execution

**Decision:** **READY WITH CONDITIONS** for a controlled Phase 2 pilot

## Executive summary

A complete synthetic pilot was run for the Knowledge Manager, Executive Assistant,
and Project Manager using two fictional users and two fictional projects. All data,
tokens, URLs, calendar events, messages, and documents were invented for this run.
No external account, network service, live model, or production configuration was used.

The initial run passed eighteen checks and exposed two review-queue defects. Both were
remediated and the complete synthetic scenario was rerun: **20 checks passed and none
failed**. Tenant/project/user filtering, document ACLs, fail-closed retrieval, source
evidence, review submission and disposition, draft labeling, audit metadata, and
exposed read-only integration operations now behave as intended.

## Synthetic scenario

| Fictional user | Authorized project | Group | Synthetic sources |
|---|---|---|---|
| `ava-fictional` | `project-aurora` | `aurora-team` | User-ACL document, group-ACL document, calendar event, email |
| `ben-fictional` | `project-borealis` | `borealis-team` | User-ACL document, calendar event, email |

Negative fixtures included a cross-project document, a cross-tenant document, a
document restricted to the other user, and a document with no ACL. The Graph adapter
used an injected in-memory transport and the review database was created under an
automatically deleted temporary directory.

## Results

| Control | Result | Evidence |
|---|---|---|
| Knowledge Manager authorized retrieval | PASS | Aurora returned only `aurora-user` and `aurora-group`; Borealis returned only `borealis-user`. |
| Project isolation before retrieval | PASS | Aurora requesting Borealis raised `ScopeDenied`. |
| Tenant isolation | PASS | The matching `other-tenant` source was excluded. |
| Document user/group ACLs | PASS | User and group grants worked; another-user and missing-ACL sources were excluded. |
| Fail-closed document access | PASS | A document with no user or group ACL was not retrievable. |
| Project Manager source citations | PASS | Both project-status drafts carried evidence objects and inline source IDs for every returned source. |
| Executive Assistant source evidence | PASS | Synthetic calendar and email IDs and locators were attached as evidence. |
| Review-queue submission | PASS | All four generated outputs entered the queue with `pending` status. |
| Human-review labeling | PASS | All generated bodies stated `human review required`. |
| Project-scoped queue isolation | PASS | Aurora could not list the Borealis project-status draft. |
| User isolation for projectless drafts | PASS | Pending listings now require `UserContext`; Aurora cannot see Ben's Executive Assistant briefing. |
| Human accept/reject workflow | PASS | Authorized pending-only accept/reject transitions store reviewer, timestamp, and reason; unauthorized and repeated transitions are denied. |
| Read-only integration surface | PASS | Public Graph operations are limited to calendar, message, and SharePoint reads; the HTTP implementation constructs `GET` requests. |
| Agent tool least privilege | PASS | Knowledge Manager, Executive Assistant, and Project Manager manifests expose only read/search tools; writes remain approval declarations rather than callable tools. |

**Final aggregate:** 20 passed, 0 failed. Legacy review-database schema migration also passed.

## Remediated findings

### P0 — Projectless review items leaked across users in one tenant — RESOLVED

`ReviewQueue.list_pending()` filters by tenant and project membership, but explicitly
includes every row whose `project_id` is null. Morning briefings are submitted with a
null project ID, so any same-tenant user who can list pending work receives every
other user's briefing. This can expose email and calendar-derived content.

`list_pending()` now requires the authenticated `UserContext`. Projectless items are
returned only when `created_by` matches the current user; project-scoped items still
require project membership. A two-user same-tenant regression test covers this rule.

### P1 — Review items could not be accepted or rejected — RESOLVED

The queue now supports atomic `accept()` and `reject()` operations. They enforce
tenant scope plus project membership or personal-item ownership, require a reason,
allow transitions only from pending, and record actor, UTC timestamp, and reason.
Existing queue databases are migrated in place with nullable audit columns.

## Read-only enforcement assessment

The tested application surface is read-only: the Graph adapter exposes retrieval
methods only, creates HTTP `GET` requests, and the three agent manifests list only
read/search tools. Generated work is inserted into a local review queue but is never
sent, published, assigned, or written back to a source system. Static configuration
also declares delegated `Mail.Read`, `Calendars.Read`, and `Sites.Selected` scopes
with write scopes disabled. This run did not edit any file under `config/`.

## Limitations and exit criteria

This was intentionally an offline synthetic pilot. It validates deterministic policy
and workflow behavior, not live Microsoft authorization, SharePoint effective-ACL
resolution, model answer quality, prompt-injection resistance, latency, cost,
retention/backup operations, or production observability. The repository's optional
`pytest` and `ruff` tools were unavailable in the local runtime, so the pilot used a
standalone assertion harness with the installed application dependency instead of
installing packages or changing the environment.

Before introducing real data, run the normal automated suite and lint checks in the
supported Python 3.11+ development environment and exercise the remaining governance
evaluation gates. Delegate/admin access to personal review items should be modeled
explicitly if that capability becomes a pilot requirement.

## Production-configuration attestation

- No external accounts were connected.
- No live credentials or real personal/project data were used.
- No network calls were made by the pilot harness.
- No live model execution occurred.
- No production configuration was modified.
- Temporary source data and the SQLite review database were deleted after execution.
