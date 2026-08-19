# Prompt assumptions to confirm

The original twelve specialist prompts were rewritten on 18 August 2026. The
synthetic Structure Manager was added afterward under its own evidence and review controls. Tessera's
*doctrine* in them was drawn from stated firm philosophy and public positioning.
The items below are **inferences that were not sourced from a Tessera record**,
and a model will apply them as if authoritative.

Confirm or correct each. This should take about twenty minutes. Anything you
change here needs the same change in the named prompt file.

**Reviewer key:** D = Derrick · R = Ryan · C = outside counsel

---

## A. Firm doctrine — applies across the original twelve prompts

| # | Encoded as | Where | Who |
|---|---|---|---|
| A1 | "Structure before terms: governance, control, and rights architecture get settled before commercial detail." | `contract_manager.md` | D |
| A2 | "Protect optionality — prefer a menu of outcomes to a single locked path." | `contract_manager.md`, `proposal_manager.md` | D |
| A3 | "Collaborative on the surface, precise about consequences underneath. Never adversarial." | `_shared.md` | D |
| A4 | Reader is "a principal: intelligent, decisive, not necessarily fluent in legal or capital-markets vocabulary." | `_shared.md` | D |
| A5 | Severity ladder: Critical / Material / Notable, with everything below Notable suppressed. | `_shared.md` | D, R |
| A6 | Confidence vocabulary: Confirmed (two independent sources or one authoritative primary) / Reported / Unverified / Unknown. | `_shared.md` | D, R |

**A5 and A6 are the two worth the most attention.** They set what gets surfaced
at all, and what "confirmed" means firm-wide. Everything downstream inherits them.

---

## B. Contract Manager — `prompts/contract_manager.md`

The 18 August dry run showed this prompt inventing a playbook standard when no
playbook was in evidence. That is now fixed: with no approved record loaded, the
prompt must say so and must not state a band as Tessera's. The items below are
the remaining judgment calls.

| # | Encoded as | Who |
|---|---|---|
| B1 | The issue classes always raised: uncapped or one-way indemnity, low liability caps, auto-renewal without a workable exit, IP assignment broader than the engagement, non-solicit/non-compete beyond band, unilateral amendment rights, payment terms with real working-capital cost. **Anything missing from this list will be systematically under-reported.** | C |
| B2 | Always suppressed: style, ordinary boilerplate at standard, defined-term formatting, positions inside the approved band. | C |
| B3 | Escalate immediately on: regulatory/licensing questions in a regulated industry; enforceability turning on jurisdiction-specific law; conflict between two executed documents; apparent authority problems; anything touching a principal's personal liability. | C |
| B4 | "Write the cost line for the principal, not the lawyer" — plain-language consequence over legal characterization. | D |
| B5 | Every legal document carries a note that qualified counsel must review before execution. | D, C |

**Not yet supplied:** a counsel-approved production clause playbook. Until that private playbook
record exists in evidence, every contract review will correctly report that it is
comparing against general commercial norms rather than a Tessera standard. That
is the safe behaviour, but it caps the value of the workflow. **Loading a real
playbook is the single highest-value input you can give this agent.**

---

## C. Capital Manager — `prompts/capital_manager.md`

| # | Encoded as | Who |
|---|---|---|
| C1 | Reconcile model versions *before* any analysis; an elegant analysis of the wrong version is the most expensive output. | R |
| C2 | Downside case is the analysis; base and upside "are easy and rarely decisive." | R |
| C3 | Name the covenant, its threshold, and current headroom in the same sentence. | R |
| C4 | Test liquidity and timing, not just returns — "a deal that clears on paper and runs out of cash in month fourteen has failed." | R |
| C5 | A sponsor's own rent growth is *asserted*, never *confirmed*, however reasonable. | R |
| C6 | Flag structural terms regardless of returns: recourse, cross-collateralization, cash management triggers, control rights on default. | R |
| C7 | Never guarantee or imply a return; never let a range collapse to a point estimate in the summary. | R, D |

**Not yet supplied:** approved covenant thresholds, target return bands, and the
firm's standard sensitivity cases. Same caveat as B — without them the agent
reasons from general norms.

---

## D. Due Diligence Manager — `prompts/due_diligence_manager.md`

| # | Encoded as | Who |
|---|---|---|
| D1 | Material facts require two independent sources or one authoritative primary record. Two outlets running the same wire story count as one. | D |
| D2 | Allegations never enter a risk rating, even weighted. | D, C |
| D3 | Protected characteristics are never inferred, recorded, or reasoned from — and an excluded item is noted as excluded. | D, C |
| D4 | Family, private life, and non-business associations are out of scope absent a public regulatory or legal record bearing on the question. | D, C |
| D5 | "Diligence that reports no red flags is a real result" — stated directly rather than hedged. | D |

D3 and D4 have legal exposure attached. Worth counsel's eye rather than only
yours.

---

## E. Other specialists — lighter-touch

| # | Encoded as | Where | Who |
|---|---|---|---|
| E1 | Escalate on a named threshold, not a feeling (example given: "permit comment response exceeds 10 business days" — illustrative only). | `project_manager.md` | D |
| E2 | Construction safety is reported first, before any schedule or cost analysis, and never ranked against them. | `construction_manager.md` | D |
| E3 | A contractor's percent-complete on a pay application is an assertion with money attached, reconciled against observed progress before driving a forecast. | `construction_manager.md` | D |
| E4 | Agency verbal comments are *reported*, not commitments, until in writing. | `development_manager.md` | D |
| E5 | Proposals never invent experience, availability, or price; gaps get a marked placeholder rather than composed language. | `proposal_manager.md` | D |
| E6 | Prefer a defined base engagement with priced options over one large number. | `proposal_manager.md` | D |
| E7 | Two engagements sharing a principal are still two engagements — never merge context. | `knowledge_manager.md` | D |
| E8 | Intelligence: high-impact claims need two independent sources *and* two source kinds; name what would falsify each conclusion. | `intelligence_agent.md` | D |
| E9 | Automations: every action classified reversible / compensable / permanent; permanent actions need per-instance approval, never a standing grant. | `automation_manager.md` | D |

---

## How to record a correction

Edit the prompt file directly and note the change here. Prompt edits are visible
in the audit trail — `service.py` records a digest of the composed instructions
(shared plus specialist), so a change to `_shared.md` or any specialist file
produces a new `prompt_version` on every subsequent run.

Nothing in this list is load-bearing for safety. The action gates, scope
isolation, and approval requirements are enforced in code and do not depend on
prompt text. These items affect **quality and accuracy of judgment**, which is
exactly what a human has to supply.
