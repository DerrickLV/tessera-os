# Incident exercise runbook

Run these exercises only in an approved synthetic sandbox. Do not introduce production
credentials or real client/project information.

## Exercises

1. **Cross-scope request:** submit a token for one project against another. Expect a
   403, no model call, no artifact, and a correlated security signal.
2. **Credential exposure:** place a synthetic token in an error. Expect DLP redaction,
   credential revocation practice, evidence preservation, and owner notification.
3. **Prompt injection:** place action instructions in an untrusted source. Expect the
   content to be treated as evidence only and central policy to deny writes.
4. **Approval bypass:** replay or substitute an exact-action approval. Expect denial,
   a dead-letter/audit record, and no target-state change.
5. **Tenant kill switch:** disable a synthetic workflow during a pending request.
   Expect fail-closed behavior and controlled recovery after accountable approval.
6. **Restore:** back up one synthetic tenant, restore to an isolated environment, verify
   integrity and tenant isolation, and record recovery point/time results.

## Evidence record

For each exercise record the date, environment, synthetic dataset version, facilitator,
observers, expected and actual results, correlation IDs, recovery time, findings, owner,
due date, and approval to close. A failed or undocumented exercise blocks production.
