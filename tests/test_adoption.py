"""Adoption is a two-key, data-driven, reversible act — never a code default.

The whole provenance system rests on one promise: the engine never claims a
Tessera position that the partners have not actually signed. These tests pin
the mechanics of that promise. The ledger ships empty; a valid entry needs two
distinct partners, a date, and a citation by reference; and deleting an entry
drops the position straight back to a starting point.
"""

import pytest

from tessera_os.adoption import AdoptedPosition, AdoptionError, AdoptionLedger
from tessera_os.governance import VentureProfile, recommend_structure


def entry(**overrides) -> dict:
    base = {"area": "Ordinary-course authority",
            "adopted_by": ["Derrick Carlisle", "Ryan Strasshofer"],
            "date": "2026-08-19",
            "source_ref": "Tesserra Holdings LLC Operating Agreement, Art. IV"}
    base.update(overrides)
    return base


def venture(**overrides) -> VentureProfile:
    base = {"venture": "Probe", "home_state": "Oklahoma"}
    base.update(overrides)
    return VentureProfile(**base)


# --- the shipped state --------------------------------------------------------

def test_the_shipped_ledger_is_empty():
    """Nothing is adopted until the partners sign. This is the load-bearing default."""
    ledger = AdoptionLedger.load()
    assert ledger.positions == []


def test_a_missing_ledger_file_is_a_valid_empty_state(tmp_path):
    ledger = AdoptionLedger.load(tmp_path / "does-not-exist.yaml")
    assert ledger.positions == []
    assert ledger.for_area("anything") is None


# --- what a valid signature requires -------------------------------------------

def test_one_partner_cannot_adopt_alone():
    """Firm positions are unanimous under Tessera's own governance."""
    with pytest.raises(ValueError, match="at least 2|two distinct"):
        AdoptedPosition(**entry(adopted_by=["Derrick Carlisle"]))


def test_the_same_name_twice_is_still_one_partner():
    with pytest.raises(ValueError, match="two distinct"):
        AdoptedPosition(**entry(adopted_by=["Derrick Carlisle", "derrick carlisle"]))


def test_a_date_is_required_in_iso_form():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        AdoptedPosition(**entry(date="August 19, 2026"))


def test_a_source_reference_is_required():
    with pytest.raises(ValueError):
        AdoptedPosition(**entry(source_ref=""))


def test_a_duplicate_area_is_refused_not_last_writer_wins(tmp_path):
    path = tmp_path / "ledger.yaml"
    path.write_text(
        "positions:\n"
        "  - {area: Titles, adopted_by: [A B, C D], date: '2026-01-01', source_ref: X}\n"
        "  - {area: titles, adopted_by: [A B, C D], date: '2026-02-01', source_ref: Y}\n")
    with pytest.raises(AdoptionError, match="twice"):
        AdoptionLedger.load(path)


def test_a_malformed_ledger_fails_loudly_rather_than_partially(tmp_path):
    path = tmp_path / "ledger.yaml"
    path.write_text("positions:\n  - {area: Titles}\n")
    with pytest.raises(AdoptionError):
        AdoptionLedger.load(path)


# --- the upgrade ---------------------------------------------------------------

def signed() -> AdoptionLedger:
    return AdoptionLedger(positions=[AdoptedPosition(**entry())])


def test_a_signed_entry_upgrades_the_matching_position():
    rec = recommend_structure(venture(), ledger=signed())
    item = next(i for i in rec.recommendations if i.area == "Ordinary-course authority")
    assert item.basis == "tessera_adopted"
    assert item.adoption is not None
    assert item in rec.adopted()
    assert item not in rec.unadopted()
    assert item not in rec.synthetic_references()


def test_an_unsigned_position_is_untouched():
    rec = recommend_structure(venture(), ledger=signed())
    other = next(i for i in rec.recommendations if i.area == "Entity form")
    assert other.basis != "tessera_adopted"


def test_deleting_the_entry_reverts_the_position():
    """Adoption is reversible data, not a ratchet."""
    before = recommend_structure(venture(), ledger=signed())
    after = recommend_structure(venture(), ledger=AdoptionLedger())
    area = "Ordinary-course authority"
    assert next(i for i in before.recommendations if i.area == area).basis == (
        "tessera_adopted")
    assert next(i for i in after.recommendations if i.area == area).basis != (
        "tessera_adopted")


def test_an_empty_ledger_changes_nothing():
    plain = recommend_structure(venture(), ledger=AdoptionLedger())
    assert not plain.adopted()


# --- what the reader sees --------------------------------------------------------

def test_the_memo_shows_the_adoption_with_its_source():
    memo = recommend_structure(venture(), ledger=signed()).to_markdown()
    assert "## Adopted Tessera positions" in memo
    assert "Derrick Carlisle and Ryan Strasshofer" in memo
    assert "Tesserra Holdings LLC Operating Agreement, Art. IV" in memo


def test_the_memo_omits_the_section_when_nothing_is_adopted():
    memo = recommend_structure(venture(), ledger=AdoptionLedger()).to_markdown()
    assert "## Adopted Tessera positions" not in memo


def test_counsel_review_retires_the_confirm_line_and_unreviewed_does_not():
    reviewed = AdoptionLedger(positions=[
        AdoptedPosition(**entry(counsel_reviewed=True))])
    unreviewed = signed()
    area = "Ordinary-course authority"

    with_review = next(i for i in recommend_structure(
        venture(), ledger=reviewed).recommendations if i.area == area)
    without = next(i for i in recommend_structure(
        venture(), ledger=unreviewed).recommendations if i.area == area)

    assert "Counsel reviewed." in with_review.to_line()
    assert "Confirm:" not in with_review.to_line()
    # Adopted but not counsel-reviewed keeps the confirmation — adoption by the
    # partners is not a substitute for counsel.
    assert "Confirm:" in without.to_line()


def test_no_position_claims_adoption_without_a_ledger_entry():
    """The invariant the whole system rests on."""
    rec = recommend_structure(venture(
        activity="film_production", regulated_regime="cannabis", real_property=True,
        passive_investors=3, tiered_economics=True), ledger=AdoptionLedger())
    assert all(item.basis != "tessera_adopted" for item in rec.recommendations)
    assert all(item.adoption is None for item in rec.recommendations)
