import sqlite3
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tessera_os.knowledge import ScopeDenied
from tessera_os.policy import (
    Environment,
    PolicyGateway,
    PolicyOutcome,
    RuntimeAction,
)
from tessera_os.registry import AgentRegistry
from tessera_os.review import ReviewAccessDenied, ReviewQueue
from tessera_os.runtime_controls import (
    BudgetExceeded,
    DLPRedactor,
    RateLimiter,
    RateLimitExceeded,
    RetentionDenied,
    RuntimeAuditStore,
    SecureArtifactStore,
)
from tessera_os.schemas import UserContext
from tessera_os.service import AuthSettings, create_app

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)
AUTH_SECRET = "synthetic-authentication-secret-at-least-32-bytes"


def context(*, groups=()) -> UserContext:
    return UserContext(tenant_id="tenant-a", user_id="alice",
                       project_ids={"project-1"}, group_ids=set(groups))


def runtime_action(**overrides) -> RuntimeAction:
    data = {"tenant_id": "tenant-a", "project_id": "project-1", "user_id": "alice",
            "agent_id": "intelligence_agent", "action": "read",
            "environment": Environment.PRODUCTION}
    data.update(overrides)
    return RuntimeAction(**data)


def auth_settings() -> AuthSettings:
    return AuthSettings(issuer="https://identity.example.invalid",
        audience="tessera-test", verification_key=AUTH_SECRET,
        algorithm="HS256", environment="test")


def token(**overrides) -> str:
    issued_at = datetime.now(UTC)
    claims = {"iss": "https://identity.example.invalid", "aud": "tessera-test",
        "sub": "alice", "tenant_id": "tenant-a", "project_ids": ["project-1"],
        "groups": ["tessera_user"], "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(hours=1)).timestamp())}
    claims.update(overrides)
    return jwt.encode(claims, AUTH_SECRET, algorithm="HS256")


def test_policy_gateway_allows_safe_actions_and_denies_production_writes():
    agent = AgentRegistry().get("intelligence_agent")
    gateway = PolicyGateway()
    assert gateway.evaluate(runtime_action(), context=context(), agent=agent).outcome == "allow"
    decision = gateway.evaluate(runtime_action(action="alert_send"),
                                context=context(), agent=agent)
    assert decision.outcome == PolicyOutcome.DENY
    assert "Production writes" in decision.reason
    assert gateway.evaluate(runtime_action(action="move_funds"),
                            context=context(), agent=agent).outcome == "deny"


def test_policy_gateway_rejects_scope_agent_and_unknown_actions():
    gateway = PolicyGateway()
    agent = AgentRegistry().get("intelligence_agent")
    with pytest.raises(ScopeDenied):
        gateway.evaluate(runtime_action(project_id="project-other"),
                         context=context(), agent=agent)
    assert gateway.evaluate(runtime_action(agent_id="capital_manager"),
                            context=context(), agent=agent).outcome == "deny"
    assert gateway.evaluate(runtime_action(action="invented_action",
        environment="sandbox"), context=context(), agent=agent).outcome == "deny"


def test_qualified_review_role_is_enforced(tmp_path):
    queue = ReviewQueue(tmp_path / "review.db")
    item = queue.submit(tenant_id="tenant-a", project_id="project-1", created_by="author",
        workflow="contract_review", title="Contract", body="draft", evidence=[],
        required_reviewer_group="qualified_counsel")
    with pytest.raises(ReviewAccessDenied, match="qualified reviewer"):
        queue.accept(item_id=item.id, context=context(), reason="Not counsel")
    accepted = queue.accept(item_id=item.id, context=context(groups={"qualified_counsel"}),
                            reason="Counsel reviewed exact draft")
    assert accepted.required_reviewer_group == "qualified_counsel"
    assert accepted.reviewed_by == "alice"


def test_qualified_reviewer_cannot_approve_their_own_draft(tmp_path):
    queue = ReviewQueue(tmp_path / "review.db")
    item = queue.submit(tenant_id="tenant-a", project_id="project-1", created_by="alice",
        workflow="contract_review", title="Contract", body="draft", evidence=[],
        required_reviewer_group="qualified_counsel")
    with pytest.raises(ReviewAccessDenied, match="separation of duties"):
        queue.accept(item_id=item.id, context=context(groups={"qualified_counsel"}),
                     reason="Self approval attempt")


def test_dlp_redacts_tokens_email_and_ssn():
    value = "Bearer secret.token email person@example.com ssn 123-45-6789 sk-abcdefghijklmnop"
    redacted = DLPRedactor.redact(value)
    assert "secret.token" not in redacted
    assert "person@example.com" not in redacted
    assert "123-45-6789" not in redacted
    assert "sk-abcdefghijklmnop" not in redacted


def test_rate_limit_is_tenant_user_scoped_and_recovers_after_window():
    limiter = RateLimiter(limit=2, window=timedelta(minutes=1))
    limiter.check(context=context(), now=NOW)
    limiter.check(context=context(), now=NOW + timedelta(seconds=1))
    with pytest.raises(RateLimitExceeded):
        limiter.check(context=context(), now=NOW + timedelta(seconds=2))
    limiter.check(context=context(), now=NOW + timedelta(minutes=2))


def test_usage_budget_is_atomic_scoped_and_fail_closed(tmp_path):
    store = RuntimeAuditStore(tmp_path / "runtime.db")
    store.set_budget(tenant_id="tenant-a", workflow="route", day=NOW.date(),
                     token_limit=100, cost_limit=1.0)
    budget = store.reserve_usage(tenant_id="tenant-a", workflow="route", day=NOW.date(),
                                 tokens=75, cost_units=0.5)
    assert budget.tokens_used == 75
    with pytest.raises(BudgetExceeded, match="Token"):
        store.reserve_usage(tenant_id="tenant-a", workflow="route", day=NOW.date(),
                            tokens=26, cost_units=0)
    with pytest.raises(BudgetExceeded, match="No approved"):
        store.reserve_usage(tenant_id="tenant-b", workflow="route", day=NOW.date(),
                            tokens=1, cost_units=0)


def test_traces_preserve_versions_scope_and_redact_errors(tmp_path):
    store = RuntimeAuditStore(tmp_path / "runtime.db")
    trace = store.record_trace(context=context(), project_id="project-1", workflow="route",
        agent_id="intelligence_agent", model_version="default-v1", prompt_version="abc123",
        policy_outcome="allow", source_ids=["source-1"], tokens=10, cost_units=0.1,
        error="person@example.com Bearer private-token", now=NOW)
    assert trace.correlation_id
    assert "example.com" not in trace.error
    assert "private-token" not in trace.error
    loaded = store.traces(context=context(), project_id="project-1")[0]
    assert loaded.model_version == "default-v1"
    assert loaded.prompt_version == "abc123"
    with pytest.raises(PermissionError):
        store.traces(context=context(), project_id="project-other")


def test_secure_artifacts_encrypt_scope_retain_hold_purge_and_backup(tmp_path):
    store = SecureArtifactStore(tmp_path / "secure.db", encryption_key=b"1" * 32)
    item = store.put(context=context(), project_id="project-1", category="review",
        value={"secret": "synthetic-sensitive-value"}, retention_days=1, now=NOW)
    assert store.get(item.id, context=context()) == {"secret": "synthetic-sensitive-value"}
    assert b"synthetic-sensitive-value" not in (tmp_path / "secure.db").read_bytes()
    wrong = UserContext(tenant_id="tenant-b", user_id="bob", project_ids={"project-1"})
    with pytest.raises(RetentionDenied):
        store.get(item.id, context=wrong)
    records_admin = context(groups={"records_admin"})
    store.set_legal_hold(item.id, context=records_admin, active=True)
    assert store.purge_expired(context=records_admin, now=NOW + timedelta(days=2)) == 0
    backup = tmp_path / "tenant-backup.db"
    digest = store.backup(backup, context=records_admin)
    assert len(digest) == 64 and backup.exists()
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT COUNT(*) FROM secure_artifacts").fetchone()[0] == 1
    store.set_legal_hold(item.id, context=records_admin, active=False)
    assert store.purge_expired(context=records_admin, now=NOW + timedelta(days=2)) == 1


def test_production_auth_rejects_symmetric_signatures():
    with pytest.raises(ValidationError, match="asymmetric"):
        AuthSettings(issuer="issuer", audience="audience", verification_key=AUTH_SECRET,
                     algorithm="HS256", environment="production")


def test_fastapi_requires_auth_role_scope_and_valid_token(tmp_path):
    app = create_app(auth_settings=auth_settings(),
        audit_store=RuntimeAuditStore(tmp_path / "runtime.db"), rate_limiter=RateLimiter(limit=10))
    client = TestClient(app)
    assert "writes" not in client.get("/health").json()  # nothing here measures it
    assert client.post("/v1/route", json={"task": "monitor policy intelligence",
                                         "project_id": "project-1"}).status_code == 401
    no_role = token(groups=[])
    assert client.post("/v1/route", headers={"Authorization": f"Bearer {no_role}"},
        json={"task": "monitor policy intelligence", "project_id": "project-1"}).status_code == 403
    bad_scope = token(project_ids=["project-other"])
    assert client.post("/v1/route", headers={"Authorization": f"Bearer {bad_scope}"},
        json={"task": "monitor policy intelligence", "project_id": "project-1"}).status_code == 403


def test_fastapi_routes_with_correlation_policy_and_trace(tmp_path):
    audit = RuntimeAuditStore(tmp_path / "runtime.db")
    app = create_app(auth_settings=auth_settings(), audit_store=audit,
                     rate_limiter=RateLimiter(limit=10))
    client = TestClient(app)
    correlation = "9a975548-c81b-4d7c-9dcb-08b2e1e23ca7"
    response = client.post("/v1/route",
        headers={"Authorization": f"Bearer {token()}", "X-Correlation-ID": correlation},
        json={"task": "monitor policy intelligence", "project_id": "project-1"})
    assert response.status_code == 200
    assert response.json()["correlation_id"] == correlation
    assert response.json()["decision"]["primary_agent"] == "intelligence_agent"
    traces = audit.traces(context=context(groups={"tessera_user"}), project_id="project-1")
    assert traces[0].correlation_id == correlation
    assert traces[0].prompt_version
    invalid = client.post("/v1/route",
        headers={"Authorization": f"Bearer {token()}", "X-Correlation-ID": "not-a-uuid"},
        json={"task": "monitor policy intelligence", "project_id": "project-1"})
    assert invalid.status_code == 400


def test_fastapi_returns_429_when_rate_limit_is_exceeded(tmp_path):
    app = create_app(auth_settings=auth_settings(),
        audit_store=RuntimeAuditStore(tmp_path / "runtime.db"),
        rate_limiter=RateLimiter(limit=1))
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token()}"}
    payload = {"task": "monitor policy intelligence", "project_id": "project-1"}
    assert client.post("/v1/route", headers=headers, json=payload).status_code == 200
    response = client.post("/v1/route", headers=headers, json=payload)
    assert response.status_code == 429
