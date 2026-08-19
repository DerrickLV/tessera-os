"""The draft structure must carry a specialist's ranking through to the reviewer.

The specialist prompts require every draft to rank findings by severity, to
distinguish a finding quoted from a document from one made by absence, to say
what could not be established, and to name what must go to a qualified
professional. Before these fields existed, all four were flattened into free
text on the way into the artifact, so a Critical exposure and an incidental note
reached the review queue looking identical. These tests pin that down.
"""

from datetime import UTC, datetime, timedelta

import pytest

from tessera_os.schemas import Evidence, UserContext
from tessera_os.workspace import (
    ArtifactCitation,
    LiveDraftContent,
    PilotArtifactStore,
    PilotClaim,
    PilotTaskRequest,
    PilotTemplate,
    PilotWorkspace,
)

TENANT = "tenant-synthetic"
PROJECT = "riverbend-multifamily"


def context() -> UserContext:
    return UserContext(tenant_id=TENANT, user_id="synthetic-reviewer-a",
                       project_ids={PROJECT}, group_ids={"tessera_user", "qualified_counsel"})


def evidence(age_days: int = 1) -> list[Evidence]:
    stamp = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    return [Evidence(source_id="rb-agreement", title="Synthetic consultant agreement",
                     locator="offline://workspace/riverbend/agreement",
                     excerpt="No aggregate liability cap is stated.", retrieved_at=stamp)]


def template(**overrides) -> PilotTemplate:
    base = {
        "project_id": PROJECT, "title": "RiverBend Contract Review Draft",
        "workflow": "contract_review", "agent_id": "contract_manager",
        "required_reviewer_group": "qualified_counsel",
        "summary": "The synthetic agreement omits a liability cap.",
        "recommendations": ["Route to qualified counsel."],
        "risks": ["Unbounded direct-damages exposure."],
        "assumptions": ["The agreement is an internal synthetic draft."],
        "unknowns": ["No approved clause playbook is in evidence for this comparison."],
        "escalations": ["Personal-liability exposure under the indemnity is for counsel."],
        "claims": [
            PilotClaim(text="No aggregate liability cap is stated.",
                       source_ids=["rb-agreement"], severity="critical", finding_type="absent"),
            PilotClaim(text="Headings clause is at ordinary standard.",
                       source_ids=["rb-agreement"], severity="notable"),
        ],
        "evidence": evidence(),
    }
    base.update(overrides)
    return PilotTemplate(**base)


def workspace(tmp_path, tpl: PilotTemplate) -> PilotWorkspace:
    return PilotWorkspace(templates=[tpl],
                          store=PilotArtifactStore(tmp_path / "artifacts.db"),
                          project_clients={PROJECT: "client-riverbend"},
                          external_action_counter=lambda ctx, project_id: 0)


def run(tmp_path, tpl: PilotTemplate | None = None):
    tpl = tpl or template()
    return workspace(tmp_path, tpl).run(
        PilotTaskRequest(project_id=PROJECT, workflow="contract_review",
                         task="Review the consultant agreement"), context=context())


def test_severity_and_finding_type_survive_into_the_artifact(tmp_path):
    artifact = run(tmp_path)
    by_text = {item.claim: item for item in artifact.citations}
    critical = by_text["No aggregate liability cap is stated."]
    assert critical.severity == "critical"
    assert critical.finding_type == "absent"
    assert by_text["Headings clause is at ordinary standard."].severity == "notable"


def test_unknowns_and_escalations_reach_the_reviewer(tmp_path):
    artifact = run(tmp_path)
    assert artifact.unknowns == [
        "No approved clause playbook is in evidence for this comparison."]
    assert artifact.escalations == [
        "Personal-liability exposure under the indemnity is for counsel."]
    body = artifact.review_body()
    assert "Route to a qualified professional" in body
    assert "Not established" in body
    assert "No approved clause playbook" in body


def test_review_body_orders_findings_by_severity(tmp_path):
    body = run(tmp_path).review_body()
    critical_at = body.index("No aggregate liability cap")
    notable_at = body.index("Headings clause")
    assert critical_at < notable_at, "critical findings must precede notable ones"
    assert "**Critical, absent**" in body


def test_defaults_keep_existing_templates_valid():
    """Templates written before these fields existed must still load."""
    claim = PilotClaim(text="A claim with no explicit ranking.", source_ids=["rb-agreement"])
    assert claim.severity == "notable"
    assert claim.finding_type == "stated"
    content = LiveDraftContent(summary="s", claims=[claim])
    assert content.unknowns == []
    assert content.escalations == []
    assert ArtifactCitation(claim="c", source_ids=["rb-agreement"]).severity == "notable"


def test_invalid_severity_is_rejected():
    with pytest.raises(ValueError):
        PilotClaim(text="x", source_ids=["rb-agreement"], severity="catastrophic")


def test_refusal_still_carries_escalations(tmp_path):
    """A refusal is the case where routing to a human matters most."""
    stale = template(evidence=evidence(age_days=400))
    artifact = run(tmp_path, stale)
    assert artifact.status == "insufficient_evidence"
    assert artifact.escalations, "a refusal must still say who should look at it"
    assert "Route to a qualified professional" in artifact.review_body()
