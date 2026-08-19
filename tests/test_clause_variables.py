"""Commercial terms are declared, validated, and filled — not left as blanks.

A template with placeholders is not a deal document. These tests pin down that
every term a draft needs is declared with a type, that a bad value is refused
rather than rendered, and that a draft with an undecided term cannot be produced
at all.
"""

import pytest

from tessera_os.clauses import ClauseLibrary, DealProfile, VariableError, VariableSpec

LIBRARY = "fixtures/clause_library"


def library() -> ClauseLibrary:
    return ClauseLibrary.load(LIBRARY)


def profile(**overrides) -> DealProfile:
    base = {"opportunity": "Harbor JV", "agreement_type": "jv", "industry": "real_estate",
            "jurisdiction": "the State of Delaware", "counterparty": "Harbor Partners LLC",
            "fee_at_risk": 0, "ownership_shape": "equal", "member_count": 2,
            "tessera_capital_at_risk": True}
    base.update(overrides)
    return DealProfile(**base)


TEXT_VALUES = {
    "survival_sections": "3, 5, 7 and 9", "company_purpose": "acquiring and operating the Property",
    "manager_name": "Tessera Holdings LLC", "promote_holder": "Tessera Holdings LLC",
    "entity_statute": "the Delaware Limited Liability Company Act",
    "jurisdiction": "the State of Delaware",
}


def test_every_needed_variable_has_a_declared_specification():
    lib = library()
    draft = lib.assemble(profile())
    undeclared = [spec.name for spec in lib.variable_prompts(draft)
                  if spec.name not in lib.variables]
    assert not undeclared, f"undeclared variables: {undeclared}"


def test_specifications_carry_a_type_and_a_prompt():
    lib = library()
    for spec in lib.variable_prompts(lib.assemble(profile())):
        assert spec.label
        assert spec.kind


def test_defaults_are_posture_aware():
    """A protective deal should get a protective number without anyone typing one."""
    spec = library().variables["member_approval_threshold"]
    assert spec.default_for("protective") == "75%"
    assert spec.default_for("accommodating") == "51%"


def test_a_draft_with_an_undecided_term_cannot_be_produced():
    lib = library()
    with pytest.raises(VariableError, match="undecided"):
        lib.fill(lib.assemble(profile()), {}, use_defaults=False)


def test_a_badly_formatted_value_is_refused_not_rendered():
    lib = library()
    with pytest.raises(VariableError, match="not a valid percent"):
        lib.fill(lib.assemble(profile()), {"preferred_return": "eight percent"})


def test_a_choice_outside_the_approved_list_is_refused():
    lib = library()
    with pytest.raises(VariableError, match="must be one of"):
        lib.fill(lib.assemble(profile()), {"arbitration_provider": "a coin toss"})


def test_a_filled_draft_has_no_placeholders_left():
    lib = library()
    filled = lib.fill(lib.assemble(profile()), dict(TEXT_VALUES))
    assert "{" not in filled.markdown
    assert filled.values["preferred_return"] == "8%"
    assert filled.counsel_notes


def test_filling_preserves_the_definitions_section():
    lib = library()
    filled = lib.fill(lib.assemble(profile()), dict(TEXT_VALUES))
    assert "## 1. Definitions" in filled.markdown
    assert "“Member”" in filled.markdown
    # A definition containing a variable must be filled too.
    assert "resident in the State of Delaware" in filled.markdown


def test_money_and_days_formats_are_enforced():
    spec_money = VariableSpec(name="x", label="X", kind="money")
    assert spec_money.validate_value("$42,000") == "$42,000"
    with pytest.raises(VariableError):
        spec_money.validate_value("forty-two thousand")

    spec_days = VariableSpec(name="d", label="D", kind="days")
    assert spec_days.validate_value("30") == "30"
    with pytest.raises(VariableError):
        spec_days.validate_value("thirty")


def test_an_undeclared_variable_surfaces_rather_than_disappearing():
    """A clause referencing an unknown variable must not silently vanish."""
    lib = ClauseLibrary(library().clauses, variables={})
    prompts = lib.variable_prompts(lib.assemble(profile()))
    assert prompts
    assert all(spec.help for spec in prompts)
