"""Entity architecture: what structure a new company should have, and why.

This is the front of the structuring work, before any document exists. A
founder describes what they are building -- who is in it, whose capital, what
assets, what the exit looks like -- and this produces the structure: how many
entities and how they stack, who may act alone and above what number, what
requires everyone, what happens when the two of them disagree, and how someone
gets out.

Two rules govern everything here.

**Nothing is invented.** Each recommendation carries a ``basis`` naming where
the position comes from. ``SYNTHETIC_REFERENCE`` means it comes from the
versioned, fictional governance playbook used for offline evaluation.
``SCAFFOLD`` means it is a reasonable starting point that no one at Tessera has
adopted yet. Neither label represents legal advice or a production standard.

**The reasoning is the deliverable.** A structure chart is not advice. Every
recommendation states what it prevents, and the report ends with the failure
modes the structure is built against and the conflicts it detected between the
choices themselves -- an S election that would void the waterfall, a deadlock
ladder handed to a party who already has control.

Nothing here is legal or tax advice, and the module does not pretend the
questions are closed: open questions are returned as first-class output, naming
what cannot be drafted until they are answered.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from .adoption import AdoptedPosition, AdoptionLedger
from .clauses import DealProfile, EntityType, Industry, Party, TaxTreatment
from .numbers import (
    APPROVAL_THRESHOLD_LABEL,
    ORDINARY_COURSE_THRESHOLD_LABEL,
    DerivedNumber,
    DerivedNumberConfirmation,
)
from .sectors import SectorPattern, pattern_for, regime_for

# --- provenance -------------------------------------------------------------

Basis = Literal["tessera_adopted", "synthetic_reference", "scaffold"]

BASIS_LABEL: dict[Basis, str] = {
    "tessera_adopted": "Tessera position — adopted by the partners; see the adoption ledger",
    "synthetic_reference": "Synthetic policy reference — fictional and not adopted by Tessera",
    "scaffold": "Starting point — not yet adopted by Tessera or reviewed by counsel",
}

# --- inputs -----------------------------------------------------------------

Activity = Literal[
    "operating",             # a business that sells something
    "real_estate_hold",      # owns and holds income property
    "development",           # builds, entitles, and sells or stabilises
    "fund",                  # pools outside capital to invest
    "ip_licensing",          # owns and licenses intangibles
    "professional_services",  # people-based services
    # Sectors Tessera actually works in, each carrying its own pattern. See
    # ``sectors.py`` -- flattening these into "operating" is how a structure ends
    # up technically correct and practically useless.
    "film_production",       # one picture at a time; the asset is a copyright
    "skilled_trades",        # a licence held by a person, and a fleet of trucks
    "hospitality",           # one location at a time, and a licence that cannot move
]
CapitalSource = Literal["founders_only", "friends_family", "private_placement", "institutional"]
ExitIntent = Literal["hold_indefinitely", "sale", "refinance_recap", "generational"]
ManagementModel = Literal["member_managed", "manager_managed"]
ApprovalRule = Literal["unanimous", "supermajority", "majority_with_minority_veto"]
BuySellStyle = Literal["shotgun", "appraisal", "none"]
# Which hat Tessera is wearing. The Holdings position is that this is stated
# rather than left to be inferred, so the engine has to know it.
TesseraRole = Literal["advisor", "principal", "both", "none"]


class VentureProfile(BaseModel):
    """What the founder tells you before anything is drafted.

    Every field changes at least one structural output. Nothing is collected
    that does not decide something.
    """

    venture: str = Field(min_length=1)
    home_state: str = Field(min_length=1, description="Where the principals and the work sit.")

    # --- who is in it
    active_principals: int = Field(default=2, ge=1,
                                   description="People who will actually run it.")
    passive_investors: int = Field(default=0, ge=0)
    equal_ownership: bool = True
    spouses_involved: bool = False
    key_person_dependency: bool = Field(
        default=True, description="Does the business stop if one named person stops?")
    estate_planning_relevant: bool = False

    # --- what it does
    activity: Activity = "operating"
    regulated_regime: str | None = Field(
        default=None, description="Cannabis, liquor, film finance, food service, lending.")
    business_lines: int = Field(default=1, ge=1,
                                description="Distinct businesses or assets to be held.")
    states_of_operation: list[str] = Field(default_factory=list)

    # --- what it owns
    real_property: bool = False
    material_ip: bool = False
    operating_liability: bool = Field(
        default=True, description="Does it have employees, customers on site, or vehicles?")

    # --- money
    capital_source: CapitalSource = "founders_only"
    initial_capital: float = Field(default=0, ge=0)
    expects_additional_capital: bool = True
    operators_take_compensation: bool = True
    tiered_economics: bool = Field(
        default=False,
        description="Preferred return, promote, or any split other than straight pro rata.")

    # --- horizon
    exit_intent: ExitIntent = "hold_indefinitely"
    expected_hold_years: int | None = Field(default=None, ge=0)

    # --- Tessera's own position
    tessera_is_principal: bool = Field(
        default=False, description="Tessera holds equity, rather than only advising.")
    tessera_role: TesseraRole = Field(
        default="advisor",
        description="Advising, holding equity, or both. Both requires written disclosure.")

    @property
    def role(self) -> TesseraRole:
        """Reconcile the explicit role with the older boolean."""
        if self.tessera_role != "advisor":
            return self.tessera_role
        return "both" if self.tessera_is_principal else "advisor"

    @property
    def sector(self) -> SectorPattern | None:
        return pattern_for(self.activity)

    @property
    def total_members(self) -> int:
        return self.active_principals + self.passive_investors

    @property
    def is_regulated(self) -> bool:
        return bool(self.regulated_regime)

    @property
    def has_passive_capital(self) -> bool:
        return self.passive_investors > 0 or self.capital_source in {
            "private_placement", "institutional"}


# --- outputs ----------------------------------------------------------------

class EntityLayer(BaseModel):
    """One box in the structure chart."""

    name: str
    role: str
    entity_form: str
    owned_by: str | None = None
    holds: str
    why: str
    basis: Basis = "scaffold"


class Recommendation(BaseModel):
    """A single structural position, with what it prevents and where it came from."""

    area: str
    position: str
    because: str
    basis: Basis
    confirm: str | None = None
    adoption: AdoptedPosition | None = None

    def to_line(self) -> str:
        line = f"**{self.area}.** {self.position} {self.because}"
        if self.adoption:
            line += f" *{self.adoption.to_note()}*"
        # A counsel-reviewed adoption has answered the confirmation; repeating
        # it teaches the reader that the confirm lines are boilerplate.
        if self.confirm and not (self.adoption and self.adoption.counsel_reviewed):
            line += f" *Confirm: {self.confirm}*"
        return line


class FailureMode(BaseModel):
    """What goes wrong if the structure is not built this way."""

    name: str
    without_this: str
    addressed_by: list[str] = Field(default_factory=list)


class Conflict(BaseModel):
    """Two choices that cannot both stand.

    Surfaced before delivery, not after counsel finds them.
    """

    between: str
    problem: str
    resolve: str


class OpenQuestion(BaseModel):
    """Something no one can decide from the profile alone."""

    question: str
    why_it_matters: str
    blocks: str


class StructureOption(BaseModel):
    """One viable way to build it, with what it buys and what it costs.

    Tessera's stated approach is to build menus of outcomes rather than to lock
    a client into a single path. An engine that returns one answer contradicts
    that, however good the answer is -- so it returns the alternatives it
    considered and says which one it would default to and why.
    """

    name: str
    summary: str
    layers: list[EntityLayer]
    protects: list[str] = Field(default_factory=list)
    costs: list[str] = Field(default_factory=list)
    choose_when: str
    recommended: bool = False

    @property
    def entity_count(self) -> int:
        return len(self.layers)


class WaterfallTier(BaseModel):
    """One step in the order money leaves the deal."""

    order: int
    name: str
    what_happens: str
    to_investors: str
    to_sponsor: str


class CapitalArchitecture(BaseModel):
    """The shape of the economics, not the model.

    A qualified finance reviewer builds the model. This is the structural frame it fits inside --
    the order of payment, who carries the promote, and which protections belong
    on each side of the table.
    """

    applies: bool = False
    why_not: str | None = None
    preferred_return: str | None = None
    promote: str | None = None
    tiers: list[WaterfallTier] = Field(default_factory=list)
    clawback: bool = False
    sponsor_protective: list[str] = Field(default_factory=list)
    investor_protective: list[str] = Field(default_factory=list)
    open_points: list[str] = Field(default_factory=list)


class GlossaryEntry(BaseModel):
    """A term the founder will hear, in the words Tessera already uses publicly."""

    term: str
    plain: str


class ControlArchitecture(BaseModel):
    """Who may act alone, above what number everyone must agree, and what happens
    when they do not."""

    management_model: ManagementModel
    ordinary_course_threshold: DerivedNumber
    approval_rule: ApprovalRule
    approval_threshold_percent: DerivedNumber
    reserved_matters: list[str]
    deadlock_ladder: bool
    deadlock_steps: list[str] = Field(default_factory=list)
    buy_sell: BuySellStyle = "none"


class ExitArchitecture(BaseModel):
    right_of_first_refusal: bool
    permitted_estate_transfer: bool
    triggering_events: list[str]
    valuation_method: str
    payment_terms: str
    tag_along: bool
    drag_along: bool
    insurance_funded: bool


class StructureRecommendation(BaseModel):
    profile: VentureProfile
    entity_form: EntityType
    tax_treatment: TaxTreatment
    layers: list[EntityLayer]
    control: ControlArchitecture
    exit: ExitArchitecture
    recommendations: list[Recommendation]
    failure_modes: list[FailureMode]
    conflicts: list[Conflict]
    open_questions: list[OpenQuestion]
    options: list[StructureOption] = Field(default_factory=list)
    capital: CapitalArchitecture = Field(default_factory=CapitalArchitecture)
    glossary: list[GlossaryEntry] = Field(default_factory=list)
    disclosure: str | None = Field(
        default=None,
        description="Dual-role disclosure text, where Tessera both advises and holds.")

    # -- provenance ----------------------------------------------------------

    def unadopted(self) -> list[Recommendation]:
        """Positions that are starting points rather than Tessera standards."""
        return [item for item in self.recommendations if item.basis == "scaffold"]

    def synthetic_references(self) -> list[Recommendation]:
        """Positions drawn from the fictional offline evaluation playbook."""
        return [item for item in self.recommendations
                if item.basis == "synthetic_reference"]

    def adopted(self) -> list[Recommendation]:
        """Positions the partners have signed in the adoption ledger."""
        return [item for item in self.recommendations
                if item.basis == "tessera_adopted"]

    # -- what the document has to contain ------------------------------------

    def expected_clause_categories(self) -> set[str]:
        """Clause categories the assembled document must carry for this memo.

        The memo and the paper are two views of one recommendation, so a
        position that promises language has to be matched by a section that
        contains it. Seven categories once went missing from the library while
        the memo kept promising them, and every coverage check passed — this is
        the contract that makes that impossible to repeat.

        Two positions are conditional rather than absent-by-oversight. Where no
        deadlock ladder applies, the memo says so explicitly: that is a
        deliberate omission, and requiring the clause would be wrong. Same for
        estate transfers, which are offered only where asked for.
        """
        required = {
            "titles", "governance", "authority", "capital", "capital_default",
            "distributions", "transfer", "duties", "information",
            "triggering_events", "valuation", "buysell", "buyout_payment",
            "work_product", "restrictive_covenants", "tax_distributions",
            "exit", "dispute", "purpose",
        }
        if self.control.deadlock_ladder:
            required.add("deadlock")
        if self.exit.permitted_estate_transfer:
            required.add("estate_transfer")
        return required

    # -- hand-off to drafting ------------------------------------------------

    def to_deal_profile(self, *, counterparty: str, jurisdiction: str | None = None,
                        parties: list[Party] | None = None,
                        effective_date: str | None = None) -> DealProfile:
        """Turn the structure into the profile the clause library assembles from.

        The point of the whole module: the document that comes out is the one
        this structure calls for, rather than one whose parameters someone set
        by hand and may have set inconsistently with the advice.
        """
        industry: Industry = (
            "regulated" if self.profile.is_regulated
            else "real_estate" if self.profile.activity in {"real_estate_hold", "development"}
            else "general")
        shape = ("single" if self.profile.total_members == 1
                 else "equal" if self.profile.equal_ownership
                 else "majority_minority")
        return DealProfile(
            opportunity=self.profile.venture,
            agreement_type="operating_agreement",
            industry=industry,
            jurisdiction=jurisdiction or f"the State of {self._formation_state()}",
            counterparty=counterparty,
            counterparty_represented=self.profile.capital_source == "institutional",
            # The structure path has no fee input to derive a real number from
            # (Phase 3 adds one); asserting zero would understate exposure
            # rather than admit it is unknown.
            tessera_capital_at_risk=self.profile.role in {"principal", "both"},
            party_role=("co_venturer" if self.profile.role in {"principal", "both"}
                        else "sponsor"),
            entity_type=self.entity_form,
            tax_treatment=self.tax_treatment,
            ownership_shape=shape,
            member_count=self.profile.total_members,
            management_model=self.control.management_model,
            counterparty_type=(
                "institutional" if self.profile.capital_source == "institutional"
                else "individual" if self.profile.total_members <= 2 else "operator"),
            deal_value=self.profile.initial_capital,
            expected_hold_years=self.profile.expected_hold_years,
            regulatory_regime=self.profile.regulated_regime,
            parties=parties or [],
            effective_date=effective_date,
        )

    def derived_values(self) -> dict[str, str]:
        """Commercial terms the structure itself decided.

        Without this the clause library falls back to its posture defaults, and
        the memo and the agreement disagree about the same number -- the memo
        says one ordinary-course threshold while the document it produced says
        another. Both are defensible; having both is not.

        Per D3, an unconfirmed figure never reaches the agreement: a value is
        included here only once its :class:`~tessera_os.numbers.DerivedNumber`
        is ``stated``. ``to_draft_request`` already refuses to reach this
        point while anything is ``proposed`` or ``unresolved`` -- this check is
        the same rule enforced a second time, at the one place that actually
        writes into document text, rather than trusted to be enforced only
        upstream.
        """
        values = {}
        threshold = self.control.ordinary_course_threshold
        if threshold.state == "stated":
            values["ordinary_course_threshold"] = f"${threshold.value:,}"
        if self.control.approval_rule == "supermajority":
            percent = self.control.approval_threshold_percent
            if percent.state == "stated":
                values["member_approval_threshold"] = f"{percent.value}%"
        return values

    def derived_numbers(self) -> list[DerivedNumber]:
        """Every figure in this recommendation that must be ``stated`` before
        it may reach an agreement. See D3 and ``to_draft_request``."""
        return [self.control.ordinary_course_threshold, self.control.approval_threshold_percent]

    def _formation_state(self) -> str:
        for layer in self.layers:
            if "Delaware" in layer.entity_form:
                return "Delaware"
        return self.profile.home_state

    # -- report --------------------------------------------------------------

    def to_markdown(self) -> str:
        return render_structure_memo(self)


# --- the engine -------------------------------------------------------------

# Phase 3 (docs/BUILD_BRIEF_PHASE_3_REAL_NUMBERS.md): none of the following
# module-level numbers are sourced from a Tessera position, a client fact, or
# anything else that would let them stand as advice on their own. Each is
# named here, once, so that a number reaching a memo or a document is always
# traceable to exactly one of these constants (or to a DerivedNumber) rather
# than typed directly into rendered prose where it would read as researched.
# tests/test_no_invented_numbers.py enforces that nothing new is typed
# directly into governance.py's rendered text without being named here first.

# Unsourced coefficients behind the ordinary-course threshold proposal (3.2).
# The floor, the coefficient, and the cap are a plausible shape with invented
# parameters -- see docs/BUILD_BRIEF_PHASE_3_REAL_NUMBERS.md section 1. There
# is deliberately no fallback figure for zero stated capital any more: that
# case is unresolved, not a fabricated $50,000 default.
_THRESHOLD_COEFFICIENT = 0.02
_THRESHOLD_FLOOR = 10_000
_THRESHOLD_CAP = 250_000

# Unsourced approval-threshold percentages (3.3). 100% for the unanimous rule
# is a direct consequence of choosing unanimity, not an independently guessed
# figure; 75% and 51% are guesses with no Tessera position behind them.
_UNANIMOUS_PERCENT = 100
_SUPERMAJORITY_PERCENT = 75
_MAJORITY_PERCENT = 51

# Unsourced reserved-matter contract-duration ceiling.
_ORDINARY_COURSE_CONTRACT_MONTHS = 12


def _ordinary_course_threshold(profile: VentureProfile) -> DerivedNumber:
    """Propose a threshold from stated capital, or leave it unresolved.

    Per D1, a venture with no stated capital gets no number at all -- the
    zero-capital case is surfaced as a blocking open question by
    ``_open_questions`` rather than papered over with a fabricated default.
    """
    if profile.initial_capital <= 0:
        return DerivedNumber(label=ORDINARY_COURSE_THRESHOLD_LABEL, value=None,
                             state="unresolved")
    scaled = int(round(profile.initial_capital * _THRESHOLD_COEFFICIENT, -3))
    value = max(_THRESHOLD_FLOOR, min(scaled, _THRESHOLD_CAP))
    derivation = (
        f"Derived as {_THRESHOLD_COEFFICIENT:.0%} of stated initial capital "
        f"(${profile.initial_capital:,.0f}), floored at ${_THRESHOLD_FLOOR:,} and capped at "
        f"${_THRESHOLD_CAP:,}. This is a common starting point but is not a Tessera position "
        "and has not been tested against your actual operating budget. Confirm or replace "
        "before this reaches a document.")
    return DerivedNumber(label=ORDINARY_COURSE_THRESHOLD_LABEL, value=value, state="proposed",
                         derivation=derivation)


def _dollars(value: int) -> str:
    return f"${value:,}"


def _percent(value: int) -> str:
    return f"{value}%"


# Generic synthetic reserved-matter checklist for offline evaluation.
_BASE_RESERVED = [
    ("Incurring, guaranteeing, or refinancing debt, or any contract above the ordinary "
     f"course threshold or running beyond twelve ({_ORDINARY_COURSE_CONTRACT_MONTHS}) months"),
    "Issuing new interests, admitting a member, or granting any option or right to acquire one",
    "Selling, leasing, transferring, or encumbering a material asset outside the ordinary course",
    "Merging, converting, consolidating, reorganising, dissolving, or filing for bankruptcy",
    "Amending the certificate of formation or the operating agreement",
    "Distributions outside the agreed waterfall, and approving a capital call",
    "Any business activity materially outside the stated purpose",
    ("Hiring, terminating, or setting compensation for a senior executive, or engaging a "
     "member's affiliate as a service provider"),
    "Commencing or settling litigation above the ordinary course threshold",
    "Changing accountants, tax classification, or any material tax election",
]

_REGULATED_RESERVED = [
    "Any application for, amendment to, surrender of, or transfer of a licence",
    "Any change of control or ownership change requiring notice to or approval from the regulator",
    "Admitting any owner who would trigger a disclosure, background check, or residency requirement",
]

_PROPERTY_RESERVED = [
    "Acquiring or disposing of real property",
    "Granting a mortgage, deed of trust, or other encumbrance on real property",
    "Any lease running beyond the ordinary course term, or to a member's affiliate",
]

_OUTSIDE_CAPITAL_RESERVED = [
    "Any transaction between the company and a member, sponsor, or their affiliates",
    "Changing the manager, or the scope of the manager's authority",
    "Any capital event -- sale, refinancing, or recapitalisation of the company or its assets",
]


def _reserved_matters(profile: VentureProfile) -> list[str]:
    matters = list(_BASE_RESERVED)
    if profile.is_regulated:
        matters += _REGULATED_RESERVED
    if profile.real_property:
        matters += _PROPERTY_RESERVED
    if profile.has_passive_capital:
        matters += _OUTSIDE_CAPITAL_RESERVED
    # What this industry, and this licensing regime, add on top.
    if (sector := profile.sector) is not None:
        matters += sector.reserved_matters
    if (regime := regime_for(profile.regulated_regime)) is not None:
        matters += regime.reserved_matters
    # Two sources can name the same matter -- a liquor licence appears in both
    # the hospitality pattern and the liquor regime. Keep the first wording.
    seen, unique = set(), []
    for matter in matters:
        key = matter.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(matter)
    return unique


def _management_model(profile: VentureProfile) -> tuple[ManagementModel, str, Basis]:
    """Passive money and apparent authority are the whole question here."""
    if profile.has_passive_capital:
        return ("manager_managed",
                ("Centralized day-to-day authority keeps passive investors from being presented "
                 "as operators; qualified counsel must confirm actual authority and securities "
                 "consequences."),
                "scaffold")
    if profile.total_members > 3:
        return ("manager_managed",
                ("Above three members, member management means every counterparty has to work out "
                 "who can sign, and any one member can bind the company by accident."),
                "scaffold")
    return ("member_managed",
            ("Every owner is active and the group is small enough that shared authority is "
             "workable in this synthetic evaluation."),
            "scaffold")


def _approval_rule(profile: VentureProfile) -> tuple[ApprovalRule, DerivedNumber, Basis]:
    if profile.total_members == 2 and profile.equal_ownership:
        return ("unanimous", DerivedNumber(
                    label=APPROVAL_THRESHOLD_LABEL, value=_UNANIMOUS_PERCENT, state="proposed",
                    derivation=(
                        f"{_percent(_UNANIMOUS_PERCENT)} follows directly from requiring "
                        "unanimous consent between both members -- it is a consequence of "
                        "choosing unanimity below, not an independently chosen figure. Confirm "
                        "that unanimity, rather than a lower threshold, is what you want.")),
                "synthetic_reference")
    if profile.equal_ownership and profile.total_members >= 3:
        return ("supermajority", DerivedNumber(
                    label=APPROVAL_THRESHOLD_LABEL, value=_SUPERMAJORITY_PERCENT, state="proposed",
                    derivation=(
                        f"{_percent(_SUPERMAJORITY_PERCENT)} is a common supermajority line for "
                        "three or more equal owners, but no Tessera position sets it and it has "
                        "not been tested against how often you expect to disagree. Confirm or "
                        "replace before this reaches a document.")),
                "scaffold")
    return ("majority_with_minority_veto", DerivedNumber(
                label=APPROVAL_THRESHOLD_LABEL, value=_MAJORITY_PERCENT, state="proposed",
                derivation=(
                    f"{_percent(_MAJORITY_PERCENT)} is a bare majority, used here only to decide "
                    "reserved matters outside the protective list. It has not been chosen for "
                    "this venture specifically. Confirm or replace before this reaches a "
                    "document.")),
            "scaffold")


def _deadlock_needed(profile: VentureProfile, rule: ApprovalRule,
                     threshold: DerivedNumber) -> bool:
    """A deadlock ladder belongs only where no coalition can carry a reserved matter.

    Where one party holds control, adding a ladder does not protect anyone -- it
    hands the other side a lever to force an exit over a decision that was never
    theirs to make. And where a supermajority can be assembled without every
    owner, a dissenter is outvoted rather than deadlocked, which is a different
    problem with a different answer.
    """
    if rule == "majority_with_minority_veto":
        return False
    if profile.total_members < 2:
        return False
    if rule == "unanimous":
        return True
    required = math.ceil(profile.total_members * threshold.value / 100)
    return required >= profile.total_members


def _no_deadlock_reason(rule: ApprovalRule) -> str:
    if rule == "majority_with_minority_veto":
        return ("One party can already carry a decision, so a ladder would not break a tie — it "
                "would hand the other side a lever to force an exit over a decision that was "
                "never theirs to make.")
    return ("The approval threshold can be met without every owner, so a dissenting member is "
            "outvoted rather than deadlocked. That calls for minority protections on an "
            "enumerated list, not an exit mechanism.")


# Unsourced procedural day-counts for the deadlock ladder -- reasonable-looking
# defaults, not tested against how this venture actually operates.
_DEADLOCK_NOTICE_DAYS = 10
_DEADLOCK_MEETING_DAYS = 15
_DEADLOCK_MEDIATION_DAYS = 30
_DEADLOCK_REMEDY_DAYS = 45

_DEADLOCK_STEPS = [
    (f"Ten ({_DEADLOCK_NOTICE_DAYS}) business days from the day either party first raises the "
     "matter in writing, after which either may serve a deadlock notice"),
    (f"A meeting in person or by video within fifteen ({_DEADLOCK_MEETING_DAYS}) business days "
     "of the notice"),
    (f"Non-binding mediation before a single neutral, completed within thirty "
     f"({_DEADLOCK_MEDIATION_DAYS}) days of selection, fees shared equally"),
    (f"Any separately approved exit remedy available forty-five ({_DEADLOCK_REMEDY_DAYS}) days "
     "after the notice — but only if the deadlock materially "
     "impairs the company's ability to operate in the ordinary course"),
]


# Unsourced shotgun-buy-sell mechanics (3.6, the known "1% shotgun unit").
_SHOTGUN_UNIT_PERCENT = 1
_SHOTGUN_ELECTION_DAYS = 30


def _buy_sell_style(profile: VentureProfile) -> tuple[BuySellStyle, str, Basis]:
    """A shotgun is only fair between parties who can both write the cheque."""
    if profile.has_passive_capital or not profile.equal_ownership:
        return ("appraisal",
                ("The parties do not have comparable liquidity, and a shotgun in that setting "
                 "simply lets the deeper pocket name the price and know it will be accepted."),
                "scaffold")
    return ("shotgun",
            ("It prices the interest honestly, because whoever names the number does not know "
             "which side of the trade they will end up on."),
            "scaffold")


# Unsourced procedural day-counts for the exit triggers below.
_DISABILITY_CONSECUTIVE_DAYS = 90
_DISABILITY_LOOKBACK_TRIGGER_DAYS = 120
_DISABILITY_LOOKBACK_WINDOW_DAYS = 180
_BREACH_CURE_DAYS = 30

_BASE_TRIGGERS = [
    "Death",
    (f"Disability — unable to perform for ninety ({_DISABILITY_CONSECUTIVE_DAYS}) consecutive "
     f"days, or one hundred twenty ({_DISABILITY_LOOKBACK_TRIGGER_DAYS}) days in any trailing "
     f"one hundred eighty ({_DISABILITY_LOOKBACK_WINDOW_DAYS})"),
    "Bankruptcy, or an assignment for the benefit of creditors",
    "Voluntary withdrawal or resignation from active involvement",
    f"Material breach uncured for thirty ({_BREACH_CURE_DAYS}) days after written notice",
    ("Conviction of, or a plea to, a felony or a crime of fraud, dishonesty, or moral turpitude "
     "that materially and adversely affects the company"),
]
_SPOUSE_TRIGGER = (
    "Divorce or dissolution of marriage that would transfer any part of the interest to a "
    "spouse or former spouse, absent a premarital or postmarital waiver")


# Unsourced valuation-and-payment commercial figures (3.6). Phase 5 owns
# whether these are the right numbers; Phase 3 only owns naming the fact that
# they are currently invented. See docs/BUILD_BRIEF_PHASE_3_REAL_NUMBERS.md.
_VALUATION_AGREEMENT_DAYS = 20
_VALUATION_BAND_PERCENT = 15
_BUYOUT_CASH_PERCENT = 25
_BUYOUT_NOTE_PERCENT = 100 - _BUYOUT_CASH_PERCENT
_BUYOUT_NOTE_MONTHS = 24


def _exit_architecture(profile: VentureProfile, buy_sell: BuySellStyle) -> ExitArchitecture:
    triggers = list(_BASE_TRIGGERS)
    if profile.spouses_involved:
        triggers.insert(3, _SPOUSE_TRIGGER)
    return ExitArchitecture(
        right_of_first_refusal=True,
        permitted_estate_transfer=profile.estate_planning_relevant,
        triggering_events=triggers,
        valuation_method=(
            f"Agree within twenty ({_VALUATION_AGREEMENT_DAYS}) days; failing that each side "
            f"appoints an appraiser, and if the two are within fifteen percent "
            f"({_VALUATION_BAND_PERCENT}%) the value is their average, otherwise the two appoint "
            "a third whose determination binds. Each pays its own appraiser; the third is "
            "shared."),
        payment_terms=(
            f"Twenty-five percent ({_BUYOUT_CASH_PERCENT}%) cash at closing and seventy-five "
            f"percent ({_BUYOUT_NOTE_PERCENT}%) by note at an approved lawful rate over "
            f"twenty-four ({_BUYOUT_NOTE_MONTHS}) months, secured by a pledge of the interest "
            "acquired, prepayable without penalty."),
        tag_along=not profile.equal_ownership or profile.has_passive_capital,
        drag_along=profile.exit_intent == "sale",
        insurance_funded=profile.key_person_dependency,
    )


def _tax_treatment(profile: VentureProfile) -> tuple[TaxTreatment, str, Basis]:
    if profile.total_members == 1:
        return ("disregarded",
                ("Use disregarded status only as a synthetic modeling assumption until a tax "
                 "advisor confirms classification and elections."),
                "scaffold")
    return ("partnership",
            ("Use partnership treatment only as a synthetic modeling assumption until a tax "
             "advisor confirms classification, allocations, and elections."),
            "scaffold")


def _form(state: str) -> str:
    """"an Oklahoma limited liability company", "a Delaware limited liability company"."""
    article = "an" if state[:1].upper() in "AEIOU" else "a"
    return f"{article} {state} limited liability company"


_HOLDING_WORDS = ("holdings", "holding", "group", "capital", "partners")


def _base_name(venture: str) -> str:
    """Strip a trailing suffix so the chart does not read "Harbor Holdings Holdings LLC"."""
    words = venture.replace(",", "").split()
    while words and words[-1].lower().rstrip(".") in {"llc", "lp", "inc", "co"}:
        words.pop()
    return " ".join(words) or venture


def _holdco_name(venture: str) -> str:
    base = _base_name(venture)
    if base.split()[-1].lower() in _HOLDING_WORDS:
        return f"{base} LLC"
    return f"{base} Holdings LLC"


def _entity_layers(profile: VentureProfile) -> list[EntityLayer]:
    """The structure chart. Separation exists to stop one loss reaching another asset."""
    state = profile.home_state
    layers: list[EntityLayer] = []

    sector = profile.sector
    # A film's rights entity is the IP entity; a beverage entity is the licence
    # entity. Emitting the general-rule version alongside is two filing fees for
    # one job, and a reader cannot tell which one the assets belong in.
    superseded = {spec.supersedes for spec in sector.layers} if sector else set()
    holdco_needed = (
        profile.business_lines > 1
        or profile.has_passive_capital
        or (profile.real_property and profile.operating_liability)
        or profile.is_regulated
        or profile.material_ip
        # Film, trades, and hospitality each need entities the general rules
        # would not produce, and those entities need something to own them.
        or sector is not None)

    if not holdco_needed:
        layers.append(EntityLayer(
            name=f"{_base_name(profile.venture)} LLC",
            role="Sole entity",
            entity_form=_form(state),
            holds="The whole business",
            why="One line of business, no outside capital, and no asset worth isolating. A "
                "second entity here would add filings and cost without moving any risk.",
            basis="scaffold"))
        return layers

    holdco_state = "Delaware" if (
        profile.has_passive_capital or profile.capital_source == "institutional") else state
    layers.append(EntityLayer(
        name=_holdco_name(profile.venture),
        role="HoldCo",
        entity_form=_form(holdco_state),
        holds="Equity in every operating entity; the cap table, the governance, and the "
              "investor rights sit here",
        why=("Ownership and control belong one level above the business that carries the "
             "liability, so a claim against operations reaches the operating entity and stops "
             "there, and so a new investor or a new line of business is admitted without "
             "reopening the operating company's paper."),
        basis="scaffold"))

    if profile.material_ip and "ip" not in superseded:
        layers.append(EntityLayer(
            name=f"{_base_name(profile.venture)} IP LLC",
            role="IP holding entity",
            entity_form=_form(holdco_state),
            owned_by=_holdco_name(profile.venture),
            holds="Trademarks, frameworks, models, software, and the licences out to the "
                  "operating entities",
            why=("The intangibles are usually the durable asset and the operating entity is "
                 "where the lawsuits land. Holding them apart and licensing them in means an "
                 "operating failure does not take the brand with it, and a sale of one line "
                 "does not hand over the frameworks behind all of them."),
            basis="scaffold"))

    if profile.real_property:
        count = max(1, profile.business_lines if profile.activity in {
            "real_estate_hold", "development"} else 1)
        first_why = (
            "Each property sits alone so a judgment, an environmental claim, or a lender's "
            "remedy at one cannot reach another, and so a single asset can be sold or "
            "refinanced without disturbing the rest.")
        for index in range(1, count + 1):
            suffix = f" {index}" if count > 1 else ""
            layers.append(EntityLayer(
                name=f"{_base_name(profile.venture)} PropCo{suffix} LLC",
                role="Property-owning entity",
                entity_form=_form(state),
                owned_by=_holdco_name(profile.venture),
                holds="Title to the real property, and the mortgage",
                why=(first_why if index == 1 else
                     "One entity per asset, for the same reason — isolation is only real if "
                     "the assets are not pooled."),
                basis="scaffold"))

    # Where the sector already supplies a per-unit operating entity -- one per
    # picture, one per location -- a general OpCo on top of it is a filing fee
    # with nothing behind it.
    sector_has_operating_units = sector is not None and any(
        spec.per_unit for spec in sector.layers)
    if (profile.activity != "real_estate_hold" or profile.operating_liability) and not (
            sector_has_operating_units):
        layers.append(EntityLayer(
            name=f"{_base_name(profile.venture)} Operations LLC",
            role="OpCo",
            entity_form=_form(state),
            owned_by=_holdco_name(profile.venture),
            holds="Employees, customer contracts, vendor contracts, insurance, and the "
                  "day-to-day liability",
            why=("Everything that can generate a claim is concentrated in the entity that owns "
                 "the least. Where there is also real property, OpCo leases it from PropCo at "
                 "a market rent — which keeps the building out of reach of an operating claim "
                 "and leaves a rent stream that survives a sale of the business."),
            basis="scaffold"))

    if profile.is_regulated and "licence" not in superseded:
        layers.append(EntityLayer(
            name=f"{_base_name(profile.venture)} Licensing LLC",
            role="Licence holder",
            entity_form=_form(state),
            owned_by=_holdco_name(profile.venture),
            holds=f"The {profile.regulated_regime} licence and nothing else of value",
            why=("A licence is usually non-transferable, tied to named owners, and lost or "
                 "suspended by the regulator rather than by a court. Isolating it means a "
                 "regulatory action against the licence does not take the assets down with it, "
                 "and an ownership change elsewhere in the structure does not automatically "
                 "become a change of control at the licence."),
            basis="scaffold"))

    layers += _sector_layers(profile)
    return layers


def _sector_layers(profile: VentureProfile) -> list[EntityLayer]:
    """Entities this industry needs that the general rules would not produce."""
    sector = profile.sector
    if sector is None:
        return []
    base = _base_name(profile.venture)
    holdco = _holdco_name(profile.venture)
    layers: list[EntityLayer] = []
    for spec in sector.layers:
        count = max(1, profile.business_lines) if spec.per_unit else 1
        for index in range(1, count + 1):
            # "Lantern Pictures Productions 2 LLC", not "Lantern Pictures 2
            # Productions LLC" -- the number belongs to the unit, not the firm.
            stem = spec.suffix.removesuffix(" LLC")
            marker = f" {index}" if count > 1 else ""
            layers.append(EntityLayer(
                name=f"{base} {stem}{marker} LLC",
                role=spec.role,
                entity_form=_form(profile.home_state),
                owned_by=holdco,
                holds=spec.holds,
                why=(spec.why if index == 1 else
                     f"One entity per {sector.unit_noun}, for the same reason — isolation is "
                     "only real if they are not pooled."),
                basis="scaffold"))
    return layers


def _recommendations(profile: VentureProfile, control: ControlArchitecture,
                     exit_arch: ExitArchitecture, entity_form: EntityType,
                     tax: TaxTreatment, tax_why: str, tax_basis: Basis,
                     mgmt_why: str, mgmt_basis: Basis,
                     approval_basis: Basis,
                     buy_sell_why: str, buy_sell_basis: Basis) -> list[Recommendation]:
    items: list[Recommendation] = []

    items.append(Recommendation(
        area="Entity form", basis="scaffold",
        position=(f"A limited liability company, formed in {profile.home_state}."
                  if entity_form == "llc" else f"A {entity_form}."),
        because="It gives the liability shield without the corporate formalities, and its "
                "economics are set by agreement rather than by statute — which is what lets the "
                "capital, control, and exit terms below be written at all.",
        confirm="Whether any investor or lender requires a corporation, and whether the "
                "founders want QSBS treatment, which an LLC cannot deliver."))

    items.append(Recommendation(
        area="Tax treatment", basis=tax_basis,
        position=f"Treated as a {tax.replace('_', ' ')} for federal and state income tax.",
        because=tax_why,
        confirm="Run this past the tax advisor before formation — the election deadline is "
                "short and the default is hard to unwind."))

    items.append(Recommendation(
        area="Management", basis=mgmt_basis,
        position=("Member-managed, with each active principal holding equal authority."
                  if control.management_model == "member_managed"
                  else "Manager-managed, with a named manager and members holding consent "
                       "rights over the reserved matters only."),
        because=mgmt_why))

    items.append(Recommendation(
        area="Titles", basis="synthetic_reference",
        position="State in the agreement that titles do not confer authority, voting power, or "
                 "ownership beyond what the agreement grants.",
        because="Titles get handed out casually and then get relied on. Saying so once in the "
                "document closes the argument that a title carried a right the cap table never "
                "gave."))

    items.append(Recommendation(
        area="Ordinary-course authority", basis="synthetic_reference",
        position=f"Either principal may act alone up to "
                 f"{control.ordinary_course_threshold.render_inline(fmt=_dollars)}; above it, "
                 "the reserved-matter rule applies.",
        because="This one number is the hinge of the whole design. Below it the business can "
                "move without a meeting; above it nobody can commit the others to something "
                "they never saw.",
        confirm="Test the number against a normal month of spending before adopting it — too "
                "low and every invoice becomes a negotiation."))

    approval_percent = control.approval_threshold_percent.render_inline(fmt=_percent)
    rule_text = {
        "unanimous": "Reserved matters require the unanimous written consent of both members, "
                     "which either may withhold in its sole discretion.",
        "supermajority": "Reserved matters require the written consent of members holding "
                         f"{approval_percent} of units.",
        "majority_with_minority_veto":
            f"Reserved matters carry on a majority of units ({approval_percent}), except for an "
            "enumerated protective list — amendments, new interests, related-party "
            "transactions, and any change to the distribution waterfall — over which the "
            "minority holds a veto.",
    }[control.approval_rule]
    items.append(Recommendation(
        area="Reserved matters", basis=approval_basis,
        position=f"{len(control.reserved_matters)} enumerated reserved matters. {rule_text}",
        because="Control is not the percentage on the cap table, it is the list of things that "
                "cannot happen without you. The list is where the real negotiation is."))

    if control.deadlock_ladder:
        items.append(Recommendation(
            area="Deadlock", basis="synthetic_reference",
            position="A four-step ladder: waiting period, meeting, non-binding mediation, then "
                     "buy-sell — the last step available only where the deadlock materially "
                     "impairs ordinary-course operation.",
            because="Without a ladder, a disagreement between equals ends in judicial "
                    "dissolution, where a court winds up a working business. The impairment "
                    "qualifier is what stops the buy-sell becoming a hair trigger someone can "
                    "pull over a decision they simply lost."))
    else:
        items.append(Recommendation(
            area="Deadlock", basis="scaffold",
            position="No deadlock ladder. Reserved matters resolve on the voting rule.",
            because=_no_deadlock_reason(control.approval_rule)))

    if control.buy_sell != "none":
        items.append(Recommendation(
            area="Buy-sell", basis=buy_sell_basis,
            position=(f"A shotgun: one party names a single price per one percent "
                      f"({_SHOTGUN_UNIT_PERCENT}%) of interest, the other elects to buy or sell "
                      f"at it within thirty ({_SHOTGUN_ELECTION_DAYS}) days, and failure to "
                      "elect is deemed an election to sell."
                      if control.buy_sell == "shotgun"
                      else "An appraisal buy-sell at fair market value determined by the "
                           "three-appraiser procedure."),
            because=buy_sell_why))

    items.append(Recommendation(
        area="Capital calls", basis="synthetic_reference",
        position="No additional contribution, member loan, or dilution occurs until the amount, "
                 "purpose, allocation, and consequences are approved in writing.",
        because="The synthetic engine must not invent a capital-call remedy or change ownership "
                "economics before the parties and qualified counsel approve it.",
        confirm="Qualified counsel drafts any loan, dilution, cure, and enforcement mechanics."))

    items.append(Recommendation(
        area="Transfer restrictions", basis="scaffold",
        position="Proposed transfer restrictions and a right of first refusal, with exact "
                 "conditions left for qualified counsel."
                 + (" Transfers to a revocable estate-planning trust are permitted without "
                    "triggering the ROFR, provided the member keeps sole voting control for "
                    "life and the trustee joins the agreement."
                    if exit_arch.permitted_estate_transfer else ""),
        because="Closely held equity is only worth what it is because of who holds it. The "
                "restriction is what stops a stranger — a creditor, an ex-spouse, a buyer you "
                "did not choose — turning up as your partner."))

    items.append(Recommendation(
        area="Triggering events", basis="scaffold",
        position=f"{len(exit_arch.triggering_events)} events give the other side the right to "
                 "buy the affected interest.",
        because="Every one of these is a moment where an owner stops being the person you went "
                "into business with. The right to buy is what converts that from a crisis into "
                "a transaction."))

    items.append(Recommendation(
        area="Valuation", basis="scaffold",
        position=exit_arch.valuation_method,
        because="A buy-out needs an approved valuation process. This synthetic three-appraiser "
                "example is a discussion starting point, not an adopted term."))

    items.append(Recommendation(
        area="Payment terms", basis="scaffold",
        position=exit_arch.payment_terms,
        because="A buy-out the buyer cannot fund is not a remedy. The fictional down payment and "
                "secured-note example keeps the right exercisable by a working business "
                "rather than only by whoever has cash on hand."))

    if exit_arch.insurance_funded:
        items.append(Recommendation(
            area="Key-person funding", basis="scaffold",
            position="Consider funding the death and disability purchase with insurance owned "
                     "by the company or cross-owned by the members.",
            because="The obligation to buy a deceased partner's interest arrives at the worst "
                    "possible moment for cash. Insurance is what makes the promise real.",
            confirm="Who owns the policies, and how the premiums are treated — this changes the "
                    "tax outcome for the survivor."))

    if exit_arch.tag_along or exit_arch.drag_along:
        both = exit_arch.tag_along and exit_arch.drag_along
        items.append(Recommendation(
            area="Tag-along and drag-along", basis="scaffold",
            position=("Both a tag-along for the minority and a drag-along at the stated "
                      "threshold." if both
                      else "A tag-along for the minority." if exit_arch.tag_along
                      else "A drag-along at the stated threshold."),
            because="Tag stops the majority selling out and leaving the minority with a new "
                    "partner they did not pick. Drag stops one small holder blocking a sale "
                    "everyone else wants. They are opposite protections and which ones belong "
                    "depends on which side of the table the client sits.",
            confirm="The drag threshold — higher protects the minority, lower protects the "
                    "exit."))

    items.append(Recommendation(
        area="Work product", basis="scaffold",
        position="All frameworks, deal structures, financial models, and governance templates "
                 "developed in connection with the business are owned by the company, with a "
                 "present assignment and a further-assurances covenant.",
        because="In a firm whose asset is how it thinks, the templates are the enterprise "
                "value. Without an assignment they leave with whoever wrote them."))

    items.append(Recommendation(
        area="Restrictive covenants", basis="scaffold",
        position="Confidentiality is included; no non-compete or non-solicit is recommended "
                 "until qualified counsel supplies a jurisdiction-specific position.",
        because="Post-departure restrictions are highly jurisdiction- and fact-dependent, so an "
                "offline synthetic engine cannot safely choose their scope or duration.",
        confirm="Qualified counsel confirms whether any restriction is permitted and drafts it."))

    items.append(Recommendation(
        area="Tax distributions", basis="scaffold",
        position="A mandatory distribution sufficient to cover each member's tax on allocated "
                 "income, by a stated date each year.",
        because="Pass-through income is taxed to the member whether or not any cash was "
                "distributed. Without this, a profitable year can hand an owner a tax bill and "
                "no money to pay it."))

    if profile.is_regulated:
        items.append(Recommendation(
            area="Regulatory overlay", basis="scaffold",
            position=f"Every ownership change is conditioned on prior {profile.regulated_regime} "
                     "regulatory clearance, and no transfer closes until it is obtained.",
            because="In a licensed business the regulator is a party to every transfer whether "
                    "the agreement says so or not. Writing the condition in means a transfer "
                    "cannot accidentally put the licence at risk.",
            confirm="Regulatory counsel confirms the disclosure thresholds and which changes "
                    "require prior approval rather than notice."))

    items.append(Recommendation(
        area="Dispute resolution", basis="scaffold",
        position="Select litigation, arbitration, venue, and emergency-relief procedures only "
                 "after qualified counsel reviews the parties and governing law.",
        because="Forum and remedy choices affect cost, timing, appeal rights, and enforceability; "
                "the synthetic engine does not choose them."))

    items += _sector_positions(profile)
    items += _dual_role_positions(profile)
    return items


def _sector_positions(profile: VentureProfile) -> list[Recommendation]:
    """What this industry and this licensing regime add to the advice."""
    items: list[Recommendation] = []
    if (sector := profile.sector) is not None:
        items += [Recommendation(area=area, position=position, because=because,
                                 basis="scaffold")
                  for area, position, because in sector.positions]
    if (regime := regime_for(profile.regulated_regime)) is not None:
        items += [Recommendation(area=area, position=position, because=because,
                                 basis="scaffold")
                  for area, position, because in regime.positions]
    return items


# Synthetic disclosure template used to test whether dual roles are surfaced.
DUAL_ROLE_DISCLOSURE = (
    "The synthetic scenario assumes Tessera may act in two capacities in this venture: "
    "advising on structure and also holding an equity interest. "
    "Those roles do not always point the same way. Advice about the reserved-matter list, "
    "the promote, the transfer restrictions, and the buy-out terms all touch positions "
    "Tessera itself will hold.\n\n"
    "Accordingly: (i) this disclosure is made in writing before terms are negotiated; "
    "(ii) the counterparty is advised to obtain independent counsel, and Tessera's work "
    "does not substitute for it; (iii) any term that runs in Tessera's favour as an owner "
    "is identified as such where it appears; and (iv) the engagement letter records the "
    "counterparty's written consent to Tessera acting in both capacities, or records that "
    "consent was declined and which role Tessera is taking."
)


def _dual_role_positions(profile: VentureProfile) -> list[Recommendation]:
    """Say which hat is being worn, in writing, before terms are discussed."""
    if profile.role != "both":
        return []
    return [Recommendation(
        area="Dual-role disclosure", basis="synthetic_reference",
        position="Disclose in writing, before terms are negotiated, that Tessera is both "
                 "advising and holding equity; recommend independent counsel; flag every "
                 "term that runs in Tessera's favour as an owner; and record written "
                 "consent in the engagement letter.",
        because="The synthetic policy requires clarity about which role Tessera may hold. "
                "A conflict that is disclosed and consented to is a structure; the "
                "same conflict discovered later is the thing that ends the relationship and "
                "taints every term Tessera recommended.",
        confirm="Counsel confirms the disclosure and consent language against the "
                "engagement letter and against any applicable professional-conduct or "
                "broker-registration rules.")]


def _failure_modes(profile: VentureProfile, control: ControlArchitecture,
                   exit_arch: ExitArchitecture) -> list[FailureMode]:
    modes: list[FailureMode] = []
    if control.deadlock_ladder:
        modes.append(FailureMode(
            name="Two people, no tiebreak",
            without_this="Equal owners disagree on something that has to be decided, neither "
                         "can carry it, and the only remaining forum is a petition for judicial "
                         "dissolution — a court winding up a business that works.",
            addressed_by=["Deadlock", "Buy-sell"]))
    modes.append(FailureMode(
        name="The operating claim reaches the building",
        without_this="A slip-and-fall, an employment claim, or a vehicle accident in the "
                     "operating business becomes a judgment against the entity that also holds "
                     "the real estate, and the asset is sold to satisfy it.",
        addressed_by=["Entity topology"]))
    modes.append(FailureMode(
        name="The departing owner keeps the vote",
        without_this="Someone stops working, stops contributing, and keeps every consent right "
                     "they had on day one — including the veto over the deal that would have "
                     "bought them out.",
        addressed_by=["Triggering events", "Withdrawal from management"]))
    modes.append(FailureMode(
        name="Your partner's heir is your new partner",
        without_this="An owner dies or divorces and the interest passes to a spouse, an estate, "
                     "or an ex — someone with no operating role, full economic rights, and no "
                     "reason to agree with you.",
        addressed_by=["Transfer restrictions", "Triggering events", "Key-person funding"]))
    if profile.expects_additional_capital:
        modes.append(FailureMode(
            name="Dilution by refusal to fund",
            without_this="The business needs money, one owner will not or cannot put it in, and "
                         "there is no mechanism — so the one who funds it either carries the "
                         "other for free or the business does not get funded.",
            addressed_by=["Capital calls"]))
    if profile.is_regulated:
        modes.append(FailureMode(
            name="The licence, not the entity, is the asset",
            without_this="An ownership change nobody thought was material triggers a change of "
                         "control at the regulator, and the licence is suspended or lost — "
                         "taking the business with it regardless of what the entities own.",
            addressed_by=["Entity topology", "Regulatory overlay"]))
    if profile.material_ip:
        modes.append(FailureMode(
            name="The frameworks walk out",
            without_this="The models, templates, and methods were built by a person rather than "
                         "assigned to a company, so they leave when that person does — and can "
                         "be used against the business the next day.",
            addressed_by=["Work product", "Entity topology"]))
    modes.append(FailureMode(
        name="Phantom income",
        without_this="A profitable year allocates taxable income to every owner, the cash stays "
                     "in the business, and the owners owe tax on money they never received.",
        addressed_by=["Tax distributions"]))
    if exit_arch.insurance_funded:
        modes.append(FailureMode(
            name="A right nobody can afford to exercise",
            without_this="The buy-out right on death exists on paper, the survivor cannot "
                         "fund it, and the estate stays in the cap table by default.",
            addressed_by=["Key-person funding", "Payment terms"]))
    if profile.role == "both":
        modes.append(FailureMode(
            name="The advisor turns out to be across the table",
            without_this="Tessera advised on the structure and also holds equity in it. The "
                         "counterparty learns that after signing, and every term Tessera "
                         "recommended is now arguable — not because it was wrong, but "
                         "because it was never disclosed.",
            addressed_by=["Dual-role disclosure"]))
    if (sector := profile.sector) is not None:
        modes += [FailureMode(name=name, without_this=detail,
                              addressed_by=["Entity topology", sector.label])
                  for name, detail in sector.failure_modes]
    return modes


def _conflicts(profile: VentureProfile, control: ControlArchitecture,
               tax: TaxTreatment) -> list[Conflict]:
    """Checks run before delivery, because a document that contradicts itself is worse
    than one that is merely incomplete."""
    found: list[Conflict] = []

    if profile.tiered_economics and tax == "s_corp":
        found.append(Conflict(
            between="S-corporation election and tiered economics",
            problem="An S corporation may have only one class of stock. A preferred return, a "
                    "promote, or any split other than straight pro rata is a second class and "
                    "terminates the election.",
            resolve="Keep partnership treatment, or drop the tiered economics. They cannot both "
                    "stand."))

    if control.deadlock_ladder and control.approval_rule == "majority_with_minority_veto":
        found.append(Conflict(
            between="Deadlock ladder and majority control",
            problem="One party can already carry a reserved matter, so the ladder never breaks "
                    "a tie — it only gives the other side a route to force a buy-out over a "
                    "decision they lost fairly.",
            resolve="Remove the ladder, or narrow it to the enumerated matters where the "
                    "minority genuinely holds a veto."))

    if control.buy_sell == "shotgun" and profile.has_passive_capital:
        found.append(Conflict(
            between="Shotgun buy-sell and passive investors",
            problem="A shotgun assumes both sides can fund the purchase. A passive investor "
                    "usually cannot, which turns a fair-price mechanism into an option held by "
                    "whoever has the cash.",
            resolve="Use appraisal-based valuation, or cap the shotgun to the active principals "
                    "only."))

    if (control.management_model == "manager_managed"
            and control.approval_rule == "unanimous"
            and len(control.reserved_matters) > 12):
        found.append(Conflict(
            between="Manager management and a long unanimous list",
            problem="Naming a manager and then requiring unanimity across a wide list means the "
                    "manager cannot actually manage, and every routine decision returns to the "
                    "members.",
            resolve="Either shorten the reserved list to genuine capital and control events, or "
                    "raise the ordinary-course threshold."))

    if profile.total_members >= 3 and control.approval_rule == "unanimous":
        found.append(Conflict(
            between="Unanimity and three or more members",
            problem="Unanimity across three or more owners means every one of them holds a veto "
                    "over every reserved matter. That is rarely what anyone intends when they "
                    "agree to 'we all have to agree'.",
            resolve="Move to a supermajority of units, with a short protective list that still "
                    "requires everyone."))

    if profile.capital_source in {"private_placement", "institutional"}:
        found.append(Conflict(
            between="Outside capital and the equity itself",
            problem="Selling an interest in a member-managed venture to a passive investor is "
                    "an offer of a security. The structure above assumes an exemption that no "
                    "one has confirmed.",
            resolve="Securities counsel confirms the exemption, the accreditation standard, and "
                    "the disclosure package before any interest is offered."))

    return found


def _open_questions(profile: VentureProfile) -> list[OpenQuestion]:
    questions = [
        OpenQuestion(
            question="What are the actual capital contributions, in dollars, and are they equal?",
            why_it_matters="Percentage interests, capital accounts, the dilution formula, and "
                           "every distribution follow from these numbers.",
            blocks="Schedule A, and any operating agreement that references it."),
        OpenQuestion(
            question="Is anyone contributing services or property rather than cash, and at what "
                     "agreed value?",
            why_it_matters="A services contribution is taxable to the contributor on receipt "
                           "unless it is structured as a profits interest.",
            blocks="Capital accounts and the tax section."),
        OpenQuestion(
            question="Who is the registered agent, and what is the principal office?",
            why_it_matters="Both go in the formation filing and the notice provision.",
            blocks="Formation, and the notices clause."),
    ]
    if profile.operators_take_compensation:
        questions.append(OpenQuestion(
            question="Are the operators taking a salary, a guaranteed payment, or only "
                     "distributions?",
            why_it_matters="It changes self-employment tax, the value of an S election, and "
                           "whether a non-working owner is being paid twice.",
            blocks="The compensation section, and the tax-treatment recommendation."))
    if profile.expected_hold_years is None:
        questions.append(OpenQuestion(
            question="How long do the owners expect to hold this?",
            why_it_matters="A three-year hold and a generational hold call for different "
                           "transfer rules, different exit rights, and a different answer on "
                           "whether a drag-along belongs at all.",
            blocks="Transfer and exit architecture."))
    if profile.initial_capital <= 0:
        questions.append(OpenQuestion(
            question="What is the ordinary-course spending threshold, or the initial capital "
                     "to derive one from?",
            why_it_matters="With no initial capital stated, the recommended threshold is a "
                           "synthetic placeholder, not a number tested against this venture's "
                           "own spending -- the hinge of the whole governance design should "
                           "not be invented.",
            blocks="The ordinary-course authority recommendation, and every reserved-matter "
                   "and Major Decision clause that cites the threshold."))
    outside = [state for state in profile.states_of_operation if state != profile.home_state]
    if outside:
        questions.append(OpenQuestion(
            question=f"Will the company do business in {', '.join(outside)} "
                     "in a way that requires foreign qualification?",
            why_it_matters="Operating unqualified can bar the company from its own courts and "
                           "accrue penalties from the first day of activity.",
            blocks="Formation state, and the filing schedule."))
    if profile.is_regulated:
        questions.append(OpenQuestion(
            question=f"What does the {profile.regulated_regime} regime require of owners — "
                     "residency, background checks, disclosure thresholds, prior approval of "
                     "transfers?",
            why_it_matters="These constrain who may hold an interest at all, and they override "
                           "anything the agreement says.",
            blocks="The cap table, the transfer provisions, and the licence-holding entity."))
    if (sector := profile.sector) is not None:
        questions += [OpenQuestion(question=q, why_it_matters=why, blocks=blocks)
                      for q, why, blocks in sector.open_questions]
    if (regime := regime_for(profile.regulated_regime)) is not None:
        questions += [OpenQuestion(question=q, why_it_matters=why, blocks=blocks)
                      for q, why, blocks in regime.open_questions]
    if profile.role == "both":
        questions.append(OpenQuestion(
            question="Has the counterparty consented in writing to Tessera acting as both "
                     "advisor and owner?",
            why_it_matters="Consent obtained after terms are agreed is worth much less than "
                           "consent obtained before, and its absence is arguable against "
                           "every term Tessera recommended.",
            blocks="The engagement letter, and any term negotiated on Tessera's behalf."))
    return questions


# --- the options menu -------------------------------------------------------

# Rough, deliberately round. The point is not the number, it is that the founder
# sees a second entity has a price and can weigh it against what it buys.
_ANNUAL_COST_PER_ENTITY = 800


def _minimal_option(profile: VentureProfile) -> StructureOption:
    """The cheapest thing that could work, stated honestly including its exposure."""
    return StructureOption(
        name="Single entity",
        summary="One limited liability company holding everything.",
        layers=[EntityLayer(
            name=f"{_base_name(profile.venture)} LLC",
            role="Sole entity",
            entity_form=_form(profile.home_state),
            holds="The whole business — assets, contracts, employees, and any licence",
            why="One filing, one bank account, one tax return, one set of minutes.",
            basis="scaffold")],
        protects=["The owners personally, against ordinary business liability"],
        costs=[
            ("Every asset is reachable by every claim — an operating judgment reaches the "
             "real estate, the licence, and the intellectual property alike"),
            ("A single asset cannot be sold, refinanced, or partnered on without the whole "
             "company coming with it"),
            "A new investor buys into everything rather than into one thing",
        ],
        choose_when="The business has one line, no outside capital, no real property, no "
                    "licence, and nothing intangible worth ring-fencing — and it is expected "
                    "to stay that way for the hold period.")


def _separated_option(profile: VentureProfile, layers: list[EntityLayer]) -> StructureOption:
    """The recommended structure, described in terms of what it buys."""
    roles = [layer.role for layer in layers]
    protects = ["Ownership and control sit above the entity that carries the liability"]
    if "Property-owning entity" in roles:
        protects.append("Each property is isolated from every other and from operations")
    if {"IP holding entity", "Rights and library entity",
            "Brand and recipe entity"} & set(roles):
        protects.append("The brand, library, and frameworks survive an operating failure")
    if "Licence holder" in roles:
        protects.append("A regulatory action against the licence does not reach the assets")
    if any(role.startswith("Production") for role in roles):
        protects.append("Each picture is financed and sued on its own")
    if "Location operating entity" in roles:
        protects.append("A failing location does not reach the brand or the other locations")
    if "Equipment and vehicle entity" in roles:
        protects.append("A catastrophic auto claim does not reach contracts and receivables")
    protects.append("A new investor or a new line is admitted without reopening existing paper")

    count = len(layers)
    return StructureOption(
        name=("HoldCo and OpCo" if count == 2 else f"HoldCo with {count - 1} entities beneath"),
        summary=f"{count} entities: " + ", ".join(
            f"{layer.name} ({layer.role})" for layer in layers[:4])
            + (", and more" if count > 4 else ""),
        layers=layers,
        protects=protects,
        costs=[
            (f"{count} formations, {count} registered agents, and roughly "
             f"${count * _ANNUAL_COST_PER_ENTITY:,} a year in filings and agent fees before "
             "any accounting"),
            ("Separate books, separate bank accounts, and intercompany agreements that have "
             "to be real — a structure ignored in practice is pierced in litigation"),
            "More moving parts for a lender or a buyer to diligence",
        ],
        choose_when="There is more than one thing worth protecting from the others, or "
                    "outside capital is coming in, or the plan involves adding assets, "
                    "locations, or partners over time.",
        recommended=True)


def _intermediate_option(profile: VentureProfile,
                         layers: list[EntityLayer]) -> StructureOption | None:
    """A middle path: one HoldCo, one operating entity, and nothing else yet.

    Offered where the recommended chart has three or more entities, because the
    honest question is usually not "one or many" but "how much separation is
    worth paying for on day one".
    """
    if len(layers) < 3:
        return None
    holdco = layers[0]
    operating = next((layer for layer in layers[1:]
                      if layer.role in {"OpCo", "Location operating entity",
                                        "Production vehicle", "Property-owning entity"}),
                     layers[1])
    trimmed = [holdco, EntityLayer(
        name=f"{_base_name(profile.venture)} Operations LLC",
        role="Single operating entity",
        entity_form=_form(profile.home_state),
        owned_by=holdco.name,
        holds="Everything the recommended structure would have split — operations, "
              "property, licences, and intangibles",
        why="One layer of separation between the owners' equity and the business's "
            "liability, without paying for separation between the business's own parts.",
        basis="scaffold")]
    del operating
    return StructureOption(
        name="HoldCo with a single operating entity",
        summary="Two entities: ownership above, everything operational below.",
        layers=trimmed,
        protects=[
            "Ownership and control sit above the liability",
            "A new investor is admitted at the HoldCo without touching operating paper",
        ],
        costs=[
            ("The operating entity's assets remain reachable by each other — the property, "
             "the licence, and the intangibles all sit in the same box"),
            ("Splitting them later means retitling assets, re-consenting lenders, and in a "
             "licensed business a fresh regulatory approval"),
        ],
        choose_when="Capital is tight now and the assets worth separating are not yet "
                    "acquired. Revisit before the second property, the second location, or "
                    "the first outside dollar.")


def _options(profile: VentureProfile, layers: list[EntityLayer]) -> list[StructureOption]:
    """Two or three viable structures, with the default named.

    A single answer, however good, forecloses the conversation. Tessera's own
    approach is to preserve optionality, so the engine shows what it rejected.
    """
    recommended = _separated_option(profile, layers)
    if len(layers) == 1:
        only = StructureOption(
            name="Single entity", summary="One limited liability company holding everything.",
            layers=layers,
            protects=["The owners personally, against ordinary business liability"],
            costs=[("Every asset is reachable by every claim, should the business acquire "
                    "assets worth separating")],
            choose_when="Nothing in this venture yet earns a second filing fee.",
            recommended=True)
        return [only]
    options = [recommended]
    if (middle := _intermediate_option(profile, layers)) is not None:
        options.append(middle)
    options.append(_minimal_option(profile))
    return options


# --- capital architecture ---------------------------------------------------

def _capital_architecture(profile: VentureProfile) -> CapitalArchitecture:
    """The order money leaves the deal, and who is protected at each step.

    A qualified finance reviewer builds the model. This is the frame the model fits inside: get
    the order of payment and the protections wrong and no amount of modelling
    fixes it, because they are governance terms wearing financial clothing.
    """
    if not (profile.tiered_economics or profile.has_passive_capital):
        return CapitalArchitecture(
            applies=False,
            why_not="Straight pro rata economics with no outside capital. A waterfall here "
                    "would be machinery with nothing to do — distributions follow percentage "
                    "interests, and the tax distribution is the only mandatory step.")

    sponsor_led = profile.role in {"principal", "both"} or profile.capital_source in {
        "private_placement", "institutional"}
    tiers = [
        WaterfallTier(
            order=1, name="Return of capital",
            what_happens="Distributable cash first returns unreturned capital contributions.",
            to_investors="All distributable cash until contributed capital is returned in full",
            to_sponsor="Pro rata on any capital the sponsor itself contributed"),
        WaterfallTier(
            order=2, name="Preferred return",
            what_happens="A cumulative, non-compounding annual return on unreturned capital, "
                         "accrued from the date each contribution was funded.",
            to_investors="All distributable cash until the preferred return is paid current",
            to_sponsor="Nothing at this tier"),
        WaterfallTier(
            order=3, name="Sponsor catch-up",
            what_happens="The sponsor receives an accelerated share until it has caught up to "
                         "its promote percentage of profits distributed so far.",
            to_investors="A reduced share, or none, during the catch-up",
            to_sponsor="An accelerated share until caught up"),
        WaterfallTier(
            order=4, name="Residual split",
            what_happens="Everything after the preferred return and catch-up splits on the "
                         "agreed promote.",
            to_investors="The residual share",
            to_sponsor="The promote"),
    ]
    if not sponsor_led:
        tiers = [tier for tier in tiers if tier.name != "Sponsor catch-up"]
        for index, tier in enumerate(tiers, start=1):
            tier.order = index

    return CapitalArchitecture(
        applies=True,
        preferred_return="A cumulative, non-compounding annual preferred return on "
                         "unreturned capital, accruing from funding.",
        promote="A share of residual distributions to the sponsor after capital and the "
                "preferred return are satisfied.",
        tiers=tiers,
        clawback=sponsor_led,
        sponsor_protective=[
            "The promote survives a removal of the sponsor other than for cause",
            ("Capital contributed by the sponsor participates in the same tiers as investor "
             "capital, rather than being subordinated by silence"),
            "The sponsor may fund a shortfall as a loan rather than being forced to dilute",
            ("Fees payable to the sponsor are stated, capped, and separate from the promote — "
             "so a fee dispute is not a promote dispute"),
        ],
        investor_protective=[
            "Preferred return is cumulative, so a lean year accrues rather than disappears",
            ("A clawback, so the sponsor cannot keep a promote paid on early distributions "
             "that the deal as a whole never earned"),
            "Distributions outside the stated waterfall are a reserved matter",
            ("The sponsor may be removed for cause without losing the investors' capital "
             "position"),
            "Reporting on a stated cadence, with the right to inspect the books behind it",
        ],
        open_points=[
            ("The preferred return rate, and whether it compounds — compounding changes the "
             "sponsor's outcome far more than the headline rate does"),
            "The promote percentage, and whether it steps up at stated return hurdles",
            ("Whether the catch-up is full or partial, which is where most of the negotiation "
             "actually sits"),
            ("Whether the waterfall runs deal-by-deal or across the whole fund, which decides "
             "whether a clawback is ever needed"),
            ("Which fees the sponsor takes — acquisition, asset management, disposition — and "
             "whether any of them credit against the promote"),
        ],
    )


# --- glossary ---------------------------------------------------------------

# Taken from Tessera's own plain-English glossary, so the memo speaks in the
# words the firm already uses publicly rather than inventing a second register.
_GLOSSARY: dict[str, str] = {
    "Equity": "Ownership in the company. The more of the equity you own, the more of the "
              "business you own.",
    "Dilution": "When your slice of ownership gets smaller because new shares were handed "
                "out, usually to bring in investors. The pie grew, but your piece is now a "
                "smaller share of it.",
    "Cap table": "A simple chart of who owns what. It lists every owner and how much of the "
                 "company they hold.",
    "HoldCo / OpCo": "A two-layer setup: the holding company owns things (the brand, the "
                     "real estate, the equity), and the operating company runs the "
                     "day-to-day. It keeps your valuable assets protected and separate from "
                     "the riskier daily operations.",
    "Operating agreement": "The rulebook for an LLC. It spells out who owns what, who makes "
                           "decisions, how money is split, and what happens if someone "
                           "leaves.",
    "Capital stack": "All the different sources of money funding a project, stacked by who "
                     "gets paid back first. Think of it as the order of the line at payout "
                     "time.",
    "Preferred return": "A promise that investors get paid back a set return first, before "
                        "profits are split with everyone else. It's the 'you get yours "
                        "before I get mine' layer.",
    "Waterfall": "The agreed order in which money flows out of a deal — who gets paid, how "
                 "much, and in what sequence as profits come in.",
    "Promote": "The sponsor's extra share of profits, earned only after the investors have "
               "received their capital back and their preferred return.",
    "Reserved matters": "The list of decisions that cannot be made without your agreement. "
                        "Control is this list, not the percentage on the cap table.",
    "Ordinary course threshold": "A dollar line. Below it, one partner can act alone. Above "
                                 "it, everyone has to agree.",
    "Deadlock": "When owners who need to agree cannot, and no one can carry the decision. "
                "The agreement should say what happens next, in steps.",
    "Buy-sell": "The mechanism for one owner to buy the other out. A shotgun means one names "
                "a price and the other chooses whether to buy or sell at it.",
    "Triggering event": "Something that gives the other owners the right to buy someone out "
                        "— death, disability, divorce, bankruptcy, or walking away.",
    "Drag-along / tag-along": "Drag lets the majority force a small holder to join a sale. "
                              "Tag lets a small holder join a sale the majority is making, "
                              "on the same terms.",
    "Clawback": "A promise that if the sponsor was paid a promote early and the deal as a "
                "whole never earned it, the money comes back.",
    "Special purpose entity (SPV)": "A company formed to hold exactly one thing — one "
                                    "property, one picture, one location — so its risks stay "
                                    "with it.",
}

_ALWAYS_GLOSS = ("Equity", "Cap table", "Operating agreement", "Reserved matters",
                 "Ordinary course threshold", "Triggering event")


def _glossary(profile: VentureProfile, rec_areas: set[str],
              capital: CapitalArchitecture, layers: list[EntityLayer]) -> list[GlossaryEntry]:
    """Only the words this memo actually uses.

    A glossary of terms the reader did not encounter is padding; a memo that uses
    "promote" without ever saying what it is asks the founder to nod along.
    """
    wanted = set(_ALWAYS_GLOSS)
    if len(layers) > 1:
        wanted |= {"HoldCo / OpCo", "Special purpose entity (SPV)"}
    if "Deadlock" in rec_areas:
        wanted |= {"Deadlock", "Buy-sell"}
    if "Tag-along and drag-along" in rec_areas:
        wanted.add("Drag-along / tag-along")
    if capital.applies:
        wanted |= {"Capital stack", "Preferred return", "Waterfall", "Promote", "Dilution"}
        if capital.clawback:
            wanted.add("Clawback")
    if profile.expects_additional_capital:
        wanted.add("Dilution")
    return [GlossaryEntry(term=term, plain=_GLOSSARY[term])
            for term in _GLOSSARY if term in wanted]


def _apply_adoptions(recommendations: list[Recommendation],
                     ledger: AdoptionLedger) -> list[Recommendation]:
    """Upgrade positions the partners have signed.

    The upgrade is data-driven and reversible: delete the ledger entry and the
    position drops back to a starting point on the next run. Nothing in code
    ever asserts adoption on its own.
    """
    upgraded = []
    for item in recommendations:
        entry = ledger.for_area(item.area)
        if entry is not None:
            item = item.model_copy(update={"basis": "tessera_adopted",
                                           "adoption": entry})
        upgraded.append(item)
    return upgraded


def _apply_confirmation(number: DerivedNumber,
                        confirmed: DerivedNumberConfirmation | None) -> DerivedNumber:
    """Override a computed proposal with a person's confirmed figure.

    Confirming is allowed to replace the proposed value, not just accept it --
    the derivation text itself says "confirm or replace". Once a number is
    ``stated`` here it stays that way; a later run of the engine (a changed
    profile, say) does not silently un-confirm it.
    """
    if confirmed is None or number.state == "stated":
        return number
    return DerivedNumber(label=number.label, value=confirmed.value, state="stated",
                         derivation=number.derivation, confirmed_by=confirmed.confirmed_by,
                         confirmed_at=confirmed.confirmed_at)


def recommend_structure(profile: VentureProfile,
                        ledger: AdoptionLedger | None = None,
                        confirmations: dict[str, DerivedNumberConfirmation] | None = None,
                        ) -> StructureRecommendation:
    """Produce the structure for a venture, with the reasoning and the open questions.

    Deterministic: the same profile and the same adoption ledger always produce
    the same structure, so a recommendation can be reviewed, disagreed with, and
    traced back to the input that drove it. ``confirmations`` is the one
    intentional exception -- it is how a person's recorded decision (D4)
    reaches a recommendation that is otherwise computed fresh from the profile
    every time, keyed by :class:`~tessera_os.numbers.DerivedNumber` label.
    """
    ledger = ledger if ledger is not None else AdoptionLedger.load()
    confirmations = confirmations or {}
    model, mgmt_why, mgmt_basis = _management_model(profile)
    rule, threshold_percent, approval_basis = _approval_rule(profile)
    threshold_percent = _apply_confirmation(
        threshold_percent, confirmations.get(APPROVAL_THRESHOLD_LABEL))
    deadlock = _deadlock_needed(profile, rule, threshold_percent)
    buy_sell, buy_sell_why, buy_sell_basis = _buy_sell_style(profile)
    tax, tax_why, tax_basis = _tax_treatment(profile)
    threshold = _apply_confirmation(
        _ordinary_course_threshold(profile), confirmations.get(ORDINARY_COURSE_THRESHOLD_LABEL))

    control = ControlArchitecture(
        management_model=model,
        ordinary_course_threshold=threshold,
        approval_rule=rule,
        approval_threshold_percent=threshold_percent,
        reserved_matters=_reserved_matters(profile),
        deadlock_ladder=deadlock,
        deadlock_steps=list(_DEADLOCK_STEPS) if deadlock else [],
        buy_sell=buy_sell if deadlock or profile.total_members > 1 else "none",
    )
    exit_arch = _exit_architecture(profile, control.buy_sell)
    layers = _entity_layers(profile)
    recommendations = _apply_adoptions(
        _recommendations(
            profile, control, exit_arch, "llc", tax, tax_why, tax_basis,
            mgmt_why, mgmt_basis, approval_basis, buy_sell_why, buy_sell_basis),
        ledger)
    capital = _capital_architecture(profile)

    return StructureRecommendation(
        profile=profile,
        entity_form="llc",
        tax_treatment=tax,
        layers=layers,
        control=control,
        exit=exit_arch,
        recommendations=recommendations,
        failure_modes=_failure_modes(profile, control, exit_arch),
        conflicts=_conflicts(profile, control, tax),
        open_questions=_open_questions(profile),
        options=_options(profile, layers),
        capital=capital,
        glossary=_glossary(profile, {item.area for item in recommendations}, capital, layers),
        disclosure=DUAL_ROLE_DISCLOSURE if profile.role == "both" else None,
    )


# --- report -----------------------------------------------------------------

def render_structure_memo(rec: StructureRecommendation) -> str:
    """The structuring memo a founder reads and counsel works from."""
    profile = rec.profile
    out: list[str] = [f"# Structure Recommendation — {profile.venture}", ""]
    out.append("> Structural advice, not legal or tax advice. Every position below is for "
               "review by qualified counsel and a tax advisor before formation or execution.")
    out.append("")

    out.append("## What this is built for")
    out.append("")
    facts = [
        f"{profile.active_principals} active principal"
        f"{'s' if profile.active_principals != 1 else ''}"
        + (f" and {profile.passive_investors} passive investor"
           f"{'s' if profile.passive_investors != 1 else ''}"
           if profile.passive_investors else ""),
        f"{'Equal' if profile.equal_ownership else 'Unequal'} ownership",
        f"{profile.activity.replace('_', ' ').title()} in {profile.home_state}",
        f"Capital from {profile.capital_source.replace('_', ' ')}"
        + (f", ${profile.initial_capital:,.0f} initially" if profile.initial_capital else ""),
        f"Exit intent: {profile.exit_intent.replace('_', ' ')}",
    ]
    if profile.is_regulated:
        facts.append(f"Regulated: {profile.regulated_regime}")
    if profile.real_property:
        facts.append("Holds real property")
    if profile.material_ip:
        facts.append("Material intellectual property")
    if (sector := profile.sector) is not None:
        facts.append(f"Sector pattern applied: {sector.label}")
    if profile.role == "both":
        facts.append("Tessera is advising and holding equity — see the disclosure below")
    out += [f"- {fact}" for fact in facts]
    out.append("")

    if rec.disclosure:
        out.append("## Disclosure — which hat we are wearing")
        out.append("")
        out += [line for line in rec.disclosure.split("\n")]
        out.append("")

    out.append("## The structure")
    out.append("")
    for layer in rec.layers:
        out.append(f"**{layer.name}** — {layer.role}, {layer.entity_form}")
        if layer.owned_by:
            out.append(f"Owned by {layer.owned_by}.")
        out.append(f"Holds: {layer.holds}.")
        out.append(f"{layer.why}")
        out.append("")

    if len(rec.options) > 1:
        out.append("## The alternatives")
        out.append("")
        out.append("Structure is a choice, not a verdict. These are the other ways this "
                   "could be built, with what each one buys and what it costs.")
        out.append("")
        for option in rec.options:
            marker = " — **recommended**" if option.recommended else ""
            out.append(f"### {option.name}{marker}")
            out.append("")
            out.append(option.summary)
            out.append("")
            out.append("*What it protects:*")
            out += [f"- {item}" for item in option.protects]
            out.append("")
            out.append("*What it costs:*")
            out += [f"- {item}" for item in option.costs]
            out.append("")
            out.append(f"*Choose it when:* {option.choose_when}")
            out.append("")

    out.append("## Control")
    out.append("")
    out.append(f"- Management: {rec.control.management_model.replace('_', ' ')}")
    out.append(f"- Either principal may act alone up to "
               f"{rec.control.ordinary_course_threshold.render_inline(fmt=_dollars)}")
    out.append(f"- Reserved matters: {len(rec.control.reserved_matters)}, decided by "
               f"{rec.control.approval_rule.replace('_', ' ')}"
               + (f" at {rec.control.approval_threshold_percent.render_inline(fmt=_percent)}"
                  if rec.control.approval_rule != "unanimous" else ""))
    out.append(f"- Deadlock ladder: {'yes' if rec.control.deadlock_ladder else 'not applicable'}")
    out.append(f"- Buy-sell: {rec.control.buy_sell}")
    out.append("")
    out.append("### Reserved matters")
    out.append("")
    out += [f"{index}. {matter}" for index, matter in enumerate(rec.control.reserved_matters, 1)]
    out.append("")
    if rec.control.deadlock_steps:
        out.append("### Deadlock ladder")
        out.append("")
        out += [f"{index}. {step}" for index, step in enumerate(rec.control.deadlock_steps, 1)]
        out.append("")

    out += _render_figures_to_confirm(rec.derived_numbers())

    out.append("## Positions")
    out.append("")
    for item in rec.recommendations:
        out.append(f"- {item.to_line()}")
    out.append("")

    out.append("## Exit")
    out.append("")
    out.append("### Triggering events")
    out.append("")
    out += [f"{index}. {event}"
            for index, event in enumerate(rec.exit.triggering_events, 1)]
    out.append("")

    out += _render_capital(rec.capital)

    if rec.conflicts:
        out.append("## Conflicts to resolve before drafting")
        out.append("")
        for conflict in rec.conflicts:
            out.append(f"**{conflict.between}.** {conflict.problem}")
            out.append(f"> {conflict.resolve}")
            out.append("")

    out.append("## What this structure is built against")
    out.append("")
    for mode in rec.failure_modes:
        addressed = ", ".join(mode.addressed_by)
        out.append(f"**{mode.name}.** {mode.without_this}")
        out.append(f"*Addressed by: {addressed}.*")
        out.append("")

    out.append("## Open questions")
    out.append("")
    for question in rec.open_questions:
        out.append(f"**{question.question}** {question.why_it_matters}")
        out.append(f"*Blocks: {question.blocks.rstrip('.')}.*")
        out.append("")

    adopted = rec.adopted()
    if adopted:
        out.append("## Adopted Tessera positions")
        out.append("")
        out.append("These are firm positions, signed by the partners in the adoption "
                   "ledger. Sources are cited by reference; the underlying documents are "
                   "not reproduced here.")
        out.append("")
        out += [f"- **{item.area}** — {item.adoption.to_note()}" for item in adopted
                if item.adoption]
        out.append("")

    unadopted = [item.area for item in rec.unadopted()]
    unadopted += sorted({f"{layer.role} — {layer.name}"
                         for layer in rec.layers if layer.basis == "scaffold"})
    if unadopted:
        out.append("## Positions not yet adopted")
        out.append("")
        out.append("These are starting points. They are not Tessera standards and no one has "
                   "reviewed them for this jurisdiction.")
        out.append("")
        out += [f"- {area}" for area in unadopted]
        out.append("")

    if rec.glossary:
        out.append("## The words used here")
        out.append("")
        out.append("You should not need a finance degree to understand what you are paying "
                   "for. These are the terms this memo uses, in plain English.")
        out.append("")
        out.append("| Term | What it means |")
        out.append("| --- | --- |")
        out += [f"| {entry.term} | {entry.plain} |" for entry in rec.glossary]
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def _render_figures_to_confirm(numbers: list[DerivedNumber]) -> list[str]:
    """D2: a proposed number renders with the rule that produced it, in plain
    language, so a reader who disagrees can see exactly what to argue with.

    Stated numbers are omitted here -- they already render plainly, with their
    source, at every place they are used. Unresolved numbers are omitted too:
    that state is surfaced as a blocking open question (D1), not repeated
    here as a second, differently-worded gap.
    """
    proposed = [number for number in numbers if number.state == "proposed"]
    if not proposed:
        return []
    formatters = {ORDINARY_COURSE_THRESHOLD_LABEL: _dollars, APPROVAL_THRESHOLD_LABEL: _percent}
    out = ["## Figures to confirm", "",
           ("These are computed starting points, not settled terms. Confirm or replace each "
            "one before it reaches a document.")]
    out.append("")
    for number in proposed:
        fmt = formatters.get(number.label, _dollars)
        out.append(f"**{number.label.capitalize()} — proposed: {fmt(number.value)}.**")
        out.append(number.derivation)
        out.append("")
    return out


def _render_capital(capital: CapitalArchitecture) -> list[str]:
    """The waterfall as a structure, with the negotiation named."""
    out = ["## Capital architecture", ""]
    if not capital.applies:
        out += [capital.why_not or "Not applicable to this venture.", ""]
        return out
    out.append("The order money leaves the deal. This is the structural frame — the rates, "
               "the percentages, and the model that proves them are built separately.")
    out.append("")
    out.append("| # | Tier | To investors | To sponsor |")
    out.append("| --- | --- | --- | --- |")
    out += [f"| {tier.order} | **{tier.name}** — {tier.what_happens} | {tier.to_investors} "
            f"| {tier.to_sponsor} |" for tier in capital.tiers]
    out.append("")
    if capital.sponsor_protective:
        out.append("### Protects the sponsor")
        out.append("")
        out += [f"- {item}" for item in capital.sponsor_protective]
        out.append("")
    if capital.investor_protective:
        out.append("### Protects the investor")
        out.append("")
        out += [f"- {item}" for item in capital.investor_protective]
        out.append("")
    if capital.open_points:
        out.append("### Still to be set")
        out.append("")
        out += [f"- {item}" for item in capital.open_points]
        out.append("")
    return out
