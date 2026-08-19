# 04 — Counsel Review Packet

*Prepared by Tessera Group for review by qualified counsel. Nothing in this
system constitutes legal or tax advice, and nothing it produces should be
executed without counsel review.*

Organised by **question**, not by clause. Counsel is not being asked to read a
structuring memo cold — they are being asked to resolve a specific list.

The four questions only counsel can close are drafted in full in
[09 — Decision packet, Track C](09_DECISION_PACKET.md). This document is the
surrounding context.

---

## What this system is

Tessera OS assembles entity-structuring recommendations and draft operating
agreements from a library of clause variants. It is deterministic: the same
facts and the same adoption ledger always produce the same document.

Every position carries a provenance marker. The adoption ledger currently ships
**empty**, so today every position is either a synthetic evaluation reference or
an unadopted starting point, and every memo says so. Counsel is being asked to
confirm the positions the partners intend to adopt.

The engine is explicit about its limits. It does not opine on enforceability,
does not confirm a securities exemption, does not give tax advice, and does not
claim to know any state's law — it carries a governing state through and flags
what turns on it.

---

## Priority order

1. **Restrictive covenant periods** — 12-month non-compete plus a 24-month
   trailing non-solicit, given by owners for equity. Void in California as
   drafted, likely unenforceable in Oklahoma under 15 O.S. § 217, and lacking a
   geographic limitation for Texas. Full question: [09 C1](09_DECISION_PACKET.md).
2. **Securities posture** — where passive capital is taken, an interest is being
   offered. Exemption, accreditation standard, disclosure package, and whether
   advisory work in a raise implicates broker registration. [09 C2].
3. **Capital call default rate and dilution mechanics** — usury limits per
   jurisdiction, the exclusive-remedies statement, Article 9 perfection, and the
   dilution formula which has never been run against a real cap table. [09 C3].
4. **Regulated ownership** — per regime, per state. [09 C4].

---

## The valuation question, called out separately

The fair-market-value clause is **silent on whether the appraiser applies
discounts for lack of marketability and lack of control.** That silence is
deliberate — the instruction can move a buy-out price by roughly a third, and it
is the most commonly litigated omission in buy-sell provisions.

The partners' proposed answer is in [09 A9](09_DECISION_PACKET.md): instruct the
appraiser to **disregard both discounts**, on the reasoning that Tessera is more
often the remaining party than the departing one, and disregarding discounts
protects the side with least leverage and most reason to litigate.

Counsel should confirm that instruction is enforceable and drafted correctly.

---

## Jurisdictional assumptions in the library

Jurisdiction handling is carried as reviewable **data** — notes and availability
flags on individual clause variants — rather than as logic. Each entry is
Tessera's reading and needs confirmation.

| Jurisdiction | Assumption | Confirm |
|---|---|---|
| California | Non-solicit and non-compete unavailable entirely | Whether the owner exception applies, and on what facts |
| Oklahoma | Non-compete likely void under 15 O.S. § 217; fallback to a 12-month mutual non-solicit | Whether the fallback is enforceable, and whether it must be limited to established customers in the text |
| Texas | Owner covenants enforceable if reasonable in duration, area, and activity | The geographic limitation to add |
| Delaware | Default HoldCo jurisdiction where capital is outside | Confirmation only |

**Anywhere else there are no overlays, and the memo does not claim there are.**
An engagement in an unlisted state is itself an open question.

---

## What the engine already refuses to do

Offered so counsel can see where the boundaries were drawn, and challenge them.

- **Refuses a hollow document.** Each agreement type declares its essential
  categories — now including the full exit set: triggering events, valuation,
  buy-sell, and payment terms. If the library cannot cover them, assembly raises
  rather than producing something that reads complete.
- **Refuses a broken cross-reference.** Every `Section X` resolves, and a
  dangling reference is reported in the document rather than silently rendered.
- **Refuses an undefined defined term.**
- **Refuses an invalid commercial term.** Money, percent, days, and choice
  values are validated on format.
- **Refuses a document with a blank in it.**
- **Refuses to promise what it cannot deliver.** A position in the memo must be
  matched by a section in the paper, enforced by test.
- **Refuses to invent a standard.** Where no adopted position exists, the output
  says so.

---

## Documents to review alongside this

| Document | What it is |
|---|---|
| `fixtures/clause_library/SAMPLE_Northstar_Operating_Agreement.docx` | A complete assembled operating agreement, all terms filled |
| `fixtures/clause_library/SAMPLE_Northstar_Structure_Recommendation.docx` | The memo that produced it |
| `fixtures/clause_library/SAMPLE_Structure_Diagnosis.md` | The screen of an inbound agreement |
| [09 — Decision packet](09_DECISION_PACKET.md) | The questions, drafted |
| [02 — Decision rules](02_DECISION_RULES.md) | Every rule and why |
| `docs/PROMPT_ASSUMPTIONS_TO_CONFIRM.md` | Assumptions in the specialist prompts, flagged separately |
