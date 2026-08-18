"""Shared domain contracts for every Tessera agent."""

from datetime import UTC, datetime
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


class UserContext(BaseModel):
    """Authenticated identity and immutable authorization boundary."""

    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    project_ids: frozenset[str] = Field(default_factory=frozenset)
    group_ids: frozenset[str] = Field(default_factory=frozenset)


class SourceDocument(BaseModel):
    """Normalized read-only document with source ACLs retained verbatim."""

    source_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str
    web_url: str | None = None
    modified_at: datetime | None = None
    allowed_user_ids: frozenset[str] = Field(default_factory=frozenset)
    allowed_group_ids: frozenset[str] = Field(default_factory=frozenset)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    source_id: str
    title: str
    excerpt: str
    locator: str | None = None
    modified_at: datetime | None = None


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReviewItem(BaseModel):
    id: str
    tenant_id: str
    project_id: str | None = None
    created_by: str
    workflow: str
    title: str
    body: str
    evidence: list[Evidence] = Field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
