"""Agreement drafting must run through the same governed path as everything else.

The Contract Manager prompt instructs the specialist to draft from approved
clause variants rather than composing language. That is only true if the library
reaches the workflow, and if the resulting document is reviewed, cited, and
audited exactly like an analysis artifact.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tessera_os.clauses import ClauseLibrary, DealProfile
from tessera_os.console import create_console_app
from tessera_os.drafting import AgreementDrafter, AgreementDraftRequest
from tessera_os.schemas import UserContext
from tessera_os.workspace import PilotArtifactStore, PilotWorkspaceError

PROJECT = "riverbend-multifamily"


def context(**overrides) -> UserContext:
    base = {"tenant_id": "tenant-synthetic", "user_id": "synthetic-reviewer-a",
            "project_ids": {PROJECT}, "group_ids": {"tessera_user", "qualified_counsel"}}
    base.update(overrides)
    return UserContext(**base)


def drafter(tmp_path) -> AgreementDrafter:
    return AgreementDrafter(library=ClauseLibrary.load("fixtures/clause_library"),
                            store=PilotArtifactStore(tmp_path / "artifacts.db"),
                            project_clients={PROJECT: "client-riverbend"})


def profile(**overrides) -> DealProfile:
    base = {"opportunity": "RiverBend JV", "agreement_type": "operating_agreement",
            "industry": "real_estate", "jurisdiction": "the State of Delaware",
            "counterparty": "Meridian Capital LLC", "fee_at_risk": 0,
            "tessera_capital_at_risk": True}
    base.update(overrides)
    return DealProfile(**base)


def draft(tmp_path, **overrides):
    return drafter(tmp_path).draft(
        AgreementDraftRequest(project_id=PROJECT, profile=profile(**overrides)),
        context=context(), structural_handoff=True)


def test_draft_requires_qualified_counsel_review(tmp_path):
    artifact = draft(tmp_path)
    assert artifact.required_reviewer_group == "qualified_counsel"
    assert artifact.status == "draft"
    assert "not legal advice" in artifact.summary


def test_every_clause_cites_the_library_variant_it_came_from(tmp_path):
    """Citation coverage on a drafted agreement must measure something real."""
    artifact = draft(tmp_path)
    evidence_ids = {item.source_id for item in artifact.evidence}
    assert evidence_ids
    for citation in artifact.citations:
        assert set(citation.source_ids) <= evidence_ids
    assert len(artifact.citations) == len(artifact.evidence)
    for item in artifact.evidence:
        assert item.locator.startswith("library://clause/")


def test_counsel_notes_become_escalations(tmp_path):
    artifact = draft(tmp_path)
    assert artifact.escalations
    assert any("MANDATORY tax review" in note for note in artifact.escalations)


def test_open_terms_become_unknowns(tmp_path):
    artifact = draft(tmp_path)
    assert any("ordinary_course_threshold" in item for item in artifact.unknowns)


def test_a_less_protective_substitution_is_a_ranked_finding(tmp_path):
    """A clause seated below the deal's posture must not be a footnote."""
    artifact = draft(tmp_path, agreement_type="finders_fee", industry="regulated",
                     counterparty_represented=False, fee_at_risk=250_000)
    flagged = [c for c in artifact.citations if c.finding_type == "inconsistent"]
    assert flagged, "the substituted contractor clause should surface as a finding"
    assert all(c.severity == "material" for c in flagged)


def test_the_operative_document_is_carried_on_the_artifact(tmp_path):
    artifact = draft(tmp_path)
    assert artifact.body_markdown
    body = artifact.review_body()
    assert "## Document" in body
    assert "Reserved Matters" in body
    assert "{n}" not in body


def test_scope_is_enforced(tmp_path):
    request = AgreementDraftRequest(project_id=PROJECT, profile=profile())
    with pytest.raises(PermissionError):
        drafter(tmp_path).draft(
            request, context=context(project_ids={"other-project"}),
            structural_handoff=True)


def test_unknown_project_is_rejected(tmp_path):
    request = AgreementDraftRequest(project_id="ghost", profile=profile())
    with pytest.raises((PilotWorkspaceError, PermissionError)):
        drafter(tmp_path).draft(
            request, context=context(project_ids={"ghost"}), structural_handoff=True)


def test_investor_subscription_is_not_an_offered_document_type():
    """Subscription paper needs reps and a securities legend no variant carries.

    That work is counsel-only under the decision packet, so the type is not
    offered at all rather than offered and permanently unable to draft --
    a document type nobody can ever produce is worse than none.
    """
    with pytest.raises(ValidationError):
        profile(agreement_type="investor_subscription")


def test_a_partially_covered_document_type_refuses(tmp_path):
    """Emitting a document missing a required category reads as complete and is not."""
    stripped = ClauseLibrary.load("fixtures/clause_library")
    library = ClauseLibrary([c for c in stripped.clauses if c.category != "buysell"],
                            variables=stripped.variables)
    with pytest.raises(PilotWorkspaceError, match="cannot draft"):
        AgreementDrafter(library=library, store=PilotArtifactStore(tmp_path / "artifacts.db"),
                         project_clients={PROJECT: "client-riverbend"}).draft(
            AgreementDraftRequest(project_id=PROJECT, profile=profile()),
            context=context(), structural_handoff=True)


def test_the_refusal_names_what_is_missing():
    stripped = ClauseLibrary.load("fixtures/clause_library")
    library = ClauseLibrary([c for c in stripped.clauses if c.category != "buysell"],
                            variables=stripped.variables)
    missing = library.missing_essentials(profile())
    assert "buysell" in missing


def test_covered_document_types_still_assemble():
    library = ClauseLibrary.load("fixtures/clause_library")
    for agreement_type in ("consulting", "advisory", "finders_fee", "deal_memo",
                           "operating_agreement", "jv", "nda"):
        assert not library.missing_essentials(profile(agreement_type=agreement_type)), \
            agreement_type


def test_console_exposes_the_library_and_drafting(tmp_path):
    app = create_console_app(data_dir=tmp_path)
    client = TestClient(app)

    library = client.get("/v1/clause-library")
    assert library.status_code == 200
    assert len(library.json()) > 20

    response = client.post("/v1/workspace/draft-agreement", json={
        "project_id": PROJECT,
        "profile": profile(agreement_type="nda").model_dump(),
    })
    assert response.status_code == 200, response.text
    artifact = response.json()
    assert artifact["workflow"] == "contract_drafting"
    assert artifact["required_reviewer_group"] == "qualified_counsel"
    assert artifact["escalations"]
    assert artifact["body_markdown"]

    # The drafted agreement joins the normal artifact list and review path.
    listed = client.get("/v1/artifacts").json()
    assert any(item["id"] == artifact["id"] for item in listed)


def test_console_direct_route_cannot_bypass_structure_review_for_entity_paper(tmp_path):
    client = TestClient(create_console_app(data_dir=tmp_path))
    response = client.post("/v1/workspace/draft-agreement", json={
        "project_id": PROJECT, "profile": profile().model_dump()})
    assert response.status_code == 422
    assert "accepted Structure Manager memo" in response.json()["detail"]


def test_console_rejects_a_project_outside_scope(tmp_path):
    client = TestClient(create_console_app(data_dir=tmp_path))
    response = client.post("/v1/workspace/draft-agreement", json={
        "project_id": "not-a-project", "profile": profile().model_dump()})
    assert response.status_code in (403, 422)
