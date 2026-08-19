"""The memo must not promise a position the document does not contain.

This is the regression that motivated the file. Seven clause categories —
titles, triggering events, valuation, buy-sell, buy-out payment, work product,
tax distributions — were absent from the library while the structure memo went
on recommending all seven. Coverage checks passed, because the essential set
had never been told those categories existed. A founder could read "7
triggering events give the other side the right to buy the affected interest",
sign the agreement it produced, and own no triggering-events clause at all.

The parity test below is the durable fix. The clause language was the content;
this is the control. The contract itself lives in
``StructureRecommendation.expected_clause_categories()`` so the engine, not a
test fixture, declares what its own advice requires the paper to contain.
"""

import pytest

from tessera_os.clauses import ClauseLibrary, DealProfile
from tessera_os.governance import VentureProfile, recommend_structure

LIBRARY = ClauseLibrary.load("fixtures/clause_library")


def venture(**overrides) -> VentureProfile:
    base = {"venture": "Parity Probe", "home_state": "Texas",
            "active_principals": 2, "equal_ownership": True,
            "key_person_dependency": True, "spouses_involved": True,
            "estate_planning_relevant": True}
    base.update(overrides)
    return VentureProfile(**base)


def assembled_categories(profile: VentureProfile) -> set[str]:
    draft = LIBRARY.assemble(
        recommend_structure(profile).to_deal_profile(counterparty="Counterparty LLC"))
    return {item.clause.category for item in draft.selections}


PROFILES = {
    "two equal partners": venture(),
    "majority and minority": venture(equal_ownership=False),
    "with passive capital": venture(passive_investors=4,
                                    capital_source="private_placement"),
    "regulated": venture(regulated_regime="cannabis"),
    "real property": venture(real_property=True, activity="real_estate_hold",
                             business_lines=2),
}


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_every_promised_position_is_delivered_by_the_document(name):
    """The core invariant. A promise in the memo is a section in the paper."""
    profile = PROFILES[name]
    rec = recommend_structure(profile)
    delivered = assembled_categories(profile)

    unmet = sorted(rec.expected_clause_categories() - delivered)
    assert not unmet, (
        f"{name}: the memo promises positions the document does not contain: {unmet}")


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_a_deliberate_omission_is_not_counted_as_a_broken_promise(name):
    """Where no deadlock ladder applies the memo says so. Requiring the clause
    anyway would make the engine contradict its own advice."""
    rec = recommend_structure(PROFILES[name])
    if not rec.control.deadlock_ladder:
        assert "deadlock" not in rec.expected_clause_categories()
        stated = next(i for i in rec.recommendations if i.area == "Deadlock")
        assert "No deadlock ladder" in stated.position


def test_the_exit_set_is_required_together():
    """A right to buy with no way to price or pay for it reads as complete and
    is not. Either all four are essential, or the memo should stop promising."""
    from tessera_os.clauses import ESSENTIAL_CATEGORIES

    for agreement_type in ("operating_agreement", "jv"):
        essential = ESSENTIAL_CATEGORIES[agreement_type]
        assert {"triggering_events", "valuation", "buysell",
                "buyout_payment"} <= essential, agreement_type


def test_coverage_refuses_rather_than_shipping_a_hollow_document():
    """If a category is removed from the library, assembly must fail loudly."""
    from tessera_os.clauses import ClauseCoverageError

    thinned = ClauseLibrary(
        [clause for clause in LIBRARY.clauses if clause.category != "buysell"],
        variables=LIBRARY.variables)
    profile = DealProfile(
        opportunity="Hollow", agreement_type="operating_agreement", industry="general",
        jurisdiction="the State of Texas", counterparty="Y", fee_at_risk=0,
        ownership_shape="equal", member_count=2)
    with pytest.raises(ClauseCoverageError, match="buysell"):
        thinned.assemble(profile)


def test_the_assembled_document_stays_internally_sound_with_the_exit_set():
    profile = venture()
    draft = LIBRARY.assemble(
        recommend_structure(profile).to_deal_profile(counterparty="Counterparty LLC"))
    assert not draft.broken_references()
    assert not draft.undefined_terms()


def test_every_expected_category_exists_in_the_library():
    """Guards the contract itself: a typo would silently pass the parity test."""
    known = {clause.category for clause in LIBRARY.clauses}
    expected: set[str] = set()
    for profile in PROFILES.values():
        expected |= recommend_structure(profile).expected_clause_categories()
    unknown = sorted(expected - known)
    assert not unknown, f"expected categories the library lacks: {unknown}"
