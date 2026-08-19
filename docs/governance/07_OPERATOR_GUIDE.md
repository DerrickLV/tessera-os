# 07 — Operator Guide

How to run this on a live engagement.

For the console API sequence and its gates, see
[00 — Console sequence](00_CONSOLE_SEQUENCE.md).

---

## The intake questionnaire

Every field changes at least one output. Nothing is collected that does not
decide something. `intake.py` can now propose many of these from documents with
a citation per field — but the proposal is unapplied until a human confirms, and
these are the questions behind it.

### Who is in it

| Ask | Field | Moves |
|---|---|---|
| "Who's actually going to run this day to day?" | `active_principals` | Management model, approval rule, whether a deadlock ladder belongs |
| "Is anyone putting money in who won't be working in it?" | `passive_investors` | Forces manager management; drives the securities conflict; switches buy-sell from shotgun to appraisal |
| "Is it split evenly?" | `equal_ownership` | Approval rule, deadlock, tag-along |
| "Is anyone married?" | `spouses_involved` | Adds the divorce triggering event |
| "If one of you stopped tomorrow, does the business stop?" | `key_person_dependency` | Insurance-funded buy-out |
| "Does anyone have an estate plan, or want one?" | `estate_planning_relevant` | Permitted revocable-trust transfer with retained voting control |

### What it does

| Ask | Field | Moves |
|---|---|---|
| "What kind of business is it?" | `activity` | The whole sector pattern |
| "Is it licensed by anyone?" | `regulated_regime` | Licence entity, regime pattern, protective posture |
| "How many of these will there be?" | `business_lines` | Per-unit entities; the options menu |
| "Where will it actually operate?" | `states_of_operation` | Foreign qualification question |
| "Where are you based?" | `home_state` | Formation state for operating entities |

### What it owns

| Ask | Field | Moves |
|---|---|---|
| "Will it own real estate?" | `real_property` | PropCo per property |
| "Is there a brand, method, or software worth owning apart?" | `material_ip` | IP entity; work-product assignment |
| "Employees? Customers on site? Vehicles?" | `operating_liability` | Whether an OpCo earns its filing fee |

### Money and horizon

| Ask | Field | Moves |
|---|---|---|
| "Where's the money coming from?" | `capital_source` | Management model, HoldCo state, securities conflict, waterfall |
| "How much is going in at the start?" | `initial_capital` | The ordinary-course threshold |
| "Will it need more later?" | `expects_additional_capital` | The dilution failure mode |
| "Is anyone taking a salary?" | `operators_take_compensation` | The S-election question |
| "Is anyone paid back first, or getting a bigger share of the upside?" | `tiered_economics` | The whole capital architecture |
| "What does the end look like?" | `exit_intent` | Drag-along; transfer architecture |
| "How long do you expect to hold it?" | `expected_hold_years` | Surfaced as an open question if unanswered |

### Tessera's own position

| Ask yourself | Field |
|---|---|
| "Are we advising, investing, or both?" | `tessera_role` |

**Get this one right before running anything.** If Tessera holds or will hold
equity and is also advising, set `"both"` — the disclosure belongs at the top of
the first memo the counterparty sees, not in a later conversation.

---

## Worked example

```python
from tessera_os.governance import VentureProfile, recommend_structure
from tessera_os.formation import build_formation_checklist
from tessera_os.clauses import ClauseLibrary, Party

rec = recommend_structure(VentureProfile(
    venture="Northstar Holdings", home_state="Texas",
    active_principals=2, equal_ownership=True,
    activity="real_estate_hold", real_property=True, business_lines=2,
    initial_capital=3_000_000, spouses_involved=True,
    estate_planning_relevant=True, tessera_role="both",
    exit_intent="refinance_recap", expected_hold_years=7,
))

print(rec.to_markdown())                          # the memo
print(build_formation_checklist(rec).to_markdown())  # the filing order
```

Then the agreement it calls for:

```python
library = ClauseLibrary.load("fixtures/clause_library")
draft = library.assemble(rec.to_deal_profile(
    counterparty="Meridian Capital LLC", parties=parties,
    effective_date="1 October 2026"))

filled = library.fill(draft, {
    "company_purpose": "acquiring, owning, and operating the Properties",
    "entity_statute": "the Texas Business Organizations Code",
    "jurisdiction": "the State of Texas",
    "manager_name": "Tessera Holdings LLC",
    "promote_holder": "Tessera Holdings LLC",
    "survival_sections": "1, 12, 19, 20 and 23",
    **rec.derived_values(),        # NOT optional — see below
})
```

**`derived_values()` is not optional.** Without it the library falls back to its
own posture defaults and the memo and the agreement disagree about the same
number — the memo saying the threshold is $60,000 while the document it produced
says $25,000. Both defensible. Having both is not.

---

## Diagnosing an agreement that already exists

```python
from tessera_os.diagnosis import diagnose_agreement

result = diagnose_agreement(text, library=library, profile=deal_profile)
print(result.to_markdown())
```

Reports what the document addresses, what it lacks with the failure mode each
gap exposes, textual contradictions, and the numbers it states. **Detection is
never endorsement** — language that is present may still be inadequate, and the
report says so in its own header.

---

## What to hand to whom

| Recipient | Give them |
|---|---|
| The founder | The structure memo as a branded DOCX — disclosure, alternatives, failure modes, glossary |
| Outside counsel | The memo, the draft, and [09 Track C](09_DECISION_PACKET.md) |
| Ryan | [06](06_CAPITAL_ARCHITECTURE.md) and the memo's capital section, plus [09 Tracks A–B] to sign |
| The engagement folder | Memo and draft into `02_Structuring_and_Governance`; agreement into `04_Contracts_DRAFTS`; only the memo into `06_Shared_with_Client` unless the client asked for the draft |

Naming: `YYYY-MM-DD_ClientOrTopic_DocType_vNN_STATUS.ext` — e.g.
`2026-10-01_Northstar_StructureMemo_v01_REVIEW.docx`. When write-back is
eventually enabled the system generates this rather than accepting it
([10](10_SHAREPOINT_WRITEBACK_SPEC.md)).

---

## Reading the output, in order of what matters

1. **Conflicts to resolve before drafting.** Non-empty means stop.
2. **Open questions.** Anything blocking Schedule A or formation must be
   answered before a document is worth producing.
3. **Adopted vs not yet adopted.** If a client will rely on an unadopted
   position, either adopt it ([09](09_DECISION_PACKET.md)) or say plainly it is
   a starting point.
4. **The alternatives.** Have the conversation. Founders often change their mind
   when they see the annual cost of separation next to what it buys.
5. **What this structure is built against.** The section founders remember.

---

## Common corrections

| Symptom | Cause | Fix |
|---|---|---|
| Threshold looks wrong | The 2% rule is a single-data-point inference | Set by hand; see [09 A1](09_DECISION_PACKET.md) |
| Too many entities | `business_lines` counts productions, locations, or properties — not products | Correct the count; consider the middle option |
| Unwanted deadlock ladder | Equal ownership with two or three members | If someone genuinely has control, set `equal_ownership=False` |
| Duplicate licence or IP entity | A sector layer is missing its `supersedes` | Set it in `sectors.py` |
| No waterfall on a deal that has one | `tiered_economics` not set | Set it |
| Disclosure missing | `tessera_role` left at default | Set `"both"` |
| A reviewer cannot accept | They are not in the mapped Entra group | Add them in Entra, not in code |

---

## Things it will not do, by design

Opine on enforceability · confirm a securities exemption · give tax advice ·
resolve a regulatory ownership question · invent a Tessera standard · file,
send, or execute anything.

Each appears in the memo as a confirmation or escalation rather than being
silently skipped.
