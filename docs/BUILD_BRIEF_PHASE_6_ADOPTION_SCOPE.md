# Build Brief — Phase 6: Adoption scope and the Rev 2 revisions

**Prerequisite:** Phases 1–5, merged. `main` at `c71e3fa` or later.
**Scope:** the adoption ledger's missing scope dimension, and the eight position
revisions carried by the Rev 2 partner decision sheet.
**Companion:** `docs/governance/11_LEDGER_STAGING_REV2.md` — the ledger blocks
this phase makes it safe to paste.

---

## 1. Why this phase exists

Rev 1 of the decision sheet put nineteen positions in front of both partners.
An independent review came back with one structural objection that is correct,
and eight substantive revisions that are mostly correct. Rev 2 of the sheet
sorts them. This brief is the code half.

**The structural objection.** The ledger has no notion of *scope*. `AdoptedPosition`
in `src/tessera_os/adoption.py` records area, adopters, date, source, approval and
counsel status — and nothing about where the position applies. That means a
position drawn from Tessera's own executed operating agreement, once adopted,
would be cited identically in a memo for a $50M development SPV, a passive
capital vehicle, and a founder-operated business.

That is overfitting the engine to its authors, and it is exactly the class of
quiet untruth this codebase exists to prevent. The provenance model already
distinguishes *invented* from *sourced*. It does not yet distinguish *sourced
from where* — and a position sourced from Tessera's own paper is authoritative
evidence about Tessera, not about a client.

**Why it is fixed with one field rather than a policy engine.** The reviewed
proposal was a five-profile policy layer with per-profile adoption states. The
insight is right and the shape is right. Building it before a single position
has ever been adopted is not: the ledger has never once run end to end, and
designing the schema for ninety-five positions before writing one teaches
nothing. `applies_to` on the entry, defaulting to the narrowest scope, carries
the distinction truthfully today and is what the profile layer grows from.

---

## 2. Design decisions

### D1. `applies_to` ships first, alone, before any position revision

Same rule as Phase 4.1. The scope field and its enforcement land as their own
commit with their own tests. Every later item in this phase is a position
change, and a position change that lands before scope exists is a position with
no honest home.

### D2. Scope is a list, and the profile classifier is `scaffold`

A position may apply to one profile, several, or all. `applies_to` is therefore
a list, never a single value, and it defaults to `["tessera_core"]` — the
narrowest claim, which is the only one the current evidence supports.

The classifier that maps a `VentureProfile` to a policy profile is a starting
point drawn from the facts already in intake. It is `scaffold`, it says so, and
where it cannot classify it must say that rather than defaulting silently. The
same loudness rule as Phase 4.1.

### D3. This phase adopts nothing

`config/adopted_positions.yaml` still reads `positions: []` when this phase
merges. Adoption requires two partners approving a protected pull request, and
no volume of code substitutes for that. This phase builds the machinery and
makes the staged blocks safe to paste. The signatures are a separate act.

### D4. A9 and A10: the code moves, the ledger does not

The engine's valuation and payment figures contradict Tessera's own executed
operating agreement, and the Rev 2 proposal changes both the engine *and* the
agreement. The code changes ship here so the behaviour can be tested. The
ledger entries stay held until the partners decide whether to amend the
executed document, because a ledger entry the executed agreement contradicts
puts a false statement inside the one record whose entire value is that it is
true.

### D5. Nothing here becomes `tessera_adopted`

Every position revised in this phase remains `scaffold` until the ledger says
otherwise. Changing a default to a better default does not adopt it.

### D6. Two review objections are already satisfied — verify, do not "fix"

The review asked for objective conduct triggers and a narrowed divorce trigger.
`_BASE_TRIGGERS` already drafts conduct as *conviction of, or a plea to, a
felony or a crime of fraud, dishonesty, or moral turpitude that materially and
adversely affects the company*, with a thirty-day cure on material breach in
`_BREACH_CURE_DAYS`. `_SPOUSE_TRIGGER` is already limited to a transfer that
would actually reach a spouse absent a waiver. The deadlock impairment
qualifier is likewise already in place.

**Do not change these.** Add tests that assert the current language holds, so a
later edit that loosens them fails CI.

---

## 3. Work items

### 6.1 — Adoption scope

**Ships first, on its own commit, before anything else in this phase.**

**Change.** In `src/tessera_os/adoption.py`:

```python
PolicyProfile = Literal[
    "tessera_core",         # Derrick and Ryan's ownership and governance of Tessera itself
    "founder_operating",    # closely held operating businesses with active owners
    "project_spv",          # real estate, development, single-project entities
    "capital_vehicle",      # passive investors, funds, syndications, co-investments
    "regulated_special",    # cannabis, liquor, licensed trades, restricted ownership
]
ALL_PROFILES: tuple[PolicyProfile, ...] = get_args(PolicyProfile)
```

`AdoptedPosition` gains:

```python
applies_to: list[PolicyProfile] = Field(
    default_factory=lambda: ["tessera_core"],
    min_length=1,
    description="Where this position governs. Defaults to the narrowest claim.")
```

with a validator rejecting duplicates, and a method:

```python
def governs(self, profile: PolicyProfile) -> bool:
    return profile in self.applies_to
```

`AdoptionLedger.for_area` gains a required `profile` argument. An entry whose
`applies_to` does not include the venture's profile is **not** returned — the
area stays unadopted for that venture, which is the correct and honest answer.

**Change.** In `src/tessera_os/governance.py`, a classifier:

```python
def policy_profile_for(profile: VentureProfile) -> tuple[PolicyProfile | None, str]:
```

returning the profile and the reason it was chosen. Starting rules, in order:

1. `profile.is_regulated` → `regulated_special`
2. sector in `{"development", "real_estate_hold"}`, or `profile.real_property`
   with a single asset purpose → `project_spv`
3. sector `fund`, or `profile.has_passive_capital` with no active operating
   business → `capital_vehicle`
4. otherwise → `founder_operating`

`tessera_core` is never inferred. It is set only by an explicit intake flag,
because "this is Tessera's own entity" is a fact, not something to guess from
shape.

**Acceptance.**
- `AdoptedPosition` defaults to `["tessera_core"]` when `applies_to` is absent,
  so every block staged for the partners is narrow by default.
- An empty `applies_to` list fails validation. A duplicate entry fails validation.
- An unknown profile string fails validation with the valid set named.
- `for_area` returns `None` for an adopted position whose scope excludes the
  venture's profile, and the memo reports that area as not adopted **for this
  venture** — wording that distinguishes it from never adopted at all.
- Where the classifier cannot decide, it returns `None` and the recommendation
  carries a blocking open question naming the venture and stating that no
  policy profile could be determined. It does not silently pick a default.
- A test enumerates every value of `PolicyProfile` and asserts the classifier
  can produce it or documents in the test why it cannot (`tessera_core`).
- The golden rule is unaffected: scope narrows citation, it never widens it.
  A test asserts no code path cites an adopted position outside its scope.

### 6.2 — A2: three reserved-matter additions

**Change.** `_BASE_RESERVED` in `governance.py` gains three entries:

- Materially reducing, changing, or allowing the lapse of any insurance
  programme required by the company's contracts, lenders, or prudent practice.
- Any change of control of the company.
- Any transaction between the company and a member, manager, sponsor, or their
  affiliates.

The third currently appears only in `_OUTSIDE_CAPITAL_RESERVED`; the second
only in `_REGULATED_RESERVED`. Both move to base. Remove the now-duplicated
entries from the conditional lists so no venture receives the same reserved
matter twice.

**Acceptance.**
- A venture with no passive capital and no regulated regime receives all three.
- A regulated venture with passive capital receives each exactly once — a test
  asserts no duplicates across the composed list.
- `governance.py` already blocks where `len(control.reserved_matters) > 12`
  triggers a manageability warning. Confirm the base list growing from ten to
  thirteen does not now fire that warning on every venture; adjust the ceiling
  with a stated reason, or exclude the base list from the count. Do not silence
  it.

### 6.3 — A1: budget-first ordinary-course authority

**The largest change in this phase.** Read this item twice before starting.

**The defect.** `_ordinary_course_threshold` scales authority off
`profile.initial_capital` at `_THRESHOLD_COEFFICIENT`, floored at
`_THRESHOLD_FLOOR` and capped at `_THRESHOLD_CAP`. That breaks precisely where
Tessera works: a project entity capitalised at $100,000 controlling a $30M
development receives a $10,000 authority ceiling, and every draw becomes a
members' vote. The inverse is worse — a well-capitalised passive vehicle
granting broad unilateral operating authority.

The engine already suspects this. Its own derivation string says the figure
"has not been tested against your actual operating budget. Confirm or replace."
This item finishes that thought.

**Change.** Authority becomes a hierarchy, not a number:

1. **Within an approved budget.** Where an approved annual or project budget
   exists, management may execute expenditures and contracts contained within
   it, subject to the always-reserved list below.
2. **Unbudgeted commitments.** Above the greater of a stated dollar figure or a
   stated percentage of the approved budget, reserved-matter approval is
   required, subject to a maximum delegated threshold.
3. **Fallback.** Where no budget exists yet — which is the formation case, and
   the case the clause is usually drafted in — the current capital-scaled rule
   applies, explicitly labelled as an interim rule until the first budget is
   adopted.

Regardless of amount and regardless of budget: debt, guarantees, related-party
transactions, and material change to project scope remain reserved.

`VentureProfile` gains the intake facts this needs: whether an approved
operating or project budget exists, and its amount. Both optional; absent means
branch 3.

**Acceptance.**
- Every figure in every branch is a `DerivedNumber` with a derivation. The
  fallback branch's derivation says it is an interim rule pending a budget.
- A venture with a stated budget produces a threshold governing unbudgeted
  commitments only, and the rendered clause says so — a reader can tell which
  branch produced the number.
- A venture with a budget and one without produce visibly different clauses. A
  test asserts they are not the same sentence with a different figure.
- The always-reserved four appear in the reserved list in every branch,
  including where a budget exists.
- The zero-capital, zero-budget case stays `unresolved` and blocking. Phase 3
  removed the fabricated default; do not reintroduce one.
- Memo and document agree on which branch applied — the parity invariant.

### 6.4 — A5: appraisal default, shotgun by recorded election

**Change.** `_buy_sell_style` inverts. Appraisal is the default in every case.
Shotgun applies only where an affirmative election has been recorded.

The current test — `has_passive_capital or not equal_ownership` — infers
liquidity comparability from ownership shape. It cannot. Someone may be wealthy
and temporarily illiquid; someone may have financing arranged; someone may know
the other side cannot buy. A shotgun against a party who cannot fund the
purchase is not a price mechanism, it is an option held by whoever has cash.

The election is a fact the record can hold. The inference is not.

**Acceptance.**
- Default with no election is `appraisal`, for every ownership shape.
- Electing shotgun requires the same recorded shape as a Phase 5 menu
  selection: who elected it, when, authenticated.
- The election is refused for a project outside the authenticated scope (403).
- The rendered clause where shotgun is elected states that both parties
  acknowledge the mechanism and represent that they have considered their
  ability to fund a purchase — collaborative on the surface, and it puts the
  liquidity question in writing where it belongs.
- `_SHOTGUN_UNIT_PERCENT` and `_SHOTGUN_ELECTION_DAYS` remain `DerivedNumber`s.
  They are not sourced and this item does not source them.
- Electing shotgun persists through `sqlite_store.connect` and survives restart.

### 6.5 — B1: LLC presumptive, with a pre-formation screen

**Change.** The engine currently recommends an LLC and raises the corporation
question as a confirmation. Invert the order: a pre-formation screen runs
*before* entity form is recommended, and where it fires, entity form is an open
question rather than a recommendation.

Screen triggers: institutional venture capital on standard terms is in view; an
option pool is contemplated; any founder has a QSBS objective; an investor or
lender requires a corporation.

**Acceptance.**
- Where no trigger fires, the recommendation is an LLC and reads as it does today.
- Where any trigger fires, entity form becomes a blocking open question naming
  the trigger, and `to_draft_request()` refuses until it is resolved.
- The QSBS question specifically states that it is decided before formation and
  cannot be recovered by converting later. That is the entire reason this item
  exists.
- The screen's questions appear in the memo whether or not they fire, so a
  reader can see what was checked.

### 6.6 — B2: restate the tax restraint as what it is

**Change.** `_tax_treatment` keeps its behaviour. Its *stated reason* changes.

"Never propose an S election" is not a claim that S elections are unwise. It is
a constraint on a system with no tax adviser, preventing it from appearing to
have one. Say that. The counsel note gains the decision tree — real property
and any structure with special allocations, a preferred return, or a promote
points to partnership treatment; a simple owner-operated service business is
where the S question is worth a CPA's time; an institutional venture or QSBS
objective points to a corporation — framed explicitly as questions for the tax
adviser, not as engine output.

**Acceptance.**
- No behaviour change: the engine still never proposes an election.
- The counsel note names a tax adviser or CPA specifically, per the Phase 4
  invariant that counsel notes name the specialist rather than "a lawyer."
- The existing incompatibility check between an S election and tiered economics
  is preserved and still fires.

### 6.7 — A9: valuation methodology

**Change.** In `_valuation_menu`, the appraisal option's mechanism changes.

Today: two appraisals; if within the band, average them; otherwise a third
appraiser's determination **binds**. That hands one person unilateral pricing
power over an outcome the other two were appointed to price.

Revised: two appraisals; if within the band, average them; otherwise obtain a
third, and the **average of the two closest** governs.

`_VALUATION_AGREEMENT_DAYS` moves 20 → 15 and `_VALUATION_BAND_PERCENT` moves
15 → 10, matching Tessera's executed agreement.

Add a discount instruction as a stated parameter: whether the appraiser is
directed to disregard discounts for lack of marketability and lack of control.
Default is to disregard **only** where the policy profile is `tessera_core`;
every other profile leaves it unresolved and blocking, because an outside
passive minority interest and a founder buy-out are not the same valuation
question.

**Acceptance.**
- The two-closest computation has a test with three concrete appraisals where
  the median and the two-closest average differ, asserting which one governs.
- The discount instruction is a `DerivedNumber`-adjacent stated parameter with
  its own confirmation, not a silent default.
- Where the profile is not `tessera_core`, the discount question blocks.
- The counsel note says plainly that the discount instruction can move a
  buy-out price materially and that a valuation professional should confirm it.
- **No ledger entry.** See D4.

### 6.8 — A10: payment terms

**Change.** In `_payment_menu`, the note option gains the terms Rev 2 proposes,
as *options within the option* rather than replacements:

- Term: 36 months and 48 months as selectable, both `DerivedNumber`-backed.
- Interest: no less than the applicable federal rate, and separately tied to a
  stated commercial benchmark — AFR establishes a tax floor, it does not price
  the risk of financing someone's purchase.
- Freely prepayable without penalty.
- Acceleration on a sale, refinancing, or change of control.
- A minimum working-capital floor, below which scheduled payments defer rather
  than the company being drained. A buy-out that disables the company the
  seller is relying on to pay the note is not a remedy.

`_BUYOUT_CASH_PERCENT` moves 25 → 20, matching the executed agreement.

**Acceptance.**
- The working-capital floor is computable from stated inputs and a worked
  example appears in the memo.
- Deferral on breaching the floor is bounded — it cannot defer indefinitely —
  and the bound is stated.
- The `ESSENTIAL_CATEGORIES` exit set stays required together. A right to buy
  with no way to price or pay for it is the failure that set prevents.
- **No ledger entry.** See D4.

### 6.9 — A11: the conflict protocol

**Change.** The dual-role disclosure is currently a single requirement. It
becomes an ordered protocol, each step recorded:

1. Disclosure that Tessera both advises and holds or will hold equity.
2. Economic disclosure — what Tessera earns on each side.
3. Written conflict acknowledgment by the client.
4. Independent client approval, by someone other than the person Tessera is
   advising day to day.
5. Tessera-side approval.
6. Regulatory check — **blocked on C2** and must say so.
7. Documentation of all of the above.

**Acceptance.**
- Step 6 carries an explicit blocking note naming C2, the securities and
  broker-registration question, and does not pretend to a conclusion.
- `to_draft_request()` refuses on any engagement where Tessera holds or will
  hold equity and steps 1–5 are not recorded.
- Posture selection reaches the protocol: a protective posture requires the
  acknowledgment before terms are negotiated rather than before execution.
- A test asserts the protocol cannot be marked complete while step 6 is blocked.

### 6.10 — B4: minority protections on drag

**Change.** `ExitArchitecture.drag_along` currently fires where
`exit_intent == "sale"`. Keep the trigger; add the protections. A dragged
minority receives:

- the same consideration and the same form of consideration as the dragging
  majority;
- escrow and holdback exposure strictly pro rata to proceeds;
- several rather than joint liability wherever the transaction structure
  permits it;
- no representations beyond title to their own interest and their authority to
  transfer it.

**Acceptance.**
- Every drag clause the engine emits carries all four.
- A test asserts a drag clause with any of the four missing fails.
- The counsel note states that several liability is not always available and
  that transaction counsel confirms it deal by deal.

### 6.11 — The memo says what scope applies

**Change.** The memo's adopted-positions section reports the venture's policy
profile, the reason the classifier chose it, and — for each area — whether the
position is adopted, adopted but out of scope for this venture, or not adopted.

**Acceptance.**
- Three states are visually distinct in the rendered memo. "Not adopted for
  this venture" must not read as "never adopted."
- The profile and the classifier's reason appear before the position list, so a
  reader can challenge the classification rather than only its consequences.
- The parity invariant holds: the document never asserts a position the memo
  reports as out of scope.

---

## 4. Invariants

1. Adoption still requires two distinct partners and an approved protected pull
   request. This phase changes nothing about that.
2. `config/adopted_positions.yaml` still reads `positions: []` when this phase
   merges.
3. Scope narrows citation and never widens it.
4. Nothing in this phase becomes `tessera_adopted`.
5. Every commercial number remains a `DerivedNumber`.
6. Memo and document carry the same terms — parity holds.
7. `knowledge.py` authorization still fails closed. Nothing here touches it.
8. `CLAUDE.md` invariants continue to hold.

---

## 5. Definition of done

- A staged ledger block with no `applies_to` loads as `["tessera_core"]`, and a
  client-profile memo correctly reports it as out of scope rather than absent.
- A project SPV with a $100,000 capitalisation and a $4M approved project
  budget produces an authority clause a reader recognises as sane.
- The default buy-sell is appraisal for every ownership shape, and electing
  shotgun is a recorded act by a named user.
- A venture with a QSBS objective cannot reach `to_draft_request()` without the
  entity-form question being answered.
- Three appraisals outside the band produce the average of the two closest, and
  a test proves it differs from the median case.
- An engagement where Tessera takes equity cannot produce a draft until the
  conflict protocol's first five steps are recorded, and step 6 says openly
  that it is waiting on counsel.
- Full suite green, ruff clean, `scripts/security_scan.py` clean.

---

## 6. Order of work

`6.1` alone, its own commit, tests green, before anything else.

Then `6.2`, `6.6`, `6.10` — small and independent.

Then `6.3` — the largest, and the one most likely to surface intake changes
that ripple.

Then `6.4`, `6.5`, `6.7`, `6.8`, `6.9`.

Then `6.11`, which reports on all of it and should be written last so it
reports what was actually built.
