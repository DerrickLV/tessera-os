"""Deal-specific clause selection and assembly.

Tessera does not have one standard agreement. A finder's fee arrangement on a
regulated cannabis deal, a consulting engagement on a multifamily entitlement,
and an NDA opening a capital introduction carry genuinely different risk, and the
right language differs with them.

This module models that: each clause carries several approved *variants* at
different risk postures, plus the conditions under which each applies. A
``DealProfile`` describes the specific opportunity, and selection resolves the
profile to one variant per clause -- producing operative language for that deal
rather than a generic template.

Nothing here decides anything. Assembly produces a draft with every selection
recorded and every counsel-review note attached, for a qualified lawyer to review
before execution.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
# Cross-reference to another clause by id, resolved to its assembled section
# number. A hardcoded "Section 7" is wrong the moment the clause set changes:
# in the first finder's-fee draft the indemnity was expressly subject to the
# independent-contractor clause rather than the liability cap.
_REFERENCE = re.compile(r"\{ref:([a-z0-9-]+)\}")

Posture = Literal["protective", "standard", "accommodating"]
AgreementType = Literal[
    # Engagement paper — Tessera contracting with a client
    "nda", "consulting", "advisory", "finders_fee", "deal_memo",
    # Entity and deal paper — what Tessera structures for or with a client
    "operating_agreement", "jv", "investor_subscription",
]
Industry = Literal["regulated", "real_estate", "trades", "media", "general"]

# Ordered most to least protective of Tessera. Selection walks down this list
# when the preferred posture has no variant for the deal.
POSTURE_ORDER: tuple[Posture, ...] = ("protective", "standard", "accommodating")

# The clause categories a document of each type must contain before it is a
# document at all. A partially-covered agreement is more dangerous than none:
# it reads as complete, and the reader cannot see what was never there. When the
# library cannot meet this bar, assembly refuses and names the gap.
ESSENTIAL_CATEGORIES: dict[AgreementType, frozenset[str]] = {
    "nda": frozenset({"confidentiality", "dispute"}),
    "consulting": frozenset({"scope", "term", "payment", "liability", "indemnity", "dispute"}),
    "advisory": frozenset({"scope", "term", "payment", "liability", "indemnity", "dispute"}),
    "finders_fee": frozenset({"success_fee", "term", "liability", "indemnity", "dispute"}),
    "deal_memo": frozenset({"binding_effect", "confidentiality", "dispute"}),
    "operating_agreement": frozenset({
        "purpose", "capital", "distributions", "governance", "transfer", "duties",
        "information", "exit", "dispute"}),
    "jv": frozenset({
        "purpose", "capital", "distributions", "governance", "transfer", "duties",
        "information", "exit", "dispute"}),
    "investor_subscription": frozenset({
        "subscription", "investor_representations", "securities_legend", "information",
        "dispute"}),
}


class ClauseCoverageError(ValueError):
    """Raised when the library cannot cover the essentials of a document type."""


class VariableError(ValueError):
    """Raised when a deal variable is missing or fails its declared format."""


PartyRole = Literal[
    "service_provider",   # Tessera performs and is paid
    "service_recipient",  # Tessera engages someone else
    "investor",           # Tessera puts capital in
    "sponsor",            # Tessera manages and raises
    "co_venturer",        # side-by-side with a partner
]
OwnershipShape = Literal["single", "equal", "majority_minority"]
CounterpartyType = Literal["institutional", "operator", "individual"]
EntityType = Literal["llc", "lp", "corporation", "none"]
TaxTreatment = Literal["partnership", "s_corp", "c_corp", "disregarded", "none"]

VariableKind = Literal["text", "money", "percent", "days", "months", "years", "date", "choice"]

_VARIABLE_FORMATS: dict[str, re.Pattern[str]] = {
    "money": re.compile(r"^\$?[\d,]+(\.\d{2})?$"),
    "percent": re.compile(r"^\d{1,3}(\.\d+)?%$"),
    "days": re.compile(r"^\d+$"),
    "months": re.compile(r"^\d+$"),
    "years": re.compile(r"^\d+$"),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
}


class DefinedTerm(BaseModel):
    """A term a clause introduces, with the definition that must accompany it.

    Definitions travel with the clause that needs them, so a document only
    defines what it actually uses, and a term cannot appear without its meaning.
    """

    term: str = Field(min_length=1)
    definition: str = Field(min_length=1)


class VariableSpec(BaseModel):
    """A commercial term the drafter must supply, declared rather than free-text.

    Turning ``{fee_percentage}`` into a typed, prompted, validated input is what
    separates a template with blanks from a deal-specific document.
    """

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: VariableKind = "text"
    help: str = ""
    choices: list[str] = Field(default_factory=list)
    defaults_by_posture: dict[Posture, str] = Field(default_factory=dict)
    required: bool = True

    def default_for(self, posture: Posture) -> str | None:
        return self.defaults_by_posture.get(posture)

    def validate_value(self, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise VariableError(f"{self.name}: {self.label} is required")
        if self.kind == "choice" and self.choices and text not in self.choices:
            raise VariableError(
                f"{self.name}: must be one of {', '.join(self.choices)}; got {text!r}")
        pattern = _VARIABLE_FORMATS.get(self.kind)
        if pattern and not pattern.match(text):
            raise VariableError(
                f"{self.name}: {text!r} is not a valid {self.kind} value")
        return text


class Party(BaseModel):
    """A signatory. Without these an assembled document has no preamble,
    no Schedule A, and nowhere to sign -- it reads as a clause set, not an
    agreement."""

    name: str = Field(min_length=1)
    role: Literal["member", "manager", "consultant", "client", "investor", "other"]
    entity_form: str | None = None
    notice_address: str | None = None
    signatory_name: str | None = None
    signatory_title: str | None = None
    capital_contribution: float | None = Field(default=None, ge=0)
    units: float | None = Field(default=None, ge=0)

    def described(self) -> str:
        return f"**{self.name}**" + (f", {self.entity_form}" if self.entity_form else "")


class ClauseCondition(BaseModel):
    """Structured inclusion rules. Declarative on purpose -- no expressions to evaluate."""

    party_roles: list[PartyRole] = Field(default_factory=list)
    ownership_shapes: list[OwnershipShape] = Field(default_factory=list)
    max_members: int | None = None
    min_members: int | None = None
    min_deal_value: float | None = None
    regulated_only: bool = False

    def matches(self, profile: DealProfile) -> bool:
        if self.party_roles and profile.party_role not in self.party_roles:
            return False
        if self.ownership_shapes and profile.ownership_shape not in self.ownership_shapes:
            return False
        if self.max_members is not None and profile.member_count > self.max_members:
            return False
        if self.min_members is not None and profile.member_count < self.min_members:
            return False
        if self.min_deal_value is not None and profile.deal_value < self.min_deal_value:
            return False
        return not (self.regulated_only and profile.industry != "regulated")


class ClauseVariant(BaseModel):
    """One approved way to write a clause, at a stated risk posture."""

    id: str = Field(min_length=1)
    posture: Posture
    text: str = Field(min_length=1)
    when: str = Field(min_length=1)
    trade_off: str = ""
    counsel_review: str = Field(min_length=1)
    # Enforceability of restrictive covenants, duty waivers, and fee-shifting
    # varies materially by state. A variant can carry an extra warning for a
    # jurisdiction, or be ruled out in one entirely.
    jurisdiction_notes: dict[str, str] = Field(default_factory=dict)
    unavailable_in: list[str] = Field(default_factory=list)

    def note_for(self, jurisdiction: str) -> str | None:
        for key, note in self.jurisdiction_notes.items():
            if key.lower() in jurisdiction.lower():
                return note
        return None

    def available_in(self, jurisdiction: str) -> bool:
        return not any(key.lower() in jurisdiction.lower() for key in self.unavailable_in)


class Clause(BaseModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    order: int = Field(ge=0)
    order_overrides: dict[AgreementType, int] = Field(default_factory=dict)
    applies_to: list[AgreementType] = Field(min_length=1)
    industries: list[Industry] = Field(default_factory=list)
    required: bool = True
    absence_risk: str = Field(min_length=1)
    condition: ClauseCondition | None = None
    defines: list[DefinedTerm] = Field(default_factory=list)
    requires_terms: list[str] = Field(default_factory=list)
    variants: list[ClauseVariant] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_postures(self) -> Clause:
        postures = [variant.posture for variant in self.variants]
        if len(postures) != len(set(postures)):
            raise ValueError(f"Clause {self.id!r} has duplicate postures")
        return self

    def referenced_clause_ids(self) -> set[str]:
        """Clause ids this clause's language cross-references."""
        return {match for variant in self.variants
                for match in _REFERENCE.findall(variant.text)}

    def order_for(self, agreement_type: AgreementType) -> int:
        """Position in this document type.

        A clause shared across document families does not sit in the same place
        in each: governing law belongs near the end of an operating agreement
        but mid-document in a short consulting agreement.
        """
        return self.order_overrides.get(agreement_type, self.order)

    def applies(self, profile: DealProfile) -> bool:
        if profile.agreement_type not in self.applies_to:
            return False
        if self.industries and profile.industry not in self.industries:
            return False
        return self.condition is None or self.condition.matches(profile)

    def variant_for(self, posture: Posture,
                    jurisdiction: str = "") -> ClauseVariant | None:
        """Return the variant at ``posture``, else the closest one available.

        Preference runs toward the more protective side first. Dropping a
        required clause because its exact posture is missing would silently
        produce an agreement with no liability cap or no contractor
        clause -- worse than substituting a neighbouring variant and saying so.
        Variants ruled out in the governing jurisdiction are excluded first.
        """
        usable = [v for v in self.variants
                  if not jurisdiction or v.available_in(jurisdiction)]
        by_posture = {variant.posture: variant for variant in usable}
        if posture in by_posture:
            return by_posture[posture]
        index = POSTURE_ORDER.index(posture)
        more_protective = POSTURE_ORDER[:index][::-1]
        less_protective = POSTURE_ORDER[index + 1:]
        for candidate in (*more_protective, *less_protective):
            if candidate in by_posture:
                return by_posture[candidate]
        return None


class DealProfile(BaseModel):
    """The specific opportunity a draft is being assembled for."""

    opportunity: str = Field(min_length=1)
    agreement_type: AgreementType
    industry: Industry
    jurisdiction: str = Field(min_length=1)
    counterparty: str = Field(min_length=1)
    counterparty_represented: bool = True
    fee_at_risk: float = Field(ge=0)
    relationship_stage: Literal["first_engagement", "established", "long_standing"] = (
        "first_engagement")
    tessera_capital_at_risk: bool = False

    # --- Which side Tessera is on. Flips indemnity direction, IP ownership, and
    # who carries the cap; the same clause library produces a different document.
    party_role: PartyRole = "service_provider"

    # --- Entity shape. Drives distributions, allocations, and transfer mechanics.
    entity_type: EntityType = "none"
    tax_treatment: TaxTreatment = "none"

    # --- Ownership structure. Decides whether drag-along, tag-along, or a
    # deadlock mechanism belong in the document at all.
    ownership_shape: OwnershipShape = "majority_minority"
    member_count: int = Field(default=2, ge=1)

    # --- Counterparty and deal scale.
    counterparty_type: CounterpartyType = "operator"
    deal_value: float = Field(default=0, ge=0)
    expected_hold_years: int | None = Field(default=None, ge=0)

    # --- Which regime, not just "regulated". Cannabis licensing, liquor, film
    # finance, and food service carry different conditions and different counsel.
    regulatory_regime: str | None = None

    # --- Signatories, capital, and units. Drive the preamble, Schedule A, and
    # the signature blocks.
    parties: list[Party] = Field(default_factory=list)
    effective_date: str | None = None

    def posture(self) -> Posture:
        """Derive the default risk posture from the deal's own characteristics.

        More protective where the downside is asymmetric -- a regulated industry,
        Tessera's own capital in the deal, a large fee, or an unrepresented
        counterparty who is likelier to dispute terms later. More accommodating
        only where the relationship is long-standing and the exposure is small.
        """
        if self.industry == "regulated" or self.tessera_capital_at_risk:
            return "protective"
        if self.fee_at_risk >= 100_000 or not self.counterparty_represented:
            return "protective"
        if self.deal_value >= 1_000_000:
            return "protective"
        # A minority position has the least leverage after signature, so the
        # document has to carry protection the cap table will not.
        if self.ownership_shape == "majority_minority" and self.party_role in {
                "investor", "co_venturer"}:
            return "protective"
        if self.relationship_stage == "long_standing" and self.fee_at_risk < 25_000:
            return "accommodating"
        return "standard"

    def posture_rationale(self) -> str:
        reasons = []
        if self.industry == "regulated":
            regime = f" ({self.regulatory_regime})" if self.regulatory_regime else ""
            reasons.append(f"a regulated industry{regime}")
        if self.tessera_capital_at_risk:
            reasons.append("Tessera capital at risk")
        if self.fee_at_risk >= 100_000:
            reasons.append(f"fee exposure of ${self.fee_at_risk:,.0f}")
        if self.deal_value >= 1_000_000:
            reasons.append(f"deal value of ${self.deal_value:,.0f}")
        if not self.counterparty_represented:
            reasons.append("an unrepresented counterparty")
        if self.ownership_shape == "majority_minority" and self.party_role in {
                "investor", "co_venturer"}:
            reasons.append("a minority position")
        if not reasons and self.relationship_stage == "long_standing":
            reasons.append("a long-standing relationship with limited exposure")
        return ", ".join(reasons) or "an ordinary engagement profile"


class SelectedClause(BaseModel):
    clause: Clause
    variant: ClauseVariant
    posture_requested: Posture
    substituted: bool = False

    @property
    def less_protective_than_requested(self) -> bool:
        return (POSTURE_ORDER.index(self.variant.posture)
                > POSTURE_ORDER.index(self.posture_requested))


class AssembledDraft(BaseModel):
    profile: DealProfile
    posture: Posture
    selections: list[SelectedClause]
    omitted_required: list[Clause] = Field(default_factory=list)

    def section_numbers(self) -> dict[str, int]:
        """Clause id to its assembled section number, definitions included."""
        offset = 1 if self.definitions() else 0
        return {item.clause.id: index + offset
                for index, item in enumerate(self.selections, start=1)}

    def broken_references(self) -> list[str]:
        """Cross-references pointing at a clause this document does not contain.

        A dangling reference is worse than a missing clause: the text asserts a
        limit or a procedure that is not there.
        """
        present = self.section_numbers()
        broken = []
        for item in self.selections:
            for target in _REFERENCE.findall(item.variant.text):
                if target not in present:
                    broken.append(f"{item.clause.title} references {target}, "
                                  "which is not in this document")
        return broken

    def missing_attachments(self) -> list[str]:
        """Exhibits and schedules the text relies on but the document lacks.

        Clause language routinely points at "Exhibit A" or "Schedule A". An
        agreement that references a schedule it does not carry is incomplete in
        exactly the way that is easy to miss on a read-through.
        """
        body = " ".join(item.variant.text for item in self.selections)
        referenced = sorted(set(re.findall(r"\b(Exhibit [A-Z]|Schedule [A-Z])\b", body)))
        generated = {"Schedule A"} if any(
            party.capital_contribution is not None or party.units is not None
            for party in self.profile.parties) else set()
        return [name for name in referenced if name not in generated]

    def _resolve(self, text: str, section_number: int) -> str:
        numbers = self.section_numbers()
        text = text.replace("{n}", str(section_number))
        return _REFERENCE.sub(
            lambda match: str(numbers.get(match.group(1), "[MISSING CLAUSE]")), text)

    def _preamble(self) -> list[str]:
        parties = self.profile.parties
        if not parties:
            return []
        date = self.profile.effective_date or "{effective_date}"
        label = self.profile.agreement_type.replace("_", " ").title()
        lines = [(f"This {label} (this \"Agreement\") is entered into as of {date} "
                  "(the \"Effective Date\") by and among:"), ""]
        lines.extend(f"- {party.described()} (\"{party.role.title()}\")" for party in parties)
        lines.extend(["", "---", ""])
        return lines

    def _schedule_a(self) -> list[str]:
        contributors = [p for p in self.profile.parties
                        if p.capital_contribution is not None or p.units is not None]
        if not contributors:
            return []
        lines = ["---", "", "## Schedule A — Members, Capital Contributions, and Units", "",
                 "| Member | Capital Contribution | Units |", "|---|---|---|"]
        for party in contributors:
            capital = (f"${party.capital_contribution:,.0f}"
                       if party.capital_contribution is not None else "—")
            units = f"{party.units:,.0f}" if party.units is not None else "—"
            lines.append(f"| {party.name} | {capital} | {units} |")
        total_capital = sum(p.capital_contribution or 0 for p in contributors)
        total_units = sum(p.units or 0 for p in contributors)
        lines.append(f"| **Total** | **${total_capital:,.0f}** | **{total_units:,.0f}** |")
        lines.append("")
        return lines

    def _signature_blocks(self) -> list[str]:
        if not self.profile.parties:
            return []
        lines = ["---", "", "## Signatures", "",
                 "The parties execute this Agreement as of the Effective Date.", ""]
        for party in self.profile.parties:
            lines.extend([
                f"**{party.name}**", "",
                "By: ______________________________", "",
                f"Name: {party.signatory_name or '______________________________'}",
                f"Title: {party.signatory_title or '______________________________'}",
                "Date: ______________________________", "",
            ])
        return lines

    def counsel_notes(self) -> list[str]:
        """Per-variant review points, plus any jurisdiction-specific warning."""
        notes = []
        for item in self.selections:
            notes.append(f"{item.clause.title}: {item.variant.counsel_review}")
            if warning := item.variant.note_for(self.profile.jurisdiction):
                notes.append(f"{item.clause.title} ({self.profile.jurisdiction}): {warning}")
        return notes

    def definitions(self) -> list[DefinedTerm]:
        """Every term introduced by a selected clause, deduplicated and sorted.

        Definitions come from the clauses that use them, so the document defines
        exactly what it contains -- no orphan definitions, and no term appearing
        without one.
        """
        seen: dict[str, DefinedTerm] = {}
        for item in self.selections:
            for term in item.clause.defines:
                seen.setdefault(term.term, term)
        return [seen[key] for key in sorted(seen)]

    def undefined_terms(self) -> list[str]:
        """Terms a selected clause relies on that nothing in the document defines.

        Derrick's drafting standard is that defined terms are internally
        consistent across every section. A term used twenty times and never
        defined is the most common way that fails.
        """
        defined = {term.term for term in self.definitions()}
        needed: set[str] = set()
        for item in self.selections:
            needed.update(item.clause.requires_terms)
        return sorted(needed - defined)

    def open_variables(self) -> list[str]:
        """Placeholders still unfilled anywhere in the assembled text.

        A draft must never leave the building with a ``{fee_percentage}`` in it.
        Every one of these is a commercial term someone has to decide.
        """
        found: set[str] = set()
        for index, item in enumerate(self.selections, start=1):
            for token in _PLACEHOLDER.findall(item.variant.text):
                if token != "n":
                    found.add(token)
            del index
        return sorted(found)

    def to_markdown(self, *, include_open_terms: bool = True) -> str:
        """Render the draft.

        ``include_open_terms`` is turned off once every term has been supplied;
        otherwise substitution rewrites the open-terms list into a meaningless
        roll-call of the values that were just filled in.
        """
        profile = self.profile
        lines = [
            f"# {profile.agreement_type.replace('_', ' ').title()} — {profile.opportunity}",
            "",
            ("**DRAFT — FOR QUALIFIED COUNSEL REVIEW BEFORE EXECUTION.** "
             "Assembled from approved clause variants; not legal advice."),
            "",
            f"- **Counterparty:** {profile.counterparty}",
            f"- **Governing law:** {profile.jurisdiction}",
            (f"- **Risk posture:** {self.posture} — selected for "
             f"{profile.posture_rationale()}"),
            "",
            "---",
            "",
        ]
        lines.extend(self._preamble())
        definitions = self.definitions()
        offset = 0
        if definitions:
            offset = 1
            lines.extend(["## 1. Definitions", ""])
            lines.extend(f"**“{term.term}”** {term.definition}" + "\n"
                         for term in definitions)
            lines.append("")
        for position, item in enumerate(self.selections, start=1):
            index = position + offset
            lines.append(f"## {index}. {item.clause.title}")
            lines.append("")
            # Clause text is stored with {n} standing in for its section number
            # and {ref:clause-id} for a cross-reference, so numbering and every
            # internal reference stay correct whichever clauses this deal
            # profile actually selects.
            lines.append(self._resolve(item.variant.text, index).strip())
            lines.append("")
            if item.substituted:
                direction = ("LESS protective than this deal's posture — confirm before sending"
                             if item.less_protective_than_requested
                             else "more protective than this deal's posture")
                lines.append(
                    f"> *No {item.posture_requested} variant exists for this clause; the "
                    f"{item.variant.posture} variant was used, which is {direction}.*")
                lines.append("")
        if self.omitted_required:
            lines.extend(["---", "", "## Required clauses with no applicable variant", ""])
            lines.extend(f"- **{clause.title}** — {clause.absence_risk}"
                         for clause in self.omitted_required)
            lines.append("")
        lines.extend(self._schedule_a())
        lines.extend(self._signature_blocks())
        attachments = self.missing_attachments()
        if attachments:
            lines.extend(["---", "", "## Attachments still to be prepared", "",
                          "The text refers to each of these; none is attached:", ""])
            lines.extend(f"- {name}" for name in attachments)
            lines.append("")
        broken = self.broken_references()
        if broken:
            lines.extend(["---", "", "## Broken cross-references", "",
                          "Resolve before this document is used:", ""])
            lines.extend(f"- {item}" for item in broken)
            lines.append("")
        undefined = self.undefined_terms()
        if undefined:
            lines.extend(["---", "", "## Terms used but not defined", "",
                          "Each of these must be defined before execution:", ""])
            lines.extend(f"- {term}" for term in undefined)
            lines.append("")
        open_vars = self.open_variables() if include_open_terms else []
        if open_vars:
            lines.extend(["---", "", "## Terms still to be filled in", "",
                          "This draft is not ready to send until each of these is decided:", ""])
            lines.extend(f"- `{{{name}}}`" for name in open_vars)
            lines.append("")
        lines.extend(["---", "", "## Counsel review checklist", ""])
        lines.extend(f"- {note}" for note in self.counsel_notes())
        return "\n".join(lines)


class FilledDraft(BaseModel):
    """An assembled draft with every commercial term supplied and validated."""

    markdown: str
    values: dict[str, str]
    counsel_notes: list[str] = Field(default_factory=list)


class ClauseLibrary:
    def __init__(self, clauses: list[Clause],
                 variables: dict[str, VariableSpec] | None = None) -> None:
        ids = [clause.id for clause in clauses]
        if len(ids) != len(set(ids)):
            raise ValueError("Clause IDs must be unique")
        self.clauses = sorted(clauses, key=lambda clause: clause.order)
        self.variables = variables or {}

    def variable_prompts(self, assembled: AssembledDraft) -> list[VariableSpec]:
        """Declared specs for exactly the terms this draft still needs.

        Anything a clause references without a declared spec is surfaced as a
        plain text field rather than silently dropped, so the gap is visible.
        """
        prompts = []
        for name in assembled.open_variables():
            prompts.append(self.variables.get(name) or VariableSpec(
                name=name, label=name.replace("_", " ").capitalize(),
                help="No specification declared for this variable yet."))
        return prompts

    def fill(self, assembled: AssembledDraft, values: dict[str, str], *,
             use_defaults: bool = True) -> FilledDraft:
        """Substitute and validate every commercial term in the draft.

        Missing required values raise rather than producing a document with a
        blank in it. Posture-aware defaults fill what the drafter did not supply,
        which is how a protective deal gets a protective number without anyone
        remembering to type one.
        """
        resolved: dict[str, str] = {}
        missing: list[str] = []
        for spec in self.variable_prompts(assembled):
            raw = values.get(spec.name)
            if raw is None and use_defaults:
                raw = spec.default_for(assembled.posture)
            if raw is None or str(raw).strip() == "":
                if spec.required:
                    missing.append(f"{spec.name} ({spec.label})")
                continue
            resolved[spec.name] = spec.validate_value(raw)
        if missing:
            raise VariableError(
                "Cannot produce a complete draft; these terms are undecided: "
                + "; ".join(missing))
        markdown = assembled.to_markdown(include_open_terms=False)
        for name, value in resolved.items():
            markdown = markdown.replace("{" + name + "}", value)
        # A record of what was chosen, so a reviewer can check the commercial
        # terms without rereading the whole document.
        supplied = ["---", "", "## Terms supplied", "",
                    "| Term | Value |", "|---|---|"]
        for name in sorted(resolved):
            spec = self.variables.get(name)
            supplied.append(f"| {spec.label if spec else name} | {resolved[name]} |")
        markdown = markdown.rstrip() + "\n\n" + "\n".join(supplied) + "\n"
        return FilledDraft(markdown=markdown, values=resolved,
                           counsel_notes=assembled.counsel_notes())

    @classmethod
    def load(cls, path: Path | str) -> ClauseLibrary:
        """Load one clause file, or every ``*.json`` in a directory.

        The library is expected to grow by document family — engagement paper,
        entity and governance paper, deal paper — so it is held as separate
        files that merge into one library rather than a single file that every
        change has to touch.
        """
        target = Path(path)
        if not target.is_dir():
            return cls([Clause(**item) for item in json.loads(target.read_text())["clauses"]])
        clauses, variables = [], {}
        for item in sorted(target.glob("*.json")):
            data = json.loads(item.read_text())
            clauses.extend(Clause(**entry) for entry in data.get("clauses", []))
            for entry in data.get("variables", []):
                spec = VariableSpec(**entry)
                variables[spec.name] = spec
        return cls(clauses, variables)

    def applicable(self, profile: DealProfile) -> list[Clause]:
        return sorted((clause for clause in self.clauses if clause.applies(profile)),
                      key=lambda clause: clause.order_for(profile.agreement_type))

    def missing_essentials(self, profile: DealProfile) -> list[str]:
        """Essential clause categories this library cannot supply for the deal."""
        required = ESSENTIAL_CATEGORIES.get(profile.agreement_type, frozenset())
        present = {clause.category for clause in self.applicable(profile)}
        return sorted(required - present)

    def assemble(self, profile: DealProfile, *, posture: Posture | None = None,
                 require_coverage: bool = True) -> AssembledDraft:
        """Resolve a deal profile to one variant per applicable clause.

        Refuses by default when the library cannot cover the document type's
        essentials. Pass ``require_coverage=False`` only to inspect a partial
        assembly; never to produce something for a reader.
        """
        if require_coverage and (missing := self.missing_essentials(profile)):
            raise ClauseCoverageError(
                f"The clause library cannot draft a {profile.agreement_type}: no approved "
                f"clauses for {', '.join(missing)}. Add them, with counsel, before drafting "
                "this document type.")
        requested = posture or profile.posture()
        selections, omitted = [], []
        for clause in self.applicable(profile):
            variant = clause.variant_for(requested, profile.jurisdiction)
            if variant is None:
                if clause.required:
                    omitted.append(clause)
                continue
            selections.append(SelectedClause(clause=clause, variant=variant,
                                             posture_requested=requested,
                                             substituted=variant.posture != requested))
        return AssembledDraft(profile=profile, posture=requested,
                              selections=selections, omitted_required=omitted)

    def review_positions(self, profile: DealProfile) -> dict[str, list[ClauseVariant]]:
        """Approved variants by category, for comparing an inbound draft.

        This is what turns the library into a review baseline: rather than one
        standard, the reviewer sees the full approved band for this deal type and
        can say where an inbound term falls within or outside it.
        """
        return {clause.category: clause.variants for clause in self.applicable(profile)}
