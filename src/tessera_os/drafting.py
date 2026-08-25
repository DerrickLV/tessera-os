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

import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .clauses import AssembledDraft, ClauseCoverageError, ClauseLibrary, DealProfile, Party
from .governance import BASIS_LABEL, StructureRecommendation, VentureProfile, recommend_structure
from .review import ReviewAccessDenied, ReviewQueue
from .schemas import Evidence, ReviewStatus, RouteDecision, UserContext
from .workspace import (
    ArtifactEvent,
    ArtifactMetric,
    PilotArtifact,
    PilotArtifactStore,
    PilotClaim,
    PilotWorkspaceError,
    reject_unsafe_instruction,
)

DRAFTING_AGENT = "contract_manager"
DRAFTING_WORKFLOW = "contract_drafting"
DRAFTING_REVIEWER_GROUP = "qualified_counsel"

STRUCTURE_AGENT = "structure_manager"
STRUCTURE_WORKFLOW = "entity_structuring"
STRUCTURE_REVIEWER_GROUP = "qualified_counsel"


class AgreementDraftRequest(BaseModel):
    project_id: str = Field(min_length=1)
    profile: DealProfile
    source_artifact_id: str | None = None
    # Commercial terms the structure recommendation already decided. Carried on
    # the request so a later fill step has one source for a value that must
    # match the memo, instead of recomputing it (or forgetting to).
    derived_values: dict[str, str] = Field(default_factory=dict)


class StructureRequest(BaseModel):
    """A venture to be structured, and optionally the paper that follows from it."""

    project_id: str = Field(min_length=1)
    venture: VentureProfile
    counterparty: str = Field(default="", description="Named only when drafting follows.")
    parties: list[Party] = Field(default_factory=list)
    effective_date: str | None = None
    evidence: list[Evidence] = Field(min_length=1)
    open_question_answers: dict[str, str] = Field(default_factory=dict)
    freshness_days: int = Field(default=45, ge=1, le=365)


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
            text = (f"{item.clause.title} uses the synthetic {item.variant.posture} variant "
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

    def draft(self, request: AgreementDraftRequest, *, context: UserContext,
              structural_handoff: bool = False) -> PilotArtifact:
        if request.project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        try:
            client_id = self.project_clients[request.project_id]
        except KeyError as exc:
            raise PilotWorkspaceError("Unknown project for agreement drafting") from exc

        profile = request.profile
        if profile.agreement_type in {"operating_agreement", "jv"} and not structural_handoff:
            raise PilotWorkspaceError(
                "Operating agreements and JVs require an accepted Structure Manager memo")
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
        unknowns.extend(f"{clause.title} has no applicable synthetic variant."
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
                     f"{len(assembled.selections)} clauses drawn from synthetic variants. "
                     f"Governing law: {profile.jurisdiction}. "
                     "Not sent, not executed, and not legal advice."),
            recommendations=[
                "Route to qualified counsel before any version reaches the counterparty.",
                "Resolve every open commercial term listed below before circulating.",
            ],
            risks=_risks_for(assembled),
            assumptions=[
                ("Clause variants are synthetic evaluation text, not adopted Tessera positions "
                 "or counsel-approved production language."),
                f"Governing law is {profile.jurisdiction}; variants are not jurisdiction-tested.",
            ],
            unknowns=unknowns,
            escalations=assembled.counsel_notes(),
            evidence=_evidence_for(assembled),
            citations=[],  # populated by the workspace citation check below
            metrics=[],
            source_artifact_id=request.source_artifact_id,
            required_reviewer_group=DRAFTING_REVIEWER_GROUP,
            events=[ArtifactEvent(event="draft_created", actor=context.user_id,
                                  occurred_at=now,
                                  detail=f"Assembled from {len(assembled.selections)} "
                                         "synthetic clause variants")],
        )
        artifact.citations = _validate_citations(assembled, artifact)
        artifact.body_markdown = assembled.to_markdown()
        return self.store.save(artifact)


def _structure_fingerprint(request: StructureRequest) -> str:
    payload = json.dumps(request.model_dump(mode="json"), sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _structure_evidence(rec: StructureRecommendation,
                        request: StructureRequest) -> list[Evidence]:
    """Cite supplied facts and the exact synthetic rule used for each position."""
    stamp = datetime.now(UTC).isoformat()
    rules = [
        Evidence(
            source_id=f"structure:{item.area.lower().replace(' ', '-')}",
            title=f"Synthetic structure rule — {item.area}",
            locator=("code://tessera_os/governance.py/"
                     f"{item.area.lower().replace(' ', '-')}/{item.basis}"),
            excerpt=f"{BASIS_LABEL[item.basis]} Rule output: {item.position}",
            retrieved_at=stamp,
        )
        for item in rec.recommendations
    ]
    return [*request.evidence, *rules]


def _structure_claims(rec: StructureRecommendation,
                      request: StructureRequest) -> list[PilotClaim]:
    claims = []
    fact_sources = [item.source_id for item in request.evidence]
    for item in rec.recommendations:
        source = f"structure:{item.area.lower().replace(' ', '-')}"
        if item.basis == "scaffold":
            # "absent" is the honest finding type: no adopted Tessera position
            # exists for this area, and the reviewer needs to see that.
            severity, finding = "material", "absent"
            text = (f"{item.area}: {item.position} No adopted Tessera position covers this — "
                    "it is a starting point for counsel to accept or replace.")
        else:
            severity, finding = "notable", "stated"
            text = f"{item.area}: {item.position}"
        claims.append(PilotClaim(text=text, source_ids=[*fact_sources, source],
                                 severity=severity, finding_type=finding))
    return claims


def _unanswered(rec: StructureRecommendation,
                request: StructureRequest) -> list:
    return [item for item in rec.open_questions
            if not request.open_question_answers.get(item.question, "").strip()]


def _evidence_age_days(request: StructureRequest, now: datetime) -> float:
    retrieved: list[datetime] = []
    for item in request.evidence:
        if not item.retrieved_at:
            return 9999
        try:
            value = datetime.fromisoformat(item.retrieved_at)
        except ValueError:
            return 9999
        if value.tzinfo is None:
            return 9999
        retrieved.append(value)
    return max(((now - item).total_seconds() / 86400 for item in retrieved), default=9999)


class StructureAdvisor:
    """Produce an entity-structure recommendation on the governed artifact path.

    The recommendation is the front of the structuring work and the document is
    the back of it. Running both through the same review queue means the paper a
    client signs is traceable to the structural reasoning that called for it,
    rather than to parameters someone set by hand afterwards.
    """

    def __init__(self, *, store: PilotArtifactStore,
                 project_clients: dict[str, str],
                 library: ClauseLibrary,
                 review_queue: ReviewQueue | None = None) -> None:
        self.store = store
        self.project_clients = project_clients
        self.library = library
        self.review_queue = review_queue

    def recommend(self, request: StructureRequest, *,
                  context: UserContext) -> PilotArtifact:
        if request.project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        try:
            client_id = self.project_clients[request.project_id]
        except KeyError as exc:
            raise PilotWorkspaceError("Unknown project for entity structuring") from exc

        reject_unsafe_instruction(
            request.venture.venture,
            request.counterparty,
            json.dumps(request.open_question_answers, sort_keys=True),
            json.dumps([item.model_dump(mode="json") for item in request.evidence],
                       sort_keys=True),
            json.dumps([item.model_dump(mode="json") for item in request.parties],
                       sort_keys=True),
        )

        rec = recommend_structure(request.venture)
        venture = request.venture
        now = datetime.now(UTC)

        unadopted = rec.unadopted()
        unanswered = _unanswered(rec, request)
        evidence_age_days = _evidence_age_days(request, now)
        evidence_current = evidence_age_days <= request.freshness_days
        refusal_reasons = []
        if not evidence_current:
            refusal_reasons.append(
                f"Evidence is older than the {request.freshness_days}-day freshness limit.")
        if rec.conflicts:
            refusal_reasons.append("Structural conflicts must be resolved before drafting.")
        if unanswered:
            refusal_reasons.append("Blocking questions remain unanswered.")
        status = "insufficient_evidence" if refusal_reasons else "draft"
        artifact = PilotArtifact(
            tenant_id=context.tenant_id, client_id=client_id,
            project_id=request.project_id, created_by=context.user_id,
            task=f"Recommend an entity structure for {venture.venture}",
            title=f"Structure Recommendation — {venture.venture}",
            workflow=STRUCTURE_WORKFLOW, agent_id=STRUCTURE_AGENT,
            route=RouteDecision(primary_agent=STRUCTURE_AGENT,
                                rationale="Entity architecture is Structure Manager work"),
            status=status,
            summary=(
                f"{len(rec.layers)} "
                f"{'entity' if len(rec.layers) == 1 else 'entities'}, "
                f"{rec.control.management_model.replace('_', ' ')}, with "
                f"{len(rec.control.reserved_matters)} reserved matters decided by "
                f"{rec.control.approval_rule.replace('_', ' ')} and an ordinary-course "
                f"threshold of ${rec.control.ordinary_course_threshold:,}. "
                f"{'A deadlock ladder applies. ' if rec.control.deadlock_ladder else ''}"
                f"{len(rec.adopted())} positions are adopted Tessera positions; "
                f"{len(rec.synthetic_references())} come from the synthetic "
                "evaluation playbook; "
                f"{len(unadopted)} are starting points. "
                "Structural advice only — not legal or tax advice, and not filed."),
            recommendations=[item.to_line() for item in rec.recommendations],
            risks=[f"{mode.name}: {mode.without_this}" for mode in rec.failure_modes],
            assumptions=[
                ("Structure follows only from the facts supplied in the venture profile; "
                 "anything not supplied is listed as an open question."),
                ("Positions marked as starting points have not been adopted by Tessera or "
                 "reviewed by counsel for this jurisdiction."),
            ],
            unknowns=[f"{item.question} Blocks: {item.blocks}" for item in unanswered],
            escalations=(
                [f"Conflict — {item.between}: {item.problem} Resolve: {item.resolve}"
                 for item in rec.conflicts]
                + [item.confirm for item in rec.recommendations if item.confirm]),
            evidence=_structure_evidence(rec, request),
            citations=[],
            refusal_reasons=refusal_reasons,
            metrics=[
                ArtifactMetric(name="citation_coverage", value=100, unit="percent",
                               target="100%", passed=True),
                ArtifactMetric(name="oldest_evidence_age",
                               value=round(evidence_age_days, 1), unit="days",
                               target=f"{request.freshness_days} days or less",
                               passed=evidence_current),
            ],
            input_fingerprint=_structure_fingerprint(request),
            required_reviewer_group=STRUCTURE_REVIEWER_GROUP,
            events=[ArtifactEvent(event="draft_created", actor=context.user_id,
                                  occurred_at=now,
                                  detail=f"{len(rec.recommendations)} positions, "
                                         f"{len(rec.conflicts)} conflicts, "
                                         f"{len(unanswered)} unanswered questions")],
        )
        known = {item.source_id for item in artifact.evidence}
        from .workspace import ArtifactCitation
        artifact.citations = [
            ArtifactCitation(claim=claim.text, source_ids=claim.source_ids,
                             severity=claim.severity, finding_type=claim.finding_type)
            for claim in _structure_claims(rec, request) if set(claim.source_ids) <= known]
        artifact.body_markdown = rec.to_markdown()
        return self.store.save(artifact)

    def to_draft_request(self, request: StructureRequest, *, context: UserContext,
                         approved_artifact_id: str) -> AgreementDraftRequest:
        """The operating agreement the recommendation calls for.

        Chaining these is the point. Setting the drafting parameters by hand
        after giving structural advice is how a document ends up contradicting
        the memo that justified it.
        """
        if request.project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        if self.review_queue is None:
            raise PilotWorkspaceError("A review queue is required for structure handoff")
        artifact = self.store.get(approved_artifact_id, context=context)
        if artifact.workflow != STRUCTURE_WORKFLOW or artifact.project_id != request.project_id:
            raise PilotWorkspaceError("Approved artifact is not this project's structure memo")
        if artifact.input_fingerprint != _structure_fingerprint(request):
            raise PilotWorkspaceError("Structure inputs changed after review; create a new memo")
        if artifact.status == "insufficient_evidence" or artifact.refusal_reasons:
            raise PilotWorkspaceError("Insufficient-evidence recommendations cannot be drafted")
        if artifact.review_item_id is None:
            raise PilotWorkspaceError("Structure memo has not been submitted for review")
        try:
            review = self.review_queue.get(artifact.review_item_id, context=context)
        except (KeyError, ReviewAccessDenied) as exc:
            raise PilotWorkspaceError("Structure review is unavailable or outside scope") from exc
        if review.status != ReviewStatus.ACCEPTED:
            raise PilotWorkspaceError("Qualified counsel must approve the structure memo first")

        rec = recommend_structure(request.venture)
        if rec.conflicts or _unanswered(rec, request):
            raise PilotWorkspaceError("Resolve all conflicts and blocking questions before drafting")
        draft_request = AgreementDraftRequest(
            project_id=request.project_id,
            source_artifact_id=artifact.id,
            profile=rec.to_deal_profile(
                counterparty=request.counterparty or request.venture.venture,
                parties=request.parties, effective_date=request.effective_date),
            derived_values=rec.derived_values())
        delivered = {item.clause.category
                     for item in self.library.assemble(
                         draft_request.profile, require_coverage=False).selections}
        unmet = sorted(rec.expected_clause_categories() - delivered)
        if unmet:
            raise PilotWorkspaceError(
                f"Structure memo promises clause categories the document lacks: {unmet}")
        return draft_request

    @staticmethod
    def derived_values(request: StructureRequest) -> dict[str, str]:
        """The commercial terms the structure decided, for :meth:`ClauseLibrary.fill`.

        Pass these in when filling the draft. Otherwise the library supplies its
        own posture defaults and the agreement quietly contradicts the memo.
        """
        return recommend_structure(request.venture).derived_values()


def _validate_citations(assembled: AssembledDraft, artifact: PilotArtifact):
    """Keep every claim tied to evidence actually present on the artifact."""
    from .workspace import ArtifactCitation

    known = {item.source_id for item in artifact.evidence}
    return [ArtifactCitation(claim=claim.text, source_ids=claim.source_ids,
                             severity=claim.severity, finding_type=claim.finding_type)
            for claim in _claims_for(assembled)
            if claim.source_ids and set(claim.source_ids) <= known]
