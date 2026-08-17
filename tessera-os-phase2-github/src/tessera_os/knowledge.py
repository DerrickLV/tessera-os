"""ACL-preserving local knowledge index for the read-only pilot."""

from __future__ import annotations
import re
from collections.abc import Iterable
from .schemas import SearchHit, SourceDocument, UserContext


class ScopeDenied(PermissionError):
    """Raised before retrieval when tenant or project scope is invalid."""


class KnowledgeIndex:
    """Dependency-free pilot index with authorization enforced before ranking."""

    def __init__(self) -> None:
        self._documents: dict[tuple[str, str], SourceDocument] = {}

    def ingest(self, documents: Iterable[SourceDocument]) -> int:
        count = 0
        for document in documents:
            self._documents[(document.tenant_id, document.source_id)] = document
            count += 1
        return count

    @staticmethod
    def _authorize_scope(context: UserContext, project_id: str) -> None:
        if project_id not in context.project_ids:
            raise ScopeDenied(f"User is not authorized for project {project_id!r}")

    @staticmethod
    def _can_read(document: SourceDocument, context: UserContext) -> bool:
        if document.tenant_id != context.tenant_id or document.project_id not in context.project_ids:
            return False
        if not document.allowed_user_ids and not document.allowed_group_ids:
            return False
        return context.user_id in document.allowed_user_ids or bool(
            context.group_ids.intersection(document.allowed_group_ids)
        )

    def search(self, query: str, *, context: UserContext, project_id: str,
               limit: int = 10) -> list[SearchHit]:
        self._authorize_scope(context, project_id)
        terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
        ranked: list[tuple[int, SourceDocument]] = []
        for document in self._documents.values():
            if document.project_id != project_id or not self._can_read(document, context):
                continue
            haystack = f"{document.title} {document.content}".casefold()
            score = sum(haystack.count(term) for term in terms)
            if not terms or score:
                ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1].title, item[1].source_id))
        return [self._hit(document, terms) for _, document in ranked[:limit]]

    @staticmethod
    def _hit(document: SourceDocument, terms: set[str]) -> SearchHit:
        content = " ".join(document.content.split())
        position = min((content.casefold().find(t) for t in terms if t in content.casefold()), default=0)
        excerpt = content[max(0, position - 80):max(0, position - 80) + 320]
        return SearchHit(source_id=document.source_id, title=document.title, excerpt=excerpt,
                         locator=document.web_url, modified_at=document.modified_at)
