"""Observability, budgets, DLP, rate limits, encryption, retention, and backup."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections import defaultdict, deque
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field

from .schemas import UserContext


class BudgetExceeded(PermissionError):
    """Raised when a tenant or workflow exceeds an approved usage budget."""


class RateLimitExceeded(PermissionError):
    """Raised when a caller exceeds the configured request rate."""


class RetentionDenied(PermissionError):
    """Raised when legal hold or scope prevents retention operations."""


class DLPRedactor:
    patterns = (
        (re.compile(r"(?i)bearer\s+[a-z0-9._~-]+"), "Bearer [REDACTED]"),
        (re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"), "[REDACTED_API_KEY]"),
        (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
         "[REDACTED_EMAIL]"),
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    )

    @classmethod
    def redact(cls, value: str) -> str:
        for pattern, replacement in cls.patterns:
            value = pattern.sub(replacement, value)
        return value


class RateLimiter:
    def __init__(self, *, limit: int = 60, window: timedelta = timedelta(minutes=1)) -> None:
        self.limit, self.window = limit, window
        self._events: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, *, context: UserContext, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        key = (context.tenant_id, context.user_id)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                raise RateLimitExceeded("Request rate limit exceeded")
            events.append(now)


class UsageBudget(BaseModel):
    tenant_id: str
    workflow: str
    day: date
    token_limit: int = Field(ge=0)
    cost_limit: float = Field(ge=0)
    tokens_used: int = Field(ge=0)
    cost_used: float = Field(ge=0)


class TraceRecord(BaseModel):
    correlation_id: str
    tenant_id: str
    project_id: str
    user_id: str
    workflow: str
    agent_id: str
    model_version: str
    prompt_version: str
    policy_outcome: str
    source_ids: list[str]
    tokens: int = Field(ge=0)
    cost_units: float = Field(ge=0)
    error: str | None = None
    created_at: datetime


class RuntimeAuditStore:
    EXTERNAL_ACTION_WORKFLOWS = frozenset({
        "send_email", "publish", "submit_application", "move_funds",
        "direct_consultant", "deploy_production",
    })
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS usage_budgets (
                    tenant_id TEXT NOT NULL, workflow TEXT NOT NULL, day TEXT NOT NULL,
                    token_limit INTEGER NOT NULL, cost_limit REAL NOT NULL,
                    tokens_used INTEGER NOT NULL DEFAULT 0, cost_used REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (tenant_id, workflow, day)
                );
                CREATE TABLE IF NOT EXISTS traces (
                    correlation_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL, user_id TEXT NOT NULL, workflow TEXT NOT NULL,
                    agent_id TEXT NOT NULL, model_version TEXT NOT NULL,
                    prompt_version TEXT NOT NULL, policy_outcome TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL, tokens INTEGER NOT NULL,
                    cost_units REAL NOT NULL, error TEXT, created_at TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def set_budget(self, *, tenant_id: str, workflow: str, day: date,
                   token_limit: int, cost_limit: float) -> UsageBudget:
        with self._connect() as connection:
            connection.execute("""INSERT INTO usage_budgets
                (tenant_id, workflow, day, token_limit, cost_limit) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, workflow, day) DO UPDATE SET
                token_limit=excluded.token_limit, cost_limit=excluded.cost_limit""",
                (tenant_id, workflow, day.isoformat(), token_limit, cost_limit))
        return self.budget(tenant_id=tenant_id, workflow=workflow, day=day)

    def reserve_usage(self, *, tenant_id: str, workflow: str, day: date,
                      tokens: int, cost_units: float) -> UsageBudget:
        if tokens < 0 or cost_units < 0:
            raise ValueError("Usage cannot be negative")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM usage_budgets WHERE tenant_id=? "
                "AND workflow=? AND day=?", (tenant_id, workflow, day.isoformat())).fetchone()
            if row is None:
                raise BudgetExceeded("No approved usage budget exists")
            if row["tokens_used"] + tokens > row["token_limit"]:
                raise BudgetExceeded("Token budget exceeded")
            if row["cost_used"] + cost_units > row["cost_limit"]:
                raise BudgetExceeded("Cost budget exceeded")
            connection.execute("""UPDATE usage_budgets SET tokens_used=tokens_used+?,
                cost_used=cost_used+? WHERE tenant_id=? AND workflow=? AND day=?""",
                (tokens, cost_units, tenant_id, workflow, day.isoformat()))
        return self.budget(tenant_id=tenant_id, workflow=workflow, day=day)

    def budget(self, *, tenant_id: str, workflow: str, day: date) -> UsageBudget:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM usage_budgets WHERE tenant_id=? "
                "AND workflow=? AND day=?", (tenant_id, workflow, day.isoformat())).fetchone()
        if row is None:
            raise KeyError((tenant_id, workflow, day))
        return UsageBudget(**dict(row))

    def record_trace(self, *, context: UserContext, project_id: str, workflow: str,
                     agent_id: str, model_version: str, prompt_version: str,
                     policy_outcome: str, source_ids: list[str], tokens: int = 0,
                     cost_units: float = 0, error: str | None = None,
                     correlation_id: str | None = None,
                     now: datetime | None = None) -> TraceRecord:
        if project_id not in context.project_ids:
            raise PermissionError("Trace project is outside authenticated scope")
        now = now or datetime.now(UTC)
        trace = TraceRecord(correlation_id=correlation_id or str(uuid4()),
            tenant_id=context.tenant_id, project_id=project_id, user_id=context.user_id,
            workflow=workflow, agent_id=agent_id, model_version=model_version,
            prompt_version=prompt_version, policy_outcome=policy_outcome,
            source_ids=source_ids, tokens=tokens, cost_units=cost_units,
            error=DLPRedactor.redact(error) if error else None, created_at=now)
        with self._connect() as connection:
            connection.execute("""INSERT INTO traces
                (correlation_id, tenant_id, project_id, user_id, workflow, agent_id,
                 model_version, prompt_version, policy_outcome, source_ids_json,
                 tokens, cost_units, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trace.correlation_id, trace.tenant_id, trace.project_id, trace.user_id,
                 trace.workflow, trace.agent_id, trace.model_version, trace.prompt_version,
                 trace.policy_outcome, json.dumps(source_ids), trace.tokens,
                 trace.cost_units, trace.error, trace.created_at.isoformat()))
        return trace

    def traces(self, *, context: UserContext, project_id: str) -> list[TraceRecord]:
        if project_id not in context.project_ids:
            raise PermissionError("Trace project is outside authenticated scope")
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM traces WHERE tenant_id=? AND project_id=? "
                "ORDER BY created_at", (context.tenant_id, project_id)).fetchall()
        results = []
        for row in rows:
            values = dict(row)
            values["source_ids"] = json.loads(values.pop("source_ids_json"))
            results.append(TraceRecord(**values))
        return results

    def count_external_actions(self, *, context: UserContext, project_id: str) -> int:
        if project_id not in context.project_ids:
            raise PermissionError("Trace project is outside authenticated scope")
        placeholders = ",".join("?" for _ in self.EXTERNAL_ACTION_WORKFLOWS)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM traces WHERE tenant_id=? AND project_id=? "
                f"AND workflow IN ({placeholders})",
                (context.tenant_id, project_id, *sorted(self.EXTERNAL_ACTION_WORKFLOWS)),
            ).fetchone()
        return int(row["count"])

    def reset_synthetic(self, *, context: UserContext) -> tuple[int, int]:
        if context.tenant_id != "tenant-synthetic":
            raise PermissionError("Audit reset is limited to the synthetic tenant")
        with self._connect() as connection:
            traces = connection.execute(
                "DELETE FROM traces WHERE tenant_id=?", (context.tenant_id,)
            ).rowcount
            budgets = connection.execute(
                "DELETE FROM usage_budgets WHERE tenant_id=?", (context.tenant_id,)
            ).rowcount
        return traces, budgets


class SecureArtifact(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    category: str
    created_at: datetime
    expires_at: datetime
    legal_hold: bool


class SecureArtifactStore:
    """Application-layer AES-GCM storage with retention, legal hold, and backup."""

    def __init__(self, path: Path | str, *, encryption_key: bytes) -> None:
        if len(encryption_key) not in {16, 24, 32}:
            raise ValueError("AES-GCM key must contain 16, 24, or 32 bytes")
        self.path = str(path)
        self._cipher = AESGCM(encryption_key)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS secure_artifacts (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT NOT NULL,
                category TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                legal_hold INTEGER NOT NULL DEFAULT 0)""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def put(self, *, context: UserContext, project_id: str, category: str,
            value: dict[str, Any], retention_days: int,
            now: datetime | None = None) -> SecureArtifact:
        if project_id not in context.project_ids or retention_days < 1:
            raise RetentionDenied("Artifact scope or retention is invalid")
        now = now or datetime.now(UTC)
        item_id = str(uuid4())
        nonce = os.urandom(12)
        aad = f"{context.tenant_id}:{project_id}:{item_id}".encode()
        ciphertext = self._cipher.encrypt(nonce, json.dumps(value, sort_keys=True).encode(), aad)
        artifact = SecureArtifact(id=item_id, tenant_id=context.tenant_id,
            project_id=project_id, category=category, created_at=now,
            expires_at=now + timedelta(days=retention_days), legal_hold=False)
        with self._connect() as connection:
            connection.execute("""INSERT INTO secure_artifacts
                (id, tenant_id, project_id, category, nonce, ciphertext,
                 created_at, expires_at, legal_hold) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (item_id, context.tenant_id, project_id, category, nonce, ciphertext,
                 now.isoformat(), artifact.expires_at.isoformat()))
        return artifact

    def get(self, item_id: str, *, context: UserContext) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM secure_artifacts WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        if row["tenant_id"] != context.tenant_id or row["project_id"] not in context.project_ids:
            raise RetentionDenied("Artifact is outside authenticated scope")
        aad = f"{row['tenant_id']}:{row['project_id']}:{row['id']}".encode()
        return json.loads(self._cipher.decrypt(row["nonce"], row["ciphertext"], aad))

    def set_legal_hold(self, item_id: str, *, context: UserContext, active: bool) -> None:
        if "records_admin" not in context.group_ids:
            raise RetentionDenied("Records administrator role is required")
        with self._connect() as connection:
            row = connection.execute("SELECT tenant_id, project_id FROM secure_artifacts "
                                     "WHERE id=?", (item_id,)).fetchone()
            if row is None:
                raise KeyError(item_id)
            if row["tenant_id"] != context.tenant_id or row["project_id"] not in context.project_ids:
                raise RetentionDenied("Artifact is outside authenticated scope")
            connection.execute("UPDATE secure_artifacts SET legal_hold=? WHERE id=?",
                               (int(active), item_id))

    def purge_expired(self, *, context: UserContext, now: datetime | None = None) -> int:
        if "records_admin" not in context.group_ids:
            raise RetentionDenied("Records administrator role is required")
        now = now or datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute("""DELETE FROM secure_artifacts
                WHERE tenant_id=? AND expires_at<=? AND legal_hold=0""",
                (context.tenant_id, now.isoformat()))
        return cursor.rowcount

    def backup(self, path: Path | str, *, context: UserContext) -> str:
        if "records_admin" not in context.group_ids:
            raise RetentionDenied("Records administrator role is required")
        target = Path(path)
        if target.exists():
            raise FileExistsError(target)
        with self._connect() as source, sqlite3.connect(target) as destination:
            destination.execute("""CREATE TABLE secure_artifacts (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT NOT NULL,
                category TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                legal_hold INTEGER NOT NULL DEFAULT 0)""")
            rows = source.execute("SELECT * FROM secure_artifacts WHERE tenant_id=?",
                                  (context.tenant_id,)).fetchall()
            destination.executemany("""INSERT INTO secure_artifacts
                (id, tenant_id, project_id, category, nonce, ciphertext,
                 created_at, expires_at, legal_hold) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [tuple(row) for row in rows])
        return hashlib.sha256(target.read_bytes()).hexdigest()
