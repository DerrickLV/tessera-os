"""Authenticated FastAPI boundary for read-only Tessera routing."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, SecretStr, model_validator

from .orchestrator import TesseraOrchestrator, instructions_digest
from .policy import Environment, PolicyGateway, PolicyOutcome, RuntimeAction
from .registry import AgentRegistry
from .runtime_controls import RateLimiter, RateLimitExceeded, RuntimeAuditStore
from .schemas import AgentRequest, RouteDecision, UserContext


class AuthSettings(BaseModel):
    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    verification_key: SecretStr
    algorithm: str = "RS256"
    environment: Environment = Environment.PRODUCTION

    @model_validator(mode="after")
    def production_uses_asymmetric_signatures(self) -> AuthSettings:
        if self.environment == Environment.PRODUCTION and self.algorithm.startswith("HS"):
            raise ValueError("Production authentication requires asymmetric JWT signatures")
        if self.algorithm not in {"RS256", "RS384", "RS512", "ES256", "HS256"}:
            raise ValueError("JWT algorithm is not allowlisted")
        return self

    @classmethod
    def from_environment(cls) -> AuthSettings:
        required = {
            "issuer": os.getenv("TESSERA_OIDC_ISSUER"),
            "audience": os.getenv("TESSERA_OIDC_AUDIENCE"),
            "verification_key": os.getenv("TESSERA_OIDC_VERIFICATION_KEY"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing authentication settings: {', '.join(missing)}")
        return cls(**required, algorithm=os.getenv("TESSERA_OIDC_ALGORITHM", "RS256"),
                   environment=os.getenv("TESSERA_ENV", "production"))


class JWTAuthenticator:
    def __init__(self, settings: AuthSettings) -> None:
        self.settings = settings

    def authenticate(self, authorization: str | None) -> UserContext:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Bearer authentication is required")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = jwt.decode(token, self.settings.verification_key.get_secret_value(),
                algorithms=[self.settings.algorithm], audience=self.settings.audience,
                issuer=self.settings.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "tenant_id",
                                     "project_ids", "groups"]})
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Authentication token is invalid") from exc
        projects = claims.get("project_ids", [])
        groups = claims.get("groups", [])
        if not isinstance(projects, list) or not isinstance(groups, list):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Authentication claims are malformed")
        if "tessera_user" not in groups:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Tessera user role is required")
        return UserContext(tenant_id=claims["tenant_id"], user_id=claims["sub"],
                           project_ids=projects, group_ids=groups)

    def __call__(
        self, authorization: Annotated[str | None, Header()] = None,
    ) -> UserContext:
        return self.authenticate(authorization)


class RouteRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    project_id: str = Field(min_length=1)


class RouteEnvelope(BaseModel):
    correlation_id: str
    decision: RouteDecision
    policy_outcome: PolicyOutcome


def create_app(*, auth_settings: AuthSettings | None = None,
               audit_store: RuntimeAuditStore | None = None,
               rate_limiter: RateLimiter | None = None,
               registry: AgentRegistry | None = None,
               context_provider: Callable[..., UserContext] | None = None,
               enable_docs: bool = False) -> FastAPI:
    settings = auth_settings or AuthSettings.from_environment()
    authenticator = context_provider or JWTAuthenticator(settings)
    registry = registry or AgentRegistry()
    orchestrator = TesseraOrchestrator(registry=registry)
    gateway = PolicyGateway()
    audit_store = audit_store or RuntimeAuditStore("tessera-runtime.db")
    rate_limiter = rate_limiter or RateLimiter()
    app = FastAPI(title="Tessera OS", version="0.9.0",
                  docs_url="/api/docs" if enable_docs else None,
                  redoc_url=None,
                  openapi_url="/api/openapi.json" if enable_docs else None)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.environment.value,
                "writes": "disabled"}

    @app.post("/v1/route", response_model=RouteEnvelope)
    def route(request: RouteRequest,
              context: UserContext = Depends(authenticator),  # noqa: B008
              x_correlation_id: Annotated[str | None, Header()] = None) -> RouteEnvelope:
        try:
            rate_limiter.check(context=context)
        except RateLimitExceeded as exc:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=str(exc)) from exc
        if request.project_id not in context.project_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Project is outside authenticated scope")
        decision = orchestrator.plan(AgentRequest(task=request.task,
            project_id=request.project_id, user_id=context.user_id,
            allowed_actions=["route", "read", "draft"]))
        agent = registry.get(decision.primary_agent)
        policy = gateway.evaluate(RuntimeAction(tenant_id=context.tenant_id,
            project_id=request.project_id, user_id=context.user_id, agent_id=agent.id,
            action="route", environment=settings.environment), context=context, agent=agent)
        if policy.outcome != PolicyOutcome.ALLOW:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=policy.reason)
        try:
            correlation_id = str(UUID(x_correlation_id)) if x_correlation_id else str(uuid4())
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Correlation ID must be a UUID") from exc
        prompt_version = instructions_digest(agent)
        audit_store.record_trace(context=context, project_id=request.project_id,
            workflow="route", agent_id=agent.id, model_version=agent.model_profile,
            prompt_version=prompt_version, policy_outcome=policy.outcome.value,
            source_ids=[], correlation_id=correlation_id)
        return RouteEnvelope(correlation_id=correlation_id, decision=decision,
                             policy_outcome=policy.outcome)

    app.state.authenticator = authenticator
    app.state.audit_store = audit_store
    app.state.policy_gateway = gateway
    return app


app = None  # Production deployment must call create_app with managed configuration.
