# 06 — Capital Architecture

*Written for Ryan.*

The engine produces the **frame** the model has to fit inside — the order money
leaves the deal, who is protected at each step, and what is still open. It does
not produce the model, the rates, or the returns. The boundary is deliberate.

---

## Why this lives in the structuring engine

A waterfall is a governance term wearing financial clothing.

1. **The distribution waterfall is a reserved matter.** "Distributions outside
   the agreed waterfall" is item six of the base ten, which means the waterfall
   has to exist as a defined thing before that reserved matter means anything.
2. **The economics and the tax election collide.** A preferred return or promote
   is a second class of interest; an S election permits one. The engine catches
   that — which it can only do if it knows the economics are tiered.
3. **The protections are governance.** "The promote survives removal other than
   for cause" and "the sponsor may be removed for cause without investors losing
   their capital position" are the same sentence read from two sides.

---

## When it applies

Tiered economics **or** passive capital. Otherwise the memo prints: *"Straight
pro rata economics with no outside capital. A waterfall here would be machinery
with nothing to do."* Saying it explicitly is the point — a silent omission
reads as an oversight.

---

## The tiers

**Sponsored deal — four tiers.** Where Tessera is a principal, or capital is a
private placement or institutional.

| # | Tier | To investors | To sponsor |
|---|---|---|---|
| 1 | Return of capital | 100% until contributed capital is returned | Pro rata on sponsor capital |
| 2 | Preferred return | 100% until paid current | Nothing at this tier |
| 3 | Sponsor catch-up | Reduced or none during catch-up | Accelerated until caught up |
| 4 | Residual split | The residual share | The promote |

A **clawback** is included: the sponsor cannot keep a promote paid on early
distributions the deal as a whole never earned.

**Club deal — three tiers.** Passive capital but no sponsor promote. The
catch-up drops and the remaining tiers renumber. No clawback, because there is
nothing to claw back.

The operating agreement's distribution clause now matches: the waterfall variant
carries the catch-up tier and the clawback, so the memo and the paper describe
the same economics. That gap is closed.

---

## Protections, by side

The engine states both. A memo listing only what protects the party Tessera
happens to be on that day is advocacy, not advice.

**Sponsor.** The promote survives removal other than for cause · sponsor capital
participates in the same tiers rather than being subordinated by silence · a
shortfall may be funded as a loan rather than forcing dilution · fees are
stated, capped, and separate from the promote, so a fee dispute is not a promote
dispute.

**Investor.** Preferred return is cumulative, so a lean year accrues · a
clawback · distributions outside the waterfall are a reserved matter · the
sponsor may be removed for cause without investors losing their capital position
· reporting on a stated cadence with inspection rights.

---

## What is deliberately left open

Printed under **Still to be set**, because these are commercial decisions that
belong to you, not defaults that belong to a library.

1. **The preferred return rate, and whether it compounds.** Compounding changes
   the sponsor's outcome far more than the headline rate, and it is the term
   most often agreed carelessly.
2. **The promote percentage, and whether it steps up at hurdles.**
3. **Whether the catch-up is full or partial.** Where most of the negotiation
   actually sits, and invisible in a headline "8 and 20." *The clause as drafted
   states a full catch-up — worth a deliberate decision.*
4. **Deal-by-deal or whole-fund.** Decides whether a clawback is ever reachable.
5. **Which fees the sponsor takes, and whether any credit against the promote.**

---

## The handoff

```
recommend_structure(profile).capital
    → CapitalArchitecture
        .applies / .why_not
        .tiers                              the order, as structure
        .sponsor_protective / .investor_protective
        .open_points                        what you decide
```

The frame does not move once counsel adopts it. The rates move every deal.

---

## Still not built

| Gap | Where it would go |
|---|---|
| A numeric waterfall engine | A new module, or your existing model taking the tiers as input — **worth a conversation before it is worth building** |
| Capital stack beyond equity | Senior debt, mezzanine, preferred equity. Lender covenants constrain governance whether or not the operating agreement calls them reserved matters, and nothing currently checks for that collision |
| Subscription and offering documents | Gated behind the securities question in [09 C2](09_DECISION_PACKET.md) |
| Sensitivity on the structure | "At what preferred return does this stop working for the sponsor?" — downstream of a numeric engine |
