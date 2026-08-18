"""Offline, deterministic, draft-only Capital Manager foundation."""

from __future__ import annotations

import json
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


class CovenantStatus(StrEnum):
    COMPLIANT = "compliant"
    WATCH = "watch"
    BREACH = "breach"
    UNKNOWN = "unknown"


class CapitalModel(BaseModel):
    id: str
    version: int = Field(ge=1)
    status: str = "draft"
    uses: dict[str, Decimal]
    sources: dict[str, Decimal]
    noi: Decimal
    debt_service: Decimal = Field(gt=0)
    debt_balance: Decimal = Field(ge=0)
    value: Decimal = Field(gt=0)
    equity: Decimal = Field(ge=0)
    source_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def sources_equal_uses(self) -> CapitalModel:
        if sum(self.sources.values(), Decimal(0)) != sum(self.uses.values(), Decimal(0)):
            raise ValueError("Capital model sources and uses do not reconcile")
        return self


class Covenant(BaseModel):
    id: str
    name: str
    metric: str
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    source_ids: list[str] = Field(min_length=1)


class CapitalDataset(BaseModel):
    id: str
    name: str
    access: ProjectAccess
    models: list[CapitalModel]
    covenants: list[Covenant]
    evidence: list[Evidence]
    retrieved_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_versions_and_citations(self) -> CapitalDataset:
        keys = [(item.id, item.version) for item in self.models]
        if len(keys) != len(set(keys)):
            raise ValueError("Conflicting capital model versions")
        known = evidence_map(self.evidence)
        for item in [*self.models, *self.covenants]:
            validate_citations(item.source_ids, known, label=item.id)
        return self


class CovenantResult(BaseModel):
    covenant_id: str
    metric: str
    actual: Decimal
    status: CovenantStatus
    source_ids: list[str]


class SensitivityResult(BaseModel):
    scenario: str
    noi_change_percent: Decimal
    dscr: Decimal
    source_ids: list[str]


class CapitalDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    model_id: str
    model_version: int
    status: str = "draft"
    dscr: Decimal
    ltv_percent: Decimal
    equity_multiple: Decimal
    covenants: list[CovenantResult]
    sensitivities: list[SensitivityResult]
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)


class CapitalLibrary:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], CapitalDataset] = {}

    def add(self, *records: CapitalDataset) -> None:
        for record in records:
            access = record.access
            key = (access.tenant_id, access.client_id, access.project_id, record.id)
            if key in self._records:
                raise ManagerPolicyError("Conflicting capital dataset")
            self._records[key] = record.model_copy(deep=True)

    def get(self, item_id: str, *, context: UserContext, client_id: str,
            project_id: str) -> CapitalDataset:
        record = self._records.get((context.tenant_id, client_id, project_id, item_id))
        if record is None:
            from .knowledge import ScopeDenied
            raise ScopeDenied("Capital record is outside the authorized scope")
        record.access.authorize(context=context, client_id=client_id, project_id=project_id)
        return record.model_copy(deep=True)


class CapitalManager(DraftManagerBase):
    workflow = "capital_underwriting_review"

    def __init__(self, *, library: CapitalLibrary, review_queue) -> None:
        super().__init__(review_queue=review_queue)
        self.library = library

    def underwrite(self, *, context: UserContext, client_id: str, project_id: str,
                   dataset_id: str, model_id: str, model_version: int) -> CapitalDraft:
        record = self.library.get(dataset_id, context=context, client_id=client_id,
                                  project_id=project_id)
        try:
            model = next(item for item in record.models
                         if item.id == model_id and item.version == model_version)
        except StopIteration as exc:
            raise ManagerPolicyError("Requested capital model version is unavailable") from exc
        dscr = (model.noi / model.debt_service).quantize(Decimal("0.01"))
        ltv = (model.debt_balance / model.value * Decimal(100)).quantize(Decimal("0.01"))
        multiple = ((model.value - model.debt_balance) / model.equity).quantize(Decimal("0.01")) \
            if model.equity else Decimal(0)
        values = {"dscr": dscr, "ltv_percent": ltv}
        covenant_results = []
        for item in record.covenants:
            if item.metric not in values:
                status, actual = CovenantStatus.UNKNOWN, Decimal(0)
            else:
                actual = values[item.metric]
                breach = ((item.minimum is not None and actual < item.minimum)
                          or (item.maximum is not None and actual > item.maximum))
                status = CovenantStatus.BREACH if breach else CovenantStatus.COMPLIANT
            covenant_results.append(CovenantResult(covenant_id=item.id,
                metric=item.metric, actual=actual, status=status, source_ids=item.source_ids))
        sensitivities = [SensitivityResult(scenario=name, noi_change_percent=change,
            dscr=((model.noi * (Decimal(1) + change / Decimal(100))) / model.debt_service)
            .quantize(Decimal("0.01")), source_ids=model.source_ids)
            for name, change in (("downside", Decimal(-10)), ("base", Decimal(0)),
                                 ("upside", Decimal(10)))]
        return CapitalDraft(tenant_id=context.tenant_id, client_id=client_id,
            project_id=project_id, title=f"Underwriting — {record.name}",
            model_id=model.id, model_version=model.version, dscr=dscr,
            ltv_percent=ltv, equity_multiple=multiple, covenants=covenant_results,
            sensitivities=sensitivities, evidence=record.evidence,
            warnings=injection_warnings(record.retrieved_notes))

    def submit_for_review(self, draft: CapitalDraft, *, context: UserContext) -> ReviewItem:
        return self._submit(context=context, tenant_id=draft.tenant_id,
            project_id=draft.project_id, title=draft.title,
            body=self.to_markdown(draft), evidence=draft.evidence)

    @staticmethod
    def to_markdown(draft: CapitalDraft) -> str:
        lines = [f"# {draft.title}", "", "DRAFT — INVESTMENT REVIEW REQUIRED", "",
                 f"- Model: {draft.model_id} v{draft.model_version}",
                 f"- DSCR: {draft.dscr}", f"- LTV: {draft.ltv_percent}%",
                 f"- Equity multiple: {draft.equity_multiple}x", "", "## Covenants"]
        lines.extend(f"- {item.covenant_id}: {item.actual} ({item.status}) "
                     f"[{', '.join(item.source_ids)}]" for item in draft.covenants)
        return "\n".join(lines)


def load_synthetic_capital_library(path: Path | str) -> CapitalLibrary:
    data = json.loads(Path(path).read_text())
    library = CapitalLibrary()
    library.add(*(CapitalDataset(**item) for item in data["capital"]))
    return library
