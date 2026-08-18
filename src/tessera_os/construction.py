"""Offline, read-only, draft-only Construction Manager foundation."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .manager_controls import (
    DraftManagerBase,
    ManagerPolicyError,
    ProjectAccess,
    evidence_map,
    injection_warnings,
    validate_citations,
)
from .schemas import Evidence, ReviewItem, UserContext


class ItemStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    OVERDUE = "overdue"
    PENDING = "pending"


class SafetySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IMMINENT = "imminent"


class ConstructionMilestone(BaseModel):
    id: str
    name: str
    baseline_date: date
    forecast_date: date
    critical: bool = False
    source_ids: list[str] = Field(min_length=1)


class CostCode(BaseModel):
    id: str
    budget: Decimal = Field(ge=0)
    committed: Decimal = Field(ge=0)
    forecast: Decimal = Field(ge=0)
    actual: Decimal = Field(ge=0)
    source_ids: list[str] = Field(min_length=1)


class TrackingItem(BaseModel):
    id: str
    kind: str
    title: str
    status: ItemStatus
    due_date: date | None = None
    responsible: str
    source_ids: list[str] = Field(min_length=1)


class ChangeExposure(BaseModel):
    id: str
    description: str
    status: ItemStatus
    requested: Decimal = Field(ge=0)
    forecast: Decimal = Field(ge=0)
    approved: Decimal = Field(default=Decimal(0), ge=0)
    source_ids: list[str] = Field(min_length=1)


class SafetySignal(BaseModel):
    id: str
    description: str
    severity: SafetySeverity
    observed: bool
    asserted_by: str | None = None
    source_ids: list[str] = Field(min_length=1)


class ConstructionDataset(BaseModel):
    id: str
    name: str
    access: ProjectAccess
    schedule_version: int = Field(ge=1)
    cost_version: int = Field(ge=1)
    milestones: list[ConstructionMilestone]
    costs: list[CostCode]
    tracking: list[TrackingItem]
    changes: list[ChangeExposure]
    safety: list[SafetySignal]
    evidence: list[Evidence]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def citations_exist(self) -> ConstructionDataset:
        known = evidence_map(self.evidence)
        for item in [*self.milestones, *self.costs, *self.tracking,
                     *self.changes, *self.safety]:
            validate_citations(item.source_ids, known, label=item.id)
        return self


class ScheduleException(BaseModel):
    milestone_id: str
    variance_days: int
    critical: bool
    source_ids: list[str]


class CostForecast(BaseModel):
    cost_code_id: str
    variance: Decimal
    remaining: Decimal
    source_ids: list[str]


class ConstructionDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    status: str = "draft"
    schedule_exceptions: list[ScheduleException]
    cost_forecasts: list[CostForecast]
    open_tracking: list[TrackingItem]
    change_exposure: Decimal
    safety_signals: list[SafetySignal]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)


class ConstructionLibrary:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], ConstructionDataset] = {}

    def add(self, *records: ConstructionDataset) -> None:
        for record in records:
            access = record.access
            key = (access.tenant_id, access.client_id, access.project_id, record.id)
            if key in self._records:
                raise ManagerPolicyError("Conflicting construction control dataset")
            self._records[key] = record.model_copy(deep=True)

    def get(self, item_id: str, *, context: UserContext, client_id: str,
            project_id: str) -> ConstructionDataset:
        record = self._records.get((context.tenant_id, client_id, project_id, item_id))
        if record is None:
            from .knowledge import ScopeDenied
            raise ScopeDenied("Construction record is outside the authorized scope")
        record.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return record.model_copy(deep=True)


class ConstructionManager(DraftManagerBase):
    workflow = "construction_exception_review"
    reviewer_group = "construction_reviewer"

    def __init__(self, *, library: ConstructionLibrary, review_queue) -> None:
        super().__init__(review_queue=review_queue)
        self.library = library

    def dashboard(self, *, context: UserContext, client_id: str, project_id: str,
                  dataset_id: str) -> ConstructionDraft:
        record = self.library.get(dataset_id, context=context, client_id=client_id,
                                  project_id=project_id)
        schedule = [ScheduleException(milestone_id=item.id,
            variance_days=(item.forecast_date - item.baseline_date).days,
            critical=item.critical, source_ids=item.source_ids) for item in record.milestones]
        costs = [CostForecast(cost_code_id=item.id, variance=item.forecast - item.budget,
            remaining=item.forecast - item.actual, source_ids=item.source_ids)
                 for item in record.costs]
        exposure = sum((item.forecast - item.approved for item in record.changes
                        if item.status != ItemStatus.CLOSED), Decimal(0))
        return ConstructionDraft(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=f"Construction controls — {record.name}",
            schedule_exceptions=schedule, cost_forecasts=costs,
            open_tracking=[item for item in record.tracking if item.status != ItemStatus.CLOSED],
            change_exposure=exposure, safety_signals=record.safety,
            evidence=record.evidence, warnings=injection_warnings(record.retrieved_notes))

    def submit_for_review(self, draft: ConstructionDraft, *,
                          context: UserContext) -> ReviewItem:
        return self._submit(context=context, tenant_id=draft.tenant_id,
            project_id=draft.project_id, title=draft.title,
            body=self.to_markdown(draft), evidence=draft.evidence)

    def escalate_safety(self, draft: ConstructionDraft, *, context: UserContext) -> list[ReviewItem]:
        return [self._submit(context=context, tenant_id=draft.tenant_id,
            project_id=draft.project_id, title=f"URGENT SAFETY REVIEW — {signal.id}",
            body=f"HUMAN REVIEW REQUIRED\n\n{signal.description} "
                 f"[{', '.join(signal.source_ids)}]", evidence=draft.evidence)
            for signal in draft.safety_signals if signal.severity == SafetySeverity.IMMINENT]

    @staticmethod
    def to_markdown(draft: ConstructionDraft) -> str:
        lines = [f"# {draft.title}", "", "DRAFT — HUMAN REVIEW REQUIRED", "",
                 "## Schedule"]
        lines.extend(f"- {item.milestone_id}: {item.variance_days:+d} days "
                     f"[{', '.join(item.source_ids)}]" for item in draft.schedule_exceptions)
        lines.extend(["", "## Cost"])
        lines.extend(f"- {item.cost_code_id}: variance {item.variance:+.2f}; "
                     f"remaining {item.remaining:.2f} [{', '.join(item.source_ids)}]"
                     for item in draft.cost_forecasts)
        return "\n".join(lines)


def load_synthetic_construction_library(path: Path | str) -> ConstructionLibrary:
    data = json.loads(Path(path).read_text())
    library = ConstructionLibrary()
    library.add(*(ConstructionDataset(**item) for item in data["construction"]))
    return library
