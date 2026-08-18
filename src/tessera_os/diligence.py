"""Offline, reproducible, draft-only Due Diligence Manager foundation."""

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


class ClaimClassification(StrEnum):
    VERIFIED_FACT = "verified_fact"
    ALLEGATION = "allegation"
    OPEN_ITEM = "open_item"


class DiligenceClaim(BaseModel):
    id: str
    category: str
    statement: str
    classification: ClaimClassification
    material: bool = False
    confidence: float = Field(ge=0, le=1)
    source_ids: list[str] = Field(min_length=1)


class DiligenceDataset(BaseModel):
    id: str
    subject: str
    question: str
    access: ProjectAccess
    claims: list[DiligenceClaim]
    evidence: list[Evidence]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_claim_controls(self) -> DiligenceDataset:
        known = evidence_map(self.evidence)
        for claim in self.claims:
            if claim.category.casefold() in {
                "race", "ethnicity", "religion", "sex", "disability", "genetic information"
            }:
                raise ValueError("Protected-trait inference is prohibited")
            validate_citations(claim.source_ids, known, label=claim.id)
            if (claim.material and claim.classification == ClaimClassification.VERIFIED_FACT
                    and len(set(claim.source_ids)) < 2):
                raise ValueError(f"Material verified fact {claim.id!r} requires corroboration")
        return self


class DiligenceDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    subject: str
    question: str
    as_of: datetime
    status: str = "draft"
    verified_facts: list[DiligenceClaim]
    allegations: list[DiligenceClaim]
    open_items: list[DiligenceClaim]
    red_flags: list[str]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)


class DiligenceLibrary:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], DiligenceDataset] = {}

    def add(self, *records: DiligenceDataset) -> None:
        for record in records:
            access = record.access
            key = (access.tenant_id, access.client_id, access.project_id, record.id)
            if key in self._records:
                raise ManagerPolicyError("Conflicting diligence dataset")
            self._records[key] = record.model_copy(deep=True)

    def get(self, item_id: str, *, context: UserContext, client_id: str,
            project_id: str) -> DiligenceDataset:
        record = self._records.get((context.tenant_id, client_id, project_id, item_id))
        if record is None:
            from .knowledge import ScopeDenied
            raise ScopeDenied("Diligence record is outside the authorized scope")
        record.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return record.model_copy(deep=True)


class DueDiligenceManager(DraftManagerBase):
    workflow = "due_diligence_review"

    def __init__(self, *, library: DiligenceLibrary, review_queue,
                 freshness_days: int = 90) -> None:
        super().__init__(review_queue=review_queue, freshness_days=freshness_days)
        self.library = library

    def report(self, *, context: UserContext, client_id: str, project_id: str,
               dataset_id: str, now: datetime | None = None) -> DiligenceDraft:
        now = now or datetime.now(UTC)
        record = self.library.get(dataset_id, context=context, client_id=client_id,
                                  project_id=project_id)
        known = evidence_map(record.evidence)
        stale = sorted({sid for claim in record.claims for sid in claim.source_ids
                        if is_stale(known[sid], now=now,
                                    freshness_days=self.freshness_days)})
        warnings = injection_warnings(record.retrieved_notes)
        if stale:
            warnings.append(f"Stale sources require refresh: {', '.join(stale)}")
        verified = [item for item in record.claims
                    if item.classification == ClaimClassification.VERIFIED_FACT]
        allegations = [item for item in record.claims
                       if item.classification == ClaimClassification.ALLEGATION]
        open_items = [item for item in record.claims
                      if item.classification == ClaimClassification.OPEN_ITEM]
        red_flags = [f"Unresolved material allegation: {item.statement}"
                     for item in allegations if item.material]
        return DiligenceDraft(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, subject=record.subject, question=record.question,
            as_of=now, verified_facts=verified, allegations=allegations,
            open_items=open_items, red_flags=red_flags, evidence=record.evidence,
            warnings=warnings)

    def submit_for_review(self, draft: DiligenceDraft, *, context: UserContext) -> ReviewItem:
        return self._submit(context=context, tenant_id=draft.tenant_id,
            project_id=draft.project_id, title=f"Diligence — {draft.subject}",
            body=self.to_markdown(draft), evidence=draft.evidence)

    @staticmethod
    def to_markdown(draft: DiligenceDraft) -> str:
        lines = [f"# Diligence — {draft.subject}", "", "DRAFT — HUMAN REVIEW REQUIRED",
                 f"As of: {draft.as_of.isoformat()}", "", "## Verified facts"]
        for heading, claims in (("Verified facts", draft.verified_facts),
                                ("Allegations", draft.allegations),
                                ("Open items", draft.open_items)):
            if heading != "Verified facts":
                lines.extend(["", f"## {heading}"])
            lines.extend(f"- {item.statement} (confidence {item.confidence:.2f}) "
                         f"[{', '.join(item.source_ids)}]" for item in claims)
        return "\n".join(lines)


def load_synthetic_diligence_library(path: Path | str) -> DiligenceLibrary:
    data = json.loads(Path(path).read_text())
    library = DiligenceLibrary()
    library.add(*(DiligenceDataset(**item) for item in data["diligence"]))
    return library
