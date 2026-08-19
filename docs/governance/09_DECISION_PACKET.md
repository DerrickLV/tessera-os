# 09 — Decision Packet

**Purpose: make sign-off cheap, not optional.**

You asked whether we could replace counsel and Ryan with answers derived from
your own material. Here is the honest split, and it is the whole design of this
document.

**Ryan is a co-decider, not a bottleneck, and that is structural.** Tessera's
own governance makes firm-level decisions unanimous between the partners. The
adoption ledger enforces it: an entry with one name is invalid by construction.
What I *can* do — and have done below — is pre-draft every decision so his part
is reading a proposal and saying yes, no, or "not that number." That turns an
afternoon into twenty minutes.

**Counsel cannot be replaced on four specific questions, and I will not pretend
otherwise.** Enforceability of restrictive covenants, whether a securities
exemption applies, the tax treatment of an election, and whether a regulator
will accept an ownership chart are not questions this system can answer from
your materials — not because the reasoning is hard, but because being wrong is
expensive in a way no amount of internal confidence fixes. For those, this
packet drafts the *question* rather than the answer, so counsel's time is spent
deciding rather than reconstructing context. That is the useful version of
"cheaper counsel."

Everything else — the great majority — is genuinely yours to decide, and every
item below is drafted to be adoptable today.

---

## How to use this

Each item states the proposal, the reasoning drawn from your own materials, what
it costs if the proposal is wrong, and the exact ledger entry to paste into
`config/adopted_positions.yaml`. Signing is copying the entry, putting both
names on it, and dating it.

| Track | Items | Who decides |
|---|---|---|
| **A — Partner-adoptable now** | 11 | Derrick + Ryan |
| **B — Partner-adoptable, counsel confirms later** | 4 | Derrick + Ryan, `counsel_reviewed: false` |
| **C — Counsel only** | 4 | Drafted questions, not answers |

---

# Track A — adoptable today

## A1. Ordinary-course authority

**Proposal.** Adopt the threshold as: **$25,000 for a venture with no stated
initial capital; otherwise 2% of initial capital, floored at $10,000 and capped
at $250,000.**

**Reasoning from your material.** The $25,000 is not an inference — it is the
figure in your own operating agreement, chosen by you for a two-partner advisory
firm. What has never been decided is what happens when the venture is not that.
The 2% rule was reverse-engineered from that single point and it produces:

| Initial capital | Threshold | Sense check |
|---|---|---|
| — | $25,000 | Your own number, unchanged |
| $150,000 | $10,000 (floor) | A small venture can still buy a laptop and a lawyer |
| $900,000 | $18,000 | A trades business can order a truck, not a fleet |
| $3,000,000 | $60,000 | A real estate hold can pay a contractor draw |
| $8,000,000 | $160,000 | Large, and defensible against a $8M balance sheet |
| $20,000,000 | $250,000 (cap) | The cap exists so the rule never outruns judgment |

**If the proposal is wrong.** Too low and every invoice becomes a negotiation,
which is how partners quietly stop following their own agreement. Too high and
one partner can commit the company to something the other never saw — which is
the failure the clause exists to prevent. The floor and cap bound both errors.

**The alternative worth considering.** A multiple of monthly operating spend
rather than of capital. It is more accurate and it requires a number nobody has
at formation, which is exactly when this clause gets drafted. My recommendation
is to adopt the capital rule and revisit at the first annual review, when real
spend exists.

```yaml
  - area: "Ordinary-course authority"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. IV; scaling rule adopted by the partners"
    counsel_reviewed: false
    note: "$25,000 default; 2% of initial capital, floor $10,000, cap $250,000."
```

## A2. Reserved matters

**Proposal.** Adopt the **base ten** as the Tessera list, and adopt the
conditional additions as **defaults that survive unless struck for a deal**.

**Reasoning.** The base ten are already yours. The twelve-plus additions
(regulated, real property, outside capital, sector) were mine, and each one
follows the same test the base ten pass: it is a decision that is expensive to
reverse and cheap to require consent for. The two most worth arguing about:

- *"Any contract extending beyond twelve months"* — duration rather than
  dollars. This is the subtlest item in your own list and I would keep it: a
  cheap five-year commitment is still a five-year commitment.
- *"Engaging a member's affiliate as a service provider"* — also yours, and the
  one most likely to be negotiated away by a counterparty who intends to do
  exactly that.

**What I think is missing from both lists.** Nothing structural. If you want a
candidate: *changing the company's insurance program or allowing a policy to
lapse*, which is a decision with a catastrophic tail and no natural owner.

**If the proposal is wrong.** An over-long list makes a manager unable to
manage — which the conflicts check already flags when a manager-managed entity
carries a long unanimous list. Under-listing is worse and slower to discover.

```yaml
  - area: "Reserved matters"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. IV (base ten); conditional additions adopted by the partners"
    counsel_reviewed: false
```

## A3. Management model

**Proposal.** Adopt: **member-managed where every owner is active and there are
three or fewer; manager-managed the moment any capital is passive, or above
three members.**

**Reasoning.** The member-managed half is yours already. The trigger on passive
capital rests on two independent grounds that point the same way — apparent
authority (a passive member who can bind the company is a problem for every
counterparty) and the securities analysis (a passive interest is the interest
most likely to be treated as a security). Either alone would justify it.

**If the proposal is wrong.** The cost is friction, not exposure: a manager-
managed entity where everyone is active makes the members sign a consent for
things they would otherwise just do.

```yaml
  - area: "Management"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. IV"
    counsel_reviewed: false
```

## A4. Deadlock

**Proposal.** Adopt the four-step ladder **including the impairment qualifier**,
and adopt the rule that a ladder applies only where no coalition can carry a
reserved matter.

**Reasoning.** The ladder is yours. The restriction — no ladder where someone
already has control — is the piece that was never written down, and it is the
one that protects you when you are the majority holder. Without it, a minority
gets an exit lever over decisions that were never theirs.

**The impairment qualifier is the sentence to defend in negotiation.** Strike
it and the buy-sell becomes something a member can trigger after simply losing a
vote.

```yaml
  - area: "Deadlock"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. IV–V"
    counsel_reviewed: false
```

## A5. Buy-sell selection

**Proposal.** Adopt: **shotgun between equals with comparable liquidity;
appraisal wherever liquidity is asymmetric.**

**Reasoning.** The shotgun is yours and it is the right mechanism between two
partners who could each fund a purchase. The asymmetry rule is the honest
extension: against a passive investor a shotgun is not a fair-price mechanism,
it is an option held by whoever has cash.

```yaml
  - area: "Buy-sell"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. X"
    counsel_reviewed: false
```

## A6–A9. Capital calls · Transfer restrictions · Triggering events · Valuation

**Proposal.** Adopt all four as drafted. Each is already Tessera's own position;
the only thing missing is the signature that lets the system say so.

- **Capital calls** — no obligation to contribute; the funding member elects
  loan or dilution; exclusive remedies.
- **Transfer restrictions** — void ab initio, ROFR on the same price and terms,
  estate-planning carve-out with retained voting control.
- **Triggering events** — the seven, including divorce and the conduct triggers.
- **Valuation** — agree in 15 days, two appraisers, 10% convergence, binding
  third.

**One thing to decide inside A9.** The valuation clause is silent on whether the
appraiser applies discounts for lack of marketability and lack of control. That
silence is currently deliberate. It is also worth a partner decision, because it
can move a buy-out price by roughly a third. *My suggestion: instruct the
appraiser to disregard both discounts.* You are more likely to be the
remaining partner than the departing one, and disregarding discounts protects
the departing side — which is the side that has least leverage and most reason
to litigate.

```yaml
  - area: "Capital calls"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. VI"
    counsel_reviewed: false
  - area: "Transfer restrictions"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. X"
    counsel_reviewed: false
  - area: "Triggering events"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. X"
    counsel_reviewed: false
  - area: "Valuation"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. X"
    counsel_reviewed: false
    note: "Discount instruction to be settled — see A9."
```

## A10. Payment terms

**Proposal.** Adopt 20% cash at closing, balance on a secured note at the
applicable federal rate over 36 months, prepayable.

**Reasoning.** Yours already, and the reasoning is worth keeping visible: a
buy-out the buyer cannot fund is not a remedy. Twenty percent down keeps the
right exercisable by a working business rather than only by whoever holds cash.

```yaml
  - area: "Payment terms"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tesserra Holdings LLC Operating Agreement, Art. X"
    counsel_reviewed: false
```

## A11. Dual-role disclosure

**Proposal.** Adopt the disclosure as a **standing requirement**, not a
case-by-case judgment: whenever Tessera both advises and holds equity, the
disclosure is signed before terms are negotiated.

**Reasoning.** This is the one item where your own published position is
stronger than anything I would have proposed. Your Holdings page commits to
being clear about which hat you are wearing. Making it standing rather than
discretionary removes the moment where someone decides this particular deal is
too small to bother.

```yaml
  - area: "Dual-role disclosure"
    adopted_by: ["Derrick Carlisle", "Ryan Strasshofer"]
    date: "YYYY-MM-DD"
    source_ref: "Tessera Group Holdings page; firm governance model"
    counsel_reviewed: false
```

---

# Track B — adopt now, counsel confirms later

These are yours to decide, but each carries a question only counsel closes.
Adopt with `counsel_reviewed: false` and the memo will keep printing the
confirmation line until it is answered.

## B1. Entity form

**Proposal.** LLC in every case, with a **named trigger list** that forces the
corporation conversation rather than leaving it to notice: institutional venture
capital on standard terms, an employee option pool, or a founder who wants QSBS.

**Why not switch automatically.** Because the trigger is usually a conversation
about the client's ambition, not a fact in an intake form. Flagging it is honest;
switching silently is not.

## B2. Tax treatment

**Proposal.** Partnership by default; never propose an S election; always flag
the S-election *question* where operators take compensation.

**Why.** The S election is genuinely attractive in one narrow case — a services
business with profit well above reasonable compensation — and it is
catastrophic in the case you work in most, because one class of stock is
incompatible with a preferred return or a promote. The engine already treats
that pair as an irreconcilable conflict. Keep the flag; leave the election to
the tax advisor.

## B3. Topology rules

**Proposal.** Adopt HoldCo/OpCo, one PropCo per property, IP held apart, and
licence isolation as Tessera defaults.

**The one I would argue about.** One PropCo per property is right until it
isn't — at some portfolio size the filing and accounting burden outruns the
isolation benefit, and lenders start asking for cross-collateralisation anyway.
*Suggestion: adopt per-property isolation as the default and set a review
trigger at six properties*, rather than pretending the rule scales forever.

## B4. Tag-along and drag-along

**Proposal.** Tag wherever a minority exists; drag only where the exit intent is
a sale; drag threshold left open per deal.

**Why the threshold stays open.** It is the single most side-dependent term in
the set — higher protects the minority, lower protects the exit — and Tessera
sits on both sides depending on the engagement. A firm default here would be
false precision.

---

# Track C — counsel only

Drafted as questions, with the context counsel would otherwise have to
reconstruct. This is the part of the packet that saves the most billable time.

## C1. Restrictive covenant periods — **highest priority**

**The question.** Tessera's own agreement runs a 12-month non-compete with a
non-solicit for 24 months *following that period* — 36 months cumulative — given
by owners in exchange for equity.

Confirm, per jurisdiction:

1. Is 36 months cumulative defensible as an **owner** covenant rather than an
   employee covenant?
2. **California** — currently marked unavailable entirely. Does the owner
   exception apply, and on what facts?
3. **Oklahoma** — 15 O.S. § 217 voids general non-competes with a narrow
   goodwill-sale exception. Is the fallback (confidentiality plus non-solicit)
   enforceable, and must the non-solicit be limited to established customers in
   the clause text rather than in a note?
4. **Texas** — enforceable if reasonable in duration, area, and activity. The
   clause has **no geographic limitation**. What limitation should be added?
5. Should there be a jurisdiction-specific schedule of periods rather than one
   global period with overlays?

**Why this is first.** It is the position most likely to be relied on, most
likely to be unenforceable as drafted, and the only one where being wrong is
discovered at exactly the moment it matters.

## C2. Securities posture

**The question.** Where Tessera structures a venture taking passive capital, an
interest is being offered. Confirm the exemption relied on, the accreditation
standard, the disclosure package, and — separately — whether any part of
Tessera's advisory work in a capital raise implicates **broker registration**.

**Why it gates other work.** The investor subscription and offering documents on
the roadmap cannot responsibly be built until this is answered.

## C3. Capital call default rate and dilution mechanics

**The question.** Confirm the default loan rate against the usury limit in each
governing jurisdiction (defaults are 12% / 10% / 8% by posture), whether the
exclusive-remedies statement forecloses anything worth preserving, and whether
the pledge is perfected under Article 9 as drafted.

**Plus one thing nobody has done.** The dilution formula has never been run
against a real cap table. That is a twenty-minute exercise and it belongs before
adoption, not after.

## C4. Regulated ownership — per regime, per state

**The question.** For each regime Tessera works in, confirm ownership disclosure
thresholds, what constitutes a change of control requiring prior approval, and
whether the proposed structure is permitted at all. Cannabis and liquor are the
live ones; hemp is a documentation question rather than a licensing one; the
contractor regimes turn on whether the licence follows the entity or the
individual.

---

## What signing changes

Today every memo prints nineteen positions under *"Positions not yet adopted."*
Adopting Track A alone moves eleven of them into *"Adopted Tessera positions,"*
each with a citation by reference and both partners' names.

That is not cosmetic. It is the difference between a founder being told "here is
a reasonable starting point" and "this is what Tessera does, and here is why" —
which is the difference the whole engine was built to make.

Track B adds four more with the confirmation line still showing. Track C is the
only part that waits, and it waits for a good reason.
