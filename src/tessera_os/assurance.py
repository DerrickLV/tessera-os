"""Deterministic Phase 6 regression gates for prompts, models, integrations, and policy."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .knowledge import ScopeDenied
from .manager_controls import ExternalActionDisabled, ManagerPolicyError, ProjectAccess
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class ArtifactKind(StrEnum):
    PROMPT = "prompt"
    MODEL = "model"
    INTEGRATION = "integration"
    POLICY = "policy"


class EvaluationDecision(StrEnum):
    PASS = "pass"
    BLOCK = "block"


class EvaluationMetrics(BaseModel):
    accuracy: float = Field(ge=0, le=1)
    citation_correctness: float = Field(ge=0, le=1)
    unsupported_claim_rate: float = Field(ge=0, le=1)
    latency_ms: int = Field(ge=0)
    cost_units: float = Field(ge=0)


class SecurityResults(BaseModel):
    cross_project_isolation: bool
    prompt_injection: bool
    approval_bypass: bool
    over_permission: bool


class EvaluationSnapshot(BaseModel):
    artifact_id: str
    kind: ArtifactKind
    version: str
    evaluated_at: datetime
    metrics: EvaluationMetrics
    security: SecurityResults
    case_count: int = Field(ge=1)
    evidence_ids: list[str] = Field(min_length=1)


class EvaluationPolicy(BaseModel):
    minimum_accuracy: float = Field(ge=0, le=1)
    minimum_citation_correctness: float = Field(ge=0, le=1)
    maximum_unsupported_claim_rate: float = Field(ge=0, le=1)
    maximum_latency_regression_percent: float = Field(ge=0)
    maximum_cost_regression_percent: float = Field(ge=0)
    cadence_days: int = Field(ge=1, le=365)
    minimum_cases: int = Field(ge=1)


class AssuranceDataset(BaseModel):
    id: str
    title: str
    access: ProjectAccess
    baseline: EvaluationSnapshot
    candidate: EvaluationSnapshot
    policy: EvaluationPolicy
    evidence: list[Evidence]

    @model_validator(mode="after")
    def matching_artifacts_and_evidence(self) -> AssuranceDataset:
        if (self.baseline.artifact_id, self.baseline.kind) != (
                self.candidate.artifact_id, self.candidate.kind):
            raise ValueError("Baseline and candidate must evaluate the same artifact")
        if self.baseline.version == self.candidate.version:
            raise ValueError("Candidate version must differ from baseline")
        known = {item.source_id for item in self.evidence}
        cited = set(self.baseline.evidence_ids + self.candidate.evidence_ids)
        if missing := cited.difference(known):
            raise ValueError(f"Evaluation cites missing evidence: {sorted(missing)}")
        return self


class AssuranceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    status: str = "draft"
    artifact_id: str
    kind: ArtifactKind
    baseline_version: str
    candidate_version: str
    decision: EvaluationDecision
    reasons: list[str]
    next_evaluation_due: datetime
    evaluation_overdue: bool
    evidence: list[Evidence]


class AssuranceLibrary:
    def __init__(self) -> None:
        self._datasets: dict[tuple[str, str, str, str], AssuranceDataset] = {}

    def add(self, *items: AssuranceDataset) -> None:
        for item in items:
            access = item.access
            key = (access.tenant_id, access.client_id, access.project_id, item.id)
            if key in self._datasets:
                raise ManagerPolicyError("Conflicting assurance dataset")
            self._datasets[key] = item.model_copy(deep=True)

    def get(self, item_id: str, *, context: UserContext, client_id: str,
            project_id: str) -> AssuranceDataset:
        item = self._datasets.get((context.tenant_id, client_id, project_id, item_id))
        if project_id not in context.project_ids or item is None:
            raise ScopeDenied("Assurance dataset is outside the authorized scope")
        item.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return item.model_copy(deep=True)


class AssuranceManager:
    def __init__(self, *, library: AssuranceLibrary, review_queue: ReviewQueue) -> None:
        self.library, self.review_queue = library, review_queue

    def evaluate(self, *, context: UserContext, client_id: str, project_id: str,
                 dataset_id: str, now: datetime | None = None) -> AssuranceReport:
        now = now or datetime.now(UTC)
        item = self.library.get(dataset_id, context=context, client_id=client_id,
                                project_id=project_id)
        baseline, candidate, policy = item.baseline, item.candidate, item.policy
        reasons = []
        if candidate.case_count < policy.minimum_cases:
            reasons.append("Representative case count is below policy minimum")
        if candidate.metrics.accuracy < policy.minimum_accuracy:
            reasons.append("Accuracy is below policy threshold")
        if candidate.metrics.citation_correctness < policy.minimum_citation_correctness:
            reasons.append("Citation correctness is below policy threshold")
        if candidate.metrics.unsupported_claim_rate > policy.maximum_unsupported_claim_rate:
            reasons.append("Unsupported-claim rate exceeds policy threshold")
        latency_regression = _percent_change(baseline.metrics.latency_ms,
                                             candidate.metrics.latency_ms)
        cost_regression = _percent_change(baseline.metrics.cost_units,
                                          candidate.metrics.cost_units)
        if latency_regression > policy.maximum_latency_regression_percent:
            reasons.append("Latency regression exceeds policy threshold")
        if cost_regression > policy.maximum_cost_regression_percent:
            reasons.append("Cost regression exceeds policy threshold")
        failed_security = [name for name, passed in candidate.security.model_dump().items()
                           if not passed]
        if failed_security:
            reasons.append(f"Security evaluations failed: {', '.join(sorted(failed_security))}")
        next_due = candidate.evaluated_at + timedelta(days=policy.cadence_days)
        if now > next_due:
            reasons.append("Evaluation cadence is overdue")
        return AssuranceReport(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=item.title, artifact_id=candidate.artifact_id,
            kind=candidate.kind, baseline_version=baseline.version,
            candidate_version=candidate.version,
            decision=EvaluationDecision.BLOCK if reasons else EvaluationDecision.PASS,
            reasons=reasons, next_evaluation_due=next_due,
            evaluation_overdue=now > next_due, evidence=item.evidence)

    def submit_for_review(self, report: AssuranceReport, *, context: UserContext) -> ReviewItem:
        if report.tenant_id != context.tenant_id or report.project_id not in context.project_ids:
            raise ScopeDenied("Assurance report is outside the authenticated scope")
        return self.review_queue.submit(tenant_id=report.tenant_id, project_id=report.project_id,
            created_by=context.user_id, workflow="artifact_assurance_review", title=report.title,
            body=self.to_markdown(report), evidence=report.evidence,
            required_reviewer_group="assurance_reviewer")

    @staticmethod
    def request_activation(action: str) -> None:
        raise ExternalActionDisabled(
            f"{action} is disabled; passing evaluation does not authorize activation"
        )

    @staticmethod
    def to_markdown(report: AssuranceReport) -> str:
        lines = [f"# {report.title}", "", "DRAFT — HUMAN REVIEW REQUIRED", "",
                 f"- Artifact: {report.artifact_id} ({report.kind})",
                 f"- Versions: {report.baseline_version} → {report.candidate_version}",
                 f"- Decision: {report.decision}",
                 f"- Next evaluation due: {report.next_evaluation_due.isoformat()}",
                 "", "## Reasons"]
        lines.extend(f"- {reason}" for reason in report.reasons or ["All configured gates passed."])
        return "\n".join(lines)


def _percent_change(baseline: float, candidate: float) -> float:
    if baseline == 0:
        return 0 if candidate == 0 else float("inf")
    return (candidate - baseline) / baseline * 100


def load_synthetic_assurance_library(path: Path | str) -> AssuranceLibrary:
    data = json.loads(Path(path).read_text())
    library = AssuranceLibrary()
    library.add(*(AssuranceDataset(**item) for item in data["assurance"]))
    return library
