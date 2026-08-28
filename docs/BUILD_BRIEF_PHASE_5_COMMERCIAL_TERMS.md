# Build Brief — Phase 5: Commercial terms

**Prerequisite:** Phases 3 (numbers) and 4 (sectors), merged.
**Scope:** the economics — distributions, capital, exit pricing, and Tessera's own
engagement terms.
**Depends on Phase 3 structurally:** every figure here is a `DerivedNumber`.
Building this before Phase 3 means writing a second generation of invented
numbers.

---

## 1. Where the economics currently are

Governance is well developed. Economics are thin, and what exists is invented
procedure presented as settled practice.

**Exit pricing** — `governance.py:614–622`

```
"Agree within twenty (20) days; failing that each side appoints an appraiser, and
 if the two are within fifteen percent (15%) the value is their average, otherwise
 the two appoint a third whose determination binds."

"Twenty-five percent (25%) cash at closing and seventy-five percent (75%) by note
 at an approved lawful rate over twenty-four (24) months..."
```

Twenty days. Fifteen percent. Twenty-five and seventy-five. Twenty-four months.
Thirty days for the shotgun election. One percent as the shotgun unit. Every one
of those is a specific commercial term, none is sourced, and each is rendered as
a complete sentence a client could sign.

The procedure is defensible — three-appraiser mechanisms are standard. The
**parameters** are not chosen, they are filled in.

**What is absent entirely.** There is no distribution waterfall beyond a
reference to "the agreed waterfall" in the reserved matters. No preferred return.
No promote or carried interest. No capital-call mechanics beyond a
`synthetic_reference` recommendation. No dilution or default remedy. No tax
distribution formula. And on the engagement side, `finders_fee` has a
`success_fee` clause category with no economics behind it — Tessera has no
structured way to express its own fee terms.

---

## 2. Design decisions

### D1. A menu, not a recommendation

Tessera's stated approach is that structure comes first and terms second, and
that the work protects optionality — building menus of outcomes rather than
locking into single-path commitments. The engine should reflect that.

Where governance produces a position, economics produces **options with
tradeoffs**: two or three viable structures, what each does for whom, and what
each costs the other side. The client chooses. The memo records the choice and
who made it.

This is a different output shape from `Recommendation`, and it needs its own
type rather than being forced into the existing one.

### D2. Every number is a `DerivedNumber`

Phase 3's contract applies without exception. A preferred return rate, a
waterfall tier, a payment period, an appraisal band — each is stated, proposed
with a derivation, or unresolved and blocking. No commercial term reaches a
document unconfirmed.

### D3. Economics are `scaffold` and stay there

Nothing in this phase is a Tessera position. A waterfall structure drawn from
standard practice is a starting point; it becomes `tessera_adopted` only through
two partner signatures in the adoption ledger.

### D4. Tessera's own paper is a first-class case

`finders_fee`, `consulting`, `advisory` are Tessera contracting with a client —
Derrick and Ryan's own economics. That deserves the same rigour as a client's
operating agreement, and it is the case where "friendly on the surface,
enforceable underneath" matters most. A fee that cannot be collected because the
trigger was vague is the failure mode this phase exists to prevent.

### D5. Sector shapes the menu

Phase 4's patterns should reach the economics. A fund's waterfall is not a
real-estate hold's, which is not an operating company's. Where a sector pattern
implies a distribution structure, the menu should reflect it rather than
offering a generic list.

---

## 3. Work items

### 5.1 — An option set, with tradeoffs

**Change.** A type expressing a commercial choice:

```python
class TermOption(BaseModel):
    label: str                        # "Pro rata, no preference"
    summary: str                      # what it does, one sentence
    favours: str                      # who it advantages, named plainly
    costs: str                        # what the other side gives up
    numbers: list[DerivedNumber]      # every figure, Phase 3 contract
    when_appropriate: str
    basis: Basis = "scaffold"

class TermMenu(BaseModel):
    area: str                         # "Distribution waterfall"
    options: list[TermOption] = Field(min_length=2)
    selected: str = ""                # option label, empty until chosen
    selected_by: str = ""
    selected_at: datetime | None = None
```

**Acceptance.**
- A menu with fewer than two options fails validation — a menu of one is a
  recommendation wearing a menu's clothes.
- `selected` naming an option not in the list fails validation.
- `selected_by` set with `selected` empty fails validation.
- Selection records the authenticated user, same shape as Phase 3 confirmation.
- A `TermOption` never carries a `Basis3` state at the option level — its numbers
  do.

### 5.2 — Distribution waterfall

**Change.** A menu covering at minimum: pro rata with no preference; preferred
return with catch-up; preferred return with a promote above a hurdle.

**Acceptance.**
- Every rate, hurdle, and tier is a `DerivedNumber`, proposed with a derivation.
- Sector-aware: `fund` and `real_estate_hold` produce different default option
  sets from `operating` (D5).
- The memo renders the menu with tradeoffs visible, not as a single structure.
- Selecting an option is required before `to_draft_request()` will proceed.
- The selected structure produces the `distributions` clause content, and memo
  and document agree — the parity invariant from `CLAUDE.md`.

### 5.3 — Capital calls, dilution, and default

**Change.** Replace the current `synthetic_reference` capital-calls
recommendation with a menu: mandatory calls with dilution; optional calls with
dilution; member loans at a stated rate.

**Acceptance.**
- Dilution formula is explicit and its parameters are `DerivedNumber`s.
- The default remedy is stated and its consequence is calculable — a remedy
  nobody can compute is not a remedy.
- Interacts correctly with the waterfall: a diluted member's position after a
  missed call is derivable from the selected options together, and there is a
  test that computes it.

### 5.4 — Exit pricing becomes a menu with sourced parameters

**Change.** The three-appraiser procedure stays — it is standard and sound. Its
parameters become `DerivedNumber`s, and the valuation method becomes a menu:
appraisal; formula (multiple of earnings); fixed value with periodic reset.

**Acceptance.**
- The 20-day, 15%, 25/75, 24-month, 30-day, and 1% figures are all
  `DerivedNumber`s with derivations, or removed.
- Payment terms are their own menu — cash at closing; note over a term; earnout
  — because the pricing method and the payment method are separate decisions
  that the current single sentence fuses.
- The `ESSENTIAL_CATEGORIES` exit set (`triggering_events`, `valuation`,
  `buysell`, `buyout_payment`) remains required together. A right to buy with no
  way to price or pay for it is the failure that set already prevents; this
  phase must not weaken it.

### 5.5 — Tax distributions

**Change.** The formula, the assumed rate, and the timing become explicit and
`DerivedNumber`-backed.

**Acceptance.**
- The assumed tax rate is proposed with a derivation naming what it assumes, and
  its counsel note says plainly that a tax advisor sets it.
- The formula is computable from stated inputs — a worked example appears in the
  memo.
- Interacts with the waterfall: tax distributions are shown either as an advance
  against distributions or as a priority above them, and which one is a choice,
  not a default.

### 5.6 — Tessera's engagement economics

**Change.** Fee structure menus for `consulting`, `advisory`, and `finders_fee`:
fixed fee with milestones; monthly retainer; success fee on a defined trigger;
hybrid.

**Acceptance.**
- The success-fee **trigger** is defined precisely enough to be enforceable —
  what event, measured how, payable when. Vagueness here is the specific way
  these fees go uncollected.
- Tail provisions: a defined period after termination during which an
  introduction Tessera made still earns. Duration is a `DerivedNumber`.
- Expense treatment is explicit.
- Posture selection (`protective` / `standard` / `accommodating`) reaches the fee
  terms, so a protective posture produces a firmer trigger and a longer tail
  without the surface tone changing. Collaborative on the surface, enforceable
  underneath.
- **`fee_at_risk` is populated here.** Phase 1 made it `float | None` and left it
  unset because the structure path had no fee data. This phase is where it
  acquires a real value — and posture logic must be tested against a populated
  value, not just against `None`.

### 5.7 — Selection is recorded and gates the document

**Change.** A console endpoint selects an option for a menu, recording user and
timestamp.

**Acceptance.**
- Selection is refused for a project outside the authenticated scope (403).
- `to_draft_request()` raises while any menu is unselected, naming each.
- Selections persist through `sqlite_store.connect` and survive a restart.
- A memo with unselected menus cannot report status `draft`.

---

## 4. Invariants

1. Every commercial number is a `DerivedNumber`.
2. Every menu has at least two real options with stated tradeoffs.
3. Nothing here is `tessera_adopted` without the ledger.
4. Memo and document carry the same terms — parity holds.
5. The exit set stays required together.
6. `CLAUDE.md` invariants continue to hold.

---

## 5. Definition of done

- A real intake produces a memo with menus for waterfall, capital calls, exit
  pricing, payment, and tax distributions — each with options, tradeoffs, and
  derivations.
- The memo refuses `draft` status until every menu is selected and every number
  confirmed.
- Selecting and confirming produces an operating agreement whose economics match
  the memo exactly, naming who chose each term.
- A `finders_fee` agreement produces a success-fee trigger a reader can apply to
  facts and get one answer.
- Full suite green, ruff clean, security scan clean.
