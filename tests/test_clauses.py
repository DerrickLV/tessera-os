"""Clause selection must vary with the deal, and must never fail silently.

Tessera's agreements differ by scope and opportunity, so the library holds
several approved variants per clause and resolves them against a deal profile.
The risks worth pinning down are: selecting a less protective variant than the
deal warrants, dropping a required clause, and shipping a draft with an unfilled
commercial term in it.
"""

import pytest

from tessera_os.clauses import ClauseLibrary, DealProfile

LIBRARY = "fixtures/clause_library/tessera_clauses.json"


def library() -> ClauseLibrary:
    return ClauseLibrary.load(LIBRARY)


def consulting(**overrides) -> DealProfile:
    base = {
        "opportunity": "RiverBend entitlement advisory", "agreement_type": "consulting",
        "industry": "real_estate", "jurisdiction": "the State of Texas",
        "counterparty": "RiverBend Residential Holdings, LLC",
        "counterparty_represented": True, "fee_at_risk": 42_000,
        "relationship_stage": "first_engagement",
    }
    base.update(overrides)
    return DealProfile(**base)


def finders(**overrides) -> DealProfile:
    base = {
        "opportunity": "Green Valley cultivation introduction",
        "agreement_type": "finders_fee", "industry": "regulated",
        "jurisdiction": "the State of Oklahoma", "counterparty": "Green Valley Holdings LLC",
        "counterparty_represented": False, "fee_at_risk": 250_000,
    }
    base.update(overrides)
    return DealProfile(**base)


def test_regulated_industry_forces_a_protective_posture():
    assert finders().posture() == "protective"
    assert "regulated industry" in finders().posture_rationale()


def test_large_fee_or_unrepresented_counterparty_forces_protective():
    assert consulting(fee_at_risk=150_000).posture() == "protective"
    assert consulting(counterparty_represented=False).posture() == "protective"


def test_long_standing_small_engagement_relaxes_posture():
    profile = consulting(relationship_stage="long_standing", fee_at_risk=10_000)
    assert profile.posture() == "accommodating"


def test_tessera_capital_at_risk_forces_protective():
    assert consulting(tessera_capital_at_risk=True).posture() == "protective"


def test_different_deals_select_different_clauses():
    lib = library()
    consulting_ids = {item.clause.id for item in lib.assemble(consulting()).selections}
    finders_ids = {item.clause.id for item in lib.assemble(finders()).selections}
    assert "compensation" in consulting_ids
    assert "finders-fee" not in consulting_ids
    assert "finders-fee" in finders_ids
    assert "compensation" not in finders_ids


def test_regulatory_clause_appears_only_for_regulated_industries():
    lib = library()
    assert "regulatory-compliance" in {i.clause.id for i in lib.assemble(finders()).selections}
    assert "regulatory-compliance" not in {
        i.clause.id for i in lib.assemble(consulting()).selections}


def test_required_clause_is_substituted_rather_than_dropped():
    """A missing posture must never silently remove a required clause."""
    draft = library().assemble(finders())
    assert not draft.omitted_required
    contractor = next(i for i in draft.selections if i.clause.id == "independent-contractor")
    assert contractor.substituted
    assert contractor.less_protective_than_requested
    assert "LESS protective" in draft.to_markdown()


def test_liability_cap_is_always_present():
    """The single most consequential omission in any Tessera agreement."""
    lib = library()
    for profile in (consulting(), finders(), consulting(agreement_type="advisory")):
        ids = {item.clause.id for item in lib.assemble(profile).selections}
        assert "limitation-liability" in ids, profile.agreement_type


def test_section_numbering_matches_assembled_order():
    draft = library().assemble(finders())
    body = draft.to_markdown()
    # The second clause must number its subsections 2.x, not carry a hardcoded number.
    assert "## 2. Fee and Fee Protection" in body
    assert "**2.1 Introduction.**" in body
    assert "{n}" not in body


def test_open_variables_are_surfaced():
    draft = library().assemble(finders())
    assert "fee_percentage" in draft.open_variables()
    assert "Terms still to be filled in" in draft.to_markdown()


def test_every_variant_carries_a_counsel_note():
    for clause in library().clauses:
        for variant in clause.variants:
            assert variant.counsel_review.strip(), f"{clause.id}/{variant.id}"


def test_draft_is_marked_for_counsel_review():
    body = library().assemble(consulting()).to_markdown()
    assert "QUALIFIED COUNSEL REVIEW BEFORE EXECUTION" in body
    assert "not legal advice" in body


def test_review_positions_expose_the_full_approved_band():
    """Review mode needs every variant, not just the selected one."""
    positions = library().review_positions(consulting())
    assert len(positions["liability"]) >= 2


def test_duplicate_posture_in_a_clause_is_rejected():
    from tessera_os.clauses import Clause
    with pytest.raises(ValueError, match="duplicate postures"):
        Clause(id="x", category="c", title="T", order=1, applies_to=["nda"],
               absence_risk="r", variants=[
                   {"id": "a", "posture": "standard", "text": "t", "when": "w",
                    "counsel_review": "c"},
                   {"id": "b", "posture": "standard", "text": "t", "when": "w",
                    "counsel_review": "c"}])
