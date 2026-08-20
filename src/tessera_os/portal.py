"""Production-facing, invite-only Tessera portal API."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .identity import BASE_GROUP, EntraGroupMap
from .integrations import MicrosoftGraphReader
from .microsoft import (
    AllowlistedSharePointReader,
    MicrosoftConfigurationError,
    MicrosoftConnectionBroker,
    MicrosoftConnectionStatus,
    MicrosoftPilotSettings,
)
from .paths import project_root
from .schemas import SourceDocument, UserContext
from .sessions import COOKIE_NAME, SESSION_HOURS, SessionCodec

logger = logging.getLogger(__name__)


class PortalProject(BaseModel):
    id: str
    name: str
    summary: str = ""


class PortalSettings(BaseModel):
    app_url: HttpUrl
    api_url: HttpUrl
    session_secret: str = Field(min_length=32)
    # An explicit allowlist of Entra object IDs. The cap is a guard against a
    # runaway configuration, not the access control -- the enumeration is.
    #
    # It was 1, which deadlocked the system. Every drafted agreement and
    # structure recommendation carries a required_reviewer_group, and the review
    # queue refuses to let the author disposition their own item ("Qualified
    # reviews require separation of duties"). With a single permitted user, the
    # only person who could draft was categorically barred from accepting, so
    # nothing could ever be approved -- the system could produce work and never
    # move it forward. The ceiling now permits both partners plus outside
    # counsel and one co-advisor, which is the review population the governance
    # model actually describes.
    allowed_user_ids: frozenset[str] = Field(min_length=1, max_length=5)
    projects: dict[str, PortalProject] = Field(min_length=1)
    data_dir: Path = Path("/var/data/tessera")

    @model_validator(mode="after")
    def production_https(self) -> PortalSettings:
        if self.app_url.scheme != "https" or self.api_url.scheme != "https":
            raise ValueError("Production portal URLs must use HTTPS")
        return self

    @classmethod
    def from_environment(cls) -> PortalSettings:
        import json

        try:
            catalog = json.loads(os.environ["TESSERA_PROJECT_CATALOG"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError("TESSERA_PROJECT_CATALOG must contain valid JSON") from exc
        allowed = frozenset(filter(None,
            (item.strip() for item in os.getenv("TESSERA_ALLOWED_USER_IDS", "").split(","))))
        return cls(app_url=os.environ["TESSERA_APP_URL"],
            api_url=os.environ["TESSERA_API_URL"],
            session_secret=os.environ["TESSERA_SESSION_SECRET"],
            allowed_user_ids=allowed, projects=catalog,
            data_dir=Path(os.getenv("TESSERA_PORTAL_DATA_DIR", "/var/data/tessera")))


class PortalSession(BaseModel):
    user_id: str
    tenant_id: str
    display_name: str
    projects: list[PortalProject]
    microsoft_connected: bool


def create_portal_app(*, portal_settings: PortalSettings | None = None,
                      microsoft_settings: MicrosoftPilotSettings | None = None,
                      broker: MicrosoftConnectionBroker | None = None) -> FastAPI:
    settings = portal_settings or PortalSettings.from_environment()
    microsoft = microsoft_settings or MicrosoftPilotSettings.from_environment()
    if not microsoft.enabled:
        raise RuntimeError("Production portal requires the Microsoft integration")
    if set(settings.projects) != set(microsoft.project_resources):
        raise RuntimeError("Portal projects and Microsoft project mappings must match exactly")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    broker = broker or MicrosoftConnectionBroker(settings=microsoft,
        cache_path=settings.data_dir / "microsoft-token-cache.bin")
    codec = SessionCodec(settings.session_secret)
    group_map = EntraGroupMap.from_environment()
    sharepoint = AllowlistedSharePointReader(settings=microsoft,
        graph_factory=lambda provider: MicrosoftGraphReader(provider),
        token_provider=broker.token)

    app = FastAPI(title="Tessera Portal API", version="0.9.0",
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,
        allowed_hosts=[settings.api_url.host, "testserver"])
    app.add_middleware(CORSMiddleware, allow_origins=[str(settings.app_url).rstrip("/")],
        allow_credentials=True, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Correlation-ID"])

    def current_context(
        tessera_session: Annotated[str | None, Cookie()] = None,
    ) -> UserContext:
        if not tessera_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Microsoft sign-in is required")
        claims = codec.decode(tessera_session)
        if claims["sub"] not in settings.allowed_user_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="User is not invited to this Tessera portal")
        # Groups were resolved from Entra membership at sign-in and travel in
        # the signed session. Every privileged group — qualified_counsel,
        # tessera_partner — exists only if an administrator mapped the Entra
        # group and the user's token carried it. Nothing here may add one.
        mapped = claims.get("grp") or []
        return UserContext(tenant_id=claims["tid"], user_id=claims["sub"],
                           project_ids=set(settings.projects),
                           group_ids={BASE_GROUP, *mapped})

    def current_claims(
        tessera_session: Annotated[str | None, Cookie()] = None,
    ) -> dict[str, str]:
        if not tessera_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Microsoft sign-in is required")
        claims = codec.decode(tessera_session)
        if claims["sub"] not in settings.allowed_user_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="User is not invited to this Tessera portal")
        return claims

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        # Same-origin delivery means the policy ships with the response rather
        # than with a static host's configuration. 'self' covers the API because
        # the UI is served from this application.
        #
        # A mounted sub-application that already set its own policy keeps it.
        # This middleware wraps the mount, so overwriting unconditionally would
        # impose the portal's script-src on the console -- whose interface is a
        # single inline script with its fonts embedded as data URIs, and which
        # would have rendered as a blank page with nothing but console errors to
        # explain why. Each application states the policy its own interface
        # needs; neither silently relaxes the other's.
        response.headers.setdefault("Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self' https://login.microsoftonline.com")
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        # ``console`` reports the state and never the reason. A degraded
        # deployment should announce itself -- a portal serving happily with no
        # console is otherwise indistinguishable from a healthy one until
        # somebody clicks through and gets a 404. But /health is unauthenticated,
        # and the underlying error carries a filesystem path. The reason stays in
        # the logs and on app.state where it needs a session to reach.
        console_state = "unavailable" if getattr(app.state, "console_error", "") else "ok"
        return {"status": "ok", "mode": "production", "writes": "disabled",
                "console": console_state}

    @app.get("/v1/auth/microsoft/start")
    def start_sign_in() -> RedirectResponse:
        try:
            return RedirectResponse(broker.begin(), status_code=status.HTTP_302_FOUND)
        except MicrosoftConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=str(exc)) from exc

    @app.get("/v1/integrations/microsoft/callback")
    def finish_sign_in(request: Request) -> RedirectResponse:
        try:
            identity = broker.complete(dict(request.query_params))
        except MicrosoftConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if identity.user_id not in settings.allowed_user_ids:
            broker.disconnect()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Microsoft user is not invited to Tessera")
        token = codec.issue(user_id=identity.user_id, tenant_id=identity.tenant_id,
                            display_name=identity.display_name or identity.username or "Tessera User",
                            group_ids=sorted(group_map.resolve(identity.entra_group_ids)))
        response = RedirectResponse(str(settings.app_url), status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(COOKIE_NAME, token, httponly=True, secure=True,
            samesite="lax", max_age=SESSION_HOURS * 60 * 60, path="/")
        return response

    @app.post("/v1/auth/logout")
    def logout() -> RedirectResponse:
        broker.disconnect()
        response = RedirectResponse(str(settings.app_url), status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.get("/v1/session", response_model=PortalSession)
    def session(claims: dict[str, str] = Depends(current_claims)) -> PortalSession:  # noqa: B008
        return PortalSession(user_id=claims["sub"], tenant_id=claims["tid"],
            display_name=claims.get("name") or "Authorized Microsoft User",
            projects=list(settings.projects.values()),
            microsoft_connected=broker.status().connected)

    @app.get("/v1/projects", response_model=list[PortalProject])
    def projects(context: UserContext = Depends(current_context)) -> list[PortalProject]:  # noqa: B008
        return [project for project in settings.projects.values()
                if project.id in context.project_ids]

    @app.get("/v1/projects/{project_id}/documents", response_model=list[SourceDocument])
    def project_documents(project_id: str,
            context: UserContext = Depends(current_context)) -> list[SourceDocument]:  # noqa: B008
        try:
            return sharepoint.project_documents(context=context, project_id=project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except MicrosoftConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.get("/v1/integrations/microsoft/status", response_model=MicrosoftConnectionStatus)
    def integration_status(
        context: UserContext = Depends(current_context),  # noqa: B008
    ) -> MicrosoftConnectionStatus:
        del context
        return broker.status()

    # --- the interface ------------------------------------------------------
    #
    # The portal UI is served by this application rather than by a separate
    # static host. That is a security decision, not a convenience one: the
    # session cookie is issued SameSite=Lax, and a browser will not attach a Lax
    # cookie to a cross-origin request. Split the UI onto another domain and
    # sign-in appears to succeed while every subsequent call arrives
    # unauthenticated -- a failure that reports itself as a permissions problem.
    # One origin removes the whole class of error.
    web_dir = project_root() / "web"
    portal_page = web_dir / "tessera-portal.html"

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        if not portal_page.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Portal interface is not installed in this image")
        return FileResponse(portal_page)

    if web_dir.is_dir():
        # Mounted last: a StaticFiles mount at "/" would otherwise shadow every
        # route declared above it.
        app.mount("/ui", StaticFiles(directory=web_dir), name="ui")
        # The portal page requests "/assets/portal.js". Serving the directory
        # only under "/ui" left that script 404ing, so the page rendered its
        # loading state, never ran its boot(), and never gave the sign-in link
        # an href -- a dead page served by a healthy container.
        assets_dir = web_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # --- the console --------------------------------------------------------
    #
    # Mounted here rather than deployed beside the portal, for the same reason
    # the portal UI is served from this app: the session cookie is SameSite=Lax
    # and a browser will not send it cross-origin. A console on its own hostname
    # would sign in successfully and then receive 401 on every request.
    #
    # It runs on the portal's own identity, projects, and data directory, so
    # there is one invitation list, one project catalog, and one durable store
    # rather than two that can disagree.
    from .console import (
        ConsoleProject,
        PortalContextProvider,
        create_console_app,
        production_console_fixture,
    )

    console_projects = [
        ConsoleProject(
            id=project.id,
            client_id=(microsoft.project_resources[project.id].client_id
                       if project.id in microsoft.project_resources
                       and microsoft.project_resources[project.id].client_id
                       else "tessera-internal"),
            name=project.name, phase="active", status="active",
            manager_agent_id="structure_manager",
            summary=project.summary or "Tessera engagement workspace")
        for project in settings.projects.values()
    ]
    # The console is mounted if it can be built, and the portal survives if it
    # cannot. This is not defensive habit: a locked SQLite file under the
    # console's data directory took the whole portal down once, because the
    # console is constructed here. Nobody could sign in, reach SharePoint, or
    # read the review queue -- over a subsystem none of those depend on. The
    # blast radius of a console fault is now the console.
    #
    # It fails loudly rather than quietly. /health reports the state and never
    # the reason, because it is unauthenticated and the reason carries a
    # filesystem path -- so the reason goes to the log, with a traceback. The
    # first version of this recorded it only on app.state, where nothing could
    # reach it, and diagnosing the very failure it was written for required
    # opening a shell inside the running container.
    console_app = None
    console_error = ""
    try:
        console_app = create_console_app(
            data_dir=settings.data_dir / "console",
            ui_path=web_dir / "tessera-console.html",
            microsoft_broker=broker,
            fixture=production_console_fixture(console_projects),
            context_provider=PortalContextProvider(
                codec=codec, project_ids=set(settings.projects),
                allowed_user_ids=settings.allowed_user_ids),
        )
        app.mount("/console", console_app, name="console")
    # Broad on purpose: the portal must outlive any one subsystem, and a
    # console that cannot build is not a reason nobody can sign in.
    except Exception as exc:
        console_error = f"{type(exc).__name__}: {exc}"
        logger.exception("Console unavailable; the portal is running without it")

    app.state.portal_settings = settings
    app.state.microsoft_broker = broker
    app.state.console_app = console_app
    app.state.console_error = console_error
    return app


app = None  # Deployment imports create_portal_app as a factory.
