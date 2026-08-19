"""The diagnosis is a screen that never overclaims.

Its three promises: a real gap is found and reported with its failure mode; a
present position is reported as detected, never as adequate; and the only
contradictions it flags are ones the text alone can prove. A screen that
guessed beyond its evidence would poison the human review it feeds.
"""

from tessera_os.clauses import ClauseLibrary, DealProfile
from tessera_os.diagnosis import diagnose_agreement

LIBRARY = ClauseLibrary.load("fixtures/clause_library")


def profile(**overrides) -> DealProfile:
    base = {"opportunity": "Inbound Review", "agreement_type": "operating_agreement",
            "industry": "general", "jurisdiction": "the State of Texas",
            "counterparty": "Existing Company LLC", "fee_at_risk": 0,
            "ownership_shape": "equal", "member_count": 2}
    base.update(overrides)
    return DealProfile(**base)


# A deliberately thin agreement: purpose, capital, distributions, governance,
# and governing law — and nothing about transfers, exits, deadlock, or buyouts.
THIN_AGREEMENT = """
OPERATING AGREEMENT OF EXISTING COMPANY LLC

1. Purpose. The purpose of the Company is to engage in any lawful business.
2. Capital. Each Member has made the Capital Contribution set forth on Exhibit A,
   in the amount of $50,000 each, and a capital account shall be maintained.
3. Management. The Company is member-managed. Decisions require the approval of
   the Members holding a majority in interest.
4. Distributions. Distributable Cash shall be distributed within thirty (30) days
   of each fiscal quarter end.
5. Governing Law. This Agreement is governed by the laws of the State of Texas.
"""

CONTRADICTORY = THIN_AGREEMENT + """
6. Manager. Notwithstanding the foregoing, the Company is manager-managed, and
   either member may act alone in the ordinary course.
7. Disputes. All disputes shall be resolved by binding arbitration. THE PARTIES
   WAIVE TRIAL BY JURY in any proceeding arising from this Agreement.
8. Consent. No Major Decision may be taken without the unanimous written consent
   of the Members.
"""


def diagnosis(text=THIN_AGREEMENT, **overrides):
    return diagnose_agreement(text, library=LIBRARY, profile=profile(**overrides))


# --- gaps ---------------------------------------------------------------------

def test_a_thin_agreement_yields_the_real_gaps():
    gaps = {gap.category for gap in diagnosis().gaps}
    for missing in ("transfer", "triggering_events", "valuation", "buysell",
                    "exit", "restrictive_covenants"):
        assert missing in gaps, missing


def test_every_gap_carries_its_failure_mode():
    for gap in diagnosis().gaps:
        assert gap.absence_risk
        assert len(gap.absence_risk) > 40, gap.category


def test_present_categories_are_not_reported_as_gaps():
    result = diagnosis()
    gap_categories = {gap.category for gap in result.gaps}
    for present in ("purpose", "capital", "distributions", "governance", "dispute"):
        assert present not in gap_categories, present
    assert present_categories(result) >= {"purpose", "capital", "distributions"}


def present_categories(result):
    return {item.category for item in result.detected}


def test_the_expected_set_follows_the_deal_shape():
    """A 50/50 expects a deadlock answer; a majority/minority does not."""
    equal = {gap.category for gap in diagnosis().gaps}
    split = {gap.category for gap in diagnosis(
        ownership_shape="majority_minority", member_count=4).gaps}
    assert "deadlock" in equal
    assert "deadlock" not in split


# --- honesty ------------------------------------------------------------------

def test_detection_is_never_phrased_as_adequacy():
    markdown = diagnosis().to_markdown()
    assert "detected, not evaluated" in markdown
    assert "Detection is not endorsement" in markdown
    assert "What this screen cannot see" in markdown


def test_each_detection_carries_an_excerpt_to_jump_to():
    for item in diagnosis().detected:
        assert item.excerpt
        assert item.matched_phrase


def test_stated_numbers_are_surfaced_but_not_judged():
    result = diagnosis()
    values = {obs.value for obs in result.observations}
    assert "$50,000" in values
    assert "30 days" in values
    markdown = result.to_markdown()
    assert "not judged" in markdown


# --- contradictions -------------------------------------------------------------

def test_textual_contradictions_are_flagged_with_both_excerpts():
    result = diagnosis(CONTRADICTORY)
    names = {item.name for item in result.contradictions}
    assert "Management model against acting authority" in names
    assert "Arbitration against a jury waiver" in names
    for item in result.contradictions:
        assert item.first_evidence and item.second_evidence


def test_a_consistent_document_raises_no_contradictions():
    assert diagnosis().contradictions == []


# --- the report ------------------------------------------------------------------

def test_required_gaps_lead_the_report():
    markdown = diagnosis().to_markdown()
    assert "## Missing, and required" in markdown
    assert markdown.index("Missing, and required") < markdown.index(
        "Present — detected")


def test_the_report_reads_without_raw_placeholders():
    markdown = diagnosis(CONTRADICTORY).to_markdown()
    assert "{" not in markdown
