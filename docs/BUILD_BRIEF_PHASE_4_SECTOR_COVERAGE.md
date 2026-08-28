# Build Brief — Phase 4: Sector and regime coverage

**Prerequisite:** Phase 3 (numbers), merged.
**Scope:** `src/tessera_os/sectors.py` — the six declared sectors with no pattern,
and the regimes Tessera actually meets.

---

## 1. The gap, in one line of evidence

`sectors.py:28` declares nine sectors:

```python
Sector = Literal[
    "operating", "real_estate_hold", "development", "fund", "ip_licensing",
    "professional_services", "film_production", "skilled_trades", "hospitality",
]
```

`SECTOR_PATTERNS` contains **three**: `FILM`, `SKILLED_TRADES`, `HOSPITALITY`.

`pattern_for(activity)` returns `None` for the other six, and the engine
proceeds without sector guidance — no extra entities, no sector reserved
matters, no failure modes, no sector open questions. The memo does not say a
pattern was missing. It reads exactly like a memo where the sector added
nothing.

**The sharpest illustration:** the venture in your own test fixture — Harbor
Point Holdings, `activity="real_estate_hold"` — is one of the six. Tessera's
flagship example runs through the engine and silently receives no real-estate
structuring at all.

Six of nine, and the most common one Tessera meets among them.

---

## 2. Design decisions

### D1. A missing pattern must be loud

Before writing a single new pattern: `pattern_for` returning `None` for a
declared sector is a defect, not a state to handle gracefully. Either the sector
has a pattern or it is not offered on the intake form.

This item ships **first**, on its own, so that any gap left after this phase
announces itself rather than degrading quietly. It is the same principle as
Phase 2's honest empty states.

### D2. Match the standard already set

`FILM` is the benchmark, and it is good. Read it before writing anything. Each
pattern carries:

- **layers** — entities the general rules would not produce, each with `why` in
  full sentences explaining the failure it prevents, and `per_unit` / `supersedes`
  set correctly so the structure doesn't emit two entities for one job
- **reserved_matters** — decisions specific to this sector
- **failure_modes** — `(name, description)`: the concrete way this goes wrong,
  written so an operator recognises it
- **open_questions** — `(question, why it matters, what it blocks)`
- **positions** — `(area, position, because)`
- **counsel_notes** — what a lawyer confirms before filing

A pattern that fills only `layers` is not finished.

### D3. Everything stays `scaffold`

The module docstring is explicit and stays true: these are informed starting
points from standard practice, not adopted Tessera positions, not reviewed by
counsel in any state. Nothing in this phase produces `tessera_adopted` — that
requires two partner signatures through the adoption ledger, and no volume of
good drafting substitutes for it.

### D4. Write what Tessera actually knows

These patterns encode judgment, and the quality ceiling is the judgment
available. Where Derrick and Ryan have direct experience — real estate, trades,
cannabis, film, hospitality — write with that specificity. Where the pattern
would be generic, say so in `counsel_notes` rather than padding it. A thin
honest pattern beats a thick invented one.

---

## 3. Work items

### 4.1 — A missing pattern is an error

**Change.** When `pattern_for` returns `None` for a sector declared in the
`Sector` literal, raise a blocking open question naming the sector and stating
that no pattern exists — the same shape Phase 1 introduced for the unresolved
threshold.

**Acceptance.**
- A recommendation for a sector with no pattern carries a blocking open question
  naming it.
- That recommendation cannot reach `draft` status, and `to_draft_request()`
  refuses.
- A test enumerates every value in the `Sector` literal and asserts a pattern
  exists — so adding a sector to the literal without a pattern fails CI.
- Ships as its own commit, before any pattern is written.

### 4.2 — `real_estate_hold`

Highest priority: it is Tessera's most common structure and its own example.

**Should cover.** Property-level entities (one per asset, or per lender's
requirement — `per_unit=True`); the separation of the holding entity from the
operating/management entity; single-purpose-entity requirements imposed by
lenders and why they are non-negotiable; title, insurance, and the entity's name
matching the deed; guarantor exposure and who signs the carve-out guaranty.

**Failure modes to name.** Title held in the wrong entity's name so the lender
refuses to close. One entity holding two properties so a claim on one reaches
the other. Insurance naming an entity that no longer exists after a
restructuring. The operating agreement conflicting with the loan documents,
which win.

**Open questions.** Is there debt, and does the lender require an SPE with an
independent manager? Is the property held for income or for sale? Who signs the
guaranty, and has that person seen the carve-outs?

### 4.3 — `development`

**Should cover.** Development entity separate from the eventual hold entity;
construction risk isolation; the transition point where a development entity
becomes or transfers to a hold entity; contractor and design-professional
contracting party; draw and lien-waiver governance.

**Failure modes.** Construction liability following the asset into the permanent
hold. A change order approved by someone without authority. The development
entity dissolved before the statute of repose has run.

### 4.4 — `fund`

**Should cover.** Fund, general partner, and management company as three
entities with three different purposes; carried interest sitting where it is
taxed correctly; capital commitments and default remedies; the sharp line
between fund governance and portfolio-company governance.

**Counsel notes must be prominent.** Securities law governs almost everything
here. This pattern's job is to frame the questions a securities lawyer answers,
not to answer them. Phase 1 removed `investor_subscription` from the agreement
types for exactly this reason — the same restraint applies to the sector
pattern.

### 4.5 — `ip_licensing`

**Should cover.** IP-holding entity separate from any operating entity;
licence-in and licence-out structure; what happens to licences on a change of
control; royalty audit rights; whether the IP is the asset or the licence stream
is.

**Failure modes.** Improvements made by the operating entity vesting in the
wrong place. A licence that terminates on change of control, discovered during
diligence.

### 4.6 — `professional_services`

**Should cover.** Professional-entity requirements where a licensed practitioner
must own the entity (PLLC/PC); who may hold equity and who may not; the
management-company structure where the professional entity cannot be owned by
outside capital; malpractice exposure and which entity carries it; departure of a
licensed owner.

**Failure modes.** An outside investor admitted into an entity whose licensing
board forbids it. A structure that is a fee-splitting violation in the practice's
state.

### 4.7 — `operating`

The general case, and the one that most needs an honest boundary. This is the
default when nothing more specific applies, so it must carry the things every
operating business needs and be candid that it is generic — an operating
business in a licensed trade should be routed to `skilled_trades`, not here.

**Acceptance across 4.2–4.7.** Each has layers, reserved matters, at least three
failure modes, at least three open questions, positions, and counsel notes. Each
appears in `SECTOR_PATTERNS`. Each has a test asserting it produces sector-
specific output distinguishable from the generic path.

### 4.8 — Regime coverage

Existing: `CANNABIS`, `HEMP`, `LIQUOR`, `CONTRACTOR`. `regime_for` matches
loosely, which is right.

**Add** where Tessera actually operates. Candidates worth considering rather than
building on spec: healthcare licensure, food service and health-department
permitting, transportation and DOT authority, firearms/ATF, childcare licensing.

**Acceptance.**
- A regime named in an intake that matches no pattern raises an open question
  naming it — the same loudness rule as 4.1.
- `regime_for` loose matching has a test for the near-miss case ("adult-use
  cannabis" → `CANNABIS`) and for the no-match case.

### 4.9 — Sector and regime compose without duplicating

**Change.** `supersedes` exists so a film's Rights entity replaces the generic IP
entity rather than sitting beside it. Every new pattern must set it correctly,
and the composition must be tested.

**Acceptance.**
- A cannabis dispensary in a leased location produces one licence entity, not
  two.
- A real-estate venture with an IP component does not produce a redundant
  holding entity.
- A test asserts no structure ever emits two entities for the same job — that is
  two filing fees and two annual reports for one purpose, and it is the specific
  waste `supersedes` was built to prevent.

---

## 4. Invariants

1. Every pattern here is `scaffold`. Nothing in this phase adopts anything.
2. A missing pattern is loud, never silent.
3. `supersedes` is set correctly; no duplicate entities.
4. Counsel notes name the specialist, not "a lawyer."
5. `CLAUDE.md` invariants continue to hold.

---

## 5. Definition of done

- Nine sectors, nine patterns, enforced by a test over the `Sector` literal.
- Harbor Point Holdings — `real_estate_hold`, the fixture venture — produces a
  memo with real-estate-specific entities, reserved matters, failure modes, and
  open questions.
- A sector or regime with no pattern blocks with a named question.
- No structure emits two entities for one job.
- Full suite green, ruff clean, security scan clean.
