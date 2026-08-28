"""Phase 4: sector and regime coverage.

Work item 4.1 ships first, on its own commit, before any new pattern is
written (docs/BUILD_BRIEF_PHASE_4_SECTOR_COVERAGE.md, D1): a sector declared
in the ``Sector`` literal with no ``SectorPattern`` must be loud, never
silent. The tests in the first section below exercise that mechanism using
``monkeypatch`` against ``SECTOR_PATTERNS`` directly, rather than against
whichever real sectors happen to lack a pattern today -- by the end of this
phase all nine have one, and a test tied to a real, temporary gap would go
stale the moment that gap closed.

``test_every_declared_sector_has_a_pattern`` is the ratchet: it enumerates
the ``Sector`` literal itself, so a sector added to the literal without a
matching entry in ``SECTOR_PATTERNS`` fails CI. It is expected to be red
until every work item through 4.7 lands -- that redness *is* the point of
shipping 4.1 first: it makes every remaining gap loud before the patterns
that close them are written.
"""

from typing import get_args

import pytest

from tessera_os.drafting import StructureAdvisor, StructureRequest
from tessera_os.governance import VentureProfile, recommend_structure
from tessera_os.review import ReviewQueue
from tessera_os.schemas import Evidence, UserContext
from tessera_os.sectors import SECTOR_PATTERNS, Sector, pattern_for
from tessera_os.workspace import PilotArtifactStore, PilotWorkspaceError

PROJECT = "sector-coverage-probe"


def venture(**overrides) -> VentureProfile:
    base = {"venture": "Probe", "home_state": "Texas", "activity": "film_production"}
    base.update(overrides)
    return VentureProfile(**base)


def context(**overrides) -> UserContext:
    base = {"tenant_id": "tenant-synthetic", "user_id": "derrick",
            "project_ids": {PROJECT}, "group_ids": {"tessera_user", "qualified_counsel"}}
    base.update(overrides)
    return UserContext(**base)


# --- 4.1 -- a missing pattern is loud, not silent --------------------------------------------

def test_a_sector_with_no_pattern_raises_a_blocking_open_question_naming_it(monkeypatch):
    monkeypatch.delitem(SECTOR_PATTERNS, "film_production")
    rec = recommend_structure(venture())
    assert pattern_for("film_production") is None  # the gap this test manufactured
    questions = [item.question for item in rec.open_questions]
    assert any("film_production" in q for q in questions)
    assert any("no structuring pattern exists" in q.lower() for q in questions)


def test_a_sector_with_a_pattern_raises_no_such_question(monkeypatch):
    """Confirms the check above is actually exercising the gap, not a question
    that appears unconditionally regardless of pattern coverage."""
    rec = recommend_structure(venture())  # film_production has a real pattern
    questions = [item.question for item in rec.open_questions]
    assert not any("no structuring pattern exists" in q.lower() for q in questions)


def test_an_unpatterned_sector_cannot_reach_draft_status(monkeypatch, tmp_path):
    monkeypatch.delitem(SECTOR_PATTERNS, "film_production")
    advisor = StructureAdvisor(
        store=PilotArtifactStore(tmp_path / "artifacts.db"),
        review_queue=ReviewQueue(tmp_path / "reviews.db"),
        library=__import__("tessera_os.clauses", fromlist=["ClauseLibrary"])
                .ClauseLibrary.load("fixtures/clause_library"),
        project_clients={PROJECT: "client-probe"})
    request = StructureRequest(
        project_id=PROJECT, venture=venture(), counterparty="Counterparty LLC",
        evidence=[Evidence(source_id="probe-1", title="Probe intake",
                           locator="fixture://probe", excerpt="Synthetic.",
                           retrieved_at="2026-08-27T00:00:00+00:00")])
    memo = advisor.recommend(request, context=context())
    assert memo.status == "insufficient_evidence"
    assert any("blocking questions remain unanswered" in reason.lower()
              for reason in memo.refusal_reasons)
    assert any("no structuring pattern exists" in item.lower() for item in memo.unknowns)


def test_to_draft_request_refuses_for_an_unpatterned_sector(monkeypatch, tmp_path):
    from tessera_os.clauses import ClauseLibrary

    monkeypatch.delitem(SECTOR_PATTERNS, "film_production")
    library = ClauseLibrary.load("fixtures/clause_library")
    advisor = StructureAdvisor(
        store=PilotArtifactStore(tmp_path / "artifacts.db"),
        review_queue=ReviewQueue(tmp_path / "reviews.db"),
        library=library, project_clients={PROJECT: "client-probe"})
    request = StructureRequest(
        project_id=PROJECT, venture=venture(), counterparty="Counterparty LLC",
        evidence=[Evidence(source_id="probe-1", title="Probe intake",
                           locator="fixture://probe", excerpt="Synthetic.",
                           retrieved_at="2026-08-27T00:00:00+00:00")])
    memo = advisor.recommend(request, context=context())
    item = advisor.review_queue.submit(
        tenant_id=memo.tenant_id, project_id=memo.project_id, created_by=memo.agent_id,
        workflow=memo.workflow, title=memo.title, body=memo.review_body(),
        evidence=memo.evidence, required_reviewer_group=memo.required_reviewer_group)
    memo.review_item_id = item.id
    advisor.store.update(memo)
    advisor.review_queue.accept(item_id=item.id, context=context(user_id="counsel-b"),
                               reason="Synthetic acceptance for the gap test.")
    with pytest.raises(PilotWorkspaceError):
        advisor.to_draft_request(request, context=context(), approved_artifact_id=memo.id)


# --- the ratchet: every declared sector must have a pattern ----------------------------------

@pytest.mark.parametrize("sector", get_args(Sector))
def test_every_declared_sector_has_a_pattern(sector):
    """Enumerates the Sector literal itself, not SECTOR_PATTERNS -- so a
    sector added to the literal without a matching pattern fails CI, per
    docs/BUILD_BRIEF_PHASE_4_SECTOR_COVERAGE.md 4.1's acceptance criterion.

    Intentionally red until every pattern through 4.7 has landed -- see the
    module docstring.
    """
    assert pattern_for(sector) is not None, (
        f"{sector!r} is declared in the Sector literal but SECTOR_PATTERNS has no entry for "
        "it. Either add a SectorPattern for it, or remove it from the Sector literal so it is "
        "not offered on the intake form with silently degraded advice.")
