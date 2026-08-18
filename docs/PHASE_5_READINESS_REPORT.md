# Phase 5 readiness report

**Assessment date:** 2026-08-18

**Verdict:** The sandbox gated-action foundation is ready for continued synthetic
testing. It is not ready for limited production or any production write.

## Implemented scope

- Versioned workflow definitions restricted to a low-risk `sandbox.record.tag`
  action, synthetic identities, least-privilege permissions, bounded attempts,
  named alert/dead-letter owners, idempotency strategy, and rollback procedure.
- Exact action requests binding tenant, client, project, initiator, action, synthetic
  target, payload, expected current state, rollback plan, idempotency key, and evidence.
- Durable SQLite approval packets with project scope, expiry, accountable approver
  group, approval reason, and separation of initiator and approver.
- HMAC-SHA256 action tokens binding the exact request digest, identity, scope, expiry,
  and a single-use nonce. Invalid signatures, expiry, replay, and payload substitution
  fail closed.
- An in-memory synthetic adapter with optimistic state checks and captured rollback
  payloads. A rollback is itself a new exact action requiring separate approval.
- Tenant/action kill switches, durable dead letters with sanitized error classes,
  operational counters, and tenant-scoped hash-chained audit reconstruction.

## Sandbox exercises and tests

The complete repository passes Ruff and 64 offline tests. Phase 5 coverage includes:

- tenant, client, and project isolation;
- production-target and over-permission rejection;
- prompt-injection input rejection;
- self-approval, wrong-role, expired-approval, and pending-approval bypass attempts;
- token signature tampering, expiry, replay, and exact-payload substitution;
- idempotency-key rebinding and duplicate execution;
- post-approval state conflict without overwrite;
- successful action and separately approved rollback;
- kill-switch activation, blocked execution, recovery, and administrative authority;
- adapter failure and dead-letter capture; and
- complete audit reconstruction and deliberate audit-record tamper detection.

## Explicitly absent

- Production adapters, endpoints, accounts, credentials, or secrets.
- External communications or writes to any system of record.
- Irreversible, financial, contractual, safety, permission, deletion, or deployment
  actions.
- Automatic retries or dead-letter replay.
- General approvals reusable across actions, targets, payloads, or time windows.

## Gates before limited production

1. Complete the applicable Phase 2–4 pilot validation and acceptance targets.
2. Approve one named reversible production workflow, system of record, accountable
   owner, approvers, target allowlist, service identity, and least-privilege scopes.
3. Replace the in-memory adapter and test signing material through a separately
   reviewed production adapter and managed secret service.
4. Establish encrypted durable storage, retention, legal hold, backup, recovery,
   monitoring, alerts, rate limits, and data-loss prevention.
5. Exercise rollback, kill switch, incident response, token rotation, dead-letter
   recovery, and audit reconstruction in an approved non-production environment.
6. Obtain a separate explicit authorization before any limited-production activation.
