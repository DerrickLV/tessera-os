"""Entity, governance, and deal paper assemble correctly from the merged library.

Operating agreements are where Tessera's structural work lives, and they fail
differently from engagement paper: the damage comes from a missing reserved-
matters list, no transfer restriction, or a waterfall with no tax distribution --
omissions that are invisible until they matter.
"""

import pytest

from tessera_os.clauses import ClauseLibrary, DealProfile

LIBRARY = "fixtures/clause_library"


def library() -> ClauseLibrary:
    return ClauseLibrary.load(LIBRARY)


def profile(agreement_type: str, **overrides) -> DealProfile:
    base = {
        "opportunity": "Harbor Logistics HoldCo/OpCo", "agreement_type": agreement_type,
        "industry": "real_estate", "jurisdiction": "the State of Delaware",
        "counterparty": "Harbor Logistics Partners LLC", "fee_at_risk": 0,
    }
    base.update(overrides)
    return DealProfile(**base)


def selected(agreement_type: str, **overrides) -> set[str]:
    draft = library().assemble(profile(agreement_type, **overrides))
    return {item.clause.id for item in draft.selections}


def test_the_library_merges_every_file_in_the_directory():
    assert len(library().clauses) > 20


def test_operating_agreement_carries_the_governance_essentials():
    ids = selected("operating_agreement")
    for required in ("gov-purpose-powers", "gov-capital", "gov-distributions",
                     "gov-management", "gov-transfer", "gov-fiduciary-exculpation",
                     "gov-information-rights", "gov-dissolution"):
        assert required in ids, required


def test_every_agreement_has_a_governing_law_clause():
    """An operating agreement with no forum is a defect, not a style choice."""
    for agreement_type in ("consulting", "finders_fee", "operating_agreement",
                           "jv", "deal_memo"):
        assert "governing-law" in selected(agreement_type), agreement_type


def test_governing_law_sits_last_in_an_entity_document():
    draft = library().assemble(profile("operating_agreement"))
    assert draft.selections[-1].clause.id == "governing-law"


def test_engagement_clauses_stay_out_of_entity_documents():
    ids = selected("operating_agreement")
    assert "compensation" not in ids
    assert "independent-contractor" not in ids
    assert "scope-services" not in ids


def test_deal_memo_is_non_binding_and_ordered_correctly():
    draft = library().assemble(profile("deal_memo"))
    ids = [item.clause.id for item in draft.selections]
    assert "memo-non-binding" in ids
    assert ids[-1] == "governing-law"
    assert "Non-Binding" in draft.to_markdown()


def test_tessera_capital_at_risk_drives_protective_governance():
    draft = library().assemble(profile("operating_agreement", tessera_capital_at_risk=True))
    assert draft.posture == "protective"
    management = next(i for i in draft.selections if i.clause.id == "gov-management")
    assert management.variant.id == "gov-mgmt-reserved"
    # The management clause states the model and points at the synthetic authority fixture.
    authority = next(i for i in draft.selections
                     if i.clause.id == "gov-ordinary-course-authority")
    assert authority.variant.id == "synthetic-manager-authority"
    assert "Ordinary Course Threshold" in authority.variant.text
    assert "Major Decision" in authority.variant.text
    assert "approved budget" in authority.variant.text


def test_the_document_cannot_contradict_itself_about_who_runs_the_company():
    """A document that says manager-managed in one section and "either Managing
    Partner, acting alone" in the next is the exact failure this guards against."""
    lib = library()

    partners = lib.assemble(profile("operating_agreement", ownership_shape="equal",
                                    member_count=2))
    ids = {i.clause.id for i in partners.selections}
    assert "gov-management-members" in ids
    assert "gov-authority-partners" in ids
    assert "gov-management" not in ids
    assert "gov-ordinary-course-authority" not in ids
    body = partners.to_markdown()
    assert "member-managed" in body
    assert "manager-managed" not in body

    managed = lib.assemble(profile("operating_agreement",
                                   ownership_shape="majority_minority", member_count=5))
    ids = {i.clause.id for i in managed.selections}
    assert "gov-management" in ids
    assert "gov-authority-partners" not in ids
    assert "Either Managing Partner, acting alone" not in managed.to_markdown()


def test_waterfall_variant_includes_a_tax_distribution():
    """Members owing tax on income they never received is the classic failure."""
    draft = library().assemble(profile("operating_agreement", tessera_capital_at_risk=True))
    distributions = next(i for i in draft.selections if i.clause.id == "gov-distributions")
    assert "Tax Distributions" in distributions.variant.text


def test_drag_along_carries_minority_protections():
    draft = library().assemble(profile("jv", tessera_capital_at_risk=True))
    drag = next(i for i in draft.selections if i.clause.id == "gov-drag-tag")
    text = drag.variant.text
    assert "same form and amount of consideration" in text
    assert "several, not joint" in text


def test_section_numbering_is_correct_across_a_long_document():
    """Definitions take section 1, so every other clause shifts and must follow."""
    body = library().assemble(profile("operating_agreement")).to_markdown()
    assert "{n}" not in body
    assert "## 1. Definitions" in body
    assert "## 2. Purpose and Powers" in body
    assert "**2.1 Purpose.**" in body


def test_the_document_defines_the_terms_it_uses():
    """"Member" appeared 89 times with no definition before this was added."""
    draft = library().assemble(profile("operating_agreement"))
    defined = {term.term for term in draft.definitions()}
    for term in ("Member", "Units", "Manager", "Transfer", "Capital Contribution",
                 "Company", "Affiliate"):
        assert term in defined, term
    assert not draft.undefined_terms()


def test_deadlock_belongs_to_equal_ownership_and_drag_to_majority_minority():
    """A 50/50 needs a way out; a majority/minority needs a way to force a sale."""
    equal = {i.clause.id for i in library().assemble(
        profile("jv", ownership_shape="equal", member_count=2)).selections}
    assert "gov-deadlock-ladder" in equal
    assert "gov-drag-tag" not in equal

    split = {i.clause.id for i in library().assemble(
        profile("jv", ownership_shape="majority_minority", member_count=4)).selections}
    assert "gov-drag-tag" in split
    assert "gov-deadlock-ladder" not in split


def test_a_minority_position_drives_a_protective_posture():
    draft = library().assemble(profile("jv", ownership_shape="majority_minority",
                                       party_role="investor"))
    assert draft.posture == "protective"
    assert "minority position" in draft.profile.posture_rationale()


def test_open_variables_are_reported_for_entity_documents():
    draft = library().assemble(profile("operating_agreement", tessera_capital_at_risk=True))
    variables = draft.open_variables()
    assert "ordinary_course_threshold" in variables
    assert "entity_statute" in variables
    # The threshold appears in a defined term and must still be prompted for.
    assert "ordinary_course_threshold" in variables


def test_unknown_agreement_type_is_rejected():
    with pytest.raises(ValueError):
        profile("franchise_agreement")


def test_a_one_form_clause_does_not_cry_wolf_about_posture():
    """A warning that fires on clauses with no risk ladder teaches readers to skip it."""
    draft = library().assemble(profile("operating_agreement", ownership_shape="equal",
                                       member_count=2))
    for item in draft.selections:
        if item.clause.posture_neutral:
            assert not item.substituted, item.clause.id
    body = draft.to_markdown()
    assert "No protective variant exists for this clause" not in body


def test_the_member_managed_pair_uses_one_term_for_one_person():
    body = library().assemble(profile("operating_agreement", ownership_shape="equal",
                                      member_count=2)).to_markdown()
    assert "Managing Member" in body
    assert "Managing Partner" not in body
