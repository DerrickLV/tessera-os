"""Phase 6, work item 6.1: the adoption ledger's missing scope dimension.

Before this item, an ``AdoptedPosition`` recorded who signed it, when, and
where it came from -- but nothing about where it applies. A position drawn
from Tessera's own executed operating agreement, once adopted, would be cited
identically in a memo for a passive capital vehicle, a regulated cannabis
operator, and a founder-run service business. ``applies_to`` closes that gap:
a position governs only the policy profiles it names, defaulting to the
narrowest claim, and ``policy_profile_for`` classifies a venture into one of
those profiles from facts intake already collects -- loudly refusing to guess
where it cannot, the same rule as Phase 4.1's missing sector pattern.

This phase adopts nothing (D3): every test here works against synthetic
in-memory ledgers, never ``config/adopted_positions.yaml``.
"""

import pytest
from pydantic import ValidationError

from tessera_os.adoption import ALL_PROFILES, AdoptedPosition, AdoptionLedger, PolicyProfile
from tessera_os.governance import VentureProfile, policy_profile_for, recommend_structure


def entry(**overrides) -> dict:
    base = {"area": "Ordinary-course authority",
            "adopted_by": ["Derrick Carlisle", "Ryan Strasshofer"],
            "date": "2026-08-19",
            "source_ref": "Tesserra Holdings LLC Operating Agreement, Art. IV",
            "approval_ref": "https://github.com/DerrickLV/tessera-os/pull/42"}
    base.update(overrides)
    return base


def venture(**overrides) -> VentureProfile:
    base = {"venture": "Probe", "home_state": "Oklahoma"}
    base.update(overrides)
    return VentureProfile(**base)


# --- the scope field itself --------------------------------------------------

def test_applies_to_defaults_to_the_narrowest_claim_when_absent():
    """Every block staged for the partners is narrow by default -- see
    docs/governance/11_LEDGER_STAGING_REV2.md, which pastes entries with no
    applies_to at all."""
    position = AdoptedPosition(**entry())
    assert position.applies_to == ["tessera_core"]


def test_an_empty_applies_to_list_fails_validation():
    with pytest.raises(ValidationError):
        AdoptedPosition(**entry(applies_to=[]))


def test_a_duplicate_profile_in_applies_to_fails_validation():
    with pytest.raises(ValidationError, match="repeat"):
        AdoptedPosition(**entry(applies_to=["project_spv", "project_spv"]))


def test_an_unknown_profile_string_fails_validation_naming_the_valid_set():
    with pytest.raises(ValidationError) as excinfo:
        AdoptedPosition(**entry(applies_to=["not_a_real_profile"]))
    message = str(excinfo.value)
    for profile in ALL_PROFILES:
        assert profile in message


def test_applies_to_may_name_more_than_one_profile():
    """A list, never a single value -- a position may apply to several
    profiles at once."""
    position = AdoptedPosition(**entry(applies_to=["project_spv", "capital_vehicle"]))
    assert position.governs("project_spv")
    assert position.governs("capital_vehicle")
    assert not position.governs("founder_operating")


# --- for_area is scope-aware --------------------------------------------------

def test_for_area_requires_a_profile_and_returns_none_outside_scope():
    ledger = AdoptionLedger(positions=[AdoptedPosition(**entry(applies_to=["project_spv"]))])
    assert ledger.for_area("Ordinary-course authority", profile="project_spv") is not None
    assert ledger.for_area("Ordinary-course authority", profile="capital_vehicle") is None


def test_for_area_any_scope_finds_an_entry_for_area_does_not():
    """The mechanism that lets a caller tell "adopted, wrong scope" apart
    from "never adopted" -- both look like None from for_area alone."""
    ledger = AdoptionLedger(positions=[AdoptedPosition(**entry(applies_to=["project_spv"]))])
    assert ledger.for_area("Ordinary-course authority", profile="capital_vehicle") is None
    assert ledger.for_area_any_scope("Ordinary-course authority") is not None
    assert ledger.for_area_any_scope("Some area nobody adopted") is None


# --- the golden rule: scope narrows citation, never widens it ----------------

def test_an_out_of_scope_entry_never_upgrades_the_position():
    ledger = AdoptionLedger(
        positions=[AdoptedPosition(**entry(applies_to=["capital_vehicle"]))])
    rec = recommend_structure(venture(), ledger=ledger)  # plain facts -> founder_operating
    item = next(i for i in rec.recommendations if i.area == "Ordinary-course authority")
    assert item.basis != "tessera_adopted"
    assert item.adoption is None


def test_an_in_scope_entry_still_upgrades_the_position():
    ledger = AdoptionLedger(
        positions=[AdoptedPosition(**entry(applies_to=["founder_operating"]))])
    rec = recommend_structure(venture(), ledger=ledger)
    item = next(i for i in rec.recommendations if i.area == "Ordinary-course authority")
    assert item.basis == "tessera_adopted"
    assert item.adoption is not None


def test_no_recommendation_ever_cites_a_position_outside_its_scope():
    """Every profile against a position scoped to a different, single
    profile: never once does citation happen outside that scope."""
    scoped_to = "regulated_special"
    ledger = AdoptionLedger(
        positions=[AdoptedPosition(**entry(applies_to=[scoped_to]))])
    probes = {
        "founder_operating": venture(),
        "project_spv": venture(activity="development"),
        "capital_vehicle": venture(activity="fund"),
        "regulated_special": venture(regulated_regime="cannabis"),
    }
    for profile, probe in probes.items():
        rec = recommend_structure(probe, ledger=ledger)
        item = next(i for i in rec.recommendations if i.area == "Ordinary-course authority")
        if profile == scoped_to:
            assert item.basis == "tessera_adopted", profile
        else:
            assert item.basis != "tessera_adopted", profile


# --- "not adopted for this venture" is a different fact from "never adopted" --

def test_the_memo_distinguishes_out_of_scope_from_never_adopted():
    out_of_scope_ledger = AdoptionLedger(
        positions=[AdoptedPosition(**entry(applies_to=["capital_vehicle"]))])
    rec = recommend_structure(venture(), ledger=out_of_scope_ledger)
    scoped_item = next(i for i in rec.recommendations if i.area == "Ordinary-course authority")
    never_adopted_item = next(i for i in rec.recommendations if i.area == "Titles")

    assert scoped_item.scope_note is not None
    assert "not adopted for this venture" in scoped_item.scope_note
    assert "not adopted for this venture" in scoped_item.to_line()
    # The area with no ledger entry at all carries no such note -- distinct
    # wording for a distinct fact.
    assert never_adopted_item.scope_note is None
    assert "not adopted for this venture" not in never_adopted_item.to_line()


def test_an_empty_ledger_produces_no_scope_notes_at_all():
    rec = recommend_structure(venture(), ledger=AdoptionLedger())
    assert all(item.scope_note is None for item in rec.recommendations)


# --- the classifier ------------------------------------------------------------

def test_the_classifier_names_a_reason_alongside_every_profile_it_returns():
    profile, reason = policy_profile_for(venture())
    assert profile == "founder_operating"
    assert reason


def test_a_regulated_venture_classifies_as_regulated_special():
    profile, _ = policy_profile_for(venture(regulated_regime="cannabis"))
    assert profile == "regulated_special"


def test_a_development_or_real_estate_hold_venture_classifies_as_project_spv():
    for activity in ("development", "real_estate_hold"):
        profile, _ = policy_profile_for(venture(activity=activity))
        assert profile == "project_spv", activity


def test_a_single_asset_real_property_venture_classifies_as_project_spv():
    profile, _ = policy_profile_for(
        venture(real_property=True, business_lines=1, activity="operating"))
    assert profile == "project_spv"


def test_a_multi_asset_real_property_venture_is_not_forced_into_project_spv():
    """"With a single asset purpose" is a real qualifier, not decoration --
    real_property alone must not be sufficient."""
    profile, _ = policy_profile_for(
        venture(real_property=True, business_lines=3, activity="operating"))
    assert profile != "project_spv"


def test_a_fund_or_passive_capital_venture_classifies_as_capital_vehicle():
    fund_profile, _ = policy_profile_for(venture(activity="fund"))
    assert fund_profile == "capital_vehicle"
    passive_profile, _ = policy_profile_for(
        venture(passive_investors=3, activity="professional_services"))
    assert passive_profile == "capital_vehicle"


def test_an_ordinary_operating_venture_classifies_as_founder_operating():
    profile, _ = policy_profile_for(venture())
    assert profile == "founder_operating"


def test_every_policy_profile_is_reachable_except_tessera_core():
    """tessera_core is deliberately excluded: it is a fact stated at intake
    (this is Tessera's own entity), never a shape the classifier infers --
    D2. There is no combination of VentureProfile facts that should produce
    it, and none of the probes below does."""
    reachable_probes = {
        "regulated_special": venture(regulated_regime="cannabis"),
        "project_spv": venture(activity="development"),
        "capital_vehicle": venture(activity="fund"),
        "founder_operating": venture(),
    }
    reached = set()
    for expected, probe in reachable_probes.items():
        profile, _ = policy_profile_for(probe)
        assert profile == expected
        reached.add(profile)
    assert reached == set(ALL_PROFILES) - {"tessera_core"}


def test_the_classifier_never_returns_tessera_core():
    """Swept across every Activity, regulated or not, real property or not,
    with and without passive capital -- none of it ever infers Tessera's own
    entity. That fact can only be stated, never guessed from shape."""
    from tessera_os.governance import Activity

    activities: tuple[str, ...] = Activity.__args__
    for activity in activities:
        for real_property in (True, False):
            for passive in (0, 3):
                for regime in (None, "cannabis"):
                    profile, _ = policy_profile_for(venture(
                        activity=activity, real_property=real_property,
                        passive_investors=passive, regulated_regime=regime))
                    assert profile != "tessera_core"


def test_a_blocking_open_question_would_name_the_venture_if_the_classifier_ever_cannot_decide():
    """The classifier's own rules are exhaustive over VentureProfile today
    (see policy_profile_for's final, unconditional branch) -- there is no
    reachable input that makes it return None. The consuming code still has
    to handle that outcome correctly rather than picking a default, so this
    drives the handling directly rather than pretending a real venture
    exists that the classifier cannot place.
    """
    from tessera_os.governance import _apply_adoptions, _open_questions

    profile = venture()
    questions = _open_questions(profile, None)
    blocking = next(q for q in questions if "policy profile" in q.question)
    assert profile.venture in blocking.question
    assert "no policy profile" in blocking.why_it_matters.lower() or (
        "could not be determined" in blocking.why_it_matters.lower())

    ledger = AdoptionLedger(positions=[AdoptedPosition(**entry())])
    from tessera_os.governance import Recommendation
    recs = [Recommendation(area="Ordinary-course authority", position="x", because="y",
                           basis="scaffold")]
    upgraded = _apply_adoptions(recs, ledger, None)
    assert upgraded[0].basis == "scaffold"
    assert upgraded[0].adoption is None


def test_every_policy_profile_type_value_is_a_valid_applies_to_entry():
    """The Literal in adoption.py and the classifier in governance.py must
    stay the same set -- ALL_PROFILES is derived from the Literal itself, so
    this is really pinning that get_args did not silently return nothing."""
    assert set(ALL_PROFILES) == {
        "tessera_core", "founder_operating", "project_spv", "capital_vehicle",
        "regulated_special"}
    for profile in ALL_PROFILES:
        AdoptedPosition(**entry(applies_to=[profile]))  # must not raise


def test_policy_profile_type_hint_matches_all_profiles():
    from typing import get_args
    assert set(get_args(PolicyProfile)) == set(ALL_PROFILES)
