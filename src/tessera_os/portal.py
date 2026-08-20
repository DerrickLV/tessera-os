"""Production-facing, invite-only Tessera portal API."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
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


class SessionCodec:
    issuer = "tessera-portal"
    audience = "tessera-portal-browser"

    def __init__(self, secret: str) -> None:
        self.secret = secret

    def issue(self, *, user_id: str, tenant_id: str, display_name: str,
              group_ids: list[str] | None = None) -> str:
        now = datetime.now(UTC)
        # ``grp`` carries the *mapped Tessera* groups, resolved once at sign-in
        # through the Entra group map. The browser can read the cookie's claims
        # but cannot mint them — the session is signed server-side.
        return jwt.encode({"sub": user_id, "tid": tenant_id, "name": display_name,
            "grp": sorted(group_ids or []),
            "iss": self.issuer, "aud": self.audience, "iat": now,
            "exp": now + timedelta(hours=8)}, self.secret, algorithm="HS256")

    def decode(self, token: str) -> dict[str, str]:
        try:
            return jwt.decode(token, self.secret, algorithms=["HS256"],
                issuer=self.issuer, audience=self.audience,
                options={"require": ["sub", "tid", "iss", "aud", "iat", "exp"]})
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Portal session is invalid or expired") from exc


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
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self' https://login.microsoftonline.com")
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "production", "writes": "disabled"}

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
        response.set_cookie("tessera_session", token, httponly=True, secure=True,
            samesite="lax", max_age=8 * 60 * 60, path="/")
        return response

    @app.post("/v1/auth/logout")
    def logout() -> RedirectResponse:
        broker.disconnect()
        response = RedirectResponse(str(settings.app_url), status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("tessera_session", path="/")
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

    app.state.portal_settings = settings
    app.state.microsoft_broker = broker
    return app


app = None  # Deployment imports create_portal_app as a factory.
