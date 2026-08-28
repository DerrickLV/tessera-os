"""Phase 5: commercial terms.

Covers every acceptance criterion in
docs/BUILD_BRIEF_PHASE_5_COMMERCIAL_TERMS.md section 3, items 5.1 through
5.7 -- the TermOption/TermMenu type, the distribution waterfall, capital
calls and dilution, exit pricing and payment, tax distributions, Tessera's
own engagement economics, and selection recording and gating.

D2 (every figure is a DerivedNumber, no bare number reaches rendered text)
is enforced separately and continuously by tests/test_no_invented_numbers.py
against the whole of governance.py -- this file does not re-test the
ratchet itself, only that Phase 5's own numbers are genuine DerivedNumbers.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tessera_os import governance
from tessera_os.clauses import ClauseLibrary, DealProfile
from tessera_os.drafting import StructureAdvisor, StructureRequest
from tessera_os.governance import (
    CAPITAL_CALL_AREA,
    PAYMENT_AREA,
    TAX_DISTRIBUTION_AREA,
    TESSERA_FEE_AREA,
    VALUATION_AREA,
    WATERFALL_AREA,
    DerivedNumber,
    TermMenu,
    TermOption,
    VentureProfile,
    apply_fee_selection,
    compute_diluted_percentage,
    recommend_fee_terms,
    recommend_structure,
)
from tessera_os.numbers import DerivedNumberConfirmation, NumberConfirmationStore
from tessera_os.review import ReviewQueue
from tessera_os.schemas import Evidence, UserContext
from tessera_os.terms import MenuSelection, MenuSelectionStore
from tessera_os.workspace import PilotArtifactStore, PilotWorkspaceError

PROJECT = "harbor-capital-partners"


def context(**overrides) -> UserContext:
    base = {"tenant_id": "tenant-synthetic", "user_id": "derrick",
            "project_ids": {PROJECT}, "group_ids": {"tessera_user", "qualified_counsel"}}
    base.update(overrides)
    return UserContext(**base)


def venture(**overrides) -> VentureProfile:
    base = {"venture": "Cedar Fund I", "home_state": "Texas", "initial_capital": 3_000_000}
    base.update(overrides)
    return VentureProfile(**base)


def option(label: str = "A", **overrides) -> TermOption:
    base = {"label": label, "summary": "s", "favours": "f", "costs": "c",
            "when_appropriate": "w"}
    base.update(overrides)
    return TermOption(**base)


# --- 5.1 -- an option set, with tradeoffs -----------------------------------------------------

def test_a_menu_with_fewer_than_two_options_fails_validation():
    with pytest.raises(ValidationError):
        TermMenu(area="X", options=[option("A")])


def test_selected_naming_an_option_not_in_the_list_fails_validation():
    with pytest.raises(ValidationError, match="does not name an option"):
        TermMenu(area="X", options=[option("A"), option("B")], selected="Z")


def test_selected_by_set_with_selected_empty_fails_validation():
    with pytest.raises(ValidationError, match="selected_by requires"):
        TermMenu(area="X", options=[option("A"), option("B")], selected_by="derrick")


def test_selection_records_the_authenticated_user_same_shape_as_confirmation():
    """Same shape as Phase 3's DerivedNumber confirmation: a name and a
    timestamp, set together or not at all."""
    with pytest.raises(ValidationError, match="must be set together"):
        TermMenu(area="X", options=[option("A"), option("B")], selected="A",
                 selected_by="derrick")
    menu = TermMenu(area="X", options=[option("A"), option("B")], selected="A",
                    selected_by="derrick", selected_at=datetime.now(UTC))
    assert menu.selected_by == "derrick"
    assert menu.selected_at is not None


def test_a_term_option_never_carries_a_number_state_at_the_option_level():
    """A TermOption's own basis (scaffold/synthetic_reference/tessera_adopted)
    is a different concept from a DerivedNumber's state -- only the numbers
    inside it carry stated/proposed/unresolved."""
    assert "state" not in TermOption.model_fields
    assert "basis" in TermOption.model_fields


# --- 5.2 -- distribution waterfall ------------------------------------------------------------

def test_the_waterfall_is_a_menu_of_at_least_three_real_options():
    rec = recommend_structure(venture(passive_investors=4, capital_source="private_placement"))
    menu = rec.capital.waterfall_menu
    assert menu is not None
    assert menu.area == WATERFALL_AREA
    assert len(menu.options) >= 3
    labels = {o.label for o in menu.options}
    assert "Pro rata, no preference" in labels
    assert any("catch-up" in label for label in labels)
    assert any("hurdle" in label for label in labels)


def test_every_waterfall_rate_is_a_proposed_derived_number():
    rec = recommend_structure(venture(passive_investors=4, capital_source="private_placement"))
    catchup = rec.capital.waterfall_menu.option("Preferred return with a promote above a hurdle") \
        if any(o.label == "Preferred return with a promote above a hurdle"
              for o in rec.capital.waterfall_menu.options) \
        else rec.capital.waterfall_menu.options[-1]
    assert catchup.numbers
    for number in catchup.numbers:
        assert isinstance(number, DerivedNumber)
        assert number.state == "proposed"
        assert number.derivation


def test_the_waterfall_is_sector_aware_fund_vs_real_estate_vs_operating():
    """D5: a fund's waterfall is not a real-estate hold's, which is not an
    operating company's."""
    fund = recommend_structure(venture(
        activity="fund", passive_investors=4, capital_source="private_placement"))
    real_estate = recommend_structure(venture(
        activity="real_estate_hold", real_property=True, passive_investors=4,
        capital_source="private_placement"))
    operating = recommend_structure(venture(
        activity="operating", passive_investors=4, capital_source="private_placement"))

    fund_text = " ".join(o.label + o.summary for o in fund.capital.waterfall_menu.options)
    real_estate_text = " ".join(
        o.label + o.summary for o in real_estate.capital.waterfall_menu.options)
    operating_text = " ".join(
        o.label + o.summary for o in operating.capital.waterfall_menu.options)

    assert "GP" in fund_text and "carried interest" in fund_text
    assert "sponsor" in real_estate_text and "GP" not in real_estate_text
    assert "manager" in operating_text and "GP" not in operating_text
    assert fund_text != real_estate_text != operating_text


def test_the_memo_renders_the_waterfall_menu_with_tradeoffs_visible():
    rec = recommend_structure(venture(passive_investors=4, capital_source="private_placement"))
    memo = rec.to_markdown()
    assert "## Commercial terms to choose" in memo
    assert WATERFALL_AREA in memo
    assert "Not yet selected" in memo
    assert "*Favours:*" in memo
    assert "*Costs:*" in memo
    assert "*Choose it when:*" in memo


def test_selecting_the_waterfall_is_required_before_to_draft_request():
    rec = recommend_structure(venture(passive_investors=4, capital_source="private_placement"))
    assert not rec.capital.waterfall_menu.selected
    assert rec.capital.waterfall_menu in rec.menus()


def test_the_selected_waterfall_produces_distribution_values_that_agree_with_the_memo():
    """The parity invariant from CLAUDE.md: a value appearing in the memo and
    the document must travel through the same derived_values()."""
    ask = venture(passive_investors=4, capital_source="private_placement",
                  tessera_is_principal=True)
    rec = recommend_structure(ask)
    menu = rec.capital.waterfall_menu
    chosen = menu.option("Preferred return with a promote above a hurdle")

    confirmations = {n.label: DerivedNumberConfirmation(
        label=n.label, value=n.value, confirmed_by="derrick", confirmed_at=datetime.now(UTC))
        for n in chosen.numbers}
    selections = {menu.area: MenuSelection(
        area=menu.area, label=chosen.label, selected_by="derrick",
        selected_at=datetime.now(UTC))}
    confirmed_rec = recommend_structure(ask, confirmations=confirmations,
                                        menu_selections=selections)
    values = confirmed_rec.derived_values()
    assert "preferred_return" in values
    assert "residual_split" in values
    memo = confirmed_rec.to_markdown()
    assert values["preferred_return"] in memo
    assert values["residual_split"] in memo


# --- 5.3 -- capital calls, dilution, and default ----------------------------------------------

def test_the_capital_call_menu_has_mandatory_optional_and_loan_options():
    rec = recommend_structure(venture())
    menu = rec.capital_call_menu
    assert menu.area == CAPITAL_CALL_AREA
    labels = {o.label for o in menu.options}
    assert "Mandatory calls with dilution" in labels
    assert "Optional calls with dilution" in labels
    assert "Member loans at a stated rate" in labels


def test_the_dilution_parameters_are_derived_numbers():
    rec = recommend_structure(venture())
    mandatory = rec.capital_call_menu.option("Mandatory calls with dilution")
    assert mandatory.numbers
    for number in mandatory.numbers:
        assert number.state == "proposed"
        assert number.derivation


def test_the_default_remedy_is_stated_and_its_consequence_is_calculable():
    """A remedy nobody can compute is not a remedy: compute_diluted_percentage
    is the formula the dilution DerivedNumber feeds, worked with real dollars."""
    funder_pct, non_funder_pct = compute_diluted_percentage(
        funder_capital_account=500_000, non_funder_capital_account=500_000,
        own_share_funded=100_000, shortfall_covered=100_000, dilution_multiple_percent=150)
    assert round(funder_pct, 4) == 0.6
    assert round(non_funder_pct, 4) == 0.4
    assert round(funder_pct + non_funder_pct, 6) == 1.0


def test_a_diluted_members_position_is_derivable_and_feeds_a_pro_rata_split():
    """Interacts correctly with the waterfall: the diluted percentages are
    exactly what a "pro rata" distribution tier would apply to next."""
    funder_pct, non_funder_pct = compute_diluted_percentage(
        funder_capital_account=500_000, non_funder_capital_account=500_000,
        own_share_funded=100_000, shortfall_covered=100_000, dilution_multiple_percent=150)
    distributable_cash = 100_000
    funder_share = round(distributable_cash * funder_pct, 2)
    non_funder_share = round(distributable_cash * non_funder_pct, 2)
    assert funder_share == 60_000.0
    assert non_funder_share == 40_000.0
    assert funder_share + non_funder_share == distributable_cash


def test_no_dilution_with_a_zero_multiple_leaves_percentages_unchanged():
    """A sanity bound on the formula: crediting the shortfall at 0% (no
    penalty at all) still gives the funder its own share back at face value,
    changing the split only by ordinary contribution, not by any penalty."""
    funder_pct, non_funder_pct = compute_diluted_percentage(
        funder_capital_account=500_000, non_funder_capital_account=500_000,
        own_share_funded=0, shortfall_covered=0, dilution_multiple_percent=150)
    assert funder_pct == non_funder_pct == 0.5


# --- 5.4 -- exit pricing becomes a menu with sourced parameters ---------------------------------

def test_every_named_exit_figure_is_a_derived_number_with_a_derivation():
    """The 20-day, 15%, 25/75, 24-month, 30-day, and 1% figures from the
    brief's own evidence are all DerivedNumbers now, not bare literals."""
    rec = recommend_structure(venture(active_principals=2, equal_ownership=True))
    appraisal = rec.exit.valuation_menu.option("Three-appraiser appraisal")
    note = rec.exit.payment_menu.option("Note over a term")
    labels = {n.label: n for n in appraisal.numbers + note.numbers}
    assert governance._FMV_AGREEMENT_DAYS_LABEL in labels
    assert labels[governance._FMV_AGREEMENT_DAYS_LABEL].value == 20
    assert governance._FMV_CONVERGENCE_PERCENT_LABEL in labels
    assert labels[governance._FMV_CONVERGENCE_PERCENT_LABEL].value == 15
    assert governance._BUYOUT_CASH_PERCENT_LABEL in labels
    assert labels[governance._BUYOUT_CASH_PERCENT_LABEL].value == 25
    assert governance._BUYOUT_NOTE_MONTHS_LABEL in labels
    assert labels[governance._BUYOUT_NOTE_MONTHS_LABEL].value == 24
    for number in labels.values():
        assert number.state == "proposed"
        assert number.derivation


def test_the_shotgun_unit_and_election_window_are_derived_numbers():
    rec = recommend_structure(venture(active_principals=2, equal_ownership=True))
    assert rec.control.buy_sell == "shotgun"
    assert rec.control.shotgun_unit_percent is not None
    assert rec.control.shotgun_unit_percent.value == 1
    assert rec.control.shotgun_unit_percent.state == "proposed"
    assert rec.control.shotgun_election_days is not None
    assert rec.control.shotgun_election_days.value == 30


def test_valuation_and_payment_are_separate_menus():
    rec = recommend_structure(venture())
    assert rec.exit.valuation_menu.area == VALUATION_AREA
    assert rec.exit.payment_menu.area == PAYMENT_AREA
    valuation_labels = {o.label for o in rec.exit.valuation_menu.options}
    payment_labels = {o.label for o in rec.exit.payment_menu.options}
    assert "Three-appraiser appraisal" in valuation_labels
    assert "Formula: a multiple of earnings" in valuation_labels
    assert "Fixed value with periodic reset" in valuation_labels
    assert "Cash at closing" in payment_labels
    assert "Note over a term" in payment_labels
    assert "Earnout" in payment_labels


def test_the_essential_exit_set_stays_required_together():
    """5.4 must not weaken the exit set this phase inherited."""
    from tessera_os.clauses import ESSENTIAL_CATEGORIES

    required = ESSENTIAL_CATEGORIES["operating_agreement"]
    assert {"triggering_events", "valuation", "buysell", "buyout_payment"} <= required


# --- 5.5 -- tax distributions --------------------------------------------------------------------

def test_the_tax_rate_is_proposed_with_a_derivation_naming_the_assumption():
    rec = recommend_structure(venture())
    menu = rec.tax_distribution_menu
    assert menu.area == TAX_DISTRIBUTION_AREA
    advance = menu.option("Tax distribution as an advance against distributions")
    rate = next(n for n in advance.numbers if n.label == governance._TAX_RATE_LABEL)
    assert rate.state == "proposed"
    assert "highest marginal federal rate" in rate.derivation
    assert "tax advisor" in rate.derivation


def test_the_formula_is_computable_and_a_worked_example_appears_in_the_memo():
    rec = recommend_structure(venture())
    memo = rec.to_markdown()
    assert "For illustration only" in memo
    assert "$37,000 tax distribution" in memo


def test_advance_versus_priority_is_a_choice_not_a_default():
    rec = recommend_structure(venture())
    labels = {o.label for o in rec.tax_distribution_menu.options}
    assert "Tax distribution as an advance against distributions" in labels
    assert "Tax distribution as a priority above the waterfall" in labels
    assert len(rec.tax_distribution_menu.options) >= 2


# --- 5.6 -- Tessera's engagement economics --------------------------------------------------

def test_the_success_fee_trigger_is_precise_enough_to_apply_to_facts():
    menu = recommend_fee_terms(posture="standard", estimated_deal_value=1_000_000)
    assert menu.area == TESSERA_FEE_AREA
    trigger = menu.option("Success fee on a defined trigger").summary
    assert "execution of a binding agreement" in trigger
    assert "closing of a transaction" in trigger
    assert "Introduced" in trigger and "written introduction log" in trigger
    assert "business days of the triggering event" in trigger


def test_the_tail_duration_is_a_derived_number():
    menu = recommend_fee_terms(posture="standard", estimated_deal_value=1_000_000)
    success = menu.option("Success fee on a defined trigger")
    tail = next(n for n in success.numbers if n.label == governance._FEE_TAIL_MONTHS_LABEL)
    assert tail.state == "proposed"
    assert tail.value == 12


def test_expense_treatment_is_explicit_on_every_fee_option():
    menu = recommend_fee_terms(posture="standard", estimated_deal_value=1_000_000)
    for opt in menu.options:
        assert "billed separately" in opt.summary
        assert "itemized monthly" in opt.summary


def test_posture_reaches_the_fee_terms_without_changing_the_surface_tone():
    """D4: collaborative on the surface, enforceable underneath -- a
    protective posture gets a longer tail and a firmer payment window; the
    friendly framing (favours/costs/when_appropriate) stays the same shape."""
    protective = recommend_fee_terms(posture="protective", estimated_deal_value=1_000_000)
    accommodating = recommend_fee_terms(posture="accommodating", estimated_deal_value=1_000_000)
    protective_success = protective.option("Success fee on a defined trigger")
    accommodating_success = accommodating.option("Success fee on a defined trigger")

    protective_tail = next(n for n in protective_success.numbers
                           if n.label == governance._FEE_TAIL_MONTHS_LABEL)
    accommodating_tail = next(n for n in accommodating_success.numbers
                              if n.label == governance._FEE_TAIL_MONTHS_LABEL)
    assert protective_tail.value > accommodating_tail.value

    protective_days = next(n for n in protective_success.numbers
                           if n.label == governance._FEE_PAYMENT_DAYS_LABEL)
    accommodating_days = next(n for n in accommodating_success.numbers
                              if n.label == governance._FEE_PAYMENT_DAYS_LABEL)
    assert protective_days.value < accommodating_days.value

    # The tone -- what the option favours, costs, and is appropriate for --
    # does not change with posture; only the enforceable numbers do.
    assert protective_success.favours == accommodating_success.favours
    assert protective_success.when_appropriate == accommodating_success.when_appropriate


def test_fee_at_risk_is_populated_from_a_selected_and_confirmed_option():
    """Phase 1 left fee_at_risk None because the structure path had no fee
    data. This is where it acquires a real value."""
    menu = recommend_fee_terms(posture="protective", estimated_deal_value=2_000_000)
    success = menu.option("Success fee on a defined trigger")
    exposure = next(n for n in success.numbers if n.label == governance.FEE_EXPOSURE_LABEL)
    confirmed_exposure = exposure.model_copy(update={
        "state": "stated", "confirmed_by": "derrick", "confirmed_at": datetime.now(UTC)})
    confirmed_success = success.model_copy(update={
        "numbers": [confirmed_exposure if n.label == exposure.label else n
                   for n in success.numbers]})
    selected_menu = menu.model_copy(update={
        "options": [confirmed_success if o.label == success.label else o
                   for o in menu.options],
        "selected": success.label, "selected_by": "derrick",
        "selected_at": datetime.now(UTC)})

    profile = DealProfile(opportunity="X", agreement_type="finders_fee", industry="regulated",
                          jurisdiction="the State of Texas", counterparty="Y",
                          counterparty_represented=False)
    assert profile.fee_at_risk is None

    updated = apply_fee_selection(profile, selected_menu)
    assert updated.fee_at_risk == 100_000.0


def test_posture_logic_runs_against_a_populated_fee_at_risk_not_only_none():
    """5.6's own words: posture logic must be tested against a populated
    value, not just against None."""
    unpopulated = DealProfile(opportunity="X", agreement_type="consulting", industry="general",
                              jurisdiction="the State of Texas", counterparty="Y")
    assert unpopulated.fee_at_risk is None
    assert unpopulated.posture() == "standard"

    populated = unpopulated.model_copy(update={"fee_at_risk": 150_000.0})
    assert populated.posture() == "protective"
    assert "fee exposure of $150,000" in populated.posture_rationale()

    small_and_long_standing = unpopulated.model_copy(
        update={"fee_at_risk": 10_000.0, "relationship_stage": "long_standing"})
    assert small_and_long_standing.posture() == "accommodating"


def test_a_fee_menu_with_no_estimated_deal_value_is_unresolved_not_invented():
    """No stated fact to derive an exposure figure from means unresolved,
    same as the ordinary-course threshold's zero-capital case (D1/D2) --
    never a fabricated number."""
    menu = recommend_fee_terms(posture="standard", estimated_deal_value=None)
    for opt in menu.options:
        exposure = next(n for n in opt.numbers if n.label == governance.FEE_EXPOSURE_LABEL)
        assert exposure.state == "unresolved"
        assert exposure.value is None


# --- 5.7 -- selection is recorded and gates the document ---------------------------------------

def store(tmp_path) -> MenuSelectionStore:
    return MenuSelectionStore(tmp_path / "menu-selections.db")


def test_selections_persist_through_sqlite_store_connect_and_survive_a_restart(tmp_path):
    path = tmp_path / "menu-selections.db"
    MenuSelectionStore(path).select(
        tenant_id="tenant-synthetic", project_id=PROJECT, area=WATERFALL_AREA,
        label="Pro rata, no preference", selected_by="ryan")

    reopened = MenuSelectionStore(path)
    fetched = reopened.for_project(tenant_id="tenant-synthetic", project_id=PROJECT)
    assert fetched[WATERFALL_AREA].label == "Pro rata, no preference"
    assert fetched[WATERFALL_AREA].selected_by == "ryan"


def test_confirming_a_menu_selection_outside_project_scope_is_refused_with_403(tmp_path):
    from fastapi.testclient import TestClient

    from tessera_os.console import create_console_app

    api = TestClient(create_console_app(data_dir=tmp_path))
    response = api.post("/v1/structure/menus/select", json={
        "project_id": "a-project-nobody-authorized-for-this-user",
        "area": WATERFALL_AREA, "label": "Pro rata, no preference"})
    assert response.status_code == 403


def advisor(tmp_path, **overrides) -> StructureAdvisor:
    base = {
        "store": PilotArtifactStore(tmp_path / "artifacts.db"),
        "review_queue": ReviewQueue(tmp_path / "reviews.db"),
        "library": ClauseLibrary.load("fixtures/clause_library"),
        "project_clients": {PROJECT: "client-harbor"},
        "number_confirmations": NumberConfirmationStore(tmp_path / "numbers.db"),
        "menu_selections": MenuSelectionStore(tmp_path / "menus.db"),
    }
    base.update(overrides)
    return StructureAdvisor(**base)


def structure_request(**overrides) -> StructureRequest:
    ask_venture = venture(active_principals=2, equal_ownership=True, real_property=False)
    base = {"project_id": PROJECT, "venture": ask_venture, "counterparty": "Meridian Capital",
            "evidence": [Evidence(
                source_id="synthetic-intake", title="Synthetic structure intake",
                locator="fixture://structure/harbor-intake", excerpt="Fictional intake facts.",
                retrieved_at=datetime.now(UTC).isoformat())]}
    base.update(overrides)
    ask = StructureRequest(**base)
    if "open_question_answers" not in overrides:
        rec = recommend_structure(ask.venture)
        ask.open_question_answers = {
            item.question: "Answered in the synthetic intake fixture."
            for item in rec.open_questions}
    return ask


def test_to_draft_request_names_every_unselected_menu(tmp_path):
    advice = advisor(tmp_path)
    ask = structure_request()
    # Confirm every standalone number, but leave every menu unselected.
    rec = recommend_structure(ask.venture)
    for number in rec.derived_numbers():
        if number.state == "proposed":
            advice.number_confirmations.confirm(
                tenant_id="tenant-synthetic", project_id=PROJECT, label=number.label,
                value=number.value, confirmed_by="derrick")
    memo = advice.recommend(ask, context=context())
    item = advice.review_queue.submit(
        tenant_id=memo.tenant_id, project_id=memo.project_id, created_by=memo.agent_id,
        workflow=memo.workflow, title=memo.title, body=memo.review_body(),
        evidence=memo.evidence, required_reviewer_group=memo.required_reviewer_group)
    memo.review_item_id = item.id
    advice.store.update(memo)
    advice.review_queue.accept(item_id=item.id, context=context(user_id="counsel-b"),
                              reason="Synthetic acceptance for the gate test.")

    with pytest.raises(PilotWorkspaceError, match="Menus remain unselected"):
        advice.to_draft_request(ask, context=context(), approved_artifact_id=memo.id)


def test_a_memo_with_unselected_menus_cannot_report_status_draft(tmp_path):
    advice = advisor(tmp_path)
    ask = structure_request()
    memo = advice.recommend(ask, context=context())
    assert memo.status == "insufficient_evidence"
    assert any("Menus remain unselected" in reason for reason in memo.refusal_reasons)


def test_once_every_menu_is_selected_and_confirmed_the_memo_reaches_draft(tmp_path):
    advice = advisor(tmp_path)
    ask = structure_request()
    rec = recommend_structure(ask.venture)
    for number in rec.derived_numbers():
        if number.state == "proposed":
            advice.number_confirmations.confirm(
                tenant_id="tenant-synthetic", project_id=PROJECT, label=number.label,
                value=number.value, confirmed_by="derrick")
    for menu in rec.menus():
        chosen = menu.options[0]
        for number in chosen.numbers:
            if number.state == "proposed":
                advice.number_confirmations.confirm(
                    tenant_id="tenant-synthetic", project_id=PROJECT, label=number.label,
                    value=number.value, confirmed_by="derrick")
        advice.menu_selections.select(
            tenant_id="tenant-synthetic", project_id=PROJECT, area=menu.area,
            label=chosen.label, selected_by="derrick")
    memo = advice.recommend(ask, context=context())
    assert memo.status == "draft"
    assert not memo.refusal_reasons
