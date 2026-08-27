"""Persistent, measurable pilot-workspace artifacts for the synthetic console."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .identity import ZoneAccessError, ZonePolicy
from .numbers import DerivedNumber
from .router import Router
from .schemas import Evidence, RouteDecision, UserContext
from .sqlite_store import connect as sqlite_connect


class PilotWorkspaceError(ValueError):
    """Raised when a synthetic workspace request violates a pilot control."""


class PilotTaskRequest(BaseModel):
    project_id: str = Field(min_length=1)
    workflow: str = Field(min_length=1)
    task: str = Field(default="", max_length=2000)
    source_mode: Literal["deterministic", "live"] = "deterministic"


class PilotClaim(BaseModel):
    """A single material claim in a draft, with the evidence supporting it.

    ``severity`` and ``finding_type`` carry the specialist's own ranking through
    to the reviewer. Without them a Critical exposure and an incidental note are
    indistinguishable in the artifact, and a finding made *by absence* (a missing
    liability cap, an unstated insurance requirement) reads as though it were
    quoted from the document. Both default to the neutral value so existing
    fixtures and deterministic templates remain valid.
    """

    text: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    severity: Literal["critical", "material", "notable"] = "notable"
    finding_type: Literal["stated", "absent", "inconsistent"] = "stated"


class PilotTemplate(BaseModel):
    project_id: str
    title: str
    workflow: str
    agent_id: str
    required_reviewer_group: str | None = None
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1)
    claims: list[PilotClaim] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    freshness_days: int = Field(default=45, ge=1)
    reconciliation_conflict: str | None = None


class PilotWorkflowOption(BaseModel):
    project_id: str
    workflow: str
    title: str
    agent_id: str


class LiveDraftContent(BaseModel):
    """Structured draft returned by a live specialist run.

    ``unknowns`` and ``escalations`` exist because the specialist prompts require
    every draft to say what it could not establish and what must go to a
    qualified professional. With nowhere to put them, both were being flattened
    into free-text risks and lost to the reviewer.
    """

    summary: str
    recommendations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    claims: list[PilotClaim] = Field(min_length=1)


class ArtifactCitation(BaseModel):
    claim: str
    source_ids: list[str] = Field(min_length=1)
    severity: Literal["critical", "material", "notable"] = "notable"
    finding_type: Literal["stated", "absent", "inconsistent"] = "stated"


class ArtifactMetric(BaseModel):
    name: str
    value: float
    unit: str
    target: str
    passed: bool


class ArtifactEvent(BaseModel):
    event: str
    actor: str
    occurred_at: datetime
    detail: str


class PilotArtifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    created_by: str
    task: str
    title: str
    workflow: str
    agent_id: str
    route: RouteDecision
    source_mode: Literal["deterministic", "live"] = "deterministic"
    status: str = "draft"
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    # Set when the artifact carries a full document (an assembled agreement)
    # rather than an analysis. Rendered verbatim in the review body so a
    # reviewer reads the operative language, not a description of it.
    body_markdown: str | None = None
    evidence: list[Evidence] = Field(min_length=1)
    citations: list[ArtifactCitation] = Field(default_factory=list)
    refusal_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Populated only by structure recommendations (Phase 3). Every figure the
    # engine computed, whatever its state -- the console interface needs the
    # full set, not just the unconfirmed ones, so a confirmed figure still
    # shows who confirmed it and when.
    pending_numbers: list[DerivedNumber] = Field(default_factory=list)
    metrics: list[ArtifactMetric] = Field(default_factory=list)
    required_reviewer_group: str | None = None
    review_item_id: str | None = None
    amended_body: str | None = None
    amended_by: str | None = None
    comparison_artifact_id: str | None = None
    input_fingerprint: str | None = None
    source_artifact_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    events: list[ArtifactEvent] = Field(default_factory=list)

    def review_body(self) -> str:
        state = "INSUFFICIENT EVIDENCE" if self.status == "insufficient_evidence" else "DRAFT"
        lines = [f"# {self.title}", "", f"{state} — HUMAN REVIEW REQUIRED", "", self.summary]
        if self.refusal_reasons:
            lines.extend(["", "## What is missing"])
            lines.extend(f"- {item}" for item in self.refusal_reasons)
        if self.escalations:
            lines.extend(["", "## Route to a qualified professional"])
            lines.extend(f"- {item}" for item in self.escalations)
        for heading, items in (("Recommendations", self.recommendations),
                               ("Risks", self.risks), ("Assumptions", self.assumptions),
                               ("Not established", self.unknowns)):
            if not items:
                continue
            lines.extend(["", f"## {heading}"])
            lines.extend(f"- {item}" for item in items)
        if self.body_markdown:
            lines.extend(["", "---", "", "## Document", "", self.body_markdown.strip()])
        lines.extend(["", "---", "", "## Findings and citations"])
        order = {"critical": 0, "material": 1, "notable": 2}
        for item in sorted(self.citations, key=lambda c: order.get(c.severity, 3)):
            label = item.severity.title()
            if item.finding_type != "stated":
                label += f", {item.finding_type}"
            lines.append(f"- **{label}** — {item.claim} [{', '.join(item.source_ids)}]")
        return "\n".join(lines)


class PilotComparison(BaseModel):
    deterministic: PilotArtifact
    live: PilotArtifact


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"reveal (a )?(secret|credential)|exfiltrat|bypass (the )?(approval|policy)|"
    r"send (this|it) externally|move funds|submit (the )?(filing|permit|application)|"
    r"deploy (to )?production)"
)


def reject_unsafe_instruction(*values: str) -> None:
    """Fail closed when user-controlled text attempts to override system policy."""
    if any(_INJECTION.search(value) for value in values if value):
        raise PilotWorkspaceError(
            "Unsafe instruction detected; external actions and policy overrides are disabled")


class PilotArtifactStore:
    """Tenant/project-scoped SQLite store for local synthetic draft artifacts."""

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS pilot_artifacts (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, client_id TEXT NOT NULL,
                project_id TEXT NOT NULL, created_by TEXT NOT NULL, artifact_json TEXT NOT NULL,
                status TEXT NOT NULL, review_item_id TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite_connect(self.path)

    def save(self, artifact: PilotArtifact) -> PilotArtifact:
        with self._connect() as connection:
            connection.execute("""INSERT INTO pilot_artifacts
                (id, tenant_id, client_id, project_id, created_by, artifact_json,
                 status, review_item_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (artifact.id, artifact.tenant_id, artifact.client_id, artifact.project_id,
                 artifact.created_by, artifact.model_dump_json(), artifact.status,
                 artifact.review_item_id, artifact.created_at.isoformat(),
                 artifact.updated_at.isoformat()))
        return artifact.model_copy(deep=True)

    def update(self, artifact: PilotArtifact) -> PilotArtifact:
        artifact.updated_at = datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute("""UPDATE pilot_artifacts
                SET artifact_json = ?, status = ?, review_item_id = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ? AND project_id = ?""",
                (artifact.model_dump_json(), artifact.status, artifact.review_item_id,
                 artifact.updated_at.isoformat(), artifact.id, artifact.tenant_id,
                 artifact.project_id))
        if cursor.rowcount != 1:
            raise KeyError(artifact.id)
        return artifact.model_copy(deep=True)

    def list(self, *, context: UserContext, project_id: str | None = None) -> list[PilotArtifact]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT artifact_json FROM pilot_artifacts WHERE tenant_id = ? "
                "ORDER BY created_at DESC", (context.tenant_id,)).fetchall()
        artifacts = [PilotArtifact.model_validate_json(row["artifact_json"]) for row in rows]
        return [item for item in artifacts if item.project_id in context.project_ids
                and (project_id is None or item.project_id == project_id)]

    def get(self, artifact_id: str, *, context: UserContext) -> PilotArtifact:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT artifact_json FROM pilot_artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        artifact = PilotArtifact.model_validate_json(row["artifact_json"])
        if artifact.tenant_id != context.tenant_id or artifact.project_id not in context.project_ids:
            raise PermissionError("Artifact is outside authenticated scope")
        return artifact

    def reset_synthetic(self, *, context: UserContext) -> int:
        if context.tenant_id != "tenant-synthetic":
            raise PermissionError("Workspace reset is limited to the synthetic tenant")
        if not context.project_ids:
            return 0
        placeholders = ",".join("?" for _ in context.project_ids)
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM pilot_artifacts WHERE tenant_id = ? "
                f"AND project_id IN ({placeholders})",
                (context.tenant_id, *sorted(context.project_ids)))
        return cursor.rowcount


class PilotWorkspace:
    """Runs controlled fixture workflows, with one optional flag-gated drafting source."""

    def __init__(self, *, templates: list[PilotTemplate], store: PilotArtifactStore,
                 project_clients: dict[str, str], router: Router | None = None,
                 external_action_counter: Callable[[UserContext, str], int] | None = None,
                 live_drafter: Callable[[PilotTaskRequest, PilotTemplate], LiveDraftContent] | None = None,
                 live_enabled: bool = False,
                 zone_policy: ZonePolicy | None = None) -> None:
        self.templates = {(item.project_id, item.workflow): item for item in templates}
        if len(self.templates) != len(templates):
            raise ValueError("Pilot workflow templates must be unique per project and workflow")
        self.store = store
        self.project_clients = project_clients
        self.router = router or Router()
        self.external_action_counter = external_action_counter or (lambda _context, _project: 0)
        self.live_drafter = live_drafter
        self.live_enabled = live_enabled
        self.zone_policy = zone_policy

    def workflows(self, *, project_id: str, context: UserContext) -> list[PilotWorkflowOption]:
        if project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        return [PilotWorkflowOption(project_id=item.project_id, workflow=item.workflow,
                                    title=item.title, agent_id=item.agent_id)
                for item in self.templates.values() if item.project_id == project_id]

    def run(self, request: PilotTaskRequest, *, context: UserContext) -> PilotArtifact:
        if request.project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        reject_unsafe_instruction(request.task)
        try:
            template = self.templates[(request.project_id, request.workflow)]
            client_id = self.project_clients[request.project_id]
        except KeyError as exc:
            raise PilotWorkspaceError("No synthetic template exists for that project workflow") from exc
        if request.source_mode == "live":
            if not self.live_enabled:
                raise PilotWorkspaceError("Live pilot drafting is disabled")
            if template.workflow != "contract_review":
                raise PilotWorkspaceError("Live pilot drafting is limited to contract review")
            if self.live_drafter is None:
                raise PilotWorkspaceError("Live pilot drafting is not configured")
            content = self.live_drafter(request, template)
        else:
            content = LiveDraftContent(summary=template.summary,
                recommendations=template.recommendations, risks=template.risks,
                assumptions=template.assumptions, claims=template.claims,
                unknowns=template.unknowns, escalations=template.escalations)

        route = self.router.route(request.task or template.title)
        now = datetime.now(UTC)
        known_sources = {item.source_id for item in template.evidence}
        evidence_by_id = {item.source_id: item for item in template.evidence}
        valid_citations = []
        zone_refusals: list[str] = []
        for claim in content.claims:
            if not claim.source_ids or not set(claim.source_ids) <= known_sources:
                continue
            try:
                if self.zone_policy:
                    for source_id in claim.source_ids:
                        evidence = evidence_by_id[source_id]
                        if evidence.source_project_id:
                            self.zone_policy.check_citation(
                                source_project_id=evidence.source_project_id,
                                artifact_project_id=request.project_id,
                                artifact_client_id=client_id)
            except ZoneAccessError as exc:
                zone_refusals.append(f"Citation {source_id!r} crossed a trust boundary: {exc}")
                continue
            valid_citations.append(ArtifactCitation(
                claim=claim.text, source_ids=claim.source_ids,
                severity=claim.severity, finding_type=claim.finding_type))
        coverage = 100 * len(valid_citations) / len(content.claims)
        retrieved = [datetime.fromisoformat(item.retrieved_at) for item in template.evidence
                     if item.retrieved_at]
        evidence_age_days = max(((now - item).total_seconds() / 86400 for item in retrieved),
                                default=9999)
        evidence_current = evidence_age_days <= template.freshness_days
        external_actions = self.external_action_counter(context, request.project_id)
        refusal_reasons = []
        refusal_reasons.extend(zone_refusals)
        if coverage < 100:
            refusal_reasons.append("One or more material claims lack valid source citations.")
        if not evidence_current:
            refusal_reasons.append(
                f"Evidence is older than the {template.freshness_days}-day freshness limit.")
        if template.reconciliation_conflict:
            refusal_reasons.append(template.reconciliation_conflict)
        metrics = [
            ArtifactMetric(name="citation_coverage", value=round(coverage, 1), unit="percent",
                           target="100%", passed=coverage == 100),
            ArtifactMetric(name="external_actions", value=external_actions, unit="actions",
                           target="0", passed=external_actions == 0),
            ArtifactMetric(name="oldest_evidence_age", value=round(evidence_age_days, 1),
                           unit="days", target=f"{template.freshness_days} days or less",
                           passed=evidence_current),
        ]
        status = "insufficient_evidence" if refusal_reasons else "draft"
        artifact = PilotArtifact(tenant_id=context.tenant_id, client_id=client_id,
            project_id=request.project_id, created_by=context.user_id,
            task=request.task.strip() or template.title, title=template.title,
            workflow=template.workflow, agent_id=template.agent_id, route=route,
            source_mode=request.source_mode, status=status, summary=content.summary,
            recommendations=content.recommendations, risks=content.risks,
            assumptions=content.assumptions, unknowns=content.unknowns,
            escalations=content.escalations, evidence=template.evidence,
            citations=valid_citations, refusal_reasons=refusal_reasons,
            metrics=metrics, required_reviewer_group=template.required_reviewer_group,
            events=[ArtifactEvent(event="refusal_created" if refusal_reasons else "draft_created",
                actor=context.user_id, occurred_at=now,
                detail=f"{request.source_mode.title()} synthetic workflow completed")])
        return self.store.save(artifact)

    def compare(self, request: PilotTaskRequest, *, context: UserContext) -> PilotComparison:
        deterministic = self.run(request.model_copy(update={"source_mode": "deterministic"}),
                                 context=context)
        live = self.run(request.model_copy(update={"source_mode": "live"}), context=context)
        deterministic.comparison_artifact_id = live.id
        live.comparison_artifact_id = deterministic.id
        self.store.update(deterministic)
        self.store.update(live)
        return PilotComparison(deterministic=deterministic, live=live)
