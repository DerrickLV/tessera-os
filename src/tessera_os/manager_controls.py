"""Shared offline controls for draft-only specialist manager foundations."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from .knowledge import ScopeDenied
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class ManagerPolicyError(ValueError):
    """Raised when source data violates a specialist control policy."""


class ExternalActionDisabled(PermissionError):
    """Raised for every external or approval-gated action in these phases."""


class ProjectAccess(BaseModel):
    tenant_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)

    def authorize(self, *, context: UserContext, client_id: str, project_id: str) -> None:
        if project_id not in context.project_ids:
            raise ScopeDenied(f"User is not authorized for project {project_id!r}")
        if (self.tenant_id, self.client_id, self.project_id) != (
            context.tenant_id, client_id, project_id
        ):
            raise ScopeDenied("Record is outside the authorized tenant/client/project scope")


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"exfiltrat|reveal (a )?(secret|credential)|sign (the )?agreement|send (the )?(report|"
    r"redline|notice)|direct (the )?(contractor|consultant)|approve (the )?(change|term)|"
    r"move (the )?funds|guarantee (a )?return)"
)


def injection_warnings(notes: list[str]) -> list[str]:
    return ["Retrieved content contained possible prompt injection; ignored."
            for note in notes if _INJECTION.search(note)]


def evidence_map(evidence: list[Evidence]) -> dict[str, Evidence]:
    ids = [item.source_id for item in evidence]
    if len(ids) != len(set(ids)):
        raise ManagerPolicyError("Evidence source IDs must be unique")
    return {item.source_id: item for item in evidence}


def validate_citations(source_ids: list[str], known: dict[str, Evidence], *, label: str) -> None:
    if not source_ids:
        raise ManagerPolicyError(f"{label} lacks cited evidence")
    missing = set(source_ids).difference(known)
    if missing:
        raise ManagerPolicyError(f"{label} cites missing evidence: {sorted(missing)}")


def is_stale(item: Evidence, *, now: datetime, freshness_days: int) -> bool:
    if not item.retrieved_at:
        return True
    try:
        retrieved = datetime.fromisoformat(item.retrieved_at)
    except ValueError:
        return True
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=UTC)
    return retrieved < now - timedelta(days=freshness_days)


class DraftManagerBase:
    workflow: str
    reviewer_group: str | None = None

    def __init__(self, *, review_queue: ReviewQueue, freshness_days: int = 45) -> None:
        self.review_queue = review_queue
        self.freshness_days = freshness_days

    def _submit(self, *, context: UserContext, tenant_id: str, project_id: str,
                title: str, body: str, evidence: list[Evidence]) -> ReviewItem:
        if tenant_id != context.tenant_id or project_id not in context.project_ids:
            raise ScopeDenied("Draft is outside the authenticated scope")
        return self.review_queue.submit(tenant_id=tenant_id, project_id=project_id,
            created_by=context.user_id, workflow=self.workflow, title=title,
            body=body, evidence=evidence,
            required_reviewer_group=self.reviewer_group)

    @staticmethod
    def request_external_action(action: str) -> None:
        raise ExternalActionDisabled(
            f"{action} is disabled; create an internal draft for accountable human review"
        )
