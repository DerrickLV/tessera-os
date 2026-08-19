# 08 — Roadmap

What is not built, mapped to **Diagnose → Architect → Capitalize → Execute**.

---

## Coverage now

| Stage | Then | Now | What changed |
|---|---|---|---|
| **Diagnose** | ~10% | ~60% | `diagnosis.py` screens an existing agreement; `intake.py` proposes a profile with a citation per field |
| **Architect** | ~90% | ~95% | Adoption ledger; memo/document parity contract; the seven restored clause categories |
| **Capitalize** | ~25% | ~40% | Waterfall clause now matches the 4-tier frame, with catch-up and clawback |
| **Execute** | ~15% | ~45% | `formation.py` derives the filing order; `digest.py` reports what is waiting; write-back spec written with writes still off |

---

## Ranked

### 1. Sign the decision packet
**Effort:** an afternoon · **Value:** highest

Not a build. [09](09_DECISION_PACKET.md) pre-drafts eleven partner-adoptable
positions; signing moves them from "reasonable starting point" to "Tessera's
position, with a source." Everything below is worth more once this is done,
because every new capability otherwise widens the surface of *"this is a
starting point"* faster than it widens *"this is what Tessera does."*

### 2. Wire diagnosis into the console and SharePoint
**Effort:** low · **Value:** high

`diagnose_agreement()` works standalone. It should run on a document read from
an engagement's SharePoint folder and land in the review queue like everything
else. Small, and it turns the "is what we have right?" half into a real
workflow.

### 3. Deepen the diagnosis from screen to review
**Effort:** medium · **Value:** high

Today it detects presence, never adequacy. The next step is comparing detected
language against the library's `review_positions()` bands and saying where an
inbound term falls inside or outside the approved range — which is what turns
"you have a buy-sell" into "your buy-sell has no valuation method and a 10-day
election window."

### 4. Capital stack beyond equity
**Effort:** medium-high · **Value:** medium-high

Senior debt, mezzanine, preferred equity. Lender covenants constrain governance
whether or not the operating agreement calls them reserved matters — a
change-of-control covenant can override a transfer provision entirely, and
nothing currently checks for that collision.

### 5. Structure comparison
**Effort:** medium · **Value:** medium-high

Two profiles in, a diff out: what changes in the chart, in control, and what it
costs to move — retitling, re-consenting lenders, fresh regulatory approval
where a licence is involved. Answers *"what happens if we add a partner?"*
without re-running the engagement.

### 6. Investor subscription and offering documents
**Effort:** high · **Value:** medium-high · **Blocked**

Gated on the securities posture in [09 C2](09_DECISION_PACKET.md). Building it
before counsel defines the exemption posture would be building on a guess.

### 7. Numeric waterfall engine
**Effort:** medium · **Value:** medium · **Ask Ryan first**

Turn tiers into distributions on real numbers. Ryan may already have this, in
which case the right build is an export of the tier structure into his model
rather than a second model.

### 8. Succession and generational planning
**Effort:** medium · **Value:** medium

The Brand Messaging Foundation names the Skilled-Trade Owner whose fear is *"the
company living and dying with them."* The engine answers the transactional
question (buy-out on death) and not the structural one (a plan for the business
to continue) — second qualifier, key-person depth, documented transition,
estate structure carrying equity across a generation.

### 9–11. Multi-state qualification map · cap table and dilution modelling · governance calendar
**Effort:** low–medium each · **Value:** medium

The dilution formula in particular has never been run against a real cap table,
which [09 C3](09_DECISION_PACKET.md) flags as a twenty-minute exercise that
belongs before adoption.

### 12. More sectors
**Effort:** low each · **Value:** depends entirely on deal flow

`sectors.py` is pure data and two generic tests cover any new pattern
automatically. **Do not build speculatively.** Build one when an engagement
needs it.

---

## Deliberately not on this list

**Enforceability opinions** — the engine flags jurisdiction and routes to
counsel; it should not start predicting outcomes.

**A jurisdiction law database** — keeping it current is a full-time obligation
and being wrong is worse than being silent.

**Automatic filing or signature** — external actions. The external-action gate
is a load-bearing safety property and should stay closed.

**A model call inside the engine** — a recommendation that varies between runs
cannot be reviewed, diffed, or defended.

**SharePoint write-back before its spec is agreed** — [10](10_SHAREPOINT_WRITEBACK_SPEC.md)
defines the gate. It stays shut until that is signed off.
