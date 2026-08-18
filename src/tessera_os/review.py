"""Durable, human-owned review queue for generated drafts."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .schemas import Evidence, ReviewItem, ReviewStatus, UserContext


class ReviewAccessDenied(PermissionError):
    """Raised when a user cannot view or disposition a review item."""


class InvalidReviewTransition(ValueError):
    """Raised when a review item is not pending or a reason is missing."""


class ReviewQueue:
    def __init__(self, path: Path | str = "tessera-review.db") -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS review_items (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT,
                created_by TEXT NOT NULL, workflow TEXT NOT NULL, title TEXT NOT NULL,
                body TEXT NOT NULL, evidence_json TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT,
                review_reason TEXT, required_reviewer_group TEXT)""")
            existing = {row[1] for row in connection.execute("PRAGMA table_info(review_items)")}
            for name in ("reviewed_by", "reviewed_at", "review_reason",
                         "required_reviewer_group"):
                if name not in existing:
                    connection.execute(f"ALTER TABLE review_items ADD COLUMN {name} TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def submit(self, *, tenant_id: str, project_id: str | None, created_by: str,
               workflow: str, title: str, body: str, evidence: list[Evidence],
               required_reviewer_group: str | None = None) -> ReviewItem:
        item = ReviewItem(id=str(uuid4()), tenant_id=tenant_id, project_id=project_id,
                          created_by=created_by, workflow=workflow, title=title,
                          body=body, evidence=evidence,
                          required_reviewer_group=required_reviewer_group)
        with self._connect() as connection:
            connection.execute("""INSERT INTO review_items
                (id, tenant_id, project_id, created_by, workflow, title, body,
                 evidence_json, status, created_at, required_reviewer_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.id, item.tenant_id, item.project_id, item.created_by, item.workflow,
                 item.title, item.body, json.dumps([e.model_dump(mode="json") for e in evidence]),
                 item.status.value, item.created_at.isoformat(), required_reviewer_group))
        return item

    def list_pending(self, *, context: UserContext) -> list[ReviewItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM review_items WHERE tenant_id = ? AND status = ? ORDER BY created_at",
                (context.tenant_id, ReviewStatus.PENDING.value)).fetchall()
        return [self._decode(row) for row in rows
                if (row["project_id"] is None and row["created_by"] == context.user_id)
                or row["project_id"] in context.project_ids]

    def accept(self, *, item_id: str, context: UserContext, reason: str) -> ReviewItem:
        return self._transition(item_id=item_id, context=context,
                                status=ReviewStatus.ACCEPTED, reason=reason)

    def reject(self, *, item_id: str, context: UserContext, reason: str) -> ReviewItem:
        return self._transition(item_id=item_id, context=context,
                                status=ReviewStatus.REJECTED, reason=reason)

    def _transition(self, *, item_id: str, context: UserContext, status: ReviewStatus,
                    reason: str) -> ReviewItem:
        reason = reason.strip()
        if not reason:
            raise InvalidReviewTransition("A review reason is required")
        reviewed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM review_items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                raise KeyError(item_id)
            if row["tenant_id"] != context.tenant_id:
                raise ReviewAccessDenied("Review item belongs to another tenant")
            if row["project_id"] is None:
                authorized = row["created_by"] == context.user_id
            else:
                authorized = row["project_id"] in context.project_ids
            if not authorized:
                raise ReviewAccessDenied("User is not authorized to disposition this review item")
            if (row["required_reviewer_group"]
                    and row["required_reviewer_group"] not in context.group_ids):
                raise ReviewAccessDenied("User lacks the required qualified reviewer role")
            if row["required_reviewer_group"] and row["created_by"] == context.user_id:
                raise ReviewAccessDenied("Qualified reviews require separation of duties")
            if row["status"] != ReviewStatus.PENDING.value:
                raise InvalidReviewTransition("Only pending review items can be dispositioned")
            connection.execute(
                """UPDATE review_items
                   SET status = ?, reviewed_by = ?, reviewed_at = ?, review_reason = ?
                   WHERE id = ? AND status = ?""",
                (status.value, context.user_id, reviewed_at.isoformat(), reason,
                 item_id, ReviewStatus.PENDING.value))
            updated = connection.execute(
                "SELECT * FROM review_items WHERE id = ?", (item_id,)).fetchone()
        return self._decode(updated)

    @staticmethod
    def _decode(row: sqlite3.Row) -> ReviewItem:
        values = dict(row)
        values.pop("evidence_json")
        evidence = [Evidence(**item) for item in json.loads(row["evidence_json"])]
        return ReviewItem(**values, evidence=evidence)
