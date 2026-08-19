# 00 — Console Sequence

*Authored by Codex. The controlled path a Structure Manager run actually takes
through the console API, and the gates it has to clear.*

The Structure Manager is available through the localhost console API. It remains
synthetic, read-only, and draft-only.

## Controlled sequence

1. Create a recommendation with `POST /v1/structure/recommendations`.
2. Supply at least one current synthetic evidence record and answer every blocking
   question returned by the previous run.
3. Submit the artifact with `POST /v1/artifacts/{artifact_id}/submit`.
4. A different user in the `qualified_counsel` group accepts the review item.
5. Create an agreement draft with
   `POST /v1/structure/recommendations/{artifact_id}/draft`, using the exact same
   request body.

The fifth step fails if evidence is stale, questions or conflicts remain, the review
is missing or rejected, the reviewer is unauthorized, the tenant/project differs, or
any input changed after review.

## Evidence format

Each `StructureRequest` includes `evidence`, with a stable `source_id`, title,
locator, excerpt, and ISO-8601 `retrieved_at`. Synthetic examples should use
`fixture://` locators. The artifact cites both the intake evidence and the exact
deterministic rule used for each recommendation.

## Provenance labels

- `tessera_adopted`: signed by both partners in `config/adopted_positions.yaml`,
  citing its source **by reference**. The ledger ships empty.
- `synthetic_reference`: fictional offline evaluation rule; not adopted by Tessera.
- `scaffold`: unresolved starting point requiring qualified review.

No real operating agreement or client material belongs in fixtures, tests, generated
samples, or documentation. The adoption ledger records *that* a position was adopted
and *where its source lives* — never the source's text. See
[03 — Provenance ledger](03_PROVENANCE.md).
