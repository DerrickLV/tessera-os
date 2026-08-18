"""Offline, synthetic, draft-only Development Manager control plane."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .knowledge import ScopeDenied
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class DevelopmentPolicyError(ValueError):
    """Raised when development data violates a control-plane policy."""


class BaselineChangeDenied(PermissionError):
    """Raised when a caller attempts to modify an approved baseline."""


class ExternalDevelopmentActionDisabled(PermissionError):
    """Raised for submissions, directions, and other external actions."""


class RecordStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class ApprovalKind(StrEnum):
    ENTITLEMENT = "entitlement"
    PERMIT = "permit"
    UTILITY = "utility"
    AGENCY = "agency"


class GateRecommendation(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RegisterKind(StrEnum):
    RISK = "risk"
    ISSUE = "issue"
    DECISION = "decision"
    DEPENDENCY = "dependency"


class DevelopmentAccess(BaseModel):
    tenant_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)

    def permits(self, *, context: UserContext, client_id: str, project_id: str) -> bool:
        return (
            self.tenant_id == context.tenant_id
            and self.client_id == client_id
            and self.project_id == project_id
            and project_id in context.project_ids
        )


class DevelopmentProject(BaseModel):
    id: str
    name: str
    client_id: str
    description: str
    current_phase: str
    access: DevelopmentAccess


class DevelopmentMilestone(BaseModel):
    id: str
    name: str
    planned_date: date
    forecast_date: date | None = None
    actual_date: date | None = None
    status: RecordStatus = RecordStatus.NOT_STARTED
    dependencies: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)


class DevelopmentSchedule(BaseModel):
    id: str
    version: int = Field(ge=1)
    project_id: str
    status: str = "draft"
    is_baseline: bool = False
    approved_by: str | None = None
    effective_date: date
    milestones: list[DevelopmentMilestone]
    source_id: str

    @model_validator(mode="after")
    def unique_milestones(self) -> DevelopmentSchedule:
        ids = [item.id for item in self.milestones]
        if len(ids) != len(set(ids)):
            raise ValueError("A schedule version cannot contain conflicting milestone IDs")
        if self.is_baseline and (self.status != "approved" or not self.approved_by):
            raise ValueError("A baseline must be approved and identify its approver")
        return self


class BudgetLine(BaseModel):
    id: str
    category: str
    amount: Decimal = Field(ge=0)
    committed: Decimal = Field(default=Decimal(0), ge=0)
    forecast: Decimal = Field(ge=0)
    actual: Decimal = Field(default=Decimal(0), ge=0)
    source_ids: list[str] = Field(min_length=1)


class DevelopmentBudget(BaseModel):
    id: str
    version: int = Field(ge=1)
    project_id: str
    status: str = "draft"
    is_baseline: bool = False
    approved_by: str | None = None
    effective_date: date
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    lines: list[BudgetLine]
    source_id: str

    @model_validator(mode="after")
    def unique_lines(self) -> DevelopmentBudget:
        ids = [item.id for item in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("A budget version cannot contain conflicting line IDs")
        if self.is_baseline and (self.status != "approved" or not self.approved_by):
            raise ValueError("A baseline must be approved and identify its approver")
        return self


class ApprovalMatrixItem(BaseModel):
    id: str
    kind: ApprovalKind
    name: str
    agency: str
    owner: str
    status: RecordStatus
    target_date: date | None = None
    expiration_date: date | None = None
    dependencies: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class Constraint(BaseModel):
    id: str
    description: str
    owner: str
    status: RecordStatus
    impact: str
    due_date: date | None = None
    source_ids: list[str] = Field(min_length=1)


class Consultant(BaseModel):
    id: str
    organization: str
    discipline: str
    responsibility: str
    owner: str


class ConsultantDeliverable(BaseModel):
    id: str
    consultant_id: str
    name: str
    responsible: str
    accountable: str
    due_date: date
    status: RecordStatus
    dependencies: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)


class RegisterEntry(BaseModel):
    id: str
    kind: RegisterKind
    title: str
    description: str
    owner: str
    status: RecordStatus
    impact: str | None = None
    probability: str | None = None
    due_date: date | None = None
    dependencies: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(min_length=1)


class GateCriterion(BaseModel):
    id: str
    description: str
    required_status: RecordStatus = RecordStatus.COMPLETE
    record_ids: list[str] = Field(min_length=1)


class StageGate(BaseModel):
    id: str
    name: str
    sequence: int = Field(ge=1)
    criteria: list[GateCriterion] = Field(min_length=1)
    approver_role: str


class DevelopmentDataset(BaseModel):
    project: DevelopmentProject
    schedules: list[DevelopmentSchedule]
    budgets: list[DevelopmentBudget]
    approvals: list[ApprovalMatrixItem]
    constraints: list[Constraint]
    consultants: list[Consultant]
    deliverables: list[ConsultantDeliverable]
    registers: list[RegisterEntry]
    gates: list[StageGate]
    evidence: list[Evidence]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> DevelopmentDataset:
        known_evidence = {item.source_id for item in self.evidence}
        cited: list[Any] = [
            *(m for schedule in self.schedules for m in schedule.milestones),
            *(line for budget in self.budgets for line in budget.lines),
            *self.approvals,
            *self.constraints,
            *self.deliverables,
            *self.registers,
        ]
        missing = {sid for item in cited for sid in item.source_ids if sid not in known_evidence}
        if missing:
            raise ValueError(f"Citations reference missing evidence: {sorted(missing)}")
        unsupported = [item.id for item in cited
                       if getattr(item, "status", None)
                       in {RecordStatus.COMPLETE, RecordStatus.APPROVED}
                       and not item.source_ids]
        if unsupported:
            raise ValueError(f"Completed or approved status lacks evidence: {unsupported}")
        project_id = self.project.id
        if any(item.project_id != project_id for item in [*self.schedules, *self.budgets]):
            raise ValueError("Schedule or budget belongs to a different project")
        return self


class ScheduleVariance(BaseModel):
    milestone_id: str
    baseline_date: date
    current_date: date
    variance_days: int


class BudgetVariance(BaseModel):
    line_id: str
    baseline_amount: Decimal
    forecast_amount: Decimal
    variance_amount: Decimal
    variance_percent: Decimal | None


class GateCriterionResult(BaseModel):
    criterion_id: str
    met: bool
    explanation: str
    source_ids: list[str]


class GateReadiness(BaseModel):
    gate_id: str
    recommendation: GateRecommendation
    evaluated_at: datetime
    criteria: list[GateCriterionResult]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)
    status: str = "draft"


class DevelopmentControlDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    status: str = "draft"
    schedule_variances: list[ScheduleVariance]
    budget_variances: list[BudgetVariance]
    gate_readiness: GateReadiness
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"exfiltrat|reveal (a )?(secret|credential)|submit (the |this )?(permit|application)|"
    r"direct (the )?consultant|approve (the )?(gate|baseline))"
)


class DevelopmentLibrary:
    """Versioned, immutable in-memory development records with fail-closed scope."""

    def __init__(self) -> None:
        self._datasets: dict[tuple[str, str, str], DevelopmentDataset] = {}

    def add(self, dataset: DevelopmentDataset) -> None:
        access = dataset.project.access
        key = (access.tenant_id, access.client_id, access.project_id)
        if key in self._datasets:
            raise DevelopmentPolicyError("Project dataset already exists; records are immutable")
        self._assert_versions(dataset.schedules, "schedule")
        self._assert_versions(dataset.budgets, "budget")
        self._datasets[key] = dataset.model_copy(deep=True)

    @staticmethod
    def _assert_versions(records: list[Any], label: str) -> None:
        keys = [(item.id, item.version) for item in records]
        if len(keys) != len(set(keys)):
            raise DevelopmentPolicyError(f"Conflicting {label} versions are not allowed")
        baselines: dict[str, int] = {}
        for item in records:
            if item.is_baseline:
                baselines[item.id] = baselines.get(item.id, 0) + 1
        if any(count > 1 for count in baselines.values()):
            raise DevelopmentPolicyError(f"Multiple approved {label} baselines conflict")

    def get(self, *, context: UserContext, client_id: str,
            project_id: str) -> DevelopmentDataset:
        if project_id not in context.project_ids:
            raise ScopeDenied(f"User is not authorized for project {project_id!r}")
        key = (context.tenant_id, client_id, project_id)
        try:
            dataset = self._datasets[key]
        except KeyError as exc:
            raise ScopeDenied("Development records are outside the authorized scope") from exc
        if not dataset.project.access.permits(
            context=context, client_id=client_id, project_id=project_id
        ):
            raise ScopeDenied("Development records are outside the authorized scope")
        return dataset.model_copy(deep=True)

    @staticmethod
    def replace_approved_baseline(*_: Any, **__: Any) -> None:
        raise BaselineChangeDenied(
            "Approved baselines are immutable; create a reviewed change request and new version"
        )


class DevelopmentManager:
    def __init__(self, *, library: DevelopmentLibrary, review_queue: ReviewQueue,
                 freshness_days: int = 45) -> None:
        self.library = library
        self.review_queue = review_queue
        self.freshness_days = freshness_days

    @staticmethod
    def _baseline_and_current(records: list[Any], label: str) -> tuple[Any, Any]:
        baselines = [item for item in records if item.is_baseline]
        if len(baselines) != 1:
            raise DevelopmentPolicyError(f"Exactly one approved {label} baseline is required")
        baseline = baselines[0]
        current = max(records, key=lambda item: item.version)
        return baseline, current

    @classmethod
    def schedule_variance(cls, schedules: list[DevelopmentSchedule]) -> list[ScheduleVariance]:
        baseline, current = cls._baseline_and_current(schedules, "schedule")
        current_items = {item.id: item for item in current.milestones}
        if set(current_items) != {item.id for item in baseline.milestones}:
            raise DevelopmentPolicyError("Current schedule conflicts with baseline milestone set")
        return [ScheduleVariance(
            milestone_id=item.id,
            baseline_date=item.planned_date,
            current_date=(current_items[item.id].actual_date
                          or current_items[item.id].forecast_date
                          or current_items[item.id].planned_date),
            variance_days=((current_items[item.id].actual_date
                            or current_items[item.id].forecast_date
                            or current_items[item.id].planned_date) - item.planned_date).days,
        ) for item in baseline.milestones]

    @classmethod
    def budget_variance(cls, budgets: list[DevelopmentBudget]) -> list[BudgetVariance]:
        baseline, current = cls._baseline_and_current(budgets, "budget")
        current_lines = {item.id: item for item in current.lines}
        if set(current_lines) != {item.id for item in baseline.lines}:
            raise DevelopmentPolicyError("Current budget conflicts with baseline line set")
        results = []
        for item in baseline.lines:
            forecast = current_lines[item.id].forecast
            variance = forecast - item.amount
            percent = (variance / item.amount * Decimal(100)) if item.amount else None
            results.append(BudgetVariance(line_id=item.id, baseline_amount=item.amount,
                forecast_amount=forecast, variance_amount=variance,
                variance_percent=percent.quantize(Decimal("0.01")) if percent is not None else None))
        return results

    def evaluate_gate(self, dataset: DevelopmentDataset, gate_id: str, *,
                      now: datetime | None = None) -> GateReadiness:
        now = now or datetime.now(UTC)
        try:
            gate = next(item for item in dataset.gates if item.id == gate_id)
        except StopIteration as exc:
            raise DevelopmentPolicyError(f"Unknown stage gate {gate_id!r}") from exc
        records = {item.id: item for item in [*dataset.approvals, *dataset.constraints,
                   *dataset.deliverables, *dataset.registers]}
        evidence = {item.source_id: item for item in dataset.evidence}
        used: set[str] = set()
        results = []
        stale = False
        missing = False
        for criterion in gate.criteria:
            referenced = [records.get(item_id) for item_id in criterion.record_ids]
            absent = [item_id for item_id, item in zip(criterion.record_ids, referenced) if item is None]
            source_ids = sorted({sid for item in referenced if item for sid in item.source_ids})
            used.update(source_ids)
            criterion_stale = any(self._is_stale(evidence.get(sid), now) for sid in source_ids)
            statuses_met = bool(referenced) and all(
                item is not None and item.status == criterion.required_status for item in referenced
            )
            has_evidence = bool(source_ids) and all(sid in evidence for sid in source_ids)
            met = statuses_met and has_evidence and not criterion_stale and not absent
            missing = missing or bool(absent) or not has_evidence
            stale = stale or criterion_stale
            reason = "criterion satisfied" if met else "criterion not satisfied"
            if absent:
                reason += f"; missing records: {', '.join(absent)}"
            if not has_evidence:
                reason += "; cited evidence is missing"
            if criterion_stale:
                reason += "; cited evidence is stale"
            results.append(GateCriterionResult(criterion_id=criterion.id, met=met,
                explanation=reason, source_ids=source_ids))
        recommendation = (GateRecommendation.INSUFFICIENT_EVIDENCE if missing or stale
                          else GateRecommendation.READY if all(item.met for item in results)
                          else GateRecommendation.NOT_READY)
        warnings = []
        if stale:
            warnings.append(f"Evidence older than {self.freshness_days} days cannot support readiness")
        return GateReadiness(gate_id=gate.id, recommendation=recommendation,
            evaluated_at=now, criteria=results, evidence=[evidence[sid] for sid in sorted(used)
            if sid in evidence], warnings=warnings)

    def create_control_draft(self, *, context: UserContext, client_id: str,
                             project_id: str, gate_id: str,
                             now: datetime | None = None) -> DevelopmentControlDraft:
        dataset = self.library.get(context=context, client_id=client_id, project_id=project_id)
        warnings = ["Retrieved content contained a possible prompt injection; ignored."
                    for note in dataset.retrieved_notes if _INJECTION.search(note)]
        return DevelopmentControlDraft(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=f"{dataset.project.name} development controls",
            schedule_variances=self.schedule_variance(dataset.schedules),
            budget_variances=self.budget_variance(dataset.budgets),
            gate_readiness=self.evaluate_gate(dataset, gate_id, now=now),
            evidence=dataset.evidence, warnings=warnings)

    def submit_for_review(self, draft: DevelopmentControlDraft, *,
                          context: UserContext) -> ReviewItem:
        if draft.tenant_id != context.tenant_id or draft.project_id not in context.project_ids:
            raise ScopeDenied("Development draft is outside the authenticated scope")
        return self.review_queue.submit(tenant_id=draft.tenant_id, project_id=draft.project_id,
            created_by=context.user_id, workflow="development_stage_gate_review",
            title=draft.title, body=self.to_markdown(draft), evidence=draft.evidence,
            required_reviewer_group="development_approver")

    def request_baseline_change(self, *, context: UserContext, client_id: str,
                                project_id: str, rationale: str) -> ReviewItem:
        dataset = self.library.get(context=context, client_id=client_id, project_id=project_id)
        return self.review_queue.submit(tenant_id=context.tenant_id, project_id=project_id,
            created_by=context.user_id, workflow="development_baseline_change_request",
            title=f"Baseline change request — {dataset.project.name}",
            body=f"DRAFT — NO BASELINE MODIFIED\n\nRationale: {rationale}", evidence=[],
            required_reviewer_group="development_approver")

    @staticmethod
    def request_external_action(action: str) -> None:
        raise ExternalDevelopmentActionDisabled(
            f"{action} is disabled in Phase 4A; submit a draft for accountable human review"
        )

    def _is_stale(self, evidence: Evidence | None, now: datetime) -> bool:
        if evidence is None or not evidence.retrieved_at:
            return True
        try:
            retrieved = datetime.fromisoformat(evidence.retrieved_at)
        except ValueError:
            return True
        if retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=UTC)
        return retrieved < now - timedelta(days=self.freshness_days)

    @staticmethod
    def to_markdown(draft: DevelopmentControlDraft) -> str:
        lines = [f"# {draft.title}", "", "DRAFT — HUMAN REVIEW REQUIRED", "",
                 "## Stage gate", f"- Recommendation: {draft.gate_readiness.recommendation}"]
        lines.extend(f"- {item.criterion_id}: {item.explanation} "
                     f"[{', '.join(item.source_ids)}]" for item in draft.gate_readiness.criteria)
        lines.extend(["", "## Schedule variance"])
        lines.extend(f"- {item.milestone_id}: {item.variance_days:+d} days"
                     for item in draft.schedule_variances)
        lines.extend(["", "## Budget variance"])
        lines.extend(f"- {item.line_id}: {item.variance_amount:+.2f} "
                     f"({item.variance_percent if item.variance_percent is not None else 'n/a'}%)"
                     for item in draft.budget_variances)
        lines.extend(["", "## Sources"])
        lines.extend(f"- [{item.source_id}] {item.title}" for item in draft.evidence)
        return "\n".join(lines)


def load_synthetic_development_library(path: Path | str) -> DevelopmentLibrary:
    data = json.loads(Path(path).read_text())
    library = DevelopmentLibrary()
    for item in data["projects"]:
        library.add(DevelopmentDataset(**item))
    return library
