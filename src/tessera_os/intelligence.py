"""Offline, allowlisted, cited Intelligence Agent foundation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .knowledge import ScopeDenied
from .manager_controls import ExternalActionDisabled, ManagerPolicyError, ProjectAccess
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class IntelligenceImpact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceKind(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    INTERNAL = "internal"


class MonitoredSource(BaseModel):
    id: str
    name: str
    kind: SourceKind
    locator: str = Field(pattern=r"^offline://[a-zA-Z0-9._/-]+$")
    topic: str
    max_age_hours: int = Field(ge=1, le=24 * 365)
    license_approved: bool = False
    owner: str
    access: ProjectAccess


class SourceSnapshot(BaseModel):
    source_id: str
    captured_at: datetime
    title: str
    content: str
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class IntelligenceFinding(BaseModel):
    id: str
    topic: str
    event: str
    interpretation: str
    scenarios: list[str] = Field(min_length=2)
    recommendation: str
    decision_relevance: str
    uncertainty: str
    impact: IntelligenceImpact
    source_ids: list[str] = Field(min_length=1)


class IntelligenceDataset(BaseModel):
    id: str
    title: str
    access: ProjectAccess
    sources: list[MonitoredSource]
    snapshots: list[SourceSnapshot]
    findings: list[IntelligenceFinding]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sources(self) -> IntelligenceDataset:
        source_ids = [item.id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Monitored source IDs must be unique")
        if any(not source.license_approved for source in self.sources):
            raise ValueError("Every monitored source must have an approved license")
        if any(source.access != self.access for source in self.sources):
            raise ValueError("Monitored source is outside the dataset scope")
        snapshot_ids = [item.source_id for item in self.snapshots]
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("A dataset may contain only one snapshot per source")
        known = set(source_ids)
        if missing := set(snapshot_ids).difference(known):
            raise ValueError(f"Snapshots reference unknown sources: {sorted(missing)}")
        for snapshot in self.snapshots:
            if hashlib.sha256(snapshot.content.encode()).hexdigest() != snapshot.content_digest:
                raise ValueError(f"Snapshot {snapshot.source_id!r} content digest does not match")
        for finding in self.findings:
            if missing := set(finding.source_ids).difference(snapshot_ids):
                raise ValueError(f"Finding {finding.id!r} cites missing snapshots: {sorted(missing)}")
            if (finding.impact in {IntelligenceImpact.HIGH, IntelligenceImpact.CRITICAL}
                    and len(set(finding.source_ids)) < 2):
                raise ValueError(f"High-impact finding {finding.id!r} requires corroboration")
            if (finding.impact in {IntelligenceImpact.HIGH, IntelligenceImpact.CRITICAL}
                    and len({self.sources[source_ids.index(source_id)].kind
                             for source_id in finding.source_ids}) < 2):
                raise ValueError(f"High-impact finding {finding.id!r} requires source diversity")
        return self


class SourceAssessment(BaseModel):
    source_id: str
    fresh: bool
    age_hours: int
    source_kind: SourceKind


class IntelligenceAlert(BaseModel):
    finding_id: str
    impact: IntelligenceImpact
    summary: str
    source_ids: list[str]
    human_review_required: bool = True


class IntelligenceBrief(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    as_of: datetime
    status: str = "draft"
    findings: list[IntelligenceFinding]
    source_assessments: list[SourceAssessment]
    alerts: list[IntelligenceAlert]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"publish (this|the brief)|send (this|the alert)|purchase (the )?source|exfiltrat)"
)


class IntelligenceLibrary:
    def __init__(self) -> None:
        self._datasets: dict[tuple[str, str, str, str], IntelligenceDataset] = {}

    def add(self, *items: IntelligenceDataset) -> None:
        for item in items:
            access = item.access
            key = (access.tenant_id, access.client_id, access.project_id, item.id)
            if key in self._datasets:
                raise ManagerPolicyError("Conflicting intelligence dataset")
            self._datasets[key] = item.model_copy(deep=True)

    def get(self, item_id: str, *, context: UserContext, client_id: str,
            project_id: str) -> IntelligenceDataset:
        if project_id not in context.project_ids:
            item = None
        else:
            item = self._datasets.get((context.tenant_id, client_id, project_id, item_id))
        if item is None:
            raise ScopeDenied("Intelligence dataset is outside the authorized scope")
        item.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return item.model_copy(deep=True)


class IntelligenceManager:
    def __init__(self, *, library: IntelligenceLibrary, review_queue: ReviewQueue) -> None:
        self.library, self.review_queue = library, review_queue

    def build_brief(self, *, context: UserContext, client_id: str, project_id: str,
                    dataset_id: str, now: datetime | None = None) -> IntelligenceBrief:
        now = now or datetime.now(UTC)
        dataset = self.library.get(dataset_id, context=context, client_id=client_id,
                                   project_id=project_id)
        sources = {item.id: item for item in dataset.sources}
        snapshots = {item.source_id: item for item in dataset.snapshots}
        assessments = []
        stale: set[str] = set()
        for source_id, snapshot in snapshots.items():
            age = max(0, int((now - snapshot.captured_at).total_seconds() // 3600))
            fresh = snapshot.captured_at >= now - timedelta(hours=sources[source_id].max_age_hours)
            assessments.append(SourceAssessment(source_id=source_id, fresh=fresh,
                age_hours=age, source_kind=sources[source_id].kind))
            if not fresh:
                stale.add(source_id)
        usable = [finding for finding in dataset.findings
                  if not set(finding.source_ids).intersection(stale)]
        alerts = [IntelligenceAlert(finding_id=item.id, impact=item.impact,
            summary=item.event, source_ids=item.source_ids) for item in usable
            if item.impact in {IntelligenceImpact.HIGH, IntelligenceImpact.CRITICAL}]
        evidence = [Evidence(source_id=snapshot.source_id, title=snapshot.title,
            locator=sources[snapshot.source_id].locator,
            excerpt=snapshot.content[:240], retrieved_at=snapshot.captured_at.isoformat())
            for snapshot in dataset.snapshots]
        warnings = [f"Stale sources excluded from supported findings: {', '.join(sorted(stale))}"] \
            if stale else []
        warnings.extend("Retrieved content contained possible prompt injection; ignored."
                        for note in dataset.retrieved_notes if _INJECTION.search(note))
        return IntelligenceBrief(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=dataset.title, as_of=now, findings=usable,
            source_assessments=assessments, alerts=alerts, evidence=evidence,
            warnings=warnings)

    def submit_for_review(self, brief: IntelligenceBrief, *, context: UserContext) -> ReviewItem:
        if brief.tenant_id != context.tenant_id or brief.project_id not in context.project_ids:
            raise ScopeDenied("Intelligence brief is outside the authenticated scope")
        return self.review_queue.submit(tenant_id=brief.tenant_id, project_id=brief.project_id,
            created_by=context.user_id, workflow="intelligence_brief_review", title=brief.title,
            body=self.to_markdown(brief), evidence=brief.evidence)

    @staticmethod
    def request_external_action(action: str) -> None:
        raise ExternalActionDisabled(f"{action} is disabled; intelligence remains an internal draft")

    @staticmethod
    def to_markdown(brief: IntelligenceBrief) -> str:
        lines = [f"# {brief.title}", "", "DRAFT — HUMAN REVIEW REQUIRED",
                 f"As of: {brief.as_of.isoformat()}", ""]
        for item in brief.findings:
            lines.extend([f"## {item.topic}", f"- Event: {item.event}",
                f"- Interpretation: {item.interpretation}",
                f"- Uncertainty: {item.uncertainty}",
                f"- Decision relevance: {item.decision_relevance}",
                f"- Sources: [{', '.join(item.source_ids)}]", ""])
        return "\n".join(lines)


def load_synthetic_intelligence_library(path: Path | str) -> IntelligenceLibrary:
    data = json.loads(Path(path).read_text())
    library = IntelligenceLibrary()
    library.add(*(IntelligenceDataset(**item) for item in data["intelligence"]))
    return library
