# Phase 7A review, and Phase 7B specification

**Date:** 18 August 2026
**Reviewer:** Claude (working alongside Codex)
**Scope:** `src/tessera_os/workspace.py`, `console.py`, `web/tessera-console.html`,
`prompts/`, and the Phase 7A readiness report, as they stand on
`codex/phase-7a-pilot-workspace`.

---

## 1. Verdict

Phase 7A built the right thing. The end-to-end loop — project → task → draft →
review queue → decision → audit trail — exists, persists, and works in a browser.
The isolation, injection, and approval controls around it are real.

Two findings below are load-bearing. Neither is a defect in what was built; both
are the difference between a pilot that *looks* successful and one that tells you
something. They should be closed before any measured pilot session runs, because
a pilot run against them will produce numbers that cannot be interpreted.

---

## 2. Finding 1 — Three of the four pilot metrics are hardcoded literals

`workspace.py`, `PilotWorkspace.run()`:

```python
metrics = [
    ArtifactMetric(name="citation_coverage",  value=100, target="100%", passed=True),
    ArtifactMetric(name="unsupported_claims", value=0,   target="0",    passed=True),
    ArtifactMetric(name="external_actions",   value=0,   target="0",    passed=True),
    ArtifactMetric(name="oldest_evidence_age", value=round(evidence_age_days, 1), ...),
]
```

`citation_coverage`, `unsupported_claims`, and `external_actions` are constants.
They do not measure anything. They will report 100 %, 0, and 0 — and `passed:
True` — for every artifact the system ever produces, including a bad one. Only
`oldest_evidence_age` is computed from data.

This matters more than it looks. The readiness report lists "citation coverage"
and "unsupported claims" as delivered metrics, and the remaining-gates section
asks the pilot to record them. A reviewer running a pilot session will see three
green metrics and reasonably conclude the drafting is sound. The metrics are
green because they are written green.

`citation_coverage` is also structurally tautological right now. The artifact
builds exactly one citation, pairing the entire summary with every source ID:

```python
citations = [ArtifactCitation(claim=template.summary,
                              source_ids=[item.source_id for item in template.evidence])]
```

One claim, all sources, therefore 100 % coverage by construction.

**What to do.** Either compute these or remove them. Do not ship a metric that
cannot fail.

- **`citation_coverage`** — requires claims to be individually enumerable. Change
  `PilotTemplate` to carry a list of discrete claims, each with its own
  `source_ids`, rather than one summary blob. Coverage is then
  `claims_with_sources / total_claims`, and a template with an uncited claim
  produces a number below 100.
- **`unsupported_claims`** — cannot be computed deterministically. It needs a
  judge: a human label or a second model grading the draft against its evidence.
  Until that exists, remove the metric rather than reporting zero. A missing
  metric is honest; a hardcoded passing one is not.
- **`external_actions`** — this one is genuinely always zero, and it is enforced
  in code. Keep it, but source it from the audit store rather than a literal, so
  it would actually move if the invariant ever broke. That is the entire value of
  the metric.

---

## 3. Finding 2 — The task input does not affect the output

`PilotWorkspace` holds one template per project:

```python
self.templates = {item.project_id: item for item in templates}
...
template = self.templates[request.project_id]
```

The user's task text is used for three things: an injection check, a routing
preview, and storage on the artifact. It does not select the workflow. Asking
for a *contract review* and an *underwriting analysis* on the same project
returns the same draft.

The routing result is computed and then explicitly discarded:

```python
if route.primary_agent != template.agent_id:
    warnings.append(f"Routing selected {route.primary_agent}; the project pilot "
                    f"template uses {template.agent_id}. The fixture-backed "
                    f"manager remains authoritative.")
```

This is honest — it warns rather than hides — but it means step 2 of the intended
loop ("choose a task, such as proposal review, contract review, development
status, or underwriting analysis") is not yet real.

**What to do.** Key templates on `(project_id, workflow)` rather than
`project_id`, and select by the routed agent with an explicit fallback when no
template matches that pairing. Present the task choice in the UI as a defined
list of workflows for the selected project, rather than free text that appears to
matter and does not. Free-text Ask stays where it is — as a routing preview,
clearly labeled as such.

---

## 4. Finding 3 — There is no refusal path

Every path through `run()` returns an artifact. Stale evidence appends a warning
and proceeds. Missing evidence cannot occur because templates require it.

The most valuable output this system can produce is a refusal: *"I cannot draft
this — the survey is 14 months stale and the two models do not reconcile."* The
rewritten prompts now instruct every specialist to lead with what is missing, and
there is nowhere for that to land.

**What to do.** Add `status="insufficient_evidence"` as a first-class artifact
outcome, not an error. It should:

- render in the UI as its own state — not a red error banner, and not an empty
  draft, but a legitimate result explaining what is missing and what would close
  it;
- be submittable to the review queue, because "the specialist declined and here
  is why" is exactly the kind of thing a principal should see and confirm;
- count in pilot metrics as a distinct outcome alongside approved and rejected.

Trigger it deterministically for now: evidence past the freshness window, a
template with an uncited claim, or a reconciliation conflict flagged in the
fixture.

---

## 5. Finding 4 — The prompts are still not exercised

`orchestrator.run()` is the only code path that loads a specialist prompt, and it
requires `OPENAI_API_KEY`. `PilotWorkspace` never calls it — the docstring says so
plainly: *"Runs fixture-backed workflows without a model or external
integration."*

All twelve prompts were rewritten on 18 August (reasoning procedures, calibrated
uncertainty vocabulary, materiality thresholds, worked examples, escalation
triggers), and `prompts/_shared.md` was reaching no model at all until the
`compose_instructions()` fix landed the same day. None of that has run.

This is the difference between testing the conveyor belt and testing what is on
it. A pilot that measures only the deterministic path will validate the workflow,
the isolation, and the review ergonomics — all genuinely worth validating — and
will tell you nothing about output quality, which is the actual product.

**What to do.** Put exactly one workflow behind a flag through the live model
path. Suggested: contract review, because it has the sharpest quality signal and
the most developed prompt.

- `TESSERA_PILOT_LIVE_DRAFTING=false` by default; the deterministic path stays the
  default and the demo path.
- When enabled, `PilotWorkspace.run()` calls the orchestrator, and the returned
  draft is parsed into the same `PilotArtifact` shape so the rest of the loop —
  review queue, decision, audit — is unchanged.
- Everything downstream stays gated exactly as it is now. This adds a drafting
  source, not a new capability or a new external path.
- Keep both artifacts comparable: run the same task through both paths and diff
  them. That comparison is the first genuinely useful quality measurement the
  project will have.

---

## 6. Finding 5 — Review is binary; reviewers will want to edit

`accept` and `reject` are the only transitions. In real use, a principal reading
a draft that is 95 % right will want to fix one line and approve, not reject it
back for a round trip.

This is a design decision, not a bug, and it is worth making deliberately now
rather than discovering it in the third pilot session. The question is whether an
edited draft requires re-review, and by whom. Recommendation: allow an edit that
is recorded as a distinct `amended_and_accepted` transition, storing both the
original and the edit, with the editor named. That preserves the audit trail
(you can always see what the system produced versus what the human shipped) and
it captures the single most valuable training signal in the whole system — what a
principal actually changes.

---

## 7. Finding 6 — Reset does not clear the audit and metrics stores

`PilotArtifactStore.reset_synthetic()` clears artifacts. The runtime audit store
and any accumulated metrics are separate. Across several reset cycles during a
pilot, audit and metric data will accumulate from abandoned runs and quietly
distort the numbers.

**What to do.** Scope reset to clear artifacts, audit events, and metrics for the
synthetic tenant together, and report the counts cleared for each. Keep the exact
confirmation control that is already there.

---

## 8. Phase 7B — specification

7A validated the loop. 7B should make the pilot measurable and the workspace
usable for real project work. Ordered by dependency.

### 7B.1 — Make the metrics real *(blocking for any measured pilot)*

Close Finding 1 and Finding 6. Enumerable claims with per-claim citations,
computed coverage, `unsupported_claims` either judged or removed,
`external_actions` sourced from the audit store, and reset that clears all three
stores together.

**Exit:** every metric can fail, and a deliberately-degraded fixture makes at
least one of them fail in a test.

### 7B.2 — Real task selection

Close Finding 2. Templates keyed on `(project_id, workflow)`; UI presents the
workflows available for the selected project; explicit handling when a project
has no template for the chosen workflow.

**Exit:** four workflows on one project produce four different artifacts.

### 7B.3 — The refusal path

Close Finding 3. `insufficient_evidence` as a first-class outcome, its own UI
state, reviewable, and counted separately in metrics.

**Exit:** a fixture with stale evidence produces a reviewable refusal rather than
a warned-but-complete draft.

### 7B.4 — Live drafting behind a flag

Close Finding 4. One workflow, flag-gated, same artifact shape, everything
downstream unchanged. Include a side-by-side comparison view of deterministic
versus live output for the same task.

**Exit:** contract review runs end-to-end through a real model, produces a
citable artifact in the existing shape, and passes the same isolation and
injection tests as the deterministic path.

### 7B.5 — Reviewer amendment

Close Finding 5. `amended_and_accepted`, original and edit both retained, editor
recorded.

**Exit:** the audit trail distinguishes what the system drafted from what the
human approved.

### 7B.6 — Project workspace depth

The registers and views deferred from the original 7A list, now that the loop
works: risk, issue, decision, and dependency registers; schedule and budget
variance views; draft and artifact history per project. These read from the
existing Phase 4A/4B structures, which already hold the data.

**Exit:** a principal can open a project and see its current state without
running a workflow.

### 7B.7 — Pilot instrumentation

The metric that matters most and is not on the original list: **categorize what
reviewers change.** Every rejection reason and every amendment is a labeled
example of where the system's judgment diverges from a principal's.

- Tag each decision with a reason category (evidence insufficient, wrong scope,
  figures incorrect, tone or framing, missing risk, other) alongside the free-text
  reason that is already captured.
- Export the labeled set.

**Exit:** after a pilot, the firm can answer "what does Tessera OS get wrong, and
how often" from recorded data rather than impression. This is also the seed of the
first real golden set — the assurance plane currently grades against fixtures
written to pass it, which measures nothing.

---

## 9. What stays out of scope

Unchanged from 7A, and worth restating because 7B adds a model path:

Offline and synthetic. Localhost only. Draft-only. Human-reviewed. No email, no
submissions, no payments, no consultant direction, no production credentials, no
external writes. The live-drafting flag in 7B.4 adds an inference call and
nothing else — no new tool access, no retrieval beyond the existing fixtures, and
no change to any gate.

---

## 10. Sequencing

7B.1 through 7B.3 are prerequisites for a pilot that produces interpretable
results, and they are small. 7B.4 is the one that tells you whether the product
is good. 7B.5 through 7B.7 can follow the first pilot sessions and will be better
designed for having watched real use.

Run the measured pilot after 7B.4, not before. A pilot on the deterministic path
alone will return a clean result that does not generalize, and a clean result is
the most expensive thing to be wrong about.

---

## Appendix — two items from the 18 August review still open

1. **`service.py:146`** hashes only the specialist prompt file for
   `prompt_version` in the audit trace. It should use
   `orchestrator.instructions_digest(agent)` so that a change to
   `prompts/_shared.md` is visible in the audit trail. One line.

2. **`tests/test_phase3a_proposals.py::test_review_queue_is_internal_and_external_delivery_stays_disabled`**
   fails on `main` and on this branch, independent of any change made on
   18 August (verified by reverting). The Phase 3A test has the same synthetic
   user submit and approve a proposal; `review.py` now enforces separation of
   duties for any item carrying a `required_reviewer_group`. The enforcement
   looks correct and the test looks stale — it should use a second identity for
   the approval rather than the enforcement being relaxed.
