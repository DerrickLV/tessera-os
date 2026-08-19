# 02 — Decision Rules

Every rule the engine applies, what triggers it, where the threshold sits, and
why. This is the document to argue with. Each names the function that implements
it and the test that pins it, so a change is made in one place and proved in
another.

The **Basis** column shows what the memo says today. `scaffold` and
`synthetic_reference` both become `tessera_adopted` the moment the area appears
in `config/adopted_positions.yaml` — see [09](09_DECISION_PACKET.md) for the
pre-drafted entry.

---

## 1. Entity form · `scaffold`

LLC, formed in the home state. The liability shield without corporate
formalities, and economics set by agreement rather than statute — which is what
makes every other term below writable at all.

**Does not decide:** whether an investor or lender requires a corporation, or
whether founders want QSBS, which an LLC cannot deliver. Both surface as
confirmations rather than being resolved.

`_recommendations`

## 2. Tax treatment · `statutory`

One member → disregarded. Two or more → partnership. Labelled statutory because
these are code defaults, not Tessera preferences. **The engine never recommends
an S election**; it surfaces the question where operators take compensation and
flags the conflict where an S election would collide with tiered economics.

`_tax_treatment`

---

## 3. Entity topology

### 3.1 Does a second entity earn its filing fee?

A HoldCo appears when **any** of: more than one line, location, property, or
production; any passive or institutional capital; real property beside an
operating business; a regulated regime; material IP; or a sector pattern
applies. Otherwise one entity, and the memo says why a second would be filings
and cost without moving risk.

`_entity_layers` · `test_a_simple_venture_gets_one_entity`

### 3.2 What sits beneath

| Layer | When | Prevents |
|---|---|---|
| HoldCo | Above | A claim against operations reaching ownership; a new investor forcing existing paper open |
| IP entity | `material_ip`, unless a sector entity supersedes | An operating failure taking the brand; a sale of one line handing over the frameworks behind all of them |
| PropCo | `real_property`; one per property in real estate | One property's judgment, environmental claim, or lender's remedy reaching another |
| OpCo | Unless the sector supplies per-unit operating entities | Concentrating everything claimable in the entity that owns the least |
| Licence holder | Regulated, unless superseded | A regulatory action taking the assets with it |

**Formation state.** Delaware for the HoldCo where capital is passive or
institutional; home state otherwise. Operating entities are always home-state — a
Delaware entity operating in Texas has to qualify in Texas anyway, so the second
filing buys nothing at the operating layer.

Sector entities: [05](05_SECTOR_PATTERNS.md).

---

## 4. The options menu · `scaffold`

Two or three viable structures, not one. Tessera's stated approach is to build
menus of outcomes rather than lock a client into a single path; an engine
returning one answer contradicts that however good the answer is.

| Option | Offered when |
|---|---|
| The recommended chart | Always, marked `recommended` |
| HoldCo with a single operating entity | Only where the recommended chart has 3+ entities |
| Single entity | Where the recommended chart has more than one |

Every option carries what it protects, what it costs (formations, agents, and
roughly `entities × $800`/year), and when to choose it. The alternatives are
written to be genuinely choosable — a menu whose other options are obviously
wrong is not a menu, and there is a test for that.

`_options` · `test_the_cheap_option_is_offered_honestly_rather_than_strawmanned`

---

## 5. Management model

| Condition | Model | Basis |
|---|---|---|
| Any passive capital | Manager-managed | `statutory` |
| More than 3 members | Manager-managed | `scaffold` |
| Otherwise | Member-managed | `synthetic_reference` → adoptable |

**Why passive capital forces it.** Two independent grounds pointing the same
way: a passive member with management rights has apparent authority no
counterparty can verify, and a passive interest is the one most likely to be
treated as a security.

**Why it matters downstream.** The model is carried into `DealProfile`, and the
clause library selects management and authority clauses on it. Without that, a
document could say *manager-managed* in §7 and *"either Managing Member, acting
alone"* in §8 — which it did, until it was caught.

`_management_model` · `test_the_document_cannot_contradict_itself_about_who_runs_the_company`

---

## 6. Ordinary-course authority threshold

The hinge. One number separates what one principal may do alone from what nobody
may do without the others.

```
no capital figure  →  $25,000
otherwise          →  2% of initial capital, floor $10,000, cap $250,000
```

| Initial capital | Threshold |
|---|---|
| — | $25,000 |
| $150,000 | $10,000 (floor) |
| $900,000 | $18,000 |
| $3,000,000 | $60,000 |
| $8,000,000 | $160,000 |
| $20,000,000 | $250,000 (cap) |

**The 2% is the weakest rule in the engine, and it is labelled as such.** The
$25,000 is real. The scaling is an inference from one data point. [09
A1](09_DECISION_PACKET.md) proposes adopting it with a review trigger at the
first annual review, when real operating spend exists.

`_ordinary_course_threshold` · `test_the_threshold_scales_with_the_capital_at_stake`

---

## 7. Reserved matters

Ten base matters, plus conditional additions, de-duplicated case-insensitively
keeping the first wording — two sources can name the same matter, and a liquor
licence appears in both the hospitality pattern and the liquor regime.

| Set | Count | When |
|---|---|---|
| Base | 10 | Always |
| Regulated | 3 | Any regime |
| Real property | 3 | `real_property` |
| Outside capital | 3 | Passive capital |
| Sector | 4–5 | Film, trades, hospitality |
| Regime | 1–2 | Cannabis, hemp, liquor, contractor |

The base ten, with the two subtlest called out:

1. Debt, guarantees, refinancing, **or any contract above the threshold or
   running beyond twelve months** — duration, not only dollars
2. New interests, admitting a member, options
3. Selling, leasing, transferring, or encumbering a material asset
4. Merging, converting, dissolving, bankruptcy
5. Amending the certificate or the agreement
6. Distributions outside the waterfall, and approving a capital call
7. Any activity materially outside the stated purpose
8. Senior executive compensation, **or engaging a member's affiliate as a
   service provider**
9. Litigation above the threshold
10. Changing accountants, tax classification, or any material tax election

`_reserved_matters`

---

## 8. Approval rule

| Condition | Rule | Threshold |
|---|---|---|
| 2 members, equal | Unanimous | 100% |
| 3+ members, equal | Supermajority | 75% |
| Otherwise | Majority with minority veto | 51% |

The minority veto covers amendments, new interests, related-party transactions,
and any change to the distribution waterfall.

`_approval_rule`

---

## 9. Deadlock ladder

Applies **only where no coalition can carry a reserved matter**.

```
majority with minority veto  →  no ladder
unanimous                    →  ladder
supermajority                →  ladder only if ceil(members × threshold%) ≥ members
```

Three equal owners at 75% need all three — unanimity by another name, so the
ladder applies. Five equal owners at 75% need four of five, so a dissenter is
**outvoted rather than deadlocked**, and no ladder applies. The memo gives a
different reason in each case.

**Why the restriction matters.** Where one party can already carry a decision, a
ladder does not break a tie — it hands the other side a lever to force an exit
over a decision that was never theirs.

**The ladder:** 15 business days → deadlock notice → meeting within 10 business
days → non-binding mediation within 30 days → buy-sell at 60 days, **but only if
the deadlock materially impairs ordinary-course operation.**

That last qualifier is the piece of craft. Strike it and a member who simply
lost a vote can force the other to buy or sell. A test asserts it survives.

`_deadlock_needed` · `test_the_deadlock_ladder_keeps_the_impairment_qualifier`

---

## 10. Buy-sell style

Passive capital or unequal ownership → **appraisal**. Otherwise → **shotgun**.

A shotgun prices the interest honestly because whoever names the number does not
know which side of the trade they will end up on — but only if both sides could
plausibly fund the purchase. Against a passive investor it becomes an option
held by the deeper pocket, and the conflicts check flags it if selected anyway.

`_buy_sell_style` · `test_a_shotgun_is_not_offered_against_a_passive_investor`

---

## 11. Exit architecture

| Element | Rule |
|---|---|
| Right of first refusal | Always |
| Permitted estate transfer | When `estate_planning_relevant` — revocable trust, retained voting control for life, trustee joinder |
| Triggering events | 6 base; divorce added only when `spouses_involved` |
| Valuation | Agree in 15 days → two appraisers → within 10% take the average → else a binding third |
| Payment | 20% cash, 80% on a note at AFR over 36 months, secured, prepayable |
| Tag-along | Where a minority exists, or capital is passive |
| Drag-along | Only where `exit_intent == "sale"` |
| Insurance funding | Where `key_person_dependency` |

The six base triggers: death; disability (90 consecutive, or 120 in any trailing
180); bankruptcy; voluntary withdrawal; material breach uncured for 30 days;
felony or crime of fraud, dishonesty, or moral turpitude materially affecting
the company.

`_exit_architecture`

---

## 12. Capital architecture

Applies with tiered economics **or** passive capital. Otherwise the memo says
why a waterfall would be machinery with nothing to do. Detail:
[06](06_CAPITAL_ARCHITECTURE.md).

`_capital_architecture`

---

## 13. Dual-role disclosure

Triggered when `tessera_role == "both"` (or the older `tessera_is_principal`).
Produces four things: a written disclosure at the **top** of the memo, before
the structure; a position; a failure mode (*"the advisor turns out to be across
the table"*); and an open question asking whether written consent was actually
obtained.

From Tessera's own published commitment: *"we're clear about which hat we're
wearing — advising you, investing alongside you, or both by agreement."*

`_dual_role_positions` · `test_the_disclosure_leads_the_memo_rather_than_hiding_in_it`

---

## 14. Conflicts

Run before delivery, because a document that contradicts itself is worse than
one that is merely incomplete.

| Conflict | Detected when |
|---|---|
| S election vs tiered economics | An S corporation may have one class of stock |
| Deadlock ladder vs majority control | Ladder present with a controlling holder |
| Shotgun vs passive investors | Shotgun selected with passive capital |
| Manager management vs a long unanimous list | The manager cannot actually manage |
| Unanimity across 3+ owners | Every owner holds a veto over everything |
| Outside capital | An interest is being offered; securities counsel confirms the exemption |

`_conflicts`

---

## 15. Open questions

Every one states what it **blocks**. A question with no consequence is noise,
and a test asserts each carries a `blocks`.

Always: capital contributions in dollars; services-or-property contributions;
registered agent and principal office. Conditionally: compensation structure;
hold period; foreign qualification (home state excluded); regime ownership
requirements; and written consent to the dual role.

`_open_questions`

---

## 16. Glossary

Only terms the memo actually uses. Six always appear; the rest are conditional
on what the memo produced. Definitions come from Tessera's own public
plain-English glossary, so the memo speaks in the register the firm already uses
rather than inventing a second one.

`_glossary` · `test_the_glossary_covers_only_words_the_memo_actually_uses`

---

## 17. The parity contract

`StructureRecommendation.expected_clause_categories()` declares which clause
categories the assembled document must carry for this memo. Nineteen always;
`deadlock` only where a ladder applies; `estate_transfer` only where offered.

Any position the memo promises must appear as a section of the paper, or the
suite fails. This exists because seven categories once went missing from the
library while the memo kept promising all seven — and every coverage check
passed.

`expected_clause_categories` · `test_every_promised_position_is_delivered_by_the_document`
