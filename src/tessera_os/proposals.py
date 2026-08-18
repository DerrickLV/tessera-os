"""Offline, draft-only Proposal Manager foundation."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import BaseModel, Field, model_validator

from .knowledge import ScopeDenied
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class ProposalPolicyError(ValueError):
    """Raised when a draft would use unapproved or unsupported content."""


class ExternalDeliveryDisabled(PermissionError):
    """Raised for every attempted external delivery during Phase 3A."""


class LanguageKind(StrEnum):
    GENERAL = "general"
    QUALIFICATION = "qualification"


class PricingBasis(StrEnum):
    FIXED = "fixed"
    HOURLY = "hourly"
    MONTHLY = "monthly"
    PERCENTAGE = "percentage"


class AccessGrant(BaseModel):
    tenant_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    project_ids: frozenset[str] = Field(default_factory=frozenset)

    def permits(self, *, context: UserContext, client_id: str, project_id: str) -> bool:
        return (
            self.tenant_id == context.tenant_id
            and self.client_id == client_id
            and project_id in context.project_ids
            and (not self.project_ids or project_id in self.project_ids)
        )


class ProposalLanguage(BaseModel):
    id: str
    version: int = Field(ge=1)
    title: str
    text: str
    kind: LanguageKind = LanguageKind.GENERAL
    approved: bool = False
    approved_by: str | None = None
    source_id: str
    access: AccessGrant


class ProposalTemplate(BaseModel):
    id: str
    version: int = Field(ge=1)
    name: str
    section_order: tuple[str, ...]
    approved: bool = False
    source_id: str
    access: AccessGrant


class FeeItem(BaseModel):
    id: str
    name: str
    basis: PricingBasis
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    unit: str | None = None


class FeeSchedule(BaseModel):
    id: str
    version: int = Field(ge=1)
    effective_date: date
    expires_on: date | None = None
    approved: bool = False
    approved_by: str | None = None
    items: list[FeeItem]
    source_id: str
    access: AccessGrant

    def is_current(self, on_date: date) -> bool:
        return self.effective_date <= on_date and (self.expires_on is None or on_date <= self.expires_on)


class CitedText(BaseModel):
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class ScopeItem(CitedText):
    id: str
    phase: str | None = None


class Deliverable(CitedText):
    id: str
    acceptance_criteria: str | None = None


class Exclusion(CitedText):
    id: str


class Assumption(CitedText):
    id: str
    owner: str | None = None


class ScheduleMilestone(CitedText):
    id: str
    target: str
    dependencies: list[str] = Field(default_factory=list)


class StaffRole(CitedText):
    id: str
    role: str
    allocation: str


class PriceLine(BaseModel):
    fee_item_id: str
    description: str
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    unit_amount: Decimal = Field(ge=0)
    total: Decimal = Field(ge=0)
    currency: str
    basis: PricingBasis
    source_ids: list[str] = Field(min_length=1)


class ProposalContent(BaseModel):
    scope: list[ScopeItem] = Field(default_factory=list)
    deliverables: list[Deliverable] = Field(default_factory=list)
    exclusions: list[Exclusion] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    schedule: list[ScheduleMilestone] = Field(default_factory=list)
    staffing: list[StaffRole] = Field(default_factory=list)


class ProposalRequest(BaseModel):
    client_id: str
    project_id: str
    title: str
    template_id: str
    template_version: int = Field(ge=1)
    content: ProposalContent
    language_ids: list[str] = Field(default_factory=list)
    qualification_ids: list[str] = Field(default_factory=list)
    fee_schedule_id: str
    fee_schedule_version: int = Field(ge=1)
    fee_quantities: dict[str, Decimal] = Field(default_factory=dict)
    source_evidence: list[Evidence] = Field(default_factory=list)
    retrieved_notes: list[str] = Field(default_factory=list)


class ProposalDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = Field(default=1, ge=1)
    tenant_id: str
    client_id: str
    project_id: str
    title: str
    status: str = "draft"
    template_id: str
    template_version: int
    content: ProposalContent
    approved_language: list[CitedText] = Field(default_factory=list)
    qualifications: list[CitedText] = Field(default_factory=list)
    pricing: list[PriceLine] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def citations_cover_all_sources(self) -> ProposalDraft:
        known = {item.source_id for item in self.evidence}
        cited: list[CitedText | PriceLine] = [
            *self.content.scope,
            *self.content.deliverables,
            *self.content.exclusions,
            *self.content.assumptions,
            *self.content.schedule,
            *self.content.staffing,
            *self.approved_language,
            *self.qualifications,
            *self.pricing,
        ]
        missing = {source for item in cited for source in item.source_ids if source not in known}
        if missing:
            raise ValueError(f"Citations reference missing evidence: {sorted(missing)}")
        return self

    @property
    def total(self) -> Decimal:
        return sum((line.total for line in self.pricing), Decimal(0))


class ProposalChange(BaseModel):
    path: str
    before: Any = None
    after: Any = None


class ProposalComparison(BaseModel):
    from_version: int
    to_version: int
    changes: list[ProposalChange]


class ProposalLibrary:
    """Versioned in-memory catalog; authorization happens before records are returned."""

    def __init__(self) -> None:
        self._language: dict[tuple[str, int], ProposalLanguage] = {}
        self._templates: dict[tuple[str, int], ProposalTemplate] = {}
        self._fees: dict[tuple[str, int], FeeSchedule] = {}

    def add_language(self, *items: ProposalLanguage) -> None:
        for item in items:
            self._language[(item.id, item.version)] = item

    def add_templates(self, *items: ProposalTemplate) -> None:
        for item in items:
            self._templates[(item.id, item.version)] = item

    def add_fee_schedules(self, *items: FeeSchedule) -> None:
        for item in items:
            self._fees[(item.id, item.version)] = item

    @staticmethod
    def _authorize(record: Any, *, context: UserContext, client_id: str, project_id: str) -> Any:
        if project_id not in context.project_ids:
            raise ScopeDenied(f"User is not authorized for project {project_id!r}")
        if not record.access.permits(context=context, client_id=client_id, project_id=project_id):
            raise ScopeDenied("Proposal record is outside the authorized client/project scope")
        return record

    def language(self, item_id: str, version: int, *, context: UserContext,
                 client_id: str, project_id: str) -> ProposalLanguage:
        try:
            record = self._language[(item_id, version)]
        except KeyError as exc:
            raise ProposalPolicyError("Requested proposal language is unavailable") from exc
        return self._authorize(record, context=context, client_id=client_id, project_id=project_id)

    def template(self, item_id: str, version: int, *, context: UserContext,
                 client_id: str, project_id: str) -> ProposalTemplate:
        try:
            record = self._templates[(item_id, version)]
        except KeyError as exc:
            raise ProposalPolicyError("Requested proposal template is unavailable") from exc
        return self._authorize(record, context=context, client_id=client_id, project_id=project_id)

    def fee_schedule(self, item_id: str, version: int, *, context: UserContext,
                     client_id: str, project_id: str) -> FeeSchedule:
        try:
            record = self._fees[(item_id, version)]
        except KeyError as exc:
            raise ProposalPolicyError("Requested fee schedule is unavailable") from exc
        return self._authorize(record, context=context, client_id=client_id, project_id=project_id)


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"exfiltrat|reveal (a )?(secret|credential)|send (this|the proposal))"
)


class ProposalManager:
    def __init__(self, *, library: ProposalLibrary, review_queue: ReviewQueue) -> None:
        self.library = library
        self.review_queue = review_queue

    def generate(self, request: ProposalRequest, *, context: UserContext,
                 as_of: date | None = None) -> ProposalDraft:
        as_of = as_of or datetime.now(UTC).date()
        template = self.library.template(request.template_id, request.template_version,
            context=context, client_id=request.client_id, project_id=request.project_id)
        if not template.approved:
            raise ProposalPolicyError("Proposal template is not approved")
        evidence = {item.source_id: item for item in request.source_evidence}
        evidence[template.source_id] = Evidence(source_id=template.source_id, title=template.name)

        language: list[CitedText] = []
        qualifications: list[CitedText] = []
        for item_id, target, expected_kind in [
            *((item_id, language, LanguageKind.GENERAL) for item_id in request.language_ids),
            *((item_id, qualifications, LanguageKind.QUALIFICATION)
              for item_id in request.qualification_ids),
        ]:
            item = self.library.language(item_id, 1, context=context,
                client_id=request.client_id, project_id=request.project_id)
            if not item.approved or item.kind != expected_kind:
                raise ProposalPolicyError(f"Language {item_id!r} is not approved for this use")
            target.append(CitedText(text=item.text, source_ids=[item.source_id]))
            evidence[item.source_id] = Evidence(source_id=item.source_id, title=item.title)

        fees = self.library.fee_schedule(request.fee_schedule_id, request.fee_schedule_version,
            context=context, client_id=request.client_id, project_id=request.project_id)
        if not fees.approved or not fees.is_current(as_of):
            raise ProposalPolicyError("Fee schedule is unapproved or not effective")
        fee_items = {item.id: item for item in fees.items}
        unknown = set(request.fee_quantities).difference(fee_items)
        if unknown:
            raise ProposalPolicyError(f"Pricing is not in the approved fee schedule: {sorted(unknown)}")
        pricing = []
        for item_id, quantity in request.fee_quantities.items():
            item = fee_items[item_id]
            pricing.append(PriceLine(fee_item_id=item.id, description=item.name,
                quantity=quantity, unit_amount=item.amount, total=item.amount * quantity,
                currency=item.currency, basis=item.basis, source_ids=[fees.source_id]))
        evidence[fees.source_id] = Evidence(source_id=fees.source_id,
            title=f"Approved fee schedule {fees.id} v{fees.version}")

        warnings = ["Retrieved content contained a possible prompt-injection instruction; ignored."
                    for note in request.retrieved_notes if _INJECTION.search(note)]
        return ProposalDraft(tenant_id=context.tenant_id, client_id=request.client_id,
            project_id=request.project_id, title=request.title, template_id=template.id,
            template_version=template.version, content=request.content,
            approved_language=language, qualifications=qualifications, pricing=pricing,
            evidence=list(evidence.values()), safety_warnings=warnings)

    def submit_for_review(self, draft: ProposalDraft, *, context: UserContext) -> ReviewItem:
        if (draft.tenant_id != context.tenant_id or draft.project_id not in context.project_ids):
            raise ScopeDenied("Draft is outside the authenticated scope")
        return self.review_queue.submit(tenant_id=draft.tenant_id, project_id=draft.project_id,
            created_by=context.user_id, workflow="proposal_review", title=draft.title,
            body=self.to_markdown(draft), evidence=draft.evidence,
            required_reviewer_group="proposal_approver")

    @staticmethod
    def request_external_delivery(*, review_item: ReviewItem) -> None:
        raise ExternalDeliveryDisabled(
            f"External delivery is disabled in Phase 3A; review item {review_item.id} remains internal"
        )

    @staticmethod
    def compare(before: ProposalDraft, after: ProposalDraft) -> ProposalComparison:
        ignored = {"id", "created_at"}
        left = before.model_dump(mode="json", exclude=ignored)
        right = after.model_dump(mode="json", exclude=ignored)
        changes: list[ProposalChange] = []

        def walk(path: str, a: Any, b: Any) -> None:
            if isinstance(a, dict) and isinstance(b, dict):
                for key in sorted(set(a) | set(b)):
                    walk(f"{path}.{key}" if path else key, a.get(key), b.get(key))
            elif a != b:
                changes.append(ProposalChange(path=path, before=a, after=b))

        walk("", left, right)
        return ProposalComparison(from_version=before.version, to_version=after.version,
                                  changes=changes)

    @staticmethod
    def to_markdown(draft: ProposalDraft) -> str:
        lines = [f"# {draft.title}", "", "DRAFT — HUMAN REVIEW REQUIRED", ""]
        for title, items in (
            ("Scope", draft.content.scope), ("Deliverables", draft.content.deliverables),
            ("Exclusions", draft.content.exclusions), ("Assumptions", draft.content.assumptions),
            ("Schedule", draft.content.schedule), ("Staffing", draft.content.staffing),
            ("Qualifications", draft.qualifications),
        ):
            lines.extend([f"## {title}", *[f"- {i.text} [{', '.join(i.source_ids)}]" for i in items], ""])
        lines.append("## Pricing")
        lines.extend(f"- {p.description}: {p.currency} {p.total:.2f} [{', '.join(p.source_ids)}]"
                     for p in draft.pricing)
        lines.extend([f"- Total: USD {draft.total:.2f}", "", "## Sources"])
        lines.extend(f"- [{e.source_id}] {e.title}" for e in draft.evidence)
        return "\n".join(lines)

    @classmethod
    def write_docx(cls, draft: ProposalDraft, path: Path | str) -> Path:
        """Write a deterministic, dependency-free Word OOXML draft artifact."""
        path = Path(path)
        paragraphs = []
        for line in cls.to_markdown(draft).splitlines():
            if not line:
                paragraphs.append("<w:p/>")
                continue
            style = "Heading1" if line.startswith("## ") else "Title" if line.startswith("# ") else None
            text = line.lstrip("# ")
            ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
            paragraphs.append(f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{"".join(paragraphs)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
            '</w:sectPr></w:body></w:document>'
        )
        styles = _word_styles()
        content_types = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '</Types>')
        root_rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
        doc_rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(path, "w", ZIP_DEFLATED) as package:
            package.writestr("[Content_Types].xml", content_types)
            package.writestr("_rels/.rels", root_rels)
            package.writestr("word/document.xml", document)
            package.writestr("word/styles.xml", styles)
            package.writestr("word/_rels/document.xml.rels", doc_rels)
        return path


def _word_styles() -> str:
    """Narrative-proposal tokens: Calibri 11, restrained blue hierarchy."""
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="280" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
 <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
 <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:color w:val="0B2545"/><w:sz w:val="48"/></w:rPr></w:style>
 <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="320" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="2E74B5"/><w:sz w:val="32"/></w:rPr></w:style>
</w:styles>'''


def load_synthetic_library(path: Path | str) -> ProposalLibrary:
    data = json.loads(Path(path).read_text())
    library = ProposalLibrary()
    library.add_language(*(ProposalLanguage(**item) for item in data["language"]))
    library.add_templates(*(ProposalTemplate(**item) for item in data["templates"]))
    library.add_fee_schedules(*(FeeSchedule(**item) for item in data["fee_schedules"]))
    return library
