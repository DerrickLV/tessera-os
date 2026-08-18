"""Synthetic, localhost-only operator console API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .paths import project_root
from .policy import Environment
from .registry import AgentDefinition, AgentRegistry
from .review import InvalidReviewTransition, ReviewAccessDenied, ReviewQueue
from .runtime_controls import RateLimiter, RuntimeAuditStore
from .schemas import ReviewItem, ReviewStatus, UserContext
from .service import AuthSettings, create_app
from .settings import SecuritySettings, load_integration_settings, load_security_settings

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


class ConsoleFixture(BaseModel):
    notice: str
    clients: list[ConsoleClient]
    projects: list[ConsoleProject]
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
    review_items: list[ReviewItem]


class ReviewDecision(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


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
                       ui_path: Path = DEFAULT_UI) -> FastAPI:
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
    review_queue = ReviewQueue(runtime_dir / "console-review.db")
    review_queue.seed(fixture.review_items)
    audit_store = RuntimeAuditStore(runtime_dir / "console-audit.db")
    registry = AgentRegistry()
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
            "script-src 'self' 'unsafe-inline'; connect-src 'self'"
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
                                           reason=request.reason)
            return review_queue.reject(item_id=item_id, context=context,
                                       reason=request.reason)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Review item was not found") from exc
        except ReviewAccessDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(exc)) from exc
        except InvalidReviewTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(exc)) from exc

    @app.post("/v1/reviews/{item_id}/accept", response_model=ReviewItem)
    def accept_review(item_id: str, request: ReviewDecision,
                      context: UserContext = Depends(context_provider)) -> ReviewItem:  # noqa: B008
        return decide(item_id, ReviewStatus.ACCEPTED, request, context)

    @app.post("/v1/reviews/{item_id}/reject", response_model=ReviewItem)
    def reject_review(item_id: str, request: ReviewDecision,
                      context: UserContext = Depends(context_provider)) -> ReviewItem:  # noqa: B008
        return decide(item_id, ReviewStatus.REJECTED, request, context)

    @app.get("/v1/console/bootstrap", response_model=ConsoleBootstrap)
    def bootstrap(
        context: UserContext = Depends(context_provider),  # noqa: B008
    ) -> ConsoleBootstrap:
        review_items = review_queue.list_items(context=context)
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
            integrations=integrations, review_items=review_items)

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
    return app
