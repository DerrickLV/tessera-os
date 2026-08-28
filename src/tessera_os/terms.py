"""Durable record of which commercial option a person chose, for which menu.

Phase 3 built the same shape for a single figure (:mod:`tessera_os.numbers`):
a computed proposal is not a settled term until a person accepts or replaces
it, and that acceptance is recorded, not implied. Phase 5 extends the same
discipline to a *choice among options* -- a distribution waterfall, a capital-
call remedy, an exit-pricing method -- where the thing a person confirms is
not a number but which of several real alternatives applies.

:class:`MenuSelectionStore` is opened through
:func:`tessera_os.sqlite_store.connect` for the same reason as the review
queue, the artifact store, and :class:`~tessera_os.numbers.NumberConfirmationStore`:
production runs this on an Azure Files SMB share, where SQLite's default
locking assumptions do not hold.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .sqlite_store import connect as sqlite_connect


class MenuSelection(BaseModel):
    """One recorded choice: this menu, this option, this person, this moment."""

    area: str = Field(min_length=1)
    label: str = Field(min_length=1)
    selected_by: str = Field(min_length=1)
    selected_at: datetime


class MenuSelectionStore:
    """Durable, per-project record of which option was selected for which menu."""

    def __init__(self, path: Path | str = "tessera-menu-selections.db") -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS menu_selections (
                tenant_id TEXT NOT NULL, project_id TEXT NOT NULL, area TEXT NOT NULL,
                label TEXT NOT NULL, selected_by TEXT NOT NULL, selected_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, project_id, area))""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite_connect(self.path)

    def select(self, *, tenant_id: str, project_id: str, area: str, label: str,
              selected_by: str, selected_at: datetime | None = None) -> MenuSelection:
        selection = MenuSelection(area=area, label=label, selected_by=selected_by,
                                  selected_at=selected_at or datetime.now(UTC))
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO menu_selections
                   (tenant_id, project_id, area, label, selected_by, selected_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT (tenant_id, project_id, area)
                   DO UPDATE SET label = excluded.label, selected_by = excluded.selected_by,
                                 selected_at = excluded.selected_at""",
                (tenant_id, project_id, area, selection.label, selection.selected_by,
                 selection.selected_at.isoformat()))
        return selection

    def for_project(self, *, tenant_id: str, project_id: str) -> dict[str, MenuSelection]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM menu_selections WHERE tenant_id = ? AND project_id = ?",
                (tenant_id, project_id)).fetchall()
        return {row["area"]: MenuSelection(
                    area=row["area"], label=row["label"], selected_by=row["selected_by"],
                    selected_at=datetime.fromisoformat(row["selected_at"]))
                for row in rows}
