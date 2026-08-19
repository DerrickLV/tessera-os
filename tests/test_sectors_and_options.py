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

    simple = recommend_structure(venture(activity="professional_services",
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


@pytest.mark.parametrize("sector", sorted(SECTOR_PATTERNS))
def test_every_sector_pattern_is_complete(sector):
    pattern = SECTOR_PATTERNS[sector]
    assert pattern.label and pattern.unit_noun
    assert pattern.layers and pattern.reserved_matters
    assert pattern.failure_modes and pattern.open_questions and pattern.positions
    for _, _, blocks in pattern.open_questions:
        assert blocks


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
