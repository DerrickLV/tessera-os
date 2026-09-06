# Ledger staging — Rev 2

Ready-to-paste blocks for `config/adopted_positions.yaml`.

**Nothing here is adopted.** These are drafts of what adoption would say. The
ledger records a decision two partners made; pasting a block is the mechanical
half of that, and it is worth nothing without the other half.

**Do not paste any block until Phase 6.1 has merged.** `applies_to` does not
exist before that, and every block below carries it.

---

## How to use this file

1. Phase 6 merges. Confirm `applies_to` exists on `AdoptedPosition`.
2. Both partners work through the Rev 2 decision sheet and agree Track 1.
3. Paste the Track 1 blocks below into `config/adopted_positions.yaml` under
   `positions:`, replacing `NNN` with the pull request number and `DATE` with
   the date both partners actually approved.
4. Open the pull request. Both partners approve it **independently** — the
   author of a position cannot be the person who approves it.
5. Merge. The deploy pipeline does the rest.

`source_ref` is a citation by reference. Never paste agreement text into this
repository — the loader does not enforce that, and the security scan will not
catch it.

---

## Track 1 — the six for signature

All scoped `tessera_core`, per Rev 2. This is deliberate and it is the narrow,
truthful claim: these positions are evidence of how Derrick and Ryan govern
Tessera. Widening any of them to a client profile is a later decision with its
own evidence.

```yaml
positions:
  - area: "Reserved matters"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "DATE"
    applies_to: ["tessera_core"]
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. V"
    approval_ref: "https://github.com/DerrickLV/tessera-os/pull/NNN"
    counsel_reviewed: false
    note: >-
      The base list as the Tessera position, plus insurance, change of control,
      and related-party transactions in every case rather than only where
      passive capital or a licensing regime is present.

  - area: "Deadlock"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "DATE"
    applies_to: ["tessera_core"]
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. VII"
    approval_ref: "https://github.com/DerrickLV/tessera-os/pull/NNN"
    counsel_reviewed: false
    note: >-
      The four-step ladder, applying only where no coalition can carry a
      reserved matter and the disagreement materially impairs operation. A
      disagreement is not a deadlock and a deadlock is not an exit right.

  - area: "Transfer restrictions"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "DATE"
    applies_to: ["tessera_core"]
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. VI"
    approval_ref: "https://github.com/DerrickLV/tessera-os/pull/NNN"
    counsel_reviewed: false
    note: >-
      Ownership cannot move outside the negotiated ownership group without the
      group's consent. Right of first refusal on identical price and terms;
      estate-planning transfers permitted where voting control is retained.
      Precise remedy language for an unauthorised transfer is counsel's.

  - area: "Triggering events"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "DATE"
    applies_to: ["tessera_core"]
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. VIII"
    approval_ref: "https://github.com/DerrickLV/tessera-os/pull/NNN"
    counsel_reviewed: false
    note: >-
      The seven events as drafted. Conduct is limited to conviction of or a
      plea to a defined offence; divorce is limited to a transfer that would
      actually reach a spouse absent a waiver. Vague conduct language is
      excluded deliberately — it becomes a weapon.

  - area: "Dual-role disclosure"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "DATE"
    applies_to: ["tessera_core", "founder_operating", "project_spv", "capital_vehicle", "regulated_special"]
    source_ref: "Tessera Advisory Group engagement policy, adopted DATE"
    approval_ref: "https://github.com/DerrickLV/tessera-os/pull/NNN"
    counsel_reviewed: false
    note: >-
      A standing requirement, not case-by-case. Wherever Tessera both advises
      and holds or will hold equity, written disclosure is signed before terms
      are negotiated. Scoped to every profile because it governs Tessera's own
      conduct, not the client's structure. The full conflict protocol is built
      in Phase 6.9; its regulatory step is blocked on counsel question C2.

  - area: "Tag-along and drag-along"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "DATE"
    applies_to: ["tessera_core"]
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. VI"
    approval_ref: "https://github.com/DerrickLV/tessera-os/pull/NNN"
    counsel_reviewed: false
    note: >-
      Tag wherever a minority exists; drag only where exit intent is a sale;
      drag threshold left open per deal. A dragged minority receives the same
      consideration and form, pro-rata escrow, several rather than joint
      liability where the structure permits, and no representations beyond
      title to its own interest.
```

**Note on the dual-role entry.** It is the only one scoped to all five
profiles, and that is not an oversight. Every other position here describes how
Tessera's own entity is governed. This one describes how Tessera behaves toward
anyone. The distinction is the whole point of the field.

---

## Held — do not paste

### A9 — Valuation

### A10 — Buyout payment terms

Phase 6 changes the engine's mechanics for both (items 6.7 and 6.8), so the
code will behave the revised way once it merges. **The ledger entries stay
out.**

The reason is not caution. It is that the Rev 2 proposal changes Tessera's
**executed operating agreement**, not just an engine default:

| | Executed agreement | Rev 2 proposal |
|---|---|---|
| Valuation window / band | 15 days, 10% | Unchanged, plus average-of-two-closest |
| Buyout cash at closing | 20% | Unchanged |
| Note term | 36 months | 48 months |
| Note rate | AFR | AFR floor plus a commercial benchmark |
| Working-capital floor | — | New |

Adopting the note-term or rate change means amending the executed document —
two signatures on the amendment, not two approvals on a pull request. Until
that happens, a ledger entry saying 48 months would assert a Tessera position
the firm's own signed agreement contradicts.

That is worse than adopting nothing. The ledger's only value is that everything
in it is true.

**When the partners decide:** if the agreement is amended, paste with
`source_ref` naming the *amendment*, not the original article. If it is not,
paste blocks carrying the executed figures — 36 months, AFR — and the engine
changes stay available as menu options nobody adopted.

---

## Deferred — no block exists yet

`A3` management model, `A6` capital-call default, `B3` topology review trigger.

Each has a sound objection and no drafted replacement. They stay unadopted and
the memo keeps listing them under positions not yet adopted, which is accurate.
Writing a placeholder block for them would be the exact failure this ledger
exists to prevent.

---

## Revise-then-sign — blocks follow the code

`A1` ordinary-course authority, `A5` buy-sell selection, `B1` entity form,
`B2` tax treatment.

Phase 6 implements all four (items 6.3, 6.4, 6.5, 6.6). Their ledger blocks are
written **after** the code merges and the behaviour has been seen in a real
memo, not before. A1 in particular changes shape, not just its number — there
is no honest way to draft its ledger note until the implemented rule exists to
describe.

---

## Counsel — never adopted here

`C1` restrictive covenants, `C2` securities and capital-raising posture, `C3`
capital-call default and Article 9, `C4` regulated ownership, `C5` dual-role
fiduciary framework, `C6` machine-assembled document posture, `C7` what
constitutes a Tessera approval.

These are questions for counsel, not positions for the partners. They reach the
ledger only as `counsel_reviewed: true` with a `counsel_review_ref` on an
existing entry, once counsel has actually answered.

C7 is worth reading twice. It asks whether two authenticated pull-request
approvals are sufficient for an act that legally requires member consent. The
answer changes how this entire file works, and it has not been answered.
