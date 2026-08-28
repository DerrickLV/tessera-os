"""Deterministic tests for the fictional offline structure reference profile."""

import pytest

from tessera_os.governance import (
    VentureProfile,
    recommend_structure,
)


def synthetic_reference() -> VentureProfile:
    """Fictional two-owner profile used only for offline evaluation."""
    return VentureProfile(
        venture="Northstar Studio", home_state="Delaware",
        active_principals=2, passive_investors=0, equal_ownership=True,
        activity="professional_services", material_ip=True,
        capital_source="founders_only", key_person_dependency=True,
        spouses_involved=True, estate_planning_relevant=True,
        exit_intent="hold_indefinitely")


# --- deterministic reference structure -------------------------------------

def test_it_reproduces_the_synthetic_reference_structure():
    control = recommend_structure(synthetic_reference()).control
    assert control.management_model == "member_managed"
    assert control.approval_rule == "unanimous"
    # No initial capital was stated, so the threshold is unresolved (Phase 3,
    # D1) rather than a fabricated $50,000 default -- see
    # test_an_underived_threshold_is_surfaced_as_an_open_question.
    assert control.ordinary_course_threshold.state == "unresolved"
    assert control.ordinary_course_threshold.value is None
    assert control.deadlock_ladder
    assert control.buy_sell == "shotgun"


def test_the_reserved_matters_match_the_major_decisions_that_were_drafted():
    matters = " ".join(
        recommend_structure(synthetic_reference()).control.reserved_matters).lower()
    for subject in ("debt", "new interests", "material asset", "dissolving",
                    "amending", "capital call", "stated purpose", "affiliate",
                    "litigation", "tax election"):
        assert subject in matters, subject


def test_the_deadlock_ladder_keeps_the_impairment_qualifier():
    """Without it the buy-sell is a hair trigger anyone can pull after losing a vote."""
    steps = recommend_structure(synthetic_reference()).control.deadlock_steps
    assert any("materially impairs" in step for step in steps)
    assert any("mediation" in step for step in steps)


def test_positions_carry_their_provenance():
    rec = recommend_structure(synthetic_reference())
    assert rec.synthetic_references()
    areas = {item.area for item in rec.synthetic_references()}
    assert {"Ordinary-course authority", "Titles"} <= areas
    # And the ones nobody has adopted say so rather than passing as standards.
    for item in rec.unadopted():
        assert item.basis == "scaffold"


# --- when a second entity earns its filing fee ------------------------------

def test_a_simple_venture_gets_one_entity():
    rec = recommend_structure(VentureProfile(
        venture="Bellwether Consulting", home_state="Oklahoma", active_principals=2,
        activity="operating", operating_liability=False))
    assert len(rec.layers) == 1
    assert rec.layers[0].role == "Sole entity"


def test_real_property_beside_an_operating_business_is_split():
    rec = recommend_structure(VentureProfile(
        venture="Harbor Logistics", home_state="Texas", real_property=True,
        operating_liability=True, activity="operating"))
    roles = [layer.role for layer in rec.layers]
    assert "HoldCo" in roles
    assert "Property-owning entity" in roles
    assert "OpCo" in roles
    opco = next(layer for layer in rec.layers if layer.role == "OpCo")
    assert "leases it from PropCo" in opco.why


def test_each_property_gets_its_own_entity():
    rec = recommend_structure(VentureProfile(
        venture="Meridian", home_state="Oklahoma", activity="real_estate_hold",
        real_property=True, business_lines=4, operating_liability=False))
    props = [layer for layer in rec.layers if layer.role == "Property-owning entity"]
    assert len(props) == 4
    assert len({layer.name for layer in props}) == 4


def test_a_licence_is_isolated_from_the_assets():
    rec = recommend_structure(VentureProfile(
        venture="Green Valley", home_state="Oklahoma", regulated_regime="cannabis",
        activity="operating"))
    licensing = next(layer for layer in rec.layers if layer.role == "Licence holder")
    assert "nothing else of value" in licensing.holds
    matters = " ".join(rec.control.reserved_matters).lower()
    assert "licence" in matters
    assert "change of control" in matters


def test_the_entity_form_reads_correctly_before_a_vowel():
    rec = recommend_structure(VentureProfile(
        venture="Meridian", home_state="Oklahoma", real_property=True))
    forms = " ".join(layer.entity_form for layer in rec.layers)
    assert "an Oklahoma limited liability company" in forms
    assert "a Oklahoma" not in forms


def test_a_holdings_name_is_not_doubled():
    rec = recommend_structure(VentureProfile(
        venture="Northstar Holdings", home_state="Delaware", material_ip=True))
    assert not any("Holdings Holdings" in layer.name for layer in rec.layers)


# --- control ----------------------------------------------------------------

def test_passive_capital_forces_manager_management():
    """A passive member with apparent authority is a problem twice over."""
    rec = recommend_structure(VentureProfile(
        venture="Cardinal Fund I", home_state="Delaware", active_principals=2,
        passive_investors=6, capital_source="private_placement", activity="fund"))
    assert rec.control.management_model == "manager_managed"


def test_the_threshold_scales_with_the_capital_at_stake():
    small = recommend_structure(VentureProfile(
        venture="A", home_state="Texas", initial_capital=150_000))
    large = recommend_structure(VentureProfile(
        venture="B", home_state="Texas", initial_capital=8_000_000))
    assert small.control.ordinary_course_threshold.state == "proposed"
    assert small.control.ordinary_course_threshold.value >= 10_000
    assert (large.control.ordinary_course_threshold.value
            > small.control.ordinary_course_threshold.value)
    assert large.control.ordinary_course_threshold.value <= 250_000


def test_an_underived_threshold_is_surfaced_as_an_open_question():
    """No initial capital means there is no basis for a threshold at all.

    Per Phase 3 D1, it must not reach a reviewer looking like a considered
    number, and it must not reach one as a fabricated placeholder either: the
    threshold carries no value at all, and an open question means the memo
    cannot reach "draft" status, and the document cannot be produced, until a
    human resolves it.
    """
    rec = recommend_structure(VentureProfile(venture="No Capital Stated", home_state="Texas"))
    assert rec.control.ordinary_course_threshold.state == "unresolved"
    assert rec.control.ordinary_course_threshold.value is None
    questions = " ".join(q.question for q in rec.open_questions)
    assert "ordinary-course spending threshold" in questions


def test_a_stated_capital_does_not_raise_the_threshold_question():
    rec = recommend_structure(VentureProfile(
        venture="Capitalized Venture", home_state="Texas", initial_capital=500_000))
    questions = " ".join(q.question for q in rec.open_questions)
    assert "ordinary-course spending threshold" not in questions


def test_no_deadlock_ladder_where_one_party_already_has_control():
    rec = recommend_structure(VentureProfile(
        venture="Ridgeline", home_state="Texas", active_principals=2,
        equal_ownership=False))
    assert not rec.control.deadlock_ladder
    reason = next(item for item in rec.recommendations if item.area == "Deadlock")
    assert "never theirs to make" in reason.because


def test_no_deadlock_ladder_where_a_supermajority_can_be_assembled():
    """Being outvoted is not a deadlock, and it does not deserve an exit right."""
    rec = recommend_structure(VentureProfile(
        venture="Quorum", home_state="Texas", active_principals=6, equal_ownership=True))
    assert rec.control.approval_rule == "supermajority"
    assert not rec.control.deadlock_ladder


def test_a_shotgun_is_not_offered_against_a_passive_investor():
    rec = recommend_structure(VentureProfile(
        venture="Cardinal", home_state="Delaware", active_principals=2,
        passive_investors=4, capital_source="private_placement"))
    assert rec.control.buy_sell == "appraisal"


# --- exit -------------------------------------------------------------------

def test_a_divorce_trigger_appears_only_where_spouses_are_in_the_picture():
    with_spouses = recommend_structure(synthetic_reference()).exit.triggering_events
    without = recommend_structure(VentureProfile(
        venture="X", home_state="Texas", spouses_involved=False)).exit.triggering_events
    assert any("Divorce" in event for event in with_spouses)
    assert not any("Divorce" in event for event in without)


def test_estate_transfers_are_permitted_only_when_asked_for():
    rec = recommend_structure(synthetic_reference())
    transfer = next(item for item in rec.recommendations if item.area == "Transfer restrictions")
    assert "revocable estate-planning trust" in transfer.position
    assert "sole voting control" in transfer.position


def test_drag_along_appears_only_where_a_sale_is_the_plan():
    holding = recommend_structure(VentureProfile(
        venture="X", home_state="Texas", exit_intent="hold_indefinitely",
        equal_ownership=False))
    selling = recommend_structure(VentureProfile(
        venture="X", home_state="Texas", exit_intent="sale", equal_ownership=False))
    assert not holding.exit.drag_along
    assert selling.exit.drag_along


# --- conflicts --------------------------------------------------------------

def test_unanimity_across_three_or_more_owners_is_flagged():
    rec = recommend_structure(VentureProfile(
        venture="Trio", home_state="Texas", active_principals=3, equal_ownership=True))
    # Three equal owners at a 75% threshold need all three, which is unanimity by
    # another name -- so the deadlock ladder is correctly present.
    assert rec.control.deadlock_ladder


def test_an_s_election_against_tiered_economics_is_caught():
    from tessera_os.governance import _conflicts

    profile = VentureProfile(venture="X", home_state="Texas", tiered_economics=True)
    control = recommend_structure(profile).control
    found = _conflicts(profile, control, "s_corp")
    assert any("one class of stock" in item.problem for item in found)


def test_outside_capital_raises_the_securities_question():
    rec = recommend_structure(VentureProfile(
        venture="Cardinal", home_state="Delaware", capital_source="private_placement",
        passive_investors=5))
    assert any("security" in item.problem for item in rec.conflicts)


def test_a_shotgun_against_passive_money_would_be_flagged_if_selected():
    from tessera_os.governance import _conflicts

    profile = VentureProfile(venture="X", home_state="Texas", passive_investors=3)
    control = recommend_structure(profile).control
    control.buy_sell = "shotgun"
    found = _conflicts(profile, control, "partnership")
    assert any("deeper pocket" in item.problem or "cash" in item.problem for item in found)


# --- failure modes and open questions ---------------------------------------

def test_the_report_names_what_the_structure_prevents():
    names = {mode.name for mode in recommend_structure(synthetic_reference()).failure_modes}
    assert "Two people, no tiebreak" in names
    assert "Your partner's heir is your new partner" in names
    assert "Phantom income" in names


def test_a_regulated_venture_is_warned_about_the_licence():
    rec = recommend_structure(VentureProfile(
        venture="Green Valley", home_state="Oklahoma", regulated_regime="cannabis"))
    assert any("licence" in mode.name.lower() for mode in rec.failure_modes)


def test_open_questions_say_what_they_block():
    questions = recommend_structure(synthetic_reference()).open_questions
    assert questions
    assert all(question.blocks for question in questions)
    assert any("capital contributions" in question.question.lower() for question in questions)


# --- the hand-off to drafting -----------------------------------------------

def test_a_recommendation_produces_the_profile_the_document_is_built_from():
    rec = recommend_structure(synthetic_reference())
    profile = rec.to_deal_profile(counterparty="Cedar Capital LLC")
    assert profile.agreement_type == "operating_agreement"
    assert profile.entity_type == "llc"
    assert profile.tax_treatment == "partnership"
    assert profile.ownership_shape == "equal"
    assert profile.member_count == 2
    assert profile.jurisdiction == "the State of Delaware"


def test_a_regulated_venture_carries_its_regime_into_the_document():
    rec = recommend_structure(VentureProfile(
        venture="Green Valley", home_state="Oklahoma", regulated_regime="cannabis",
        tessera_is_principal=True))
    profile = rec.to_deal_profile(counterparty="Green Valley Holdings LLC")
    assert profile.industry == "regulated"
    assert profile.regulatory_regime == "cannabis"
    assert profile.posture() == "protective"


def test_the_memo_reads_as_a_document_not_a_data_dump():
    memo = recommend_structure(synthetic_reference()).to_markdown()
    for heading in ("## The structure", "## Control", "## Positions", "## Exit",
                    "## What this structure is built against", "## Open questions"):
        assert heading in memo
    assert "not legal or tax advice" in memo
    assert "{" not in memo


@pytest.mark.parametrize("state", ["Delaware", "Oklahoma", "Texas", "California"])
def test_every_state_produces_a_complete_recommendation(state):
    rec = recommend_structure(VentureProfile(
        venture="Probe", home_state=state, real_property=True, material_ip=True,
        regulated_regime="liquor", passive_investors=2, business_lines=2))
    assert rec.layers and rec.recommendations and rec.failure_modes and rec.open_questions
    assert rec.to_markdown()


def test_the_memo_does_not_double_its_own_punctuation():
    memo = recommend_structure(synthetic_reference()).to_markdown()
    assert ".." not in memo.replace("...", "")


def test_an_unadopted_entity_layer_is_listed_with_the_unadopted_positions():
    rec = recommend_structure(VentureProfile(
        venture="Harbor", home_state="Texas", real_property=True, activity="operating"))
    memo = rec.to_markdown()
    assert "## Positions not yet adopted" in memo
    assert "Property-owning entity" in memo.split("## Positions not yet adopted")[1]


def test_the_home_state_is_not_asked_about_as_a_foreign_qualification():
    rec = recommend_structure(VentureProfile(
        venture="Harbor", home_state="Texas", states_of_operation=["Texas", "Oklahoma"]))
    question = next(q for q in rec.open_questions if "foreign qualification" in q.question)
    assert "Oklahoma" in question.question
    assert "Texas" not in question.question


def test_the_recommendation_fixes_the_management_model_for_drafting():
    """The document must not be free to choose a different model than the memo."""
    rec = recommend_structure(synthetic_reference())
    profile = rec.to_deal_profile(counterparty="Cedar Capital LLC")
    assert profile.management_model == "member_managed"
    assert profile.management() == "member_managed"
