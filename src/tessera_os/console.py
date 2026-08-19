"""Synthetic, localhost-only operator console API."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .clauses import Clause, ClauseLibrary
from .drafting import AgreementDrafter, AgreementDraftRequest
from .microsoft import (
    MicrosoftConfigurationError,
    MicrosoftConnectionBroker,
    MicrosoftConnectionStatus,
    MicrosoftPilotSettings,
)
from .orchestrator import TesseraOrchestrator
from .paths import project_root
from .policy import Environment
from .registry import AgentDefinition, AgentRegistry
from .review import InvalidReviewTransition, ReviewAccessDenied, ReviewQueue
from .runtime_controls import RateLimiter, RuntimeAuditStore
from .schemas import AgentRequest, ReviewItem, ReviewReasonCategory, ReviewStatus, UserContext
from .service import AuthSettings, create_app
from .settings import SecuritySettings, load_integration_settings, load_security_settings
from .workspace import (
    ArtifactEvent,
    LiveDraftContent,
    PilotArtifact,
    PilotArtifactStore,
    PilotComparison,
    PilotTaskRequest,
    PilotTemplate,
    PilotWorkflowOption,
    PilotWorkspace,
    PilotWorkspaceError,
)

ROOT = project_root()
DEFAULT_FIXTURE = ROOT / "fixtures" / "console" / "phase7.json"
DEFAULT_UI = ROOT / "web" / "tessera-console.html"


class ConsoleClient(BaseModel):
    id: str
    name: str


class ConsoleProject(BaseModel):
    id: str
    client_id: str
    name: str
    phase: str
    status: str
    manager_agent_id: str
    summary: str


class ProjectRegisterItem(BaseModel):
    id: str
    kind: str
    title: str
    owner: str
    status: str


class ProjectControlSnapshot(BaseModel):
    project_id: str
    registers: list[ProjectRegisterItem] = Field(default_factory=list)
    schedule_variance_days: int = 0
    budget_variance_amount: float = 0
    schedule_source_ids: list[str] = Field(default_factory=list)
    budget_source_ids: list[str] = Field(default_factory=list)


class ConsoleFixture(BaseModel):
    notice: str
    clients: list[ConsoleClient]
    projects: list[ConsoleProject]
    pilot_templates: list[PilotTemplate] = Field(default_factory=list)
    project_controls: list[ProjectControlSnapshot] = Field(default_factory=list)
    review_items: list[ReviewItem]


class ConsoleAgent(BaseModel):
    id: str
    name: str
    owns: str
    boundary: str
    profile: str
    tools: list[str]


class ConsoleIntegration(BaseModel):
    name: str
    status: str
    detail: str


class ConsoleSession(BaseModel):
    tenant_id: str
    user_id: str
    display_name: str
    project_ids: list[str]
    groups: list[str]
    environment: Environment
    synthetic: bool = True


class DashboardSummary(BaseModel):
    pending_reviews: int
    active_agents: int
    pilot_integrations: int
    integration_count: int
    external_writes: str = "disabled"


class ConsoleBootstrap(BaseModel):
    notice: str
    session: ConsoleSession
    dashboard: DashboardSummary
    clients: list[ConsoleClient]
    projects: list[ConsoleProject]
    agents: list[ConsoleAgent]
    security: dict[str, Any]
    integrations: list[ConsoleIntegration]
    microsoft: MicrosoftConnectionStatus
    review_items: list[ReviewItem]
    artifacts: list[PilotArtifact]
    workflows: list[PilotWorkflowOption]
    project_controls: list[ProjectControlSnapshot]


class ReviewDecision(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    category: ReviewReasonCategory = ReviewReasonCategory.OTHER


class ReviewAmendment(ReviewDecision):
    amended_body: str = Field(min_length=3, max_length=20000)


class WorkspaceResetRequest(BaseModel):
    confirmation: str = Field(pattern=r"^RESET SYNTHETIC$")


class WorkspaceResetResult(BaseModel):
    artifacts_removed: int
    reviews_restored: int
    audit_traces_removed: int
    budgets_removed: int


class SyntheticContextProvider:
    """Issue one fixed, least-surprise identity for localhost synthetic exercises."""

    def __init__(self, project_ids: set[str]) -> None:
        self.context = UserContext(
            tenant_id="tenant-synthetic",
            user_id="synthetic-reviewer-a",
            project_ids=project_ids,
            group_ids={
                "tessera_user", "project_reviewer", "proposal_approver",
                "qualified_counsel", "diligence_reviewer", "development_approver",
                "construction_reviewer", "investment_reviewer",
                "intelligence_reviewer", "engineering_reviewer", "assurance_reviewer",
            },
        )

    def __call__(
        self,
        authorization: Annotated[str | None, Header()] = None,
    ) -> UserContext:
        if authorization is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Sandbox console does not accept credentials")
        return self.context


def load_console_fixture(path: Path = DEFAULT_FIXTURE) -> ConsoleFixture:
    return ConsoleFixture.model_validate(json.loads(path.read_text()))


def _agent_card(agent: AgentDefinition) -> ConsoleAgent:
    boundary = ", ".join(agent.approval_required) or "No external action configured"
    return ConsoleAgent(id=agent.id, name=agent.name, owns=agent.purpose,
                        boundary=boundary, profile=agent.model_profile,
                        tools=list(agent.tools))


def _integration_cards() -> list[ConsoleIntegration]:
    settings = load_integration_settings()
    cards = []
    for name, entry in settings.integrations.items():
        detail_parts = [value for value in (entry.auth, entry.mode) if value]
        detail_parts.extend(entry.scopes)
        if entry.write_scopes_enabled is False:
            detail_parts.append("writes disabled")
        cards.append(ConsoleIntegration(name=name, status=entry.status,
                                        detail=" · ".join(detail_parts)))
    return cards


def _visible_projects(fixture: ConsoleFixture, context: UserContext) -> list[ConsoleProject]:
    return [project for project in fixture.projects if project.id in context.project_ids]


def _visible_clients(fixture: ConsoleFixture, context: UserContext) -> list[ConsoleClient]:
    client_ids = {project.client_id for project in _visible_projects(fixture, context)}
    return [client for client in fixture.clients if client.id in client_ids]


def _session(context: UserContext) -> ConsoleSession:
    return ConsoleSession(tenant_id=context.tenant_id, user_id=context.user_id,
                          display_name="Avery Reviewer (Synthetic)",
                          project_ids=sorted(context.project_ids),
                          groups=sorted(context.group_ids),
                          environment=Environment.SANDBOX)


def create_console_app(*, data_dir: Path | None = None,
                       fixture_path: Path = DEFAULT_FIXTURE,
                       ui_path: Path = DEFAULT_UI,
                       live_drafter: Callable[[PilotTaskRequest, PilotTemplate],
                                              LiveDraftContent] | None = None,
                       microsoft_broker: MicrosoftConnectionBroker | None = None) -> FastAPI:
    """Create a localhost sandbox app; production construction fails closed."""
    environment = Environment(os.getenv("TESSERA_ENV", "sandbox"))
    if environment == Environment.PRODUCTION:
        raise RuntimeError("Synthetic console cannot run in production")
    if environment not in {Environment.TEST, Environment.SANDBOX}:
        raise RuntimeError("Synthetic console is limited to test and sandbox environments")
    fixture = load_console_fixture(fixture_path)
    project_ids = {project.id for project in fixture.projects}
    context_provider = SyntheticContextProvider(project_ids)
    runtime_dir = data_dir or Path(os.getenv("TESSERA_CONSOLE_DATA_DIR",
                                             ROOT / "data" / "runtime"))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    if microsoft_broker is None:
        microsoft_settings = MicrosoftPilotSettings.from_environment()
        microsoft_broker = MicrosoftConnectionBroker(
            settings=microsoft_settings,
            cache_path=runtime_dir / "microsoft-token-cache.bin",
        )
    review_queue = ReviewQueue(runtime_dir / "console-review.db")
    review_queue.seed(fixture.review_items)
    artifact_store = PilotArtifactStore(runtime_dir / "console-artifacts.db")
    clauses = ClauseLibrary.load(ROOT / "fixtures" / "clause_library")
    drafter = AgreementDrafter(library=clauses, store=artifact_store,
                               project_clients={project.id: project.client_id
                                                for project in fixture.projects})
    audit_store = RuntimeAuditStore(runtime_dir / "console-audit.db")
    registry = AgentRegistry()
    live_enabled = os.getenv("TESSERA_PILOT_LIVE_DRAFTING", "false").lower() == "true"
    if live_enabled and live_drafter is None:
        orchestrator = TesseraOrchestrator(registry=registry)

        def live_drafter(request: PilotTaskRequest,
                         template: PilotTemplate) -> LiveDraftContent:
            source_ids = [item.source_id for item in template.evidence]
            # The envelope must not contradict the specialist prompt. It asks for
            # the same structure the prompt produces -- ranked findings, what was
            # not established, and what must go to a qualified professional -- so
            # the analysis survives the JSON boundary instead of being flattened
            # into free text.
            task = (
                f"Contract review: {request.task or template.title}. Return JSON only, with keys "
                "summary, recommendations, risks, assumptions, unknowns, escalations, claims. "
                "unknowns lists what you could not establish and what would resolve it. "
                "escalations lists anything requiring qualified counsel and why. "
                "claims is a list of objects with text, source_ids, "
                "severity (critical|material|notable), and finding_type "
                "(stated|absent|inconsistent; use absent when the finding is that the document "
                "omits something). Rank claims by severity, apply the materiality threshold in "
                f"your instructions, and use only these source_ids: {source_ids}."
            )
            output = asyncio.run(orchestrator.run(AgentRequest(task=task,
                project_id=request.project_id, user_id=context_provider.context.user_id,
                allowed_actions=["read", "draft"]), context=context_provider.context))
            cleaned = output.strip().removeprefix("```json").removesuffix("```").strip()
            return LiveDraftContent.model_validate_json(cleaned)

    workspace = PilotWorkspace(templates=fixture.pilot_templates, store=artifact_store,
        project_clients={project.id: project.client_id for project in fixture.projects},
        external_action_counter=lambda context, project_id:
            audit_store.count_external_actions(context=context, project_id=project_id),
        live_drafter=live_drafter, live_enabled=live_enabled)
    auth_settings = AuthSettings(issuer="offline://tessera-console",
        audience="tessera-console", verification_key="synthetic-console-key-not-for-production",
        algorithm="HS256", environment=environment)
    app = create_app(auth_settings=auth_settings, audit_store=audit_store,
                     rate_limiter=RateLimiter(limit=60), registry=registry,
                     context_provider=context_provider, enable_docs=False)
    app.title = "Tessera OS Console API"
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.add_middleware(CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
        allow_credentials=False, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Correlation-ID"])

    security_settings: SecuritySettings = load_security_settings()

    @app.middleware("http")
    async def sandbox_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
            # The console UI embeds its brand webfonts as data: URIs so it renders
            # correctly with no external requests. font-src must allow data:
            # explicitly, because it otherwise falls back to default-src 'self'.
            "font-src 'self' data:; img-src 'self' data:"
        )
        return response

    @app.get("/", include_in_schema=False)
    def console_ui() -> FileResponse:
        if not ui_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Console UI is not installed")
        return FileResponse(ui_path, media_type="text/html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/v1/session", response_model=ConsoleSession)
    def session(context: UserContext = Depends(context_provider)) -> ConsoleSession:  # noqa: B008
        return _session(context)

    @app.get("/v1/agents", response_model=list[ConsoleAgent])
    def agents(context: UserContext = Depends(context_provider)) -> list[ConsoleAgent]:  # noqa: B008
        del context
        return [_agent_card(agent) for agent in registry.all()]

    @app.get("/v1/policy", response_model=dict[str, Any])
    def policy(context: UserContext = Depends(context_provider)) -> dict[str, Any]:  # noqa: B008
        del context
        return security_settings.model_dump(mode="json")

    @app.get("/v1/integrations", response_model=list[ConsoleIntegration])
    def integrations(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> list[ConsoleIntegration]:
        del context
        return _integration_cards()

    @app.get(
        "/v1/integrations/microsoft/status",
        response_model=MicrosoftConnectionStatus,
    )
    def microsoft_status(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> MicrosoftConnectionStatus:
        del context
        return microsoft_broker.status()

    @app.post("/v1/integrations/microsoft/connect")
    def microsoft_connect(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> dict[str, str]:
        del context
        try:
            return {"authorization_url": microsoft_broker.begin()}
        except MicrosoftConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(exc)) from exc

    @app.get("/v1/integrations/microsoft/callback")
    def microsoft_callback(request: Request) -> RedirectResponse:
        try:
            microsoft_broker.complete(dict(request.query_params))
        except MicrosoftConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=str(exc)) from exc
        return RedirectResponse("/?microsoft=connected", status_code=status.HTTP_303_SEE_OTHER)

    @app.post(
        "/v1/integrations/microsoft/disconnect",
        response_model=MicrosoftConnectionStatus,
    )
    def microsoft_disconnect(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> MicrosoftConnectionStatus:
        del context
        microsoft_broker.disconnect()
        return microsoft_broker.status()

    @app.get("/v1/clients", response_model=list[ConsoleClient])
    def clients(context: UserContext = Depends(context_provider)) -> list[ConsoleClient]:  # noqa: B008
        return _visible_clients(fixture, context)

    @app.get("/v1/projects", response_model=list[ConsoleProject])
    def projects(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> list[ConsoleProject]:
        return _visible_projects(fixture, context)

    @app.get("/v1/projects/{project_id}", response_model=ConsoleProject)
    def project(project_id: str,
                context: UserContext = Depends(context_provider)) -> ConsoleProject:  # noqa: B008
        if project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        for item in fixture.projects:
            if item.id == project_id:
                return item
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Project was not found")

    @app.get("/v1/projects/{project_id}/controls", response_model=ProjectControlSnapshot)
    def project_controls(project_id: str,
            context: UserContext = Depends(context_provider)) -> ProjectControlSnapshot:  # noqa: B008
        if project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        return next((item for item in fixture.project_controls
                     if item.project_id == project_id), ProjectControlSnapshot(project_id=project_id))

    @app.get("/v1/reviews", response_model=list[ReviewItem])
    def reviews(review_status: Annotated[ReviewStatus | None, Query(alias="status")] = None,
                context: UserContext = Depends(context_provider)) -> list[ReviewItem]:  # noqa: B008
        return review_queue.list_items(context=context, status=review_status)

    @app.get("/v1/reviews/{item_id}", response_model=ReviewItem)
    def review(item_id: str,
               context: UserContext = Depends(context_provider)) -> ReviewItem:  # noqa: B008
        try:
            return review_queue.get(item_id, context=context)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Review item was not found") from exc
        except ReviewAccessDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
    def decide(item_id: str, decision: ReviewStatus, request: ReviewDecision,
               context: UserContext) -> ReviewItem:
        try:
            if decision == ReviewStatus.ACCEPTED:
                return review_queue.accept(item_id=item_id, context=context,
                                           reason=request.reason, category=request.category)
            return review_queue.reject(item_id=item_id, context=context,
                                       reason=request.reason, category=request.category)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Review item was not found") from exc
        except ReviewAccessDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except InvalidReviewTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(exc)) from exc

    def refreshed_artifact(artifact: PilotArtifact, context: UserContext) -> PilotArtifact:
        if artifact.review_item_id is None:
            return artifact
        try:
            item = review_queue.get(artifact.review_item_id, context=context)
        except KeyError:
            return artifact
        if item.status.value == artifact.status:
            return artifact
        if item.status in {ReviewStatus.ACCEPTED, ReviewStatus.REJECTED,
                           ReviewStatus.AMENDED_AND_ACCEPTED}:
            artifact.status = item.status.value
            artifact.amended_body = item.amended_body
            artifact.amended_by = item.reviewed_by if item.amended_body else None
            artifact.events.append(ArtifactEvent(
                event=f"review_{item.status.value}",
                actor=item.reviewed_by or "synthetic-reviewer",
                occurred_at=item.reviewed_at or datetime.now(UTC),
                detail=item.review_reason or "Review decision recorded",
            ))
            return artifact_store.update(artifact)
        return artifact

    @app.post("/v1/workspace/run", response_model=PilotArtifact)
    def run_workspace(request: PilotTaskRequest,
                      context: UserContext = Depends(context_provider)) -> PilotArtifact:  # noqa: B008
        try:
            return workspace.run(request, context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=str(exc)) from exc

    @app.post("/v1/workspace/compare", response_model=PilotComparison)
    def compare_workspace(request: PilotTaskRequest,
                          context: UserContext = Depends(context_provider)) -> PilotComparison:  # noqa: B008
        try:
            return workspace.compare(request, context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=str(exc)) from exc

    @app.get("/v1/projects/{project_id}/workflows",
             response_model=list[PilotWorkflowOption])
    def project_workflows(project_id: str,
            context: UserContext = Depends(context_provider)) -> list[PilotWorkflowOption]:  # noqa: B008
        try:
            return workspace.workflows(project_id=project_id, context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    @app.get("/v1/artifacts", response_model=list[PilotArtifact])
    def artifacts(project_id: str | None = None,
                  context: UserContext = Depends(context_provider)) -> list[PilotArtifact]:  # noqa: B008
        if project_id is not None and project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        return [refreshed_artifact(item, context)
                for item in artifact_store.list(context=context, project_id=project_id)]

    @app.get("/v1/artifacts/{artifact_id}", response_model=PilotArtifact)
    def artifact(artifact_id: str,
                 context: UserContext = Depends(context_provider)) -> PilotArtifact:  # noqa: B008
        try:
            return refreshed_artifact(artifact_store.get(artifact_id, context=context), context)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Artifact was not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc

    @app.post("/v1/artifacts/{artifact_id}/submit", response_model=PilotArtifact)
    def submit_artifact(artifact_id: str,
                        context: UserContext = Depends(context_provider)) -> PilotArtifact:  # noqa: B008
        try:
            artifact = artifact_store.get(artifact_id, context=context)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Artifact was not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        if artifact.review_item_id is not None:
            return refreshed_artifact(artifact, context)
        item = review_queue.submit(
            tenant_id=artifact.tenant_id, project_id=artifact.project_id,
            created_by=artifact.agent_id, workflow=artifact.workflow,
            title=artifact.title, body=artifact.review_body(), evidence=artifact.evidence,
            required_reviewer_group=artifact.required_reviewer_group,
        )
        artifact.status = "submitted"
        artifact.review_item_id = item.id
        artifact.events.append(ArtifactEvent(
            event="submitted_for_review", actor=context.user_id,
            occurred_at=datetime.now(UTC), detail=f"Queued as review {item.id}",
        ))
        return artifact_store.update(artifact)

    @app.get("/v1/clause-library", response_model=list[Clause])
    def clause_library(context: UserContext = Depends(context_provider)) -> list[Clause]:  # noqa: B008
        """The approved clause variants, so a reviewer can see the whole band.

        Exposed read-only. Adopting or changing a variant is a counsel decision
        made in the repository, not through this API.
        """
        del context
        return clauses.clauses

    @app.post("/v1/workspace/draft-agreement", response_model=PilotArtifact)
    def draft_agreement(request: AgreementDraftRequest,
                        context: UserContext = Depends(context_provider)) -> PilotArtifact:  # noqa: B008
        try:
            return drafter.draft(request, context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=str(exc)) from exc

    @app.post("/v1/workspace/reset", response_model=WorkspaceResetResult)
    def reset_workspace(request: WorkspaceResetRequest,
                        context: UserContext = Depends(context_provider)) -> WorkspaceResetResult:  # noqa: B008
        del request
        try:
            removed = artifact_store.reset_synthetic(context=context)
            restored = review_queue.reset_synthetic(
                tenant_id=context.tenant_id, items=fixture.review_items)
            traces_removed, budgets_removed = audit_store.reset_synthetic(context=context)
        except (PermissionError, ReviewAccessDenied) as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        return WorkspaceResetResult(artifacts_removed=removed, reviews_restored=restored,
            audit_traces_removed=traces_removed, budgets_removed=budgets_removed)

    @app.post("/v1/reviews/{item_id}/accept", response_model=ReviewItem)
    def accept_review(item_id: str, request: ReviewDecision,
                      context: UserContext = Depends(context_provider)) -> ReviewItem:  # noqa: B008
        return decide(item_id, ReviewStatus.ACCEPTED, request, context)

    @app.post("/v1/reviews/{item_id}/reject", response_model=ReviewItem)
    def reject_review(item_id: str, request: ReviewDecision,
                      context: UserContext = Depends(context_provider)) -> ReviewItem:  # noqa: B008
        return decide(item_id, ReviewStatus.REJECTED, request, context)

    @app.post("/v1/reviews/{item_id}/amend-and-accept", response_model=ReviewItem)
    def amend_review(item_id: str, request: ReviewAmendment,
                     context: UserContext = Depends(context_provider)) -> ReviewItem:  # noqa: B008
        try:
            return review_queue.amend_and_accept(item_id=item_id, context=context,
                reason=request.reason, category=request.category,
                amended_body=request.amended_body)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Review item was not found") from exc
        except ReviewAccessDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except InvalidReviewTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.get("/v1/pilot/export")
    def export_pilot_labels(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> list[dict[str, Any]]:
        return [{
            "review_id": item.id, "project_id": item.project_id,
            "workflow": item.workflow, "decision": item.status.value,
            "reason_category": item.review_reason_category.value
                if item.review_reason_category else None,
            "reason": item.review_reason, "original_body": item.body,
            "amended_body": item.amended_body, "reviewed_by": item.reviewed_by,
            "source_ids": [evidence.source_id for evidence in item.evidence],
        } for item in review_queue.list_items(context=context)
            if item.status != ReviewStatus.PENDING]

    @app.get("/v1/console/bootstrap", response_model=ConsoleBootstrap)
    def bootstrap(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> ConsoleBootstrap:
        review_items = review_queue.list_items(context=context)
        artifacts = [refreshed_artifact(item, context)
                     for item in artifact_store.list(context=context)]
        agents = [_agent_card(agent) for agent in registry.all()]
        integrations = _integration_cards()
        return ConsoleBootstrap(notice=fixture.notice, session=_session(context),
            dashboard=DashboardSummary(
                pending_reviews=sum(item.status == ReviewStatus.PENDING
                                    for item in review_items),
                active_agents=len(agents),
                pilot_integrations=sum(item.status == "pilot" for item in integrations),
                integration_count=len(integrations)),
            clients=_visible_clients(fixture, context),
            projects=_visible_projects(fixture, context), agents=agents,
            security=security_settings.model_dump(mode="json"),
            integrations=integrations, microsoft=microsoft_broker.status(),
            review_items=review_items, artifacts=artifacts,
            workflows=[option for project_id in sorted(context.project_ids)
                       for option in workspace.workflows(project_id=project_id,
                                                         context=context)],
            project_controls=[item for item in fixture.project_controls
                              if item.project_id in context.project_ids])

    @app.get("/api/openapi.json", include_in_schema=False)
    def openapi_contract() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/api/docs", include_in_schema=False)
    def offline_docs() -> HTMLResponse:
        return HTMLResponse("""<!doctype html><html><head><title>Tessera Console API</title>
        <meta charset="utf-8"></head><body><main><h1>Tessera Console API</h1>
        <p>Offline synthetic sandbox. External writes are disabled.</p>
        <p><a href="/api/openapi.json">OpenAPI JSON contract</a></p>
        <p>See <code>docs/CONSOLE_API.md</code> in the repository for endpoint guidance.</p>
        </main></body></html>""")

    app.state.console_fixture = fixture
    app.state.context_provider = context_provider
    app.state.review_queue = review_queue
    app.state.artifact_store = artifact_store
    app.state.workspace = workspace
    app.state.audit_store = audit_store
    return app
