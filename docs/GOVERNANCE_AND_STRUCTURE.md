# Structure Manager — Synthetic Foundation

The Structure Manager is an offline, draft-only specialist for evaluating fictional
entity-topology and governance scenarios. It does not provide legal or tax advice,
form entities, file documents, or send agreements.

## Implemented components

- Deterministic `VentureProfile` → `StructureRecommendation` evaluation.
- Explicit distinction between synthetic reference rules and unadopted scaffolds.
- Current, cited intake evidence required for every recommendation artifact.
- Unanswered questions, conflicts, and stale evidence produce
  `insufficient_evidence`; they never produce a ready or approved claim.
- Qualified-counsel review is required before the exact recommendation inputs can
  be handed to agreement drafting.
- The approved recommendation ID and input fingerprint travel into the agreement
  artifact for lineage.
- Prompt-injection, cross-project, cross-tenant, approval-bypass, stale-evidence,
  changed-input, and role-consistency tests.
- Synthetic governance support clauses that are not derived from Tessera or client
  agreements.
- Local API endpoints for UI integration.

## Safety boundary

Everything under this capability is synthetic. The rules and sample clauses are
evaluation material, not adopted Tessera positions. Any live use requires a separate
production-data authorization, current authoritative sources, qualified legal and tax
review, and completion of the repository production gates.

See [the Structure Manager operator guide](governance/README.md).
