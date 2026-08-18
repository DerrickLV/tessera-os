"""Central runtime authorization policy for every Tessera request."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .knowledge import ScopeDenied
from .registry import AgentDefinition
from .schemas import UserContext
from .settings import SecuritySettings, load_security_settings


class Environment(StrEnum):
    TEST = "test"
    SANDBOX = "sandbox"
    PILOT = "pilot"
    PRODUCTION = "production"


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class RuntimeAction(BaseModel):
    tenant_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    environment: Environment
    target: str | None = None
    approval_id: str | None = None


class PolicyDecision(BaseModel):
    outcome: PolicyOutcome
    reason: str
    required_approver_group: str | None = None


class PolicyGateway:
    """Fail-closed action authorization independent of model instructions."""

    safe_actions = frozenset({"read", "search", "summarize", "calculate", "draft", "route"})
    forbidden_actions = frozenset({
        "delete_record", "deploy", "execute_contract", "field_directive", "move_funds",
        "permission_change", "production_write", "secret_change", "signature_request",
    })

    def __init__(self, settings: SecuritySettings | None = None) -> None:
        self.settings = settings or load_security_settings()
        authorization = self.settings.authorization
        if authorization.central_policy_gateway != "required" or not authorization.fail_closed:
            raise ValueError("Central policy gateway must be required and fail closed")
        self.safe_actions = self.safe_actions | frozenset(self.settings.approval_tiers.none)
        self.forbidden_actions = (
            self.forbidden_actions | frozenset(self.settings.approval_tiers.executive)
        )

    def evaluate(self, request: RuntimeAction, *, context: UserContext,
                 agent: AgentDefinition) -> PolicyDecision:
        if request.tenant_id != context.tenant_id or request.user_id != context.user_id:
            raise ScopeDenied("Runtime action identity does not match authenticated context")
        if request.project_id not in context.project_ids:
            raise ScopeDenied("Runtime action is outside the authenticated project scope")
        if request.agent_id != agent.id:
            return PolicyDecision(outcome=PolicyOutcome.DENY,
                                  reason="Agent identity does not match routed specialist")
        if request.action in self.forbidden_actions:
            return PolicyDecision(outcome=PolicyOutcome.DENY,
                                  reason="Action is prohibited by central policy")
        if request.environment == Environment.PRODUCTION and request.action not in self.safe_actions:
            return PolicyDecision(outcome=PolicyOutcome.DENY,
                                  reason="Production writes are disabled")
        if request.action in agent.approval_required:
            if not request.approval_id:
                return PolicyDecision(outcome=PolicyOutcome.REQUIRE_APPROVAL,
                    reason="Exact action requires accountable approval",
                    required_approver_group=f"{agent.id}_approver")
            return PolicyDecision(outcome=PolicyOutcome.DENY,
                reason="Approval identifiers require gateway verification before execution")
        if request.action not in self.safe_actions:
            return PolicyDecision(outcome=PolicyOutcome.DENY,
                                  reason="Action is not on the safe-action allowlist")
        return PolicyDecision(outcome=PolicyOutcome.ALLOW,
                              reason="Read-only or draft action is allowed")
