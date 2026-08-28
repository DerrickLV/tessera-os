"""Four things the engine has to do that a generic structuring tool would not.

**A menu, not a verdict.** Tessera's stated approach is to build menus of
outcomes rather than lock a client into one path. An engine returning a single
structure contradicts that however good the structure is.

**Sectors, not categories.** A film finances one picture at a time and the asset
is a copyright. A trades business lives on a licence held by a named human being.
A restaurant's second location is a different liability universe from its first.
Flattening them into "regulated" or "operating" is how a structure ends up
technically correct and practically useless.

**Capital as structure.** The waterfall is a governance term wearing financial
clothing. Get the order of payment wrong and no amount of modelling fixes it.

**Which hat.** Tessera's public position is that it says whether it is advising,
investing, or both. An engine that knows Tessera holds equity and stays silent
fails that commitment quietly, which is the worst way to fail it.
"""

import pytest

from tessera_os.governance import VentureProfile, recommend_structure
from tessera_os.sectors import REGIME_PATTERNS, SECTOR_PATTERNS, regime_for


def venture(**overrides) -> VentureProfile:
    base = {"venture": "Probe", "home_state": "Oklahoma"}
    base.update(overrides)
    return VentureProfile(**base)


# --- the options menu -------------------------------------------------------

def test_a_structure_is_offered_as_a_menu():
    rec = recommend_structure(venture(real_property=True, material_ip=True,
                                      activity="operating"))
    assert len(rec.options) >= 2
    assert sum(1 for option in rec.options if option.recommended) == 1


def test_every_option_states_what_it_buys_and_what_it_costs():
    rec = recommend_structure(venture(real_property=True, business_lines=3,
                                      activity="real_estate_hold"))
    for option in rec.options:
        assert option.protects, option.name
        assert option.costs, option.name
        assert option.choose_when


def test_the_cheap_option_is_offered_honestly_rather_than_strawmanned():
    """A menu whose alternatives are obviously wrong is not a menu."""
    rec = recommend_structure(venture(real_property=True, material_ip=True))
    single = next(option for option in rec.options if option.name == "Single entity")
    assert single.protects, "the single entity does protect something and must say so"
    assert any("filing fee" in option.choose_when or "one line" in option.choose_when
               for option in rec.options)


def test_a_middle_path_appears_only_where_there_is_one():
    """Two entities have no middle. Five do, and it is usually the real question."""
    big = recommend_structure(venture(real_property=True, business_lines=4,
                                      material_ip=True, activity="real_estate_hold"))
    assert any(option.name.startswith("HoldCo with a single") for option in big.options)

    simple = recommend_structure(venture(activity="operating",
                                         operating_liability=False))
    assert len(simple.options) == 1
    assert simple.options[0].recommended


def test_the_cost_of_separation_is_quantified_not_waved_at():
    rec = recommend_structure(venture(real_property=True, business_lines=3,
                                      activity="real_estate_hold"))
    recommended = next(option for option in rec.options if option.recommended)
    assert any("$" in cost and "year" in cost for cost in recommended.costs)


def test_the_recommended_option_matches_the_chart_the_memo_prints():
    rec = recommend_structure(venture(real_property=True, material_ip=True))
    recommended = next(option for option in rec.options if option.recommended)
    assert [layer.name for layer in recommended.layers] == [
        layer.name for layer in rec.layers]


# --- sector patterns --------------------------------------------------------

def test_film_gets_one_entity_per_picture_and_a_rights_entity():
    rec = recommend_structure(venture(
        venture="Lantern Pictures", activity="film_production", business_lines=3,
        material_ip=True))
    roles = [layer.role for layer in rec.layers]
    assert roles.count("Production vehicle") == 3
    assert "Rights and library entity" in roles
    # The rights entity IS the IP entity; emitting both is two filing fees for one job.
    assert "IP holding entity" not in roles
    # And no generic OpCo on top of per-picture vehicles.
    assert "OpCo" not in roles


def test_film_asks_about_chain_of_title_and_backend():
    rec = recommend_structure(venture(activity="film_production"))
    questions = " ".join(item.question for item in rec.open_questions).lower()
    assert "chain of title" in questions
    assert "participations" in questions
    modes = {mode.name for mode in rec.failure_modes}
    assert "Chain of title with a hole in it" in modes


def test_trades_isolates_the_licence_and_the_fleet():
    rec = recommend_structure(venture(
        venture="Redline Mechanical", activity="skilled_trades",
        regulated_regime="contractor_licensing"))
    roles = {layer.role for layer in rec.layers}
    assert "Licence and qualifier entity" in roles
    assert "Equipment and vehicle entity" in roles
    assert "Licence holder" not in roles, "the sector entity supersedes the generic one"
    modes = {mode.name for mode in rec.failure_modes}
    assert "The licence walks out with the qualifier" in modes
    assert "A truck ends the company" in modes


def test_trades_raises_worker_classification():
    rec = recommend_structure(venture(activity="skilled_trades"))
    questions = " ".join(item.question for item in rec.open_questions).lower()
    assert "1099" in questions or "classification" in questions


def test_hospitality_splits_locations_and_holds_the_brand_apart():
    rec = recommend_structure(venture(
        venture="Osteria Vine", activity="hospitality", business_lines=3,
        regulated_regime="liquor", material_ip=True))
    roles = [layer.role for layer in rec.layers]
    assert roles.count("Location operating entity") == 3
    assert "Brand and recipe entity" in roles
    assert "Liquor licence entity" in roles
    assert "IP holding entity" not in roles
    assert "Licence holder" not in roles


def test_hospitality_flags_the_personal_guarantee():
    rec = recommend_structure(venture(activity="hospitality"))
    text = " ".join(item.question for item in rec.open_questions)
    text += " ".join(mode.without_this for mode in rec.failure_modes)
    assert "personal guarantee" in text.lower()


def test_hemp_is_not_treated_as_cannabis():
    hemp = recommend_structure(venture(regulated_regime="hemp"))
    cannabis = recommend_structure(venture(regulated_regime="cannabis"))
    hemp_areas = {item.area for item in hemp.recommendations}
    cannabis_areas = {item.area for item in cannabis.recommendations}
    assert hemp_areas != cannabis_areas
    assert "Testing and documentation chain" in hemp_areas
    assert "Banking and cash" in cannabis_areas
    assert "Banking and cash" not in hemp_areas


def test_a_regime_name_is_matched_loosely():
    """A founder says "adult-use cannabis", not "cannabis"."""
    assert regime_for("adult-use cannabis") is REGIME_PATTERNS["cannabis"]
    assert regime_for("Hemp") is REGIME_PATTERNS["hemp"]
    assert regime_for(None) is None
    assert regime_for("aviation") is None


def test_a_regime_adds_reserved_matters_without_duplicating_them():
    rec = recommend_structure(venture(activity="hospitality", regulated_regime="liquor"))
    matters = rec.control.reserved_matters
    assert len(matters) == len({matter.casefold() for matter in matters})
    assert any("liquor licence" in matter.lower() for matter in matters)


@pytest.mark.parametrize("sector", sorted(set(SECTOR_PATTERNS) - {"operating"}))
def test_every_sector_pattern_is_complete(sector):
    """Phase 4, D2: a pattern that fills only `layers` is not finished, and one
    with no layers at all is not a pattern -- except `operating`, which is
    tested on its own just below for exactly why it is the one exception."""
    pattern = SECTOR_PATTERNS[sector]
    assert pattern.label and pattern.unit_noun
    assert pattern.layers and pattern.reserved_matters
    assert len(pattern.failure_modes) >= 3, sector
    assert len(pattern.open_questions) >= 3, sector
    assert pattern.positions and pattern.counsel_notes
    for _, _, blocks in pattern.open_questions:
        assert blocks


def test_operating_deliberately_carries_no_layers():
    """The one documented exception to test_every_sector_pattern_is_complete:
    `_entity_layers()` treats any sector with a pattern as needing a HoldCo
    split, and `operating` is the default for the most common, simplest
    ventures in the whole engine -- forcing an entity onto every one of them
    just because the activity now has a pattern would be exactly the padding
    Phase 4 argues against. Everything else about the pattern is real."""
    pattern = SECTOR_PATTERNS["operating"]
    assert pattern.layers == []
    assert pattern.reserved_matters
    assert len(pattern.failure_modes) >= 3
    assert len(pattern.open_questions) >= 3
    assert pattern.positions and pattern.counsel_notes


def test_counsel_notes_name_the_specialist_not_a_generic_lawyer():
    """Invariant 4: counsel notes name the specialist, not "a lawyer"."""
    for sector, pattern in SECTOR_PATTERNS.items():
        for note in pattern.counsel_notes:
            assert "a lawyer" not in note.lower(), (sector, note)


@pytest.mark.parametrize("sector", sorted(SECTOR_PATTERNS))
def test_every_sector_produces_a_readable_memo(sector):
    memo = recommend_structure(venture(activity=sector, business_lines=2)).to_markdown()
    assert "## The structure" in memo
    assert "{" not in memo


def test_sector_positions_are_never_passed_off_as_tessera_standards():
    rec = recommend_structure(venture(activity="film_production"))
    unadopted = {item.area for item in rec.unadopted()}
    assert "Production vehicles" in unadopted
    assert "Rights separation" in unadopted


# --- Phase 4: the new sector patterns ----------------------------------------

def test_real_estate_hold_separates_management_from_ownership():
    rec = recommend_structure(venture(
        venture="Harbor Point Holdings", activity="real_estate_hold", real_property=True,
        business_lines=2))
    roles = [layer.role for layer in rec.layers]
    assert "Property management entity" in roles
    assert roles.count("Property-owning entity") == 2
    modes = {mode.name for mode in rec.failure_modes}
    assert "Title held in the wrong name" in modes
    questions = " ".join(item.question for item in rec.open_questions).lower()
    assert "carve-out" in questions or "guaranty" in questions


def test_harbor_point_holdings_gets_real_estate_structuring():
    """Definition of done: the fixture venture must not silently receive no
    real-estate structuring at all (docs/BUILD_BRIEF_PHASE_4_SECTOR_COVERAGE.md
    section 1's own sharpest illustration of the gap)."""
    memo = recommend_structure(venture(
        venture="Harbor Point Holdings", activity="real_estate_hold",
        real_property=True)).to_markdown()
    assert "Property management entity" in memo
    assert "single-purpose" in memo.lower() or "spe" in memo.lower()


def test_development_isolates_construction_risk_per_project():
    rec = recommend_structure(venture(
        venture="Meridian Development", activity="development", business_lines=2,
        real_property=True))
    roles = [layer.role for layer in rec.layers]
    assert roles.count("Development entity") == 2
    modes = {mode.name for mode in rec.failure_modes}
    assert "Dissolved before the statute of repose has run" in modes
    questions = " ".join(item.question for item in rec.open_questions).lower()
    assert "statute of repose" in questions


def test_fund_gets_three_entities_for_three_purposes():
    rec = recommend_structure(venture(
        venture="Cardinal Fund I", activity="fund", passive_investors=6,
        capital_source="private_placement"))
    roles = {layer.role for layer in rec.layers}
    assert {"Fund entity", "General partner entity", "Management company"} <= roles


def test_fund_counsel_notes_are_prominent_about_securities_law():
    """D2: 'counsel notes must be prominent. Securities law governs almost
    everything here.'"""
    pattern = SECTOR_PATTERNS["fund"]
    notes = " ".join(pattern.counsel_notes).lower()
    assert "securities counsel" in notes
    positions = " ".join(position for _, position, _ in pattern.positions).lower()
    assert "without answering any of them" in positions


def test_ip_licensing_separates_holding_from_administration():
    rec = recommend_structure(venture(venture="Lantern IP", activity="ip_licensing"))
    roles = [layer.role for layer in rec.layers]
    assert "IP portfolio entity" in roles
    assert "Licensing and royalty administration entity" in roles
    # The sector's own IP entity supersedes the generic one -- one job, one entity.
    assert "IP holding entity" not in roles


def test_ip_licensing_asks_about_change_of_control_and_audit_rights():
    rec = recommend_structure(venture(activity="ip_licensing"))
    questions = " ".join(item.question for item in rec.open_questions).lower()
    assert "change of control" in questions
    assert "audit" in questions


def test_professional_services_separates_the_licensed_entity_from_the_manager():
    rec = recommend_structure(venture(venture="Meridian Health", activity="professional_services"))
    roles = [layer.role for layer in rec.layers]
    assert "Professional entity" in roles
    assert "Management services entity" in roles
    modes = {mode.name for mode in rec.failure_modes}
    assert "An owner the licensing board would not allow" in modes


def test_professional_services_flags_fee_splitting():
    rec = recommend_structure(venture(activity="professional_services"))
    text = " ".join(item.question for item in rec.open_questions).lower()
    text += " ".join(mode.without_this for mode in rec.failure_modes).lower()
    assert "fee-splitting" in text or "fee splitting" in text


def test_operating_stays_a_single_entity_but_gains_real_content():
    """4.7: operating must carry the things every operating business needs
    while staying candid that it is generic -- distinguishable from the old
    behaviour (sector is None) by its content, not by extra entities."""
    rec = recommend_structure(venture(activity="operating", operating_liability=False))
    assert len(rec.layers) == 1  # no forced HoldCo just because a pattern now exists
    modes = {mode.name for mode in rec.failure_modes}
    assert "Customer concentration nobody priced in" in modes
    questions = " ".join(item.question for item in rec.open_questions).lower()
    assert "customer or vendor" in questions


def test_operating_tells_a_misrouted_venture_where_it_belongs():
    pattern = SECTOR_PATTERNS["operating"]
    notes = " ".join(pattern.counsel_notes).lower()
    assert "re-run the recommendation" in notes


# --- Phase 4: regime coverage -------------------------------------------------

def test_a_near_miss_regime_name_still_matches_the_new_regimes():
    assert regime_for("commercial food service permit") is REGIME_PATTERNS["food_service"]
    assert regime_for("DOT transportation authority") is REGIME_PATTERNS["transportation"]
    assert regime_for("skydiving") is None


def test_an_unmatched_regime_raises_a_blocking_open_question_naming_it():
    """4.8: the same loudness rule as 4.1, for a regime instead of a sector."""
    rec = recommend_structure(venture(activity="operating", regulated_regime="aviation"))
    questions = [item.question for item in rec.open_questions]
    assert any("aviation" in q for q in questions)
    assert any("no regulatory pattern exists" in q.lower() for q in questions)


def test_a_matched_regime_raises_no_such_question():
    rec = recommend_structure(venture(activity="operating", regulated_regime="cannabis"))
    questions = [item.question for item in rec.open_questions]
    assert not any("no regulatory pattern exists" in q.lower() for q in questions)


# --- Phase 4, 4.9: sector and regime compose without duplicating -------------

def test_a_cannabis_dispensary_in_a_leased_location_gets_one_licence_entity():
    rec = recommend_structure(venture(
        venture="Green Valley Dispensary", activity="operating",
        regulated_regime="cannabis"))
    roles = [layer.role for layer in rec.layers]
    assert roles.count("Licence holder") == 1


def test_a_real_estate_venture_with_ip_gets_no_redundant_holding_entity():
    rec = recommend_structure(venture(
        venture="Harbor Point Holdings", activity="real_estate_hold", real_property=True,
        material_ip=True))
    roles = [layer.role for layer in rec.layers]
    assert roles.count("IP holding entity") == 1
    assert "IP portfolio entity" not in roles  # that role only exists under ip_licensing


@pytest.mark.parametrize("sector", sorted(SECTOR_PATTERNS))
def test_no_structure_ever_emits_two_entities_for_the_same_job(sector):
    """The specific waste `supersedes` exists to prevent: two filing fees and
    two annual reports for one purpose."""
    rec = recommend_structure(venture(
        venture="Composition Probe", activity=sector, material_ip=True,
        regulated_regime="cannabis", real_property=True, business_lines=2))
    roles = [layer.role for layer in rec.layers]
    pattern = SECTOR_PATTERNS[sector]
    ip_superseded = any(spec.supersedes == "ip" for spec in pattern.layers)
    licence_superseded = any(spec.supersedes == "licence" for spec in pattern.layers)
    if ip_superseded:
        assert "IP holding entity" not in roles, sector
    if licence_superseded:
        assert "Licence holder" not in roles, sector
    # A per_unit sector layer legitimately repeats its own role once per unit;
    # what must never happen is the *generic* IP or licence role coexisting
    # with the sector's own version of the same job.
    assert roles.count("IP holding entity") <= 1
    assert roles.count("Licence holder") <= 1


# --- capital architecture ---------------------------------------------------

def test_no_waterfall_where_there_is_nothing_to_waterfall():
    capital = recommend_structure(venture(activity="professional_services")).capital
    assert not capital.applies
    assert capital.why_not
    assert "pro rata" in capital.why_not


def test_a_sponsored_deal_gets_the_full_waterfall():
    capital = recommend_structure(venture(
        activity="real_estate_hold", real_property=True, passive_investors=6,
        capital_source="private_placement", tiered_economics=True,
        tessera_is_principal=True)).capital
    assert capital.applies
    names = [tier.name for tier in capital.tiers]
    assert names == ["Return of capital", "Preferred return", "Sponsor catch-up",
                     "Residual split"]
    assert capital.clawback


def test_a_club_deal_with_no_sponsor_skips_the_catch_up():
    capital = recommend_structure(venture(
        passive_investors=3, capital_source="friends_family")).capital
    assert capital.applies
    names = [tier.name for tier in capital.tiers]
    assert "Sponsor catch-up" not in names
    assert [tier.order for tier in capital.tiers] == list(range(1, len(names) + 1))


def test_the_waterfall_protects_both_sides_and_says_which_is_which():
    capital = recommend_structure(venture(
        passive_investors=5, capital_source="private_placement",
        tessera_is_principal=True, tiered_economics=True)).capital
    assert capital.sponsor_protective and capital.investor_protective
    assert any("clawback" in item.lower() for item in capital.investor_protective)
    assert any("promote survives" in item.lower() for item in capital.sponsor_protective)


def test_the_negotiation_is_named_rather_than_assumed_settled():
    capital = recommend_structure(venture(
        passive_investors=5, capital_source="private_placement",
        tiered_economics=True)).capital
    points = " ".join(capital.open_points).lower()
    assert "catch-up" in points
    assert "compound" in points


def test_the_waterfall_reaches_the_memo():
    memo = recommend_structure(venture(
        passive_investors=5, capital_source="private_placement",
        tiered_economics=True, tessera_is_principal=True)).to_markdown()
    assert "## Capital architecture" in memo
    assert "Preferred return" in memo
    assert "Protects the sponsor" in memo


# --- dual-role disclosure ---------------------------------------------------

def test_holding_equity_and_advising_produces_a_written_disclosure():
    rec = recommend_structure(venture(tessera_role="both"))
    assert rec.disclosure
    assert "two capacities" in rec.disclosure
    assert "independent counsel" in rec.disclosure
    assert "written consent" in rec.disclosure.lower()


def test_the_disclosure_is_a_position_a_risk_and_an_open_question():
    rec = recommend_structure(venture(tessera_role="both"))
    assert any(item.area == "Dual-role disclosure" for item in rec.recommendations)
    assert any("advisor turns out to be across the table" in mode.name
               for mode in rec.failure_modes)
    assert any("consented in writing" in item.question for item in rec.open_questions)


def test_the_older_boolean_still_means_both():
    """Profiles written before the role field existed must not lose the disclosure."""
    rec = recommend_structure(venture(tessera_is_principal=True))
    assert rec.profile.role == "both"
    assert rec.disclosure


def test_advising_alone_produces_no_disclosure():
    rec = recommend_structure(venture(tessera_role="advisor"))
    assert rec.disclosure is None
    assert not any(item.area == "Dual-role disclosure" for item in rec.recommendations)


def test_the_disclosure_leads_the_memo_rather_than_hiding_in_it():
    memo = recommend_structure(venture(tessera_role="both")).to_markdown()
    assert "## Disclosure — which hat we are wearing" in memo
    assert memo.index("## Disclosure") < memo.index("## The structure")


# --- glossary ---------------------------------------------------------------

def test_the_glossary_covers_only_words_the_memo_actually_uses():
    plain = recommend_structure(venture(activity="professional_services"))
    assert not any(entry.term == "Promote" for entry in plain.glossary)

    sponsored = recommend_structure(venture(
        passive_investors=5, capital_source="private_placement", tiered_economics=True,
        tessera_is_principal=True))
    terms = {entry.term for entry in sponsored.glossary}
    assert {"Promote", "Waterfall", "Preferred return", "Clawback"} <= terms


def test_the_glossary_always_explains_the_two_terms_that_carry_the_design():
    for profile in (venture(), venture(activity="hospitality", business_lines=2)):
        terms = {entry.term for entry in recommend_structure(profile).glossary}
        assert "Reserved matters" in terms
        assert "Ordinary course threshold" in terms


def test_the_glossary_reaches_the_memo_as_a_table():
    memo = recommend_structure(venture(real_property=True)).to_markdown()
    assert "## The words used here" in memo
    assert "| Term | What it means |" in memo


def test_a_per_unit_entity_numbers_the_unit_not_the_firm():
    rec = recommend_structure(venture(
        venture="Lantern Pictures", activity="film_production", business_lines=2))
    names = [layer.name for layer in rec.layers]
    assert "Lantern Pictures Productions 1 LLC" in names
    assert "Lantern Pictures 1 Productions LLC" not in names


def test_a_sector_rights_entity_counts_as_protecting_the_intangibles():
    rec = recommend_structure(venture(activity="film_production", material_ip=True))
    recommended = next(option for option in rec.options if option.recommended)
    assert any("library" in item for item in recommended.protects)
