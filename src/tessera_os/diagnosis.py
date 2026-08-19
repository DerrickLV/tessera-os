"""Diagnose an existing operating agreement against the position set.

Half of what a founder actually asks is not "how should we set this up?" but
"is what we have right?" — and that half is where an engagement usually starts,
because the founder already has paper and a problem. This module reads an
existing agreement and reports, position by position: what the document has,
what it lacks, and the failure mode each gap exposes.

What this is, precisely: a **screen**, not a review. It is deterministic
keyword detection over the document's own text, mapped onto the clause
library's category set. It can say "this agreement contains no deadlock
mechanism" with confidence, because the absence of every phrase that could
express one is checkable. It cannot say the deadlock mechanism that *is* there
is well drafted — that is reading, and reading is counsel's job and the
Structure Manager's job, in that order.

Three honesty rules are load-bearing:

- A **gap** is reported with the library's own ``absence_risk`` — the failure
  mode in plain words — because "missing: buysell" is not information a founder
  can act on, and "a triggering event creates a right to buy with no mechanism
  to exercise it" is.
- A **presence** is reported as *detected*, never as *adequate*. The strongest
  claim this module ever makes about existing language is that it exists.
- **Contradictions** are limited to the ones detectable from text alone — a
  document that claims manager management and also grants members ordinary
  acting authority, or names arbitration and courtroom jury waivers for the
  same disputes. Everything subtler is left to a human.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .clauses import ClauseLibrary, DealProfile

# --- what each category looks like in the wild --------------------------------
#
# Generic drafting phrases only. Signatures are matched casefolded against the
# inbound text; a category is DETECTED if any phrase appears. Phrases are chosen
# to be common across drafting styles, not to match any particular firm's paper.

CATEGORY_SIGNATURES: dict[str, tuple[str, ...]] = {
    "purpose": ("purpose of the company", "purposes of the company",
                "the company is formed", "the business of the company"),
    "capital": ("capital contribution", "capital account", "initial capital"),
    "capital_default": ("capital call", "defaulting member", "failure to fund",
                        "additional capital contribution"),
    "distributions": ("distribut", "available cash", "distributable cash"),
    "governance": ("manager-managed", "member-managed", "management of the company",
                   "board of managers", "managing member"),
    "authority": ("major decision", "reserved matter", "unanimous consent",
                  "consent of the members", "approval of the members"),
    "titles": ("title", "officer"),
    "transfer": ("transfer restriction", "right of first refusal",
                 "shall not transfer", "may not transfer", "no member shall transfer",
                 "permitted transferee"),
    "estate_transfer": ("revocable trust", "estate planning", "estate-planning"),
    "triggering_events": ("triggering event", "death of a member", "disability",
                          "bankruptcy of a member", "divorce"),
    "valuation": ("fair market value", "appraiser", "appraisal", "valuation"),
    "buysell": ("buy-sell", "buy sell", "shotgun", "offer notice",
                "elect to purchase or sell", "put option", "call option"),
    "buyout_payment": ("promissory note", "payment of the purchase price",
                       "installments", "applicable federal rate"),
    "deadlock": ("deadlock", "impasse", "mediation", "tie vote", "tiebreak"),
    "duties": ("fiduciary", "duty of loyalty", "duty of care", "exculpation",
               "indemnif"),
    "information": ("books and records", "inspect", "financial statements",
                    "annual report", "reporting"),
    "tax_distributions": ("tax distribution", "schedule k-1", "partnership representative",
                          "tax matters"),
    "work_product": ("work product", "intellectual property", "assigns to the company",
                     "owned by the company"),
    "restrictive_covenants": ("non-compet", "noncompet", "non-solicit", "nonsolicit",
                              "confidential information", "restrictive covenant"),
    "exit": ("dissolution", "winding up", "liquidat"),
    "dispute": ("governing law", "arbitration", "jurisdiction", "venue",
                "dispute resolution"),
}

# Text-detectable contradictions: (name, first pattern set, second pattern set,
# what it means). Both sets present = flag. Deliberately few and deliberately
# blunt — a false accusation of inconsistency costs more credibility than a
# missed one.
_CONTRADICTIONS: list[tuple[str, tuple[str, ...], tuple[str, ...], str]] = [
    ("Management model against acting authority",
     ("manager-managed",),
     ("either member may act alone", "any member may bind the company",
      "each member has authority to act"),
     ("The document claims manager management and also grants members general "
      "acting authority. A counterparty cannot tell who may sign, which is the "
      "exact question a management clause exists to answer.")),
    ("Arbitration against a jury waiver",
     ("binding arbitration",),
     ("trial by jury", "jury trial"),
     ("The document sends disputes to arbitration and also waives a jury for "
      "court proceedings over the same subject matter. One of these is doing no "
      "work, and a court may read the pair as ambiguity about the forum.")),
    ("Unanimity against a stated voting percentage",
     ("unanimous consent of the members", "unanimous written consent"),
     ("a majority in interest", "at least fifty percent", "at least 50%"),
     ("The document requires unanimity in one place and a lower threshold in "
      "another for what may be the same decisions. Which controls will be "
      "litigated at the worst possible moment.")),
]

# Dollar amounts and day-periods, extracted as observations. Never judged here.
_MONEY = re.compile(r"\$[\d,]+(?:\.\d{2})?")
_DAYS = re.compile(r"\b(\w+(?:-\w+)?|\d+)\s*\((\d+)\)\s*(business\s+)?days?\b",
                   re.IGNORECASE)


class DetectedPosition(BaseModel):
    """A category the document appears to address. Detected, never adequate."""

    category: str
    label: str
    matched_phrase: str
    excerpt: str = Field(description="A short window around the first match, for "
                                     "the reviewer to jump to. Never a judgment.")


class Gap(BaseModel):
    """A category the document does not appear to address, with its failure mode."""

    category: str
    label: str
    required: bool
    absence_risk: str


class Contradiction(BaseModel):
    name: str
    first_evidence: str
    second_evidence: str
    why_it_matters: str


class Observation(BaseModel):
    """A number the document states, surfaced for a human to evaluate."""

    kind: str
    value: str
    context: str


class StructureDiagnosis(BaseModel):
    """The screen's whole output, with its limits stated on the object itself."""

    agreement_type: str
    detected: list[DetectedPosition]
    gaps: list[Gap]
    contradictions: list[Contradiction]
    observations: list[Observation]

    @property
    def required_gaps(self) -> list[Gap]:
        return [gap for gap in self.gaps if gap.required]

    def to_markdown(self) -> str:
        out = ["# Structure Diagnosis — existing agreement", ""]
        out.append("> A deterministic screen of the document's text against the "
                   "position set: what it addresses, what it lacks, and what the "
                   "gaps expose. Detection is not endorsement — language that is "
                   "present may still be inadequate, and only qualified counsel "
                   "can say. Not legal advice.")
        out.append("")

        if self.required_gaps:
            out.append("## Missing, and required")
            out.append("")
            out.append("The document does not appear to address these at all. Each "
                       "entry states what goes wrong without it.")
            out.append("")
            for gap in self.required_gaps:
                out.append(f"**{gap.label}.** {gap.absence_risk}")
                out.append("")
        optional_gaps = [gap for gap in self.gaps if not gap.required]
        if optional_gaps:
            out.append("## Missing, and conditional")
            out.append("")
            out.append("Not every agreement needs these; whether this one does is a "
                       "judgment call the screen cannot make.")
            out.append("")
            for gap in optional_gaps:
                out.append(f"**{gap.label}.** {gap.absence_risk}")
                out.append("")

        if self.contradictions:
            out.append("## Internal contradictions detected")
            out.append("")
            for item in self.contradictions:
                out.append(f"**{item.name}.** {item.why_it_matters}")
                out.append(f"> First: “…{item.first_evidence}…” · "
                           f"Second: “…{item.second_evidence}…”")
                out.append("")

        if self.detected:
            out.append("## Present — detected, not evaluated")
            out.append("")
            out.append("| Position | Found near |")
            out.append("| --- | --- |")
            for item in self.detected:
                excerpt = item.excerpt.replace("|", "\\|")
                out.append(f"| {item.label} | …{excerpt}… |")
            out.append("")

        if self.observations:
            out.append("## Numbers the document states")
            out.append("")
            out.append("Surfaced for review, not judged. Whether each is right for "
                       "this deal is exactly the conversation to have.")
            out.append("")
            for obs in self.observations[:20]:
                out.append(f"- **{obs.value}** — …{obs.context}…")
            out.append("")

        out.append("## What this screen cannot see")
        out.append("")
        out.append("Whether present language is well drafted, whether defined terms "
                   "are used consistently, whether the numbers are right for the "
                   "parties, and anything that depends on the deal's facts rather "
                   "than the document's text. Route the document and this screen "
                   "together to the Structure Manager and to counsel.")
        return "\n".join(out).rstrip() + "\n"


def _label(category: str) -> str:
    return category.replace("_", " ").title()


def _window(text: str, index: int, width: int = 60) -> str:
    start, end = max(0, index - width // 2), min(len(text), index + width)
    return " ".join(text[start:end].split())


def diagnose_agreement(text: str, *, library: ClauseLibrary,
                       profile: DealProfile) -> StructureDiagnosis:
    """Screen an inbound agreement's text against the library's position set.

    The profile supplies the deal's shape, which decides which categories are
    even expected — a two-member equal LLC is expected to have a deadlock
    answer; a majority/minority one is not.
    """
    lowered = text.casefold()

    expected = {clause.category: clause for clause in library.applicable(profile)}

    detected: list[DetectedPosition] = []
    gaps: list[Gap] = []
    for category, clause in sorted(expected.items()):
        signatures = CATEGORY_SIGNATURES.get(category, ())
        hit = None
        for phrase in signatures:
            index = lowered.find(phrase)
            if index >= 0:
                hit = (phrase, index)
                break
        if hit is not None:
            phrase, index = hit
            detected.append(DetectedPosition(
                category=category, label=_label(category), matched_phrase=phrase,
                excerpt=_window(text, index)))
        else:
            gaps.append(Gap(category=category, label=_label(category),
                            required=clause.required,
                            absence_risk=clause.absence_risk))

    contradictions: list[Contradiction] = []
    for name, first_set, second_set, why in _CONTRADICTIONS:
        first = next((p for p in first_set if p in lowered), None)
        second = next((p for p in second_set if p in lowered), None)
        if first and second:
            contradictions.append(Contradiction(
                name=name,
                first_evidence=_window(text, lowered.find(first)),
                second_evidence=_window(text, lowered.find(second)),
                why_it_matters=why))

    observations: list[Observation] = []
    seen_values: set[str] = set()
    for match in _MONEY.finditer(text):
        value = match.group(0)
        if value not in seen_values:
            seen_values.add(value)
            observations.append(Observation(
                kind="money", value=value, context=_window(text, match.start())))
    for match in _DAYS.finditer(text):
        value = f"{match.group(2)} days"
        key = f"{value}:{match.start() // 500}"
        if key not in seen_values:
            seen_values.add(key)
            observations.append(Observation(
                kind="days", value=value, context=_window(text, match.start())))

    return StructureDiagnosis(
        agreement_type=profile.agreement_type,
        detected=detected, gaps=gaps,
        contradictions=contradictions, observations=observations)
