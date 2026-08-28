"""Synthetic, localhost-only operator console API."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .clauses import Clause, ClauseLibrary
from .drafting import (
    AgreementDrafter,
    AgreementDraftRequest,
    StructureAdvisor,
    StructureRequest,
)
from .governance import VentureProfile, recommend_structure
from .identity import BASE_GROUP
from .microsoft import (
    MicrosoftConfigurationError,
    MicrosoftConnectionBroker,
    MicrosoftConnectionStatus,
    MicrosoftPilotSettings,
)
from .numbers import DerivedNumberConfirmation, NumberConfirmationStore
from .orchestrator import TesseraOrchestrator
from .paths import project_root
from .policy import Environment
from .registry import AgentDefinition, AgentRegistry
from .review import InvalidReviewTransition, ReviewAccessDenied, ReviewQueue
from .runtime_controls import RateLimiter, RuntimeAuditStore
from .schemas import (
    AgentRequest,
    Evidence,
    ReviewItem,
    ReviewReasonCategory,
    ReviewStatus,
    UserContext,
)
from .service import AuthSettings, create_app
from .sessions import SessionCodec
from .settings import SecuritySettings, load_integration_settings, load_security_settings
from .terms import MenuSelection, MenuSelectionStore
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


class PortalContextProvider:
    """Real identity, taken from the session the portal already issued.

    The synthetic provider above hands every caller one fixed identity carrying
    every privileged group at once. That is right for a localhost exercise and
    disqualifying anywhere else: under it, separation of duties is a label the
    interface displays rather than a boundary anything enforces, because the
    same identity both drafts and accepts.

    This reads the signed portal session cookie instead, and three properties
    follow -- each one a boundary the console did not previously have:

    - **The user is who Entra says they are.** ``sub`` is the Entra object ID,
      minted server-side and signed with a secret the browser never sees.
    - **Privileged groups come from the directory, not from code.** ``grp``
      holds the Tessera groups resolved through the Entra group map at sign-in.
      A user outside the mapped security group cannot carry
      ``qualified_counsel``, so the review queue's refusal to let an author
      disposition their own draft becomes enforceable instead of advisory.
    - **The invitation list still applies.** A structurally valid session for
      someone outside ``TESSERA_ALLOWED_USER_IDS`` is refused here as well as at
      the portal, so mounting the console widens the surface without widening
      who may reach it.
    """

    def __init__(self, *, codec: SessionCodec, project_ids: set[str],
                 allowed_user_ids: frozenset[str]) -> None:
        self._codec = codec
        self._project_ids = frozenset(project_ids)
        self._allowed_user_ids = frozenset(allowed_user_ids)

    def __call__(
        self,
        tessera_session: Annotated[str | None, Cookie()] = None,
    ) -> UserContext:
        if not tessera_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Sign in to Tessera OS to use the console")
        claims = self._codec.decode(tessera_session)
        user_id = str(claims["sub"])
        if user_id not in self._allowed_user_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="This account is not invited to Tessera OS")
        # An absent or empty ``grp`` is not an error. Entra omits the groups
        # claim entirely once a user exceeds the token's group limit, and the
        # correct reading of "no mapped groups" is no privilege -- never an
        # assumption that the user must have meant to have some.
        mapped = {str(item) for item in (claims.get("grp") or [])}
        return UserContext(tenant_id=str(claims["tid"]), user_id=user_id,
                           display_name=str(claims.get("name") or ""),
                           project_ids=self._project_ids,
                           group_ids=frozenset(mapped | {BASE_GROUP}))


PRODUCTION_NOTICE = (
    "Live engagement data. Records here are real, every decision is written to "
    "the audit chain, and no synthetic fixture is loaded.")


def production_console_fixture(projects: list[ConsoleProject]) -> ConsoleFixture:
    """The catalog the console runs on when it is not running on fixtures.

    Carries no ``pilot_templates`` and no ``review_items``, deliberately. The
    templates are pre-authored synthetic drafts, and seeding a production review
    queue with them would put invented findings in front of a reviewer through
    the same interface, and with the same weight, as real ones. An empty queue
    that fills from real work is the correct starting state.
    """
    return ConsoleFixture(
        notice=PRODUCTION_NOTICE,
        clients=[ConsoleClient(id=client_id,
                               name=client_id.replace("-", " ").replace("_", " ").title())
                 for client_id in sorted({project.client_id for project in projects})],
        projects=list(projects), pilot_templates=[], project_controls=[], review_items=[])


class StructureIntakeRequest(BaseModel):
    """A venture described by the operator, rather than by a fixture."""

    project_id: str = Field(min_length=1)
    venture: VentureProfile
    counterparty: str = ""


class NumberConfirmationRequest(BaseModel):
    project_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value: int


class MenuSelectionRequest(BaseModel):
    project_id: str = Field(min_length=1)
    area: str = Field(min_length=1)
    label: str = Field(min_length=1)


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


def _session(context: UserContext, *, environment: Environment = Environment.SANDBOX,
             synthetic: bool = True) -> ConsoleSession:
    return ConsoleSession(tenant_id=context.tenant_id, user_id=context.user_id,
                          display_name=(context.display_name
                                        or ("Avery Reviewer (Synthetic)" if synthetic
                                            else context.user_id)),
                          project_ids=sorted(context.project_ids),
                          groups=sorted(context.group_ids),
                          environment=environment, synthetic=synthetic)


def create_console_app(*, data_dir: Path | None = None,
                       fixture_path: Path = DEFAULT_FIXTURE,
                       ui_path: Path = DEFAULT_UI,
                       live_drafter: Callable[[PilotTaskRequest, PilotTemplate],
                                              LiveDraftContent] | None = None,
                       microsoft_broker: MicrosoftConnectionBroker | None = None,
                       context_provider: Callable[..., UserContext] | None = None,
                       fixture: ConsoleFixture | None = None,
                       trusted_hosts: list[str] | None = None) -> FastAPI:
    """Create the console app.

    Production is permitted, but only on terms. The old guard refused it
    outright, and that was the right refusal for what the console then was: an
    app whose every request resolved to one hardcoded identity holding every
    privileged group. Running that in production would have put an interface
    with no access control in front of real client work.

    What the guard was actually protecting against is the synthetic *identity*,
    not the console. So the condition is now the specific one: production
    requires a real context provider. Supply ``PortalContextProvider`` and the
    console authenticates every request against the signed portal session, the
    project ACLs are enforced against a real user, and the review queue's
    separation of duties has two distinct people to distinguish. Supply nothing
    and it still refuses, exactly as before.
    """
    environment = Environment(os.getenv("TESSERA_ENV", "sandbox"))
    production = environment == Environment.PRODUCTION
    if production and context_provider is None:
        raise RuntimeError(
            "Production console requires an authenticated context provider; "
            "the synthetic identity carries every reviewer group and cannot "
            "enforce separation of duties")
    if not production and environment not in {Environment.TEST, Environment.SANDBOX}:
        raise RuntimeError("Synthetic console is limited to test and sandbox environments")
    fixture = fixture or load_console_fixture(fixture_path)
    project_ids = {project.id for project in fixture.projects}
    context_provider = context_provider or SyntheticContextProvider(project_ids)

    def refuse_in_production(surface: str) -> None:
        """Refuse a surface whose content is pre-authored fiction.

        These endpoints return fixture drafts, or restore them. In a sandbox
        that is the point. In production the output would be indistinguishable
        in the interface from a real engine result, which is the one failure
        this system exists to prevent.
        """
        if production:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                detail=(f"{surface} serves pre-authored synthetic content and is "
                        "available only in the sandbox console"))
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
    if fixture.review_items:
        review_queue.seed(fixture.review_items)
    artifact_store = PilotArtifactStore(runtime_dir / "console-artifacts.db")
    clauses = ClauseLibrary.load(ROOT / "fixtures" / "clause_library")
    drafter = AgreementDrafter(library=clauses, store=artifact_store,
                               project_clients={project.id: project.client_id
                                                for project in fixture.projects})
    number_confirmations = NumberConfirmationStore(
        runtime_dir / "console-number-confirmations.db")
    menu_selections = MenuSelectionStore(runtime_dir / "console-menu-selections.db")
    structure_advisor = StructureAdvisor(
        store=artifact_store,
        review_queue=review_queue,
        library=clauses,
        project_clients={project.id: project.client_id for project in fixture.projects},
        number_confirmations=number_confirmations,
        menu_selections=menu_selections,
    )

    def synthetic_structure_request(project_id: str) -> StructureRequest:
        project = next((item for item in fixture.projects if item.id == project_id), None)
        if project is None:
            raise PilotWorkspaceError("No synthetic structure fixture exists for that project")
        venture = VentureProfile(
            venture=f"{project.name} Structure (Synthetic)", home_state="Texas",
            activity="real_estate_hold", real_property=True,
            initial_capital=2_000_000, expected_hold_years=5,
            operators_take_compensation=False,
        )
        return StructureRequest(
            project_id=project_id, venture=venture,
            counterparty="Synthetic Counterparty",
            evidence=[Evidence(
                source_id=f"{project_id}-synthetic-structure-intake",
                title="Synthetic structure intake fixture",
                locator=f"fixture://console/{project_id}/structure-intake",
                excerpt="Fictional facts for offline Structure Manager evaluation.",
                retrieved_at=datetime.now(UTC).isoformat(),
            )],
            open_question_answers={
                item.question: "Answered in the synthetic console fixture."
                for item in recommend_structure(venture).open_questions
            },
        )
    audit_store = RuntimeAuditStore(runtime_dir / "console-audit.db")
    registry = AgentRegistry()
    live_enabled = os.getenv("TESSERA_PILOT_LIVE_DRAFTING", "false").lower() == "true"
    if live_enabled and live_drafter is None and not isinstance(
            context_provider, SyntheticContextProvider):
        # The fallback drafter below runs the orchestrator as the provider's one
        # fixed identity, which only exists in the synthetic console. Rather
        # than silently run real drafting as the wrong user, live drafting stays
        # off until a drafter bound to the authenticated caller is supplied.
        live_enabled = False
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

    def workflow_options(project_id: str, context: UserContext) -> list[PilotWorkflowOption]:
        return [*workspace.workflows(project_id=project_id, context=context),
                PilotWorkflowOption(project_id=project_id, workflow="entity_structuring",
                                    title="Entity Structure Recommendation",
                                    agent_id="structure_manager")]
    # The verification key is never used: create_app builds a JWT authenticator
    # only when no context provider is supplied, and one always is here. It is
    # still declared honestly per environment, because AuthSettings refuses a
    # symmetric algorithm in production and that refusal is worth keeping intact
    # rather than working around.
    auth_settings = AuthSettings(issuer="offline://tessera-console",
        audience="tessera-console",
        verification_key=("unused-authentication-is-delegated-to-the-portal-session"
                          if production else "synthetic-console-key-not-for-production"),
        algorithm="RS256" if production else "HS256", environment=environment)
    app = create_app(auth_settings=auth_settings, audit_store=audit_store,
                     rate_limiter=RateLimiter(limit=60), registry=registry,
                     context_provider=context_provider, enable_docs=False)
    app.title = "Tessera OS Console API"
    if trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
    elif not production:
        app.add_middleware(TrustedHostMiddleware,
                           allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    if not production:
        # Mounted on the portal, the console is same-origin by construction and
        # the parent app already enforces the host allowlist. Declaring CORS
        # here would only ever widen it.
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

    def console_session(context: UserContext) -> ConsoleSession:
        return _session(context, environment=environment, synthetic=not production)

    @app.get("/v1/session", response_model=ConsoleSession)
    def session(context: UserContext = Depends(context_provider)) -> ConsoleSession:  # noqa: B008
        return console_session(context)

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
        return microsoft_broker.status(context.user_id)

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
        microsoft_broker.disconnect(context.user_id)
        return microsoft_broker.status(context.user_id)

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
        # Both branches are fixtures. The templates are pre-authored drafts, and
        # entity_structuring here runs the real engine over a hardcoded venture
        # -- a genuine recommendation about an imaginary company. Production
        # reaches the same engine through /v1/structure/intake with the
        # operator's own facts.
        refuse_in_production("Running a workspace workflow")
        try:
            if request.workflow == "entity_structuring":
                if request.project_id not in context.project_ids:
                    raise PermissionError("Project is outside authenticated scope")
                return structure_advisor.recommend(
                    synthetic_structure_request(request.project_id), context=context)
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
        refuse_in_production("Comparing workspace drafts")
        try:
            return workspace.compare(request, context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=str(exc)) from exc

    @app.post("/v1/structure/intake", response_model=PilotArtifact)
    def structure_intake(request: StructureIntakeRequest,
                         context: UserContext = Depends(context_provider)) -> PilotArtifact:  # noqa: B008
        """Recommend a structure from facts the operator states at intake.

        This is the production entry to the structure engine. It exists because
        the sandbox route supplies a hardcoded venture, and the whole value of
        the recommendation is that it responds to *this* venture's facts.

        The evidence record attached below is an operator statement, and is
        labelled as one rather than dressed as a document. ``StructureRequest``
        requires at least one piece of evidence precisely so that nothing enters
        the record without a provenance, and the honest provenance here is "the
        partner said so at intake on this date". A memo built on stated facts
        should read as one; if the facts later come from a signed term sheet,
        that becomes a different evidence record and the memo strengthens.
        """
        if request.project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        stamp = datetime.now(UTC)
        venture = request.venture
        summary = (f"{venture.venture} · {venture.home_state} · {venture.activity} · "
                   f"{venture.active_principals} active principal(s), "
                   f"{venture.passive_investors} passive · capital "
                   f"{venture.capital_source} · exit {venture.exit_intent}")
        stated_by = context.display_name or context.user_id
        try:
            return structure_advisor.recommend(
                StructureRequest(
                    project_id=request.project_id, venture=venture,
                    counterparty=request.counterparty,
                    evidence=[Evidence(
                        source_id=f"{request.project_id}-intake-{stamp:%Y%m%dT%H%M%S}",
                        title=f"Structuring intake stated by {stated_by}",
                        locator=f"portal://structure-intake/{request.project_id}",
                        excerpt=summary,
                        retrieved_at=stamp.isoformat())]),
                context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=str(exc)) from exc

    @app.post("/v1/structure/recommendations", response_model=PilotArtifact)
    def recommend_structure_api(
        request: StructureRequest,
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> PilotArtifact:
        """Create an evidence-backed, synthetic structure memo draft."""
        try:
            return structure_advisor.recommend(request, context=context)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=str(exc)) from exc

    @app.post("/v1/structure/recommendations/{artifact_id}/draft",
              response_model=PilotArtifact)
    def draft_approved_structure(
        artifact_id: str,
        request: StructureRequest,
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> PilotArtifact:
        """Draft only from the exact structure inputs accepted by qualified counsel."""
        try:
            draft_request = structure_advisor.to_draft_request(
                request, context=context, approved_artifact_id=artifact_id)
            return drafter.draft(
                draft_request, context=context, structural_handoff=True)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except (PilotWorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(exc)) from exc

    @app.post("/v1/structure/numbers/confirm", response_model=DerivedNumberConfirmation)
    def confirm_number(
        request: NumberConfirmationRequest,
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> DerivedNumberConfirmation:
        """Record a person's decision on a proposed figure (D4).

        Same authorization boundary as ``/v1/structure/intake``: a project
        outside the caller's scope is a 403, not a 404 that would leak which
        project IDs exist.
        """
        if request.project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        return number_confirmations.confirm(
            tenant_id=context.tenant_id, project_id=request.project_id, label=request.label,
            value=request.value, confirmed_by=context.user_id)

    @app.post("/v1/structure/menus/select", response_model=MenuSelection)
    def select_menu_option(
        request: MenuSelectionRequest,
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> MenuSelection:
        """Record a person's choice among a commercial menu's options
        (Phase 5, 5.7). Same authorization boundary as
        ``/v1/structure/numbers/confirm`` and ``/v1/structure/intake``.
        """
        if request.project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        return menu_selections.select(
            tenant_id=context.tenant_id, project_id=request.project_id, area=request.area,
            label=request.label, selected_by=context.user_id)

    @app.get("/v1/projects/{project_id}/workflows",
             response_model=list[PilotWorkflowOption])
    def project_workflows(project_id: str,
            context: UserContext = Depends(context_provider)) -> list[PilotWorkflowOption]:  # noqa: B008
        try:
            return workflow_options(project_id, context)
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
        """The synthetic clause variants, so a reviewer can see the whole band.

        Exposed read-only. Approving or changing a production variant is a counsel decision
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
        # Reset restores the synthetic queue. Against real work it would delete
        # artifacts and decisions of record and replace them with fixtures.
        refuse_in_production("Resetting the workspace")
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
        return ConsoleBootstrap(notice=fixture.notice, session=console_session(context),
            dashboard=DashboardSummary(
                pending_reviews=sum(item.status == ReviewStatus.PENDING
                                    for item in review_items),
                active_agents=len(agents),
                pilot_integrations=sum(item.status == "pilot" for item in integrations),
                integration_count=len(integrations)),
            clients=_visible_clients(fixture, context),
            projects=_visible_projects(fixture, context), agents=agents,
            security=security_settings.model_dump(mode="json"),
            integrations=integrations, microsoft=microsoft_broker.status(context.user_id),
            review_items=review_items, artifacts=artifacts,
            workflows=[option for project_id in sorted(context.project_ids)
                       for option in workflow_options(project_id, context)],
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
    app.state.structure_advisor = structure_advisor
    app.state.workspace = workspace
    app.state.audit_store = audit_store
    return app
