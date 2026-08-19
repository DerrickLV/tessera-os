"""Bridge the clause library into the governed draft pipeline.

The Contract Manager prompt instructs the specialist to draft from approved
clause variants rather than composing language. That instruction is only true if
the library actually reaches the workflow, so this module turns a
:class:`~tessera_os.clauses.DealProfile` into the same ``PilotArtifact`` every
other workflow produces -- reviewed, cited, and audited on the same path.

Two mappings do the real work:

* every clause cites the library variant it came from, so citation coverage on a
  drafted agreement measures something real rather than being true by
  construction;
* the things a draft cannot answer for itself become first-class fields --
  unfilled commercial terms become ``unknowns``, per-variant counsel notes become
  ``escalations``, and a clause seated below the deal's posture becomes a ranked
  finding rather than a footnote.

Nothing here sends, files, or executes anything. The output is an internal draft
for qualified human review, exactly as with the deterministic workflows.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .clauses import AssembledDraft, ClauseCoverageError, ClauseLibrary, DealProfile
from .schemas import Evidence, RouteDecision, UserContext
from .workspace import (
    ArtifactEvent,
    PilotArtifact,
    PilotArtifactStore,
    PilotClaim,
    PilotWorkspaceError,
)

DRAFTING_AGENT = "contract_manager"
DRAFTING_WORKFLOW = "contract_drafting"
DRAFTING_REVIEWER_GROUP = "qualified_counsel"


class AgreementDraftRequest(BaseModel):
    project_id: str = Field(min_length=1)
    profile: DealProfile


def _evidence_for(assembled: AssembledDraft) -> list[Evidence]:
    """One evidence record per selected clause variant.

    The library is the source. Citing the exact variant means a reviewer can
    trace any sentence in the agreement back to approved language, and means a
    newly drafted clause would stand out as uncited.
    """
    stamp = datetime.now(UTC).isoformat()
    return [
        Evidence(
            source_id=item.variant.id,
            title=f"{item.clause.title} — {item.variant.posture} variant",
            locator=f"library://clause/{item.clause.id}/{item.variant.id}",
            excerpt=item.variant.when,
            retrieved_at=stamp,
        )
        for item in assembled.selections
    ]


def _claims_for(assembled: AssembledDraft) -> list[PilotClaim]:
    claims = []
    for item in assembled.selections:
        if item.less_protective_than_requested:
            severity, finding = "material", "inconsistent"
            text = (f"{item.clause.title} uses the {item.variant.posture} variant, which is "
                    f"less protective than this deal's {item.posture_requested} posture.")
        else:
            severity, finding = "notable", "stated"
            text = (f"{item.clause.title} uses the approved {item.variant.posture} variant "
                    f"({item.variant.id}).")
        claims.append(PilotClaim(text=text, source_ids=[item.variant.id],
                                 severity=severity, finding_type=finding))
    return claims


def _risks_for(assembled: AssembledDraft) -> list[str]:
    risks = [f"{item.clause.title}: {item.variant.trade_off}"
             for item in assembled.selections if item.variant.trade_off]
    risks.extend(f"{clause.title} is required but no variant applies. {clause.absence_risk}"
                 for clause in assembled.omitted_required)
    return risks


class AgreementDrafter:
    """Assemble deal-specific agreements into the standard artifact shape."""

    def __init__(self, *, library: ClauseLibrary, store: PilotArtifactStore,
                 project_clients: dict[str, str]) -> None:
        self.library = library
        self.store = store
        self.project_clients = project_clients

    def draft(self, request: AgreementDraftRequest, *,
              context: UserContext) -> PilotArtifact:
        if request.project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        try:
            client_id = self.project_clients[request.project_id]
        except KeyError as exc:
            raise PilotWorkspaceError("Unknown project for agreement drafting") from exc

        profile = request.profile
        try:
            assembled = self.library.assemble(profile)
        except ClauseCoverageError as exc:
            raise PilotWorkspaceError(str(exc)) from exc
        if not assembled.selections:
            raise PilotWorkspaceError(
                f"No clause variants apply to a {profile.agreement_type} in "
                f"{profile.industry}; the library cannot draft this agreement")

        unknowns = [f"{{{name}}} is not yet decided." for name in assembled.open_variables()]
        # A required clause with no applicable variant is a gap in the library,
        # not something the reader should have to notice in the text.
        unknowns.extend(f"{clause.title} has no applicable approved variant."
                        for clause in assembled.omitted_required)

        now = datetime.now(UTC)
        artifact = PilotArtifact(
            tenant_id=context.tenant_id, client_id=client_id,
            project_id=request.project_id, created_by=context.user_id,
            task=f"Draft a {profile.agreement_type} for {profile.opportunity}",
            title=(f"{profile.agreement_type.replace('_', ' ').title()} — "
                   f"{profile.opportunity}"),
            workflow=DRAFTING_WORKFLOW, agent_id=DRAFTING_AGENT,
            route=RouteDecision(primary_agent=DRAFTING_AGENT,
                                rationale="Agreement drafting is Contract Manager work"),
            status="draft",
            summary=(f"Assembled a {profile.agreement_type.replace('_', ' ')} for "
                     f"{profile.counterparty} at a {assembled.posture} posture, selected for "
                     f"{profile.posture_rationale()}. "
                     f"{len(assembled.selections)} clauses drawn from approved variants. "
                     f"Governing law: {profile.jurisdiction}. "
                     "Not sent, not executed, and not legal advice."),
            recommendations=[
                "Route to qualified counsel before any version reaches the counterparty.",
                "Resolve every open commercial term listed below before circulating.",
            ],
            risks=_risks_for(assembled),
            assumptions=[
                "Clause variants are the approved library text and have not been edited here.",
                f"Governing law is {profile.jurisdiction}; variants are not jurisdiction-tested.",
            ],
            unknowns=unknowns,
            escalations=assembled.counsel_notes(),
            evidence=_evidence_for(assembled),
            citations=[],  # populated by the workspace citation check below
            metrics=[],
            required_reviewer_group=DRAFTING_REVIEWER_GROUP,
            events=[ArtifactEvent(event="draft_created", actor=context.user_id,
                                  occurred_at=now,
                                  detail=f"Assembled from {len(assembled.selections)} "
                                         "approved clause variants")],
        )
        artifact.citations = _validate_citations(assembled, artifact)
        artifact.body_markdown = assembled.to_markdown()
        return self.store.save(artifact)


def _validate_citations(assembled: AssembledDraft, artifact: PilotArtifact):
    """Keep every claim tied to evidence actually present on the artifact."""
    from .workspace import ArtifactCitation

    known = {item.source_id for item in artifact.evidence}
    return [ArtifactCitation(claim=claim.text, source_ids=claim.source_ids,
                             severity=claim.severity, finding_type=claim.finding_type)
            for claim in _claims_for(assembled)
            if claim.source_ids and set(claim.source_ids) <= known]
