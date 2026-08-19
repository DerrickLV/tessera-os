# 03 — Provenance Ledger

How a starting point becomes a Tessera position, why that is deliberately hard,
and what is signed today.

---

## The problem this solves

Two rules pull in opposite directions, and both are right.

**No real agreement text in the repository.** This codebase is shared with
collaborators, runs in CI, and may one day be public. Reproducing Tessera's or a
client's operating agreement in fixtures, tests, or samples is not acceptable,
and everything here is synthetic or generic.

**The firm's actual decisions have to reach the engine.** A memo that can only
say "here is a reasonable starting point" is worth strictly less than one that
can say "this is what Tessera does, and here is the source." Suppressing the
firm's own positions to satisfy the first rule makes every memo weaker than the
firm actually is.

The ledger separates *provenance* from *text*. It records **that** a position
was adopted, **by whom**, **when**, and **where the source lives** — as a
citation by reference (`Tesserra Holdings LLC Operating Agreement, Art. IV`),
never as reproduced language. A governance fact is not agreement text.

---

## The four bases

| Basis | Means | In the memo |
|---|---|---|
| `tessera_adopted` | Both partners signed it in `config/adopted_positions.yaml` | **Adopted Tessera positions**, with adopters, date, and source reference |
| `synthetic_reference` | From the offline evaluation fixture; fictional | Stated as such, so nobody mistakes it for a firm position |
| `statutory` | A consequence of statute or the tax code, not a preference | Stated as such |
| `scaffold` | A defensible starting point nobody has adopted | **Positions not yet adopted**, and ranked `material` / `absent` in the review artifact |

---

## What adoption requires

Enforced by `src/tessera_os/adoption.py`, not by convention:

- **Two distinct partners.** Tessera's own governance makes firm-level decisions
  unanimous, so a ledger entry with one name is invalid by construction. The
  same name twice is still one partner.
- **An ISO date.** When the decision was made, not when the file was edited.
- **A source reference.** A document name and section. Never text.
- **`counsel_reviewed` defaults to false.** Partner adoption is not a substitute
  for counsel: an adopted-but-unreviewed position keeps printing its
  confirmation line in every memo. Only counsel review retires it.
- **No duplicate areas.** A ledger listing the same area twice raises rather
  than silently taking the last one.
- **A malformed ledger fails loudly.** Half-adopted positions are worse than
  none.

---

## The current state: empty

`config/adopted_positions.yaml` ships with `positions: []`.

That is the load-bearing default. Until the partners sign, every structural
position is labelled a starting point or a synthetic reference, and every memo
says so. There is a test asserting exactly this, because the day it silently
stops being true is the day the system starts inventing standards.

---

## Adopting a position

1. Open [09 — Decision packet](09_DECISION_PACKET.md). Every open decision is
   pre-drafted there with its reasoning, what it costs if wrong, and the exact
   YAML to paste.
2. Copy the entry into `config/adopted_positions.yaml`, put both names on it,
   and date it.
3. Run the suite. `test_adoption.py` confirms the entry is valid and that the
   position upgraded.

The `area` must match a `Recommendation` area exactly — the list is in
[02 — Decision rules](02_DECISION_RULES.md).

**Adoption is reversible.** Delete the entry and the position drops back to a
starting point on the next run. Nothing in code ever asserts adoption on its
own; the ledger is the only door, and there is a test for that too.

---

## What adopting Track A would change

Measured on a two-partner Texas real-estate hold with $3M in:

| | Adopted | Not yet adopted |
|---|---|---|
| Today | 0 | 13 |
| After Track A | 11 | 7 |

Eleven positions move from *"here is a reasonable starting point"* to *"this is
Tessera's position, adopted by Derrick Carlisle and Ryan Strasshofer on
[date], per Tesserra Holdings LLC Operating Agreement Art. IV."*

That is the difference the whole engine was built to make, and it costs one
afternoon.

---

## What stays unadopted regardless

Some positions should never carry `tessera_adopted`, and the packet does not
propose them:

- **Sector patterns** (film, trades, hospitality) and **regime patterns**
  (cannabis, hemp, liquor, contractor licensing). These are informed standard
  practice, not firm doctrine, and none has been reviewed by counsel or by a
  regulator in any state. Detail in [05](05_SECTOR_PATTERNS.md).
- **Entity form as an absolute.** LLC in every case is right almost always and
  wrong in exactly the cases that matter most — institutional venture capital,
  an option pool, QSBS. It stays a flagged question.
- **The drag-along threshold.** The most side-dependent term in the set, and
  Tessera sits on both sides depending on the engagement. A firm default here
  would be false precision.

---

## What provenance does inside the system

Not just a label on a document:

- **In the memo** — adopted positions get their own section with adopters and
  source; unadopted ones get a closing section, so a founder can see which
  advice is house doctrine and which is a starting point.
- **In the review artifact** — a `scaffold` position becomes a citation with
  severity `material` and finding type `absent`, meaning *no adopted Tessera
  position covers this*. It is ranked alongside real findings rather than
  footnoted.
- **In the confirmation lines** — a counsel-reviewed adoption retires its
  confirm line; an adopted-but-unreviewed one keeps it. Repeating a confirmation
  counsel has already answered teaches readers that confirm lines are
  boilerplate, and that is exactly when they stop reading them.
- **In the counsel packet** — the unadopted list is the agenda.
