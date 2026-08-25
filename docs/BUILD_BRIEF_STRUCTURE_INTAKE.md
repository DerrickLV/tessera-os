# Build brief — structure intake

**Status:** approved for build / awaiting approval — mark one before starting.
**Source:** review of `governance.py`, `clauses.py`, `drafting.py`, `sectors.py`
and the clause library, August 2026.

Read `CLAUDE.md` first. Everything below is subject to the invariants there.

---

## The problem this solves

The Structure Manager takes 24 inputs. Eleven do real work. Five are close to
inert: `states_of_operation` and `operators_take_compensation` each produce one
open question and nothing else; `expected_hold_years` only has an effect when it
is *absent*; `active_principals` is only ever summed into `total_members`, so
the engine cannot distinguish four working partners from two partners and two
investors; `tessera_is_principal` is superseded by `tessera_role`.

Six of nine `activity` values carry no sector logic. Three of four `exit_intent`
values are indistinguishable. `friends_family` capital behaves exactly like
`founders_only`.

The consequence is that the intake form looks more precise than the engine is,
and adding fields in the same style would widen that gap rather than close it.

**The rule for every field added below:** it must name the recommendation,
entity, clause, or number it changes. A field whose only effect is to raise a
better question belongs in the follow-up questionnaire, where the sector
patterns already put their best material.

---

## Phase 1 — Wire the guards that already exist

No new inputs. No UI. This is correctness, and everything after it depends on
the system being trustworthy first.

### 1.1 `derived_values()` is never called on the production path

`StructureRecommendation.derived_values()` exists to stop the memo and the
agreement quoting different numbers. Its own docstring names the failure. But
`StructureAdvisor.to_draft_request()` builds the request and returns; nothing
calls it, and the clause library fills `{ordinary_course_threshold}` from its
own posture default instead.

**Do:** carry derived values from the recommendation into the fill step, so a
value that appears in both documents has one source.

**Acceptance:** a test that runs a structure recommendation through to a filled
draft and asserts the threshold quoted in the memo is the threshold in the
agreement text — failing before the change.

### 1.2 `fee_at_risk` is hardcoded to zero

`to_deal_profile()` sets `fee_at_risk=0` unconditionally. The clause library's
posture rule promotes a deal to `protective` at `>= 100_000`, so that branch is
unreachable from the structure path.

**Do:** carry a real value (see Phase 3) or, until then, leave it unset rather
than asserting zero.

**Acceptance:** a test that a high-fee engagement selects protective variants
for that reason.

### 1.3 `investor_subscription` can never be drafted

It requires categories `subscription`, `investor_representations`, and
`securities_legend`. No clause carries any of them. Every attempt raises
`ClauseCoverageError`.

**Do:** either add the three clause categories, with counsel, or remove the type
from the offered list. Do not leave a document type that is offered and cannot
be produced.

**Note:** securities work is counsel-only under the decision packet. Removing
the type is the honest short-term answer.

### 1.4 The invented threshold can reach a document

`_ordinary_course_threshold()` returns a fictional `$50,000` when
`initial_capital <= 0`, and the comment says so. That number flows into the
governance clause.

**Do:** treat an underived threshold as an unanswered term — surfaced, not
silently defaulted.

---

## Phase 2 — Cap table, parties, effective date

The change that converts output from a clause set into a document you could send.

### 2.1 `members[]` replaces three proxies

Per member: name, entity form (if not an individual), percentage, capital
contribution, units, active or passive, manager or not, spouse holds a
community-property interest.

Retires `active_principals`, `passive_investors`, and `equal_ownership`, which
exist only because the engine has no cap table. Keep them as derived properties
so nothing downstream breaks in one commit.

**Links to:** approval rule and threshold, deadlock necessity, buy-sell style,
tag-along and drag-along. Today a supermajority is `ceil(members × pct / 100)`,
which assumes one member one vote; with percentages it becomes arithmetic.

**Also links to:** `DealProfile.parties`, which the structure path currently
passes empty — which is why there is no preamble, no Schedule A, and nowhere to
sign. The `Party` docstring says exactly this.

**Acceptance:** an assembled agreement for a two-member venture contains a
preamble naming both, a Schedule A with contributions, and two signature
blocks. A 60/40 cap table produces a different approval threshold than 50/50.

### 2.2 `effective_date`

Currently a real leak: the preamble emits the literal `{effective_date}` when
absent, and because `open_variables()` scans only clause bodies and definitions,
it is never prompted for, never listed as outstanding, and never filled.

**Acceptance:** no draft can be produced containing an unresolved brace, and the
"terms still to be filled in" list is complete.

---

## Phase 3 — The numbers that stop being invented

Each displaces something the code currently calls fictional or infers from a
proxy.

| Field | Replaces | Drives |
|---|---|---|
| `ordinary_course_threshold` (explicit, derive as fallback) | a 2%-of-capital rule the code calls fictional | three reserved matters, the authority recommendation, `{ordinary_course_threshold}` |
| `monthly_operating_spend` | nothing — new | lets the engine propose a threshold *with a reason*, which is what its own confirmation line asks for |
| `formation_state` | recovering the state by string-matching "Delaware" inside an entity-form sentence | governing law, `{jurisdiction}`, `{entity_statute}`, foreign qualification, the jurisdiction filter that keeps a non-compete out of a California agreement |
| `counterparty_counsel` | inferring representation from `capital_source == "institutional"` | document posture |
| `engagement_economics` (fee at risk, capital at risk) | a hardcoded zero | posture, dual-role disclosure, sponsor catch-up |
| `entity_form_constraints` (investor requires a corporation / option pool / QSBS / institutional VC in the hold) | a hardcoded `"llc"` | entity form, tax treatment, and the stop-and-ask behaviour in decision packet item 1.4 |

`{jurisdiction}` and `{entity_statute}` currently have no source at all and
block a complete draft. `formation_state` fixes both.

---

## Phase 4 — Sector and regime coverage

The overlay architecture works; it is only populated for three activities and
four regimes. This is content work, not engineering.

- **Six sector patterns:** `fund`, `ip_licensing`, `professional_services`,
  `operating`, `real_estate_hold`, `development`. Each supplies extra entity
  layers, reserved matters, positions, failure modes, and the sector open
  questions the code calls "the questions nobody can answer from a generic
  intake form."
- **`regulated_regime` becomes a picklist.** It is free text matched by
  substring today; only cannabis, hemp, liquor, and contractor licensing match.
  "Food service" and "lending" — both named in the field's own help text — match
  nothing and degrade silently to generic treatment. An unmodelled regime should
  be visibly unmodelled.
- **`states_of_operation` gets consequences:** foreign-qualification steps in the
  formation checklist, per-state licensing questions, jurisdiction-aware clause
  selection. The skilled-trades pattern already says to confirm licensing "in
  every state of operation" — in a `counsel_notes` field nothing ever reads.
- **`unit_kind`** so `business_lines` stops meaning properties, productions,
  locations, or distinct businesses depending on context.

**While in here:** four of six conflict checks are unreachable — shotgun with
passive investors, unanimity with three or more members, deadlock with majority
control, and S-corp with tiered economics are each excluded by construction
elsewhere. Either make them reachable or delete them; a detector that cannot
fire is worse than no detector, because it reads as coverage.

Also unread: `SectorPattern.counsel_notes`, `RegimePattern.counsel_notes`, and
`RegimePattern.isolate_licence` are declared and never consumed.

---

## Phase 5 — Commercial terms and the fill step

Forty-two placeholders appear in clause text. Nine have no source and no
default: `company_purpose`, `manager_name`, `promote_holder`, `advisory_cadence`,
`survival_sections`, `binding_sections`, `buyer_party`, `seller_party`,
`entity_statute`. Several are derivable — `manager_name` from the cap table, the
section lists from numbering the assembler already computes.

`fee_percentage` and `retainer_amount` declare no accommodating-posture default,
so an accommodating consulting or finder's-fee draft fails outright.

Twelve declared variables are orphans, left over from clauses since defanged —
`noncompete_months`, `nonsolicit_months`, six deadlock timings, and four others.
The restrictive-covenants clause now reads "No non-competition or
non-solicitation restriction is created by this synthetic fixture." Do not
collect a number for a clause that no longer uses it.

**Acceptance:** a completed intake produces a document with no unresolved
braces, or refuses and names every term still outstanding.

---

## Interface rules

**Progressive disclosure, not a longer wall.** Core stays short — venture,
state, members, activity, capital. Everything else appears in response to
something already entered: regulated regime opens the regime block; passive
members open the capital and waterfall block; real property opens the property
block; Tessera as principal opens the disclosure block.

**One source of truth.** Anything appearing in both memo and agreement travels
through `derived_values()`.

**Save and resume.** A structuring intake is not a single sitting. Drafts of the
intake itself should persist — on the same durable store, under the same ACLs.

---

## Out of scope

Do not, in this work:

- Promote any position to `tessera_adopted` — that is the ledger's job.
- Add a Microsoft scope, or any write path.
- Raise `maxReplicas`.
- Change the review queue's separation-of-duties rule.
- Add real agreement language to the clause library.

## Definition of done, per phase

`python -m pytest -q && ruff check . && python scripts/security_scan.py` clean,
a test that fails before the change and passes after, and — for anything
touching the memo/document boundary — a parity assertion.
