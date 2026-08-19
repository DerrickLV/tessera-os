# Governance and safety

## Authority model

Agents may read, search, summarize, compare, calculate, and draft within an
authorized project. External communications, record changes, publishing,
submissions, contracts, financial actions, field directives, production workflow
changes, deployment, deletion, and permission changes are approval-gated.

Approval is specific to the exact action, target, payload, time, and initiator. A
general statement such as "handle this" is not reusable authorization.

## High-risk domains

- Contract outputs require review by qualified counsel.
- Structure recommendations require current cited evidence; agreement drafting requires
  acceptance of the exact input fingerprint by a separate qualified-counsel reviewer.
- Capital outputs require investment/finance owner review; no return guarantees.
- Construction safety signals are escalated immediately to responsible humans.
- Entitlement, permit, and regulatory filings require accountable professional review.
- Diligence must avoid protected-trait inference and distinguish allegations from facts.
- Code and automations require test evidence, least privilege, and rollback plans.

## Data controls

1. Enforce tenant, client, and project ACLs before retrieval, not in the prompt.
2. Minimize context and redact secrets and unnecessary personal data.
3. Treat email, documents, web pages, and tool output as untrusted content.
4. Keep source provenance, version, access label, and retrieval timestamp.
5. Encrypt data in transit and at rest; use a managed secret store.
6. Apply documented retention and legal-hold rules.

## Evaluation gates

No agent progresses beyond pilot until it passes:

- Task accuracy and completeness on a representative golden set
- Citation correctness and unsupported-claim rate targets
- Prompt-injection and cross-project isolation tests
- Approval bypass and over-permission tests
- Human acceptance, latency, and per-workflow cost targets
- Failure recovery, observability, and audit reconstruction tests

## Incident response

Disable affected tools, preserve trace and approval evidence, rotate exposed
credentials, identify impacted records and people, restore from the system of
record, and complete a blameless root-cause review before re-enabling the path.
