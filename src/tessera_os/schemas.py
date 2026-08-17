"""Shared domain contracts for every Tessera agent."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    APPROVED = "approved"
    REJECTED = "rejected"


class Evidence(BaseModel):
    source_id: str
    title: str
    locator: str | None = None
    excerpt: str | None = None
    retrieved_at: str | None = None


class AgentRequest(BaseModel):
    task: str = Field(min_length=1)
    project_id: str | None = None
    user_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=lambda: ["read", "draft"])


class AgentResponse(BaseModel):
    agent_id: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    proposed_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class RouteDecision(BaseModel):
    primary_agent: str
    supporting_agents: list[str] = Field(default_factory=list)
    matched_terms: dict[str, list[str]] = Field(default_factory=dict)
    rationale: str
