"""Regenerate the checked-in Structure Manager samples from synthetic inputs only."""

from pathlib import Path

from tessera_os.agreement_docx import render_agreement_docx, render_structure_docx
from tessera_os.clauses import ClauseLibrary, Party, VariableSpec
from tessera_os.governance import VentureProfile, recommend_structure

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "fixtures" / "clause_library"


def _value(spec: VariableSpec) -> str:
    defaults = spec.defaults_by_posture
    if defaults:
        return defaults.get("protective") or next(iter(defaults.values()))
    named = {
        "company_purpose": "owning and operating fictional evaluation assets",
        "entity_statute": "the applicable synthetic entity statute placeholder",
        "jurisdiction": "the State of Texas",
        "manager_name": "Northstar Sponsor LLC",
        "promote_holder": "Northstar Sponsor LLC",
        "survival_sections": "the confidentiality and dispute sections",
        "ordinary_course_threshold": "$60,000",
    }
    if spec.name in named:
        return named[spec.name]
    if spec.kind == "money":
        return "$100,000"
    if spec.kind == "percent":
        return "50%"
    if spec.kind in {"days", "months", "years"}:
        return "30"
    if spec.kind == "date":
        return "2026-10-01"
    if spec.kind == "choice" and spec.choices:
        return spec.choices[0]
    return f"Synthetic {spec.label.lower()}"


def _write_structure(profile: VentureProfile, stem: str) -> None:
    recommendation = recommend_structure(profile)
    markdown = recommendation.to_markdown()
    (OUTPUT / f"{stem}.md").write_text(markdown)
    render_structure_docx(recommendation, OUTPUT / f"{stem}.docx")


def main() -> None:
    northstar = VentureProfile(
        venture="Northstar Housing (Synthetic)", home_state="Texas",
        active_principals=2, equal_ownership=True,
        activity="real_estate_hold", real_property=True, business_lines=2,
        initial_capital=3_000_000, expected_hold_years=5,
        spouses_involved=True, estate_planning_relevant=True,
        tessera_role="principal",
    )
    lantern = VentureProfile(
        venture="Lantern Pictures (Synthetic)", home_state="California",
        activity="film_production", business_lines=2, material_ip=True,
        initial_capital=5_000_000, expected_hold_years=3,
        capital_source="private_placement", passive_investors=8,
        tessera_role="advisor",
    )
    _write_structure(northstar, "SAMPLE_Northstar_Structure_Recommendation")
    _write_structure(lantern, "SAMPLE_Lantern_Structure_Recommendation")

    recommendation = recommend_structure(northstar)
    profile = recommendation.to_deal_profile(
        counterparty="Cedar Capital LLC (Synthetic)",
        effective_date="1 October 2026",
        parties=[
            Party(
                name="Northstar Sponsor LLC (Synthetic)", role="member",
                entity_form="a Delaware limited liability company",
                signatory_name="Avery Quinn", signatory_title="Managing Member",
                capital_contribution=1_500_000, units=1500,
            ),
            Party(
                name="Cedar Capital LLC (Synthetic)", role="member",
                entity_form="a Texas limited liability company",
                signatory_name="Jordan Rivera", signatory_title="Manager",
                capital_contribution=1_500_000, units=1500,
            ),
        ],
    )
    library = ClauseLibrary.load(OUTPUT)
    assembled = library.assemble(profile)
    supplied = {spec.name: _value(spec) for spec in library.variable_prompts(assembled)}
    supplied.update(recommendation.derived_values())
    filled = library.fill(assembled, supplied)
    stem = "SAMPLE_Northstar_Operating_Agreement"
    (OUTPUT / f"{stem}.md").write_text(filled.markdown)
    render_agreement_docx(assembled, OUTPUT / f"{stem}.docx", markdown=filled.markdown)


if __name__ == "__main__":
    main()
