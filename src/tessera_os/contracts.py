"""Offline, cited, draft-only Contract Manager foundation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
    is_stale,
    validate_citations,
)
from .schemas import Evidence, ReviewItem, UserContext


class ContractRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContractClause(BaseModel):
    id: str
    topic: str
    text: str
    locator: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class PlaybookRule(BaseModel):
    id: str
    topic: str
    approved_position: str
    fallback_language: str
    maximum_risk: ContractRisk
    approved: bool = False
    source_ids: list[str] = Field(min_length=1)


class ContractDataset(BaseModel):
    id: str
    title: str
    access: ProjectAccess
    version: int = Field(ge=1)
    parties: list[str] = Field(min_length=2)
    effective_date: str | None = None
    clauses: list[ContractClause]
    playbook_version: int = Field(ge=1)
    playbook_rules: list[PlaybookRule]
    evidence: list[Evidence]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def citations_exist(self) -> ContractDataset:
        known = evidence_map(self.evidence)
        for item in [*self.clauses, *self.playbook_rules]:
            validate_citations(item.source_ids, known, label=item.id)
        return self


class ClauseIssue(BaseModel):
    clause_id: str
    topic: str
    risk: ContractRisk
    comparison: str
    fallback_language: str
    legal_uncertainty: str
    clause_locator: str
    source_ids: list[str]


class ContractDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    status: str = "draft"
    issues: list[ClauseIssue]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContractLibrary:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str, int], ContractDataset] = {}

    def add(self, *records: ContractDataset) -> None:
        for record in records:
            access = record.access
            key = (access.tenant_id, access.client_id, access.project_id,
                   record.id, record.version)
            if key in self._records:
                raise ManagerPolicyError("Conflicting contract version")
            self._records[key] = record.model_copy(deep=True)

    def get(self, contract_id: str, version: int, *, context: UserContext,
            client_id: str, project_id: str) -> ContractDataset:
        if project_id not in context.project_ids:
            record = None
        else:
            record = self._records.get((context.tenant_id, client_id, project_id,
                                        contract_id, version))
        if record is None:
            from .knowledge import ScopeDenied
            raise ScopeDenied("Contract is outside the authorized scope")
        record.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return record.model_copy(deep=True)


class ContractManager(DraftManagerBase):
    workflow = "contract_review"

    def __init__(self, *, library: ContractLibrary, review_queue, freshness_days: int = 45) -> None:
        super().__init__(review_queue=review_queue, freshness_days=freshness_days)
        self.library = library

    def analyze(self, *, context: UserContext, client_id: str, project_id: str,
                contract_id: str, version: int, now: datetime | None = None) -> ContractDraft:
        now = now or datetime.now(UTC)
        record = self.library.get(contract_id, version, context=context,
                                  client_id=client_id, project_id=project_id)
        known = evidence_map(record.evidence)
        if any(is_stale(known[sid], now=now, freshness_days=self.freshness_days)
               for item in record.clauses for sid in item.source_ids):
            raise ManagerPolicyError("Contract evidence is stale")
        rules = {item.topic: item for item in record.playbook_rules if item.approved}
        issues = []
        for clause in record.clauses:
            rule = rules.get(clause.topic)
            if rule is None:
                issues.append(ClauseIssue(clause_id=clause.id, topic=clause.topic,
                    risk=ContractRisk.HIGH, comparison="No approved playbook rule",
                    fallback_language="Qualified legal review required before drafting fallback.",
                    legal_uncertainty="No approved position is available.",
                    clause_locator=clause.locator, source_ids=clause.source_ids))
                continue
            issues.append(ClauseIssue(clause_id=clause.id, topic=clause.topic,
                risk=rule.maximum_risk, comparison=f"Compare with: {rule.approved_position}",
                fallback_language=rule.fallback_language,
                legal_uncertainty="Decision support only; qualified counsel must review.",
                clause_locator=clause.locator,
                source_ids=sorted(set(clause.source_ids + rule.source_ids))))
        return ContractDraft(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=f"Contract review — {record.title}", issues=issues,
            evidence=record.evidence, warnings=injection_warnings(record.retrieved_notes))

    def submit_for_review(self, draft: ContractDraft, *, context: UserContext) -> ReviewItem:
        return self._submit(context=context, tenant_id=draft.tenant_id,
            project_id=draft.project_id, title=draft.title,
            body=self.to_markdown(draft), evidence=draft.evidence)

    @staticmethod
    def to_markdown(draft: ContractDraft) -> str:
        lines = [f"# {draft.title}", "", "DRAFT — LEGAL REVIEW REQUIRED", ""]
        lines.extend(f"- {item.topic} ({item.risk}) at {item.clause_locator}: "
                     f"{item.comparison} [{', '.join(item.source_ids)}]"
                     for item in draft.issues)
        return "\n".join(lines)


def load_synthetic_contract_library(path: Path | str) -> ContractLibrary:
    data = json.loads(Path(path).read_text())
    library = ContractLibrary()
    library.add(*(ContractDataset(**item) for item in data["contracts"]))
    return library
