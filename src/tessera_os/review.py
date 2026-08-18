"""Durable, human-owned review queue for generated drafts."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from .schemas import Evidence, ReviewItem, ReviewStatus


class ReviewQueue:
    def __init__(self, path: Path | str = "tessera-review.db") -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS review_items (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT,
                created_by TEXT NOT NULL, workflow TEXT NOT NULL, title TEXT NOT NULL,
                body TEXT NOT NULL, evidence_json TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL)""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def submit(self, *, tenant_id: str, project_id: str | None, created_by: str,
               workflow: str, title: str, body: str, evidence: list[Evidence]) -> ReviewItem:
        item = ReviewItem(id=str(uuid4()), tenant_id=tenant_id, project_id=project_id,
                          created_by=created_by, workflow=workflow, title=title,
                          body=body, evidence=evidence)
        with self._connect() as connection:
            connection.execute("INSERT INTO review_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.id, item.tenant_id, item.project_id, item.created_by, item.workflow,
                 item.title, item.body, json.dumps([e.model_dump(mode="json") for e in evidence]),
                 item.status.value, item.created_at.isoformat()))
        return item

    def list_pending(self, *, tenant_id: str, project_ids: frozenset[str]) -> list[ReviewItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM review_items WHERE tenant_id = ? AND status = ? ORDER BY created_at",
                (tenant_id, ReviewStatus.PENDING.value)).fetchall()
        return [self._decode(row) for row in rows
                if row["project_id"] is None or row["project_id"] in project_ids]

    @staticmethod
    def _decode(row: sqlite3.Row) -> ReviewItem:
        values = dict(row)
        values.pop("evidence_json")
        return ReviewItem(**values, evidence=[Evidence(**e) for e in json.loads(row["evidence_json"])])
