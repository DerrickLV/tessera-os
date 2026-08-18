"""Offline, isolated, PR-only Codex Engineering Agent foundation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .knowledge import ScopeDenied
from .manager_controls import ExternalActionDisabled, ManagerPolicyError, ProjectAccess
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class GateDecision(StrEnum):
    READY_FOR_PR_REVIEW = "ready_for_pr_review"
    BLOCKED = "blocked"


class WorkspaceDefinition(BaseModel):
    id: str
    repository: str
    access: ProjectAccess
    base_commit: str = Field(pattern=r"^[a-f0-9]{7,40}$")
    branch: str = Field(pattern=r"^agent/[a-z0-9][a-z0-9-]*$")
    isolated_root: str = Field(pattern=r"^sandbox://workspaces/[a-zA-Z0-9._/-]+$")
    allowed_paths: list[str] = Field(min_length=1)
    production_config_paths: list[str] = Field(default_factory=list)
    dependency_changes_allowed: bool = False
    deployment_allowed: bool = False

    @model_validator(mode="after")
    def safe_paths(self) -> WorkspaceDefinition:
        for value in [*self.allowed_paths, *self.production_config_paths]:
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Workspace paths must be repository-relative and traversal-free")
        if self.deployment_allowed:
            raise ValueError("Deployment cannot be enabled in the Phase 6 foundation")
        return self


class ProposedFileChange(BaseModel):
    path: str
    purpose: str
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def relative_path(self) -> ProposedFileChange:
        parsed = PurePosixPath(self.path)
        if parsed.is_absolute() or ".." in parsed.parts:
            raise ValueError("Change path must be repository-relative and traversal-free")
        return self


class CheckEvidence(BaseModel):
    id: str
    command: str
    passed: bool
    output_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    completed_at: datetime
    source_ids: list[str] = Field(min_length=1)


class EngineeringChangeSet(BaseModel):
    id: str
    title: str
    access: ProjectAccess
    workspace_id: str
    acceptance_criteria: list[str] = Field(min_length=1)
    changes: list[ProposedFileChange]
    checks: list[CheckEvidence]
    migration_plan: str
    rollback_plan: str
    release_notes: str
    dependency_changes: list[str] = Field(default_factory=list)
    production_config_changes: list[str] = Field(default_factory=list)
    destructive_operations: list[str] = Field(default_factory=list)
    evidence: list[Evidence]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_exists(self) -> EngineeringChangeSet:
        known = {item.source_id for item in self.evidence}
        cited = [*self.changes, *self.checks]
        if missing := {source for item in cited for source in item.source_ids if source not in known}:
            raise ValueError(f"Engineering change cites missing evidence: {sorted(missing)}")
        return self


class ReleaseGateResult(BaseModel):
    decision: GateDecision
    reasons: list[str]
    pr_required: bool = True
    deployment_allowed: bool = False


class EngineeringPacket(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    status: str = "draft"
    workspace: WorkspaceDefinition
    change_set: EngineeringChangeSet
    gate: ReleaseGateResult
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"exfiltrat|reveal (a )?(secret|credential)|deploy (to )?production|skip (the )?(test|review)|"
    r"delete (the )?(repository|branch)|add (the )?dependency)"
)


class EngineeringLibrary:
    def __init__(self) -> None:
        self._workspaces: dict[tuple[str, str, str, str], WorkspaceDefinition] = {}
        self._changes: dict[tuple[str, str, str, str], EngineeringChangeSet] = {}

    def add(self, workspace: WorkspaceDefinition, change_set: EngineeringChangeSet) -> None:
        if workspace.access != change_set.access or workspace.id != change_set.workspace_id:
            raise ManagerPolicyError("Workspace and change set scope do not match")
        access = workspace.access
        workspace_key = (access.tenant_id, access.client_id, access.project_id, workspace.id)
        change_key = (access.tenant_id, access.client_id, access.project_id, change_set.id)
        if workspace_key in self._workspaces or change_key in self._changes:
            raise ManagerPolicyError("Conflicting engineering workspace or change set")
        self._workspaces[workspace_key] = workspace.model_copy(deep=True)
        self._changes[change_key] = change_set.model_copy(deep=True)

    def get(self, workspace_id: str, change_id: str, *, context: UserContext,
            client_id: str, project_id: str) -> tuple[WorkspaceDefinition, EngineeringChangeSet]:
        key = (context.tenant_id, client_id, project_id)
        workspace = self._workspaces.get((*key, workspace_id))
        change = self._changes.get((*key, change_id))
        if project_id not in context.project_ids or workspace is None or change is None:
            raise ScopeDenied("Engineering records are outside the authorized scope")
        workspace.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return workspace.model_copy(deep=True), change.model_copy(deep=True)


class EngineeringManager:
    def __init__(self, *, library: EngineeringLibrary, review_queue: ReviewQueue) -> None:
        self.library, self.review_queue = library, review_queue

    def prepare_packet(self, *, context: UserContext, client_id: str, project_id: str,
                       workspace_id: str, change_id: str) -> EngineeringPacket:
        workspace, change = self.library.get(workspace_id, change_id, context=context,
            client_id=client_id, project_id=project_id)
        reasons = []
        for item in change.changes:
            if not any(_within(item.path, allowed) for allowed in workspace.allowed_paths):
                reasons.append(f"Change outside allowed paths: {item.path}")
            if any(_within(item.path, protected) for protected in workspace.production_config_paths):
                reasons.append(f"Production configuration change prohibited: {item.path}")
        if change.dependency_changes and not workspace.dependency_changes_allowed:
            reasons.append("Dependency changes require separate approval")
        if change.production_config_changes:
            reasons.append("Production configuration changes are prohibited")
        if change.destructive_operations:
            reasons.append("Destructive operations are prohibited")
        if not change.checks or any(not item.passed for item in change.checks):
            reasons.append("All required CI and acceptance checks must pass")
        gate = ReleaseGateResult(decision=(GateDecision.BLOCKED if reasons
            else GateDecision.READY_FOR_PR_REVIEW), reasons=reasons)
        warnings = ["Repository content contained possible prompt injection; ignored."
                    for note in change.retrieved_notes if _INJECTION.search(note)]
        return EngineeringPacket(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=change.title, workspace=workspace,
            change_set=change, gate=gate, evidence=change.evidence, warnings=warnings)

    def submit_for_review(self, packet: EngineeringPacket, *,
                          context: UserContext) -> ReviewItem:
        if packet.tenant_id != context.tenant_id or packet.project_id not in context.project_ids:
            raise ScopeDenied("Engineering packet is outside the authenticated scope")
        return self.review_queue.submit(tenant_id=packet.tenant_id, project_id=packet.project_id,
            created_by=context.user_id, workflow="engineering_pr_review", title=packet.title,
            body=self.to_markdown(packet), evidence=packet.evidence,
            required_reviewer_group="engineering_reviewer")

    @staticmethod
    def request_repository_or_release_action(action: str) -> None:
        raise ExternalActionDisabled(
            f"{action} is disabled; Phase 6 produces a PR-only internal change packet"
        )

    @staticmethod
    def to_markdown(packet: EngineeringPacket) -> str:
        lines = [f"# {packet.title}", "", "DRAFT — PR REVIEW REQUIRED", "",
                 f"- Base commit: {packet.workspace.base_commit}",
                 f"- Branch: {packet.workspace.branch}",
                 f"- Gate: {packet.gate.decision}", "", "## Changes"]
        lines.extend(f"- {item.path}: {item.purpose} [{', '.join(item.source_ids)}]"
                     for item in packet.change_set.changes)
        lines.extend(["", "## Checks"])
        lines.extend(f"- {item.command}: {'pass' if item.passed else 'fail'} "
                     f"[{', '.join(item.source_ids)}]" for item in packet.change_set.checks)
        return "\n".join(lines)


def _within(path: str, allowed: str) -> bool:
    candidate, root = PurePosixPath(path), PurePosixPath(allowed)
    return candidate == root or root in candidate.parents


def load_synthetic_engineering_library(path: Path | str) -> EngineeringLibrary:
    data = json.loads(Path(path).read_text())
    library = EngineeringLibrary()
    for item in data["engineering"]:
        library.add(WorkspaceDefinition(**item["workspace"]),
                    EngineeringChangeSet(**item["change_set"]))
    return library
