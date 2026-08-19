"""Reviewer groups come from Entra, and trust zones enforce the governance model.

Two boundaries, both previously conventions rather than controls. Reviewer
groups: the portal handed every signed-in user the same ``tessera_user`` set,
so ``required_reviewer_group`` was UI decoration — now a privileged group
exists only if an administrator mapped the Entra group and the user's token
carried it. Zones: Tessera's own governance model organizes SharePoint by
trust boundary, and the golden rule is that Internal originals never leave
zone 01 — now the read path and the citation path both enforce it.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tessera_os.identity import (
    BASE_GROUP,
    EntraGroupMap,
    IdentityConfigurationError,
    ZoneAccessError,
    ZonePolicy,
    build_user_context,
)
from tessera_os.microsoft import (
    AllowlistedSharePointReader,
    MicrosoftPilotSettings,
    SharePointProjectResource,
)
from tessera_os.schemas import Evidence, UserContext
from tessera_os.workspace import (
    PilotArtifactStore,
    PilotClaim,
    PilotTaskRequest,
    PilotTemplate,
    PilotWorkspace,
)

COUNSEL_ENTRA = "9f3c0000-0000-0000-0000-00000000c0de"
PARTNER_ENTRA = "1ab20000-0000-0000-0000-0000000050a5"


def group_map() -> EntraGroupMap:
    return EntraGroupMap(groups={COUNSEL_ENTRA: "qualified_counsel",
                                 PARTNER_ENTRA: "tessera_partner"})


# --- group mapping -----------------------------------------------------------

def test_a_mapped_entra_group_becomes_a_tessera_group():
    context = build_user_context(
        tenant_id="t", user_id="u", entra_group_ids=[COUNSEL_ENTRA],
        project_ids={"p"}, group_map=group_map())
    assert "qualified_counsel" in context.group_ids
    assert BASE_GROUP in context.group_ids


def test_an_unmapped_entra_group_grants_nothing():
    context = build_user_context(
        tenant_id="t", user_id="u",
        entra_group_ids=["ffff0000-0000-0000-0000-00000000beef"],
        project_ids={"p"}, group_map=group_map())
    assert context.group_ids == frozenset({BASE_GROUP})


def test_groups_overage_fails_closed():
    """Entra omits the groups claim when a user has too many groups. Absent
    claim means no privileged groups — never an error, never a guess."""
    context = build_user_context(
        tenant_id="t", user_id="u", entra_group_ids=None,
        project_ids={"p"}, group_map=group_map())
    assert context.group_ids == frozenset({BASE_GROUP})


def test_nothing_downstream_can_self_assert_a_reviewer_group():
    """The map is the only door. An empty map means no privileged user exists."""
    context = build_user_context(
        tenant_id="t", user_id="u", entra_group_ids=[COUNSEL_ENTRA, PARTNER_ENTRA],
        project_ids={"p"}, group_map=EntraGroupMap())
    assert "qualified_counsel" not in context.group_ids
    assert "tessera_partner" not in context.group_ids


def test_a_blank_map_entry_is_refused():
    # Pydantic wraps validator errors; the refusal itself is what matters.
    with pytest.raises(ValidationError, match="non-empty"):
        EntraGroupMap(groups={"": "qualified_counsel"})


def test_the_environment_map_must_be_json():
    import os
    os.environ["TESSERA_M365_GROUP_MAP"] = "not json"
    try:
        with pytest.raises(IdentityConfigurationError, match="valid JSON"):
            EntraGroupMap.from_environment()
    finally:
        del os.environ["TESSERA_M365_GROUP_MAP"]


# --- zones on resources --------------------------------------------------------

def test_an_engagement_resource_must_name_its_client():
    with pytest.raises(ValidationError, match="client"):
        SharePointProjectResource(site_id="s", drive_id="d", zone="engagement")


def test_an_undeclared_zone_is_internal():
    """Fail closed: a mapping that forgets its zone gets the strictest one."""
    resource = SharePointProjectResource(site_id="s", drive_id="d")
    assert resource.zone == "internal"


def partner_context(projects=("internal-pilot",)) -> UserContext:
    return UserContext(tenant_id="t", user_id="derrick",
                       project_ids=set(projects),
                       group_ids={BASE_GROUP, "tessera_partner"})


def user_context(projects=("internal-pilot",)) -> UserContext:
    return UserContext(tenant_id="t", user_id="collaborator",
                       project_ids=set(projects), group_ids={BASE_GROUP})


def internal_settings() -> MicrosoftPilotSettings:
    return MicrosoftPilotSettings(
        enabled=True, tenant_id="t", client_id="c", client_secret="s", cache_key="k",
        project_resources={"internal-pilot": {
            "site_id": "site", "drive_id": "drive", "zone": "internal"}})


def test_an_internal_library_is_readable_only_by_the_partners_group():
    def transport(url, headers):
        return {"value": []}

    from tessera_os.integrations import MicrosoftGraphReader

    reader = AllowlistedSharePointReader(
        settings=internal_settings(),
        graph_factory=lambda provider: MicrosoftGraphReader(provider, transport=transport),
        token_provider=lambda _user_id: "token")

    assert reader.project_documents(context=partner_context(),
                                    project_id="internal-pilot") == []
    with pytest.raises(ZoneAccessError, match="partners"):
        reader.project_documents(context=user_context(), project_id="internal-pilot")


def test_documents_carry_their_zone_so_downstream_checks_can_run():
    def transport(url, headers):
        return {"value": [{
            "id": "doc-1", "name": "Model.docx", "file": {},
            "lastModifiedDateTime": "2026-08-18T12:00:00+00:00",
            "listItem": {"fields": {"ProjectId": "internal-pilot",
                                    "TesseraContent": "content"}},
        }]}

    from tessera_os.integrations import MicrosoftGraphReader

    reader = AllowlistedSharePointReader(
        settings=internal_settings(),
        graph_factory=lambda provider: MicrosoftGraphReader(provider, transport=transport),
        token_provider=lambda _user_id: "token")
    documents = reader.project_documents(context=partner_context(),
                                         project_id="internal-pilot")
    assert documents[0].metadata["trust_zone"] == "internal"


# --- the golden rule at citation time --------------------------------------------

def policy() -> ZonePolicy:
    return ZonePolicy(
        resource_zones={"internal-master": "internal",
                        "acme-workspace": "engagement",
                        "bravo-workspace": "engagement",
                        "counsel-shared": "collaborator"},
        resource_clients={"acme-workspace": "client-acme",
                          "bravo-workspace": "client-bravo",
                          "counsel-shared": "client-acme"})


def test_a_document_cited_within_its_own_project_passes():
    policy().check_citation(source_project_id="acme-workspace",
                            artifact_project_id="acme-workspace",
                            artifact_client_id="client-acme")


def test_an_internal_original_never_reaches_a_client_artifact():
    """Work originates in Internal; a COPY goes outward. The original is never
    cited across the boundary — this is the governance model's golden rule."""
    with pytest.raises(ZoneAccessError, match="never leave"):
        policy().check_citation(source_project_id="internal-master",
                                artifact_project_id="acme-workspace",
                                artifact_client_id="client-acme")


def test_one_clients_documents_cannot_surface_in_anothers_artifact():
    with pytest.raises(ZoneAccessError, match="outside"):
        policy().check_citation(source_project_id="acme-workspace",
                                artifact_project_id="bravo-workspace",
                                artifact_client_id="client-bravo")


def test_an_engagement_zone_without_a_client_wall_is_invalid():
    with pytest.raises(ValidationError, match="client"):
        ZonePolicy(resource_zones={"x": "engagement"})


def test_workspace_artifact_path_refuses_a_cross_zone_citation(tmp_path):
    """The policy must run in artifact creation, not only in a helper unit test."""
    evidence = Evidence(
        source_id="internal-source", title="Internal source",
        locator="fixture://internal/source", excerpt="Internal-only material",
        retrieved_at=datetime.now(UTC).isoformat(),
        source_project_id="internal-master", source_client_id="tessera",
        trust_zone="internal")
    template = PilotTemplate(
        project_id="acme-workspace", title="Acme draft", workflow="contract_review",
        agent_id="contract_manager", summary="Synthetic draft", evidence=[evidence],
        claims=[PilotClaim(text="Internal claim", source_ids=[evidence.source_id])])
    workspace = PilotWorkspace(
        templates=[template], store=PilotArtifactStore(tmp_path / "artifacts.db"),
        project_clients={"acme-workspace": "client-acme"},
        zone_policy=policy())
    artifact = workspace.run(
        PilotTaskRequest(project_id="acme-workspace", workflow="contract_review"),
        context=UserContext(tenant_id="t", user_id="u",
                            project_ids={"acme-workspace"}))
    assert artifact.status == "insufficient_evidence"
    assert artifact.citations == []
    assert any("trust boundary" in item for item in artifact.refusal_reasons)
