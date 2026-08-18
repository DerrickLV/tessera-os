"""Sandbox-only Phase 5 gated actions, approvals, and audit controls."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, model_validator

from .knowledge import ScopeDenied
from .schemas import Evidence, UserContext


class ActionPolicyError(ValueError):
    """Raised when an action violates the Phase 5 sandbox policy."""


class ApprovalDenied(PermissionError):
    """Raised when approval authority or scope is insufficient."""


class TokenRejected(PermissionError):
    """Raised when a signed action token is invalid, expired, or replayed."""


class KillSwitchActive(PermissionError):
    """Raised when execution is disabled for a workflow or tenant."""


class ActionExecutionError(RuntimeError):
    """Raised after a failed action is captured in the dead-letter queue."""


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ExecutionState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkflowDefinition(BaseModel):
    """Versioned design for the single allowed low-risk sandbox workflow class."""

    id: str
    version: int = Field(ge=1)
    tenant_id: str
    client_id: str
    project_id: str
    name: str
    environment: Literal["sandbox"] = "sandbox"
    risk_tier: Literal["low"] = "low"
    action_type: str = Field(pattern=r"^sandbox\.record\.tag$")
    trigger: str
    input_schema: dict[str, str]
    service_identity: str
    permissions: list[Literal["synthetic.record.read", "synthetic.record.tag"]]
    max_attempts: int = Field(ge=1, le=3)
    idempotency_strategy: str
    dead_letter_owner: str
    alert_owner: str
    rollback_procedure: str
    enabled: bool = False

    @model_validator(mode="after")
    def least_privilege_and_recovery(self) -> WorkflowDefinition:
        if "synthetic.record.tag" not in self.permissions:
            raise ValueError("Workflow lacks the minimum sandbox tag permission")
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("Workflow permissions must be unique")
        for value in (self.idempotency_strategy, self.dead_letter_owner,
                      self.alert_owner, self.rollback_procedure):
            if not value.strip():
                raise ValueError("Workflow recovery and ownership fields are required")
        return self


class WorkflowLibrary:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str, str, str, int], WorkflowDefinition] = {}

    def add(self, *items: WorkflowDefinition) -> None:
        for item in items:
            key = (item.tenant_id, item.client_id, item.project_id, item.id, item.version)
            if key in self._definitions:
                raise ActionPolicyError("Conflicting workflow definition version")
            self._definitions[key] = item.model_copy(deep=True)

    def get(self, workflow_id: str, version: int, *, context: UserContext,
            client_id: str, project_id: str) -> WorkflowDefinition:
        if project_id not in context.project_ids:
            item = None
        else:
            item = self._definitions.get((context.tenant_id, client_id, project_id,
                                          workflow_id, version))
        if item is None:
            raise ScopeDenied("Workflow is outside the authorized scope")
        return item.model_copy(deep=True)


class SandboxActionRequest(BaseModel):
    """Exact, immutable action scope. Only synthetic sandbox records are allowed."""

    tenant_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    initiator_id: str = Field(min_length=1)
    action_type: str = Field(pattern=r"^sandbox\.record\.(tag|restore)$")
    target: str = Field(pattern=r"^synthetic://[a-zA-Z0-9._/-]+$")
    payload: dict[str, Any]
    expected_current: dict[str, Any]
    rollback_plan: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8)
    evidence: list[Evidence] = Field(min_length=1)

    @model_validator(mode="after")
    def restrict_payload(self) -> SandboxActionRequest:
        if self.action_type == "sandbox.record.tag":
            if set(self.payload) != {"tag", "value"} or not isinstance(self.payload["tag"], str):
                raise ValueError("Tag actions require only string tag and value fields")
        elif set(self.payload) != {"record"} or not isinstance(self.payload["record"], dict):
            raise ValueError("Restore actions require only a record object")
        untrusted = json.dumps({"payload": self.payload, "rollback": self.rollback_plan})
        if _INJECTION.search(untrusted):
            raise ValueError("Action input contains a possible prompt-injection instruction")
        return self

    @property
    def digest(self) -> str:
        return _sha256(self.model_dump(mode="json"))


class ApprovalPacket(BaseModel):
    id: str
    request: SandboxActionRequest
    request_digest: str
    required_approver_group: str
    state: ApprovalState = ApprovalState.PENDING
    created_at: datetime
    expires_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    approval_reason: str | None = None


class TokenClaims(BaseModel):
    packet_id: str
    request_digest: str
    tenant_id: str
    project_id: str
    initiator_id: str
    nonce: str
    issued_at: datetime
    expires_at: datetime


class ActionReceipt(BaseModel):
    id: str
    packet_id: str
    idempotency_key: str
    request_digest: str
    state: ExecutionState
    result: dict[str, Any]
    rollback_request: dict[str, Any]
    executed_at: datetime


class DeadLetter(BaseModel):
    id: str
    packet_id: str
    request_digest: str
    error: str
    attempts: int = 1
    created_at: datetime


class AuditEvent(BaseModel):
    sequence: int
    event_type: str
    tenant_id: str
    project_id: str
    actor_id: str
    packet_id: str | None = None
    request_digest: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
    previous_hash: str
    event_hash: str


class AuditReconstruction(BaseModel):
    valid: bool
    events: list[AuditEvent]
    errors: list[str]


class ControlMetrics(BaseModel):
    pending_approvals: int
    approved_approvals: int
    consumed_approvals: int
    successful_actions: int
    dead_letters: int
    active_kill_switches: int


class SandboxAdapter(Protocol):
    def execute(self, request: SandboxActionRequest) -> tuple[dict[str, Any], dict[str, Any]]: ...


class SyntheticRecordAdapter:
    """In-memory reversible adapter; it cannot address network or production targets."""

    def __init__(self, records: dict[str, dict[str, Any]] | None = None,
                 *, fail_targets: set[str] | None = None) -> None:
        self.records = {key: dict(value) for key, value in (records or {}).items()}
        self.fail_targets = fail_targets or set()
        self.calls = 0

    def execute(self, request: SandboxActionRequest) -> tuple[dict[str, Any], dict[str, Any]]:
        self.calls += 1
        if request.target in self.fail_targets:
            raise RuntimeError("Synthetic adapter failure")
        if request.target not in self.records:
            raise KeyError("Synthetic target does not exist")
        current = dict(self.records[request.target])
        if current != request.expected_current:
            raise ActionPolicyError("Target changed after approval; expected state does not match")
        if request.action_type == "sandbox.record.tag":
            updated = dict(current)
            updated[request.payload["tag"]] = request.payload["value"]
        else:
            updated = dict(request.payload["record"])
        self.records[request.target] = updated
        rollback = {"action_type": "sandbox.record.restore", "target": request.target,
                    "payload": {"record": current}, "expected_current": updated}
        return {"target": request.target, "record": updated}, rollback


class ActionControlStore:
    """Durable SQLite approval, replay, kill-switch, dead-letter, and audit store."""

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS approval_packets (
                    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT NOT NULL,
                    request_json TEXT NOT NULL, request_digest TEXT NOT NULL,
                    approver_group TEXT NOT NULL, state TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    approved_by TEXT, approved_at TEXT, approval_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS consumed_tokens (
                    nonce TEXT PRIMARY KEY, packet_id TEXT NOT NULL, consumed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    id TEXT PRIMARY KEY, packet_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL, request_digest TEXT NOT NULL,
                    state TEXT NOT NULL, result_json TEXT NOT NULL,
                    rollback_json TEXT NOT NULL, executed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dead_letters (
                    id TEXT PRIMARY KEY, packet_id TEXT NOT NULL, request_digest TEXT NOT NULL,
                    error TEXT NOT NULL, attempts INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kill_switches (
                    tenant_id TEXT NOT NULL, action_type TEXT NOT NULL, active INTEGER NOT NULL,
                    reason TEXT NOT NULL, changed_by TEXT NOT NULL, changed_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, action_type)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def submit(self, request: SandboxActionRequest, *, context: UserContext,
               approver_group: str, now: datetime | None = None,
               ttl: timedelta = timedelta(hours=4)) -> ApprovalPacket:
        now = now or datetime.now(UTC)
        _authorize_request(request, context=context)
        if not approver_group.strip():
            raise ActionPolicyError("An accountable approver group is required")
        packet = ApprovalPacket(id=str(uuid4()), request=request,
            request_digest=request.digest, required_approver_group=approver_group,
            created_at=now, expires_at=now + ttl)
        with self._connect() as connection:
            prior = connection.execute(
                "SELECT request_digest FROM approval_packets WHERE tenant_id=? AND project_id=? "
                "AND json_extract(request_json, '$.idempotency_key')=?",
                (request.tenant_id, request.project_id, request.idempotency_key)).fetchone()
            if prior:
                if prior["request_digest"] != request.digest:
                    raise ActionPolicyError("Idempotency key is already bound to another payload")
                raise ActionPolicyError("An approval packet already exists for this idempotency key")
            connection.execute("""INSERT INTO approval_packets
                (id, tenant_id, project_id, request_json, request_digest, approver_group,
                 state, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (packet.id, request.tenant_id, request.project_id,
                 request.model_dump_json(), request.digest, approver_group,
                 packet.state.value, now.isoformat(), packet.expires_at.isoformat()))
            self._audit(connection, event_type="approval_requested", request=request,
                        actor_id=context.user_id, packet_id=packet.id, now=now)
        return packet

    def approve(self, packet_id: str, *, context: UserContext, reason: str,
                now: datetime | None = None) -> ApprovalPacket:
        now = now or datetime.now(UTC)
        if not reason.strip():
            raise ApprovalDenied("An approval reason is required")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._packet_row(connection, packet_id)
            request = SandboxActionRequest.model_validate_json(row["request_json"])
            if (request.tenant_id != context.tenant_id
                    or request.project_id not in context.project_ids):
                raise ScopeDenied("Approval is outside the authenticated tenant/project scope")
            if row["state"] != ApprovalState.PENDING.value:
                raise ApprovalDenied("Only pending packets can be approved")
            if now >= datetime.fromisoformat(row["expires_at"]):
                connection.execute("UPDATE approval_packets SET state=? WHERE id=?",
                                   (ApprovalState.EXPIRED.value, packet_id))
                raise ApprovalDenied("Approval packet expired")
            if context.user_id == request.initiator_id:
                raise ApprovalDenied("Initiator cannot approve their own action")
            if row["approver_group"] not in context.group_ids:
                raise ApprovalDenied("User lacks the required approver role")
            connection.execute("""UPDATE approval_packets SET state=?, approved_by=?,
                approved_at=?, approval_reason=? WHERE id=?""",
                (ApprovalState.APPROVED.value, context.user_id, now.isoformat(),
                 reason.strip(), packet_id))
            self._audit(connection, event_type="approval_granted", request=request,
                        actor_id=context.user_id, packet_id=packet_id,
                        detail={"reason": reason.strip()}, now=now)
            return self._decode_packet(self._packet_row(connection, packet_id))

    def packet(self, packet_id: str, *, context: UserContext) -> ApprovalPacket:
        with self._connect() as connection:
            packet = self._decode_packet(self._packet_row(connection, packet_id))
        _authorize_request(packet.request, context=context)
        return packet

    def set_kill_switch(self, *, tenant_id: str, action_type: str, active: bool,
                        context: UserContext, reason: str,
                        now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        if tenant_id != context.tenant_id or "automation_admin" not in context.group_ids:
            raise ApprovalDenied("Automation admin authority is required")
        if not reason.strip():
            raise ActionPolicyError("Kill-switch changes require a reason")
        with self._connect() as connection:
            connection.execute("""INSERT INTO kill_switches
                (tenant_id, action_type, active, reason, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(tenant_id, action_type) DO UPDATE SET
                active=excluded.active, reason=excluded.reason,
                changed_by=excluded.changed_by, changed_at=excluded.changed_at""",
                (tenant_id, action_type, int(active), reason.strip(),
                 context.user_id, now.isoformat()))
            synthetic = SandboxActionRequest(tenant_id=tenant_id, client_id="control",
                project_id=next(iter(context.project_ids), "control"), initiator_id=context.user_id,
                action_type="sandbox.record.tag", target="synthetic://control/kill-switch",
                payload={"tag": "active", "value": active}, expected_current={},
                rollback_plan="Reverse the kill-switch state.", idempotency_key=str(uuid4()),
                evidence=[Evidence(source_id="admin-control", title="Administrative control")])
            self._audit(connection, event_type="kill_switch_changed", request=synthetic,
                actor_id=context.user_id, detail={"active": active, "reason": reason.strip(),
                                                  "action_type": action_type}, now=now)

    def kill_switch_active(self, tenant_id: str, action_type: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT active FROM kill_switches WHERE tenant_id=? "
                "AND action_type IN (?, '*') ORDER BY action_type DESC LIMIT 1",
                (tenant_id, action_type)).fetchone()
        return bool(row and row["active"])

    def dead_letters(self, *, context: UserContext) -> list[DeadLetter]:
        with self._connect() as connection:
            rows = connection.execute("""SELECT d.* FROM dead_letters d
                JOIN approval_packets p ON p.id=d.packet_id WHERE p.tenant_id=?
                ORDER BY d.created_at""", (context.tenant_id,)).fetchall()
        return [DeadLetter(**dict(row)) for row in rows]

    def metrics(self, *, context: UserContext) -> ControlMetrics:
        with self._connect() as connection:
            counts = {row["state"]: row["count"] for row in connection.execute(
                "SELECT state, COUNT(*) AS count FROM approval_packets WHERE tenant_id=? "
                "GROUP BY state", (context.tenant_id,)).fetchall()}
            successful = connection.execute("""SELECT COUNT(*) AS count FROM receipts r
                JOIN approval_packets p ON p.id=r.packet_id WHERE p.tenant_id=?
                AND r.state=?""", (context.tenant_id, ExecutionState.SUCCEEDED.value)).fetchone()
            dead = connection.execute("""SELECT COUNT(*) AS count FROM dead_letters d
                JOIN approval_packets p ON p.id=d.packet_id WHERE p.tenant_id=?""",
                (context.tenant_id,)).fetchone()
            switches = connection.execute("SELECT COUNT(*) AS count FROM kill_switches "
                "WHERE tenant_id=? AND active=1", (context.tenant_id,)).fetchone()
        return ControlMetrics(
            pending_approvals=counts.get(ApprovalState.PENDING.value, 0),
            approved_approvals=counts.get(ApprovalState.APPROVED.value, 0),
            consumed_approvals=counts.get(ApprovalState.CONSUMED.value, 0),
            successful_actions=successful["count"], dead_letters=dead["count"],
            active_kill_switches=switches["count"])

    def reconstruct(self, *, context: UserContext) -> AuditReconstruction:
        with self._connect() as connection:
            rows = connection.execute("""SELECT * FROM audit_events
                WHERE json_extract(event_json, '$.tenant_id')=? ORDER BY sequence""",
                (context.tenant_id,)).fetchall()
        events, errors = [], []
        prior = "GENESIS"
        for row in rows:
            values = json.loads(row["event_json"])
            calculated = _sha256({"event": values, "previous_hash": row["previous_hash"]})
            if row["previous_hash"] != prior:
                errors.append(f"Sequence {row['sequence']} has broken predecessor")
            if not hmac.compare_digest(calculated, row["event_hash"]):
                errors.append(f"Sequence {row['sequence']} has invalid hash")
            try:
                event = AuditEvent(sequence=row["sequence"], previous_hash=row["previous_hash"],
                                   event_hash=row["event_hash"], **values)
            except ValidationError:
                errors.append(f"Sequence {row['sequence']} contains malformed event data")
            else:
                events.append(event)
            prior = row["event_hash"]
        return AuditReconstruction(valid=not errors, events=events, errors=errors)

    @staticmethod
    def _packet_row(connection: sqlite3.Connection, packet_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM approval_packets WHERE id=?", (packet_id,)).fetchone()
        if row is None:
            raise KeyError(packet_id)
        return row

    @staticmethod
    def _decode_packet(row: sqlite3.Row) -> ApprovalPacket:
        return ApprovalPacket(id=row["id"],
            request=SandboxActionRequest.model_validate_json(row["request_json"]),
            request_digest=row["request_digest"], required_approver_group=row["approver_group"],
            state=row["state"], created_at=row["created_at"], expires_at=row["expires_at"],
            approved_by=row["approved_by"], approved_at=row["approved_at"],
            approval_reason=row["approval_reason"])

    @staticmethod
    def _audit(connection: sqlite3.Connection, *, event_type: str,
               request: SandboxActionRequest, actor_id: str, packet_id: str | None = None,
               detail: dict[str, Any] | None = None, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        prior_row = connection.execute("""SELECT event_hash FROM audit_events
            WHERE json_extract(event_json, '$.tenant_id')=?
            ORDER BY sequence DESC LIMIT 1""", (request.tenant_id,)).fetchone()
        previous = prior_row["event_hash"] if prior_row else "GENESIS"
        event = {"event_type": event_type, "tenant_id": request.tenant_id,
                 "project_id": request.project_id, "actor_id": actor_id,
                 "packet_id": packet_id, "request_digest": request.digest,
                 "detail": detail or {}, "occurred_at": now.isoformat()}
        event_hash = _sha256({"event": event, "previous_hash": previous})
        connection.execute("INSERT INTO audit_events (event_json, previous_hash, event_hash) "
                           "VALUES (?, ?, ?)",
                           (json.dumps(event, sort_keys=True), previous, event_hash))


class SignedActionTokenService:
    def __init__(self, secret: bytes) -> None:
        if len(secret) < 32:
            raise ValueError("Signing secret must contain at least 32 bytes")
        self._secret = secret

    def issue(self, packet: ApprovalPacket, *, now: datetime | None = None,
              ttl: timedelta = timedelta(minutes=15)) -> str:
        now = now or datetime.now(UTC)
        if packet.state != ApprovalState.APPROVED:
            raise ApprovalDenied("Only approved packets can receive action tokens")
        expires = min(now + ttl, packet.expires_at)
        claims = TokenClaims(packet_id=packet.id, request_digest=packet.request_digest,
            tenant_id=packet.request.tenant_id, project_id=packet.request.project_id,
            initiator_id=packet.request.initiator_id, nonce=str(uuid4()),
            issued_at=now, expires_at=expires)
        payload = _b64(claims.model_dump_json().encode())
        signature = _b64(hmac.new(self._secret, payload.encode(), hashlib.sha256).digest())
        return f"{payload}.{signature}"

    def verify(self, token: str, *, now: datetime | None = None) -> TokenClaims:
        now = now or datetime.now(UTC)
        try:
            payload, signature = token.split(".", 1)
            expected = _b64(hmac.new(self._secret, payload.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise TokenRejected("Action token signature is invalid")
            claims = TokenClaims.model_validate_json(_unb64(payload))
        except TokenRejected:
            raise
        except (ValueError, json.JSONDecodeError) as exc:
            raise TokenRejected("Action token is malformed") from exc
        if now >= claims.expires_at:
            raise TokenRejected("Action token expired")
        return claims


class SandboxActionGateway:
    def __init__(self, *, store: ActionControlStore,
                 tokens: SignedActionTokenService, adapter: SandboxAdapter) -> None:
        self.store, self.tokens, self.adapter = store, tokens, adapter

    def execute(self, request: SandboxActionRequest, *, token: str,
                context: UserContext, now: datetime | None = None) -> ActionReceipt:
        now = now or datetime.now(UTC)
        _authorize_request(request, context=context)
        claims = self.tokens.verify(token, now=now)
        if self.store.kill_switch_active(request.tenant_id, request.action_type):
            raise KillSwitchActive("Action execution is disabled by the kill switch")
        if (claims.request_digest != request.digest or claims.tenant_id != request.tenant_id
                or claims.project_id != request.project_id
                or claims.initiator_id != request.initiator_id):
            raise TokenRejected("Token does not authorize this exact action")
        with self.store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            packet = self.store._decode_packet(self.store._packet_row(connection, claims.packet_id))
            used = connection.execute("SELECT 1 FROM consumed_tokens WHERE nonce=?",
                                      (claims.nonce,)).fetchone()
            if used:
                raise TokenRejected("Action token replay detected")
            if packet.state != ApprovalState.APPROVED:
                raise TokenRejected("Approval is not executable")
            if packet.request_digest != request.digest:
                raise TokenRejected("Approved payload does not match execution payload")
            prior = connection.execute("SELECT * FROM receipts WHERE idempotency_key=?",
                                       (request.idempotency_key,)).fetchone()
            if prior:
                raise TokenRejected("Action was already executed")
            connection.execute("INSERT INTO consumed_tokens (nonce, packet_id, consumed_at) "
                               "VALUES (?, ?, ?)",
                               (claims.nonce, claims.packet_id, now.isoformat()))
            try:
                result, rollback = self.adapter.execute(request)
            except Exception as exc:
                dead_id = str(uuid4())
                connection.execute("""INSERT INTO dead_letters
                    (id, packet_id, request_digest, error, attempts, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (dead_id, packet.id, request.digest, type(exc).__name__, 1, now.isoformat()))
                connection.execute("UPDATE approval_packets SET state=? WHERE id=?",
                    (ApprovalState.CONSUMED.value, packet.id))
                self.store._audit(connection, event_type="action_failed", request=request,
                    actor_id=context.user_id, packet_id=packet.id,
                    detail={"dead_letter_id": dead_id, "error": type(exc).__name__}, now=now)
                connection.commit()
                raise ActionExecutionError("Sandbox action failed and was dead-lettered") from exc
            receipt = ActionReceipt(id=str(uuid4()), packet_id=packet.id,
                idempotency_key=request.idempotency_key, request_digest=request.digest,
                state=ExecutionState.SUCCEEDED, result=result, rollback_request=rollback,
                executed_at=now)
            connection.execute("""INSERT INTO receipts
                (id, packet_id, idempotency_key, request_digest, state, result_json,
                 rollback_json, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt.id, packet.id, receipt.idempotency_key, request.digest,
                 receipt.state.value, json.dumps(result, sort_keys=True),
                 json.dumps(rollback, sort_keys=True), now.isoformat()))
            connection.execute("UPDATE approval_packets SET state=? WHERE id=?",
                (ApprovalState.CONSUMED.value, packet.id))
            self.store._audit(connection, event_type="action_succeeded", request=request,
                actor_id=context.user_id, packet_id=packet.id,
                detail={"receipt_id": receipt.id, "rollback": rollback}, now=now)
        return receipt


def load_synthetic_workflows(path: Path | str) -> tuple[WorkflowLibrary,
                                                         dict[str, dict[str, Any]]]:
    data = json.loads(Path(path).read_text())
    library = WorkflowLibrary()
    library.add(*(WorkflowDefinition(**item) for item in data["workflows"]))
    return library, {key: dict(value) for key, value in data["records"].items()}


def _authorize_request(request: SandboxActionRequest, *, context: UserContext) -> None:
    if request.tenant_id != context.tenant_id or request.project_id not in context.project_ids:
        raise ScopeDenied("Action is outside the authenticated tenant/project scope")
    if request.initiator_id != context.user_id and "automation_approver" not in context.group_ids:
        raise ScopeDenied("User cannot act for the action initiator")


def _sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


_INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|system)|system prompt|developer message|"
    r"exfiltrat|reveal (a )?(secret|credential)|disable (the )?(approval|kill switch)|"
    r"bypass (the )?(approval|policy)|use production)"
)
