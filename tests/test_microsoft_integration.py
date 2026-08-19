from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessera_os.console import create_console_app
from tessera_os.integrations import GraphThrottleError, MicrosoftGraphReader
from tessera_os.microsoft import (
    AllowlistedSharePointReader,
    MicrosoftConfigurationError,
    MicrosoftConnectionBroker,
    MicrosoftConnectionStatus,
    MicrosoftIdentity,
    MicrosoftPilotSettings,
    MicrosoftUserConnectionBroker,
)
from tessera_os.schemas import UserContext


class FakeAuthClient:
    def __init__(self) -> None:
        self.accounts = []
        self.flow = {"state": "state-123", "auth_uri": "https://login.microsoft.test/authorize"}

    def initiate_auth_code_flow(self, scopes, redirect_uri):
        assert scopes == ["User.Read", "Sites.Selected"]
        assert redirect_uri.startswith("http://127.0.0.1")
        return self.flow

    def acquire_token_by_auth_code_flow(self, auth_code_flow, auth_response):
        assert auth_code_flow == self.flow
        assert auth_response["state"] == "state-123"
        self.accounts = [{"username": "pilot@example.test", "local_account_id": "user-1"}]
        return {"access_token": "never-exposed", "id_token_claims": {
            "tid": "tenant-id", "oid": "user-1", "preferred_username": "pilot@example.test",
            "name": "Pilot User",
        }}

    def get_accounts(self):
        return list(self.accounts)

    def acquire_token_silent(self, scopes, account):
        return {"access_token": "never-exposed"}

    def remove_account(self, account):
        self.accounts.remove(account)


def settings(*, enabled=True, scopes=("User.Read", "Sites.Selected"),
             zone="engagement", client_id="client-pilot"):
    return MicrosoftPilotSettings(
        enabled=enabled, tenant_id="tenant-id", client_id="client-id",
        client_secret="secret", cache_key="not-used-by-fake-client", scopes=scopes,
        project_resources={"project-1": {
            "site_id": "approved-site", "drive_id": "approved-drive",
            "folder_item_id": "approved-folder",
            "zone": zone, "client_id": client_id,
        }},
    )


def context(projects=("project-1",), groups=("project-team",)):
    return UserContext(tenant_id="tenant-a", user_id="alice",
                       project_ids=set(projects), group_ids=set(groups))


def test_settings_reject_write_broad_and_unmapped_configuration():
    with pytest.raises(ValueError, match="permits only"):
        settings(scopes=("User.Read", "Sites.ReadWrite.All"))
    with pytest.raises(ValueError, match="mapping"):
        MicrosoftPilotSettings(enabled=True, tenant_id="t", client_id="c",
            client_secret="s", cache_key="k", project_resources={})


def test_oauth_broker_binds_state_never_returns_token_and_disconnects(tmp_path):
    auth = FakeAuthClient()
    broker = MicrosoftConnectionBroker(settings=settings(), cache_path=tmp_path / "cache",
                                       auth_client=auth)
    assert broker.begin() == "https://login.microsoft.test/authorize"
    with pytest.raises(MicrosoftConfigurationError, match="state"):
        broker.complete({"state": "attacker-state", "code": "code"})
    assert broker.begin() == "https://login.microsoft.test/authorize"
    broker.complete({"state": "state-123", "code": "code"})
    assert broker.status().connected is True
    assert broker.status().writes_enabled is False
    assert broker.token("user-1") == "never-exposed"
    with pytest.raises(MicrosoftConfigurationError, match="this user"):
        broker.token("user-2")
    broker.disconnect()
    assert broker.status().connected is False


def test_allowlisted_reader_resolves_project_mapping_and_preserves_scope():
    calls = []

    def transport(url, headers):
        calls.append((url, headers))
        return {"value": [{
            "id": "doc-1", "name": "Status.docx", "file": {},
            "lastModifiedDateTime": "2026-08-18T12:00:00+00:00",
            "listItem": {"fields": {
                "ProjectId": "project-1", "TesseraContent": "Milestone is current",
            }},
            "allowedGroupIds": ["project-team"],
        }]}

    reader = AllowlistedSharePointReader(settings=settings(),
        graph_factory=lambda provider: MicrosoftGraphReader(provider, transport=transport),
        token_provider=lambda user_id: f"token-{user_id}")
    documents = reader.project_documents(context=context(), project_id="project-1")
    assert documents[0].content == "Milestone is current"
    assert "sites/approved-site/drives/approved-drive/items/approved-folder/children" in calls[0][0]
    assert "token" not in calls[0][0]
    assert calls[0][1]["Authorization"] == "Bearer token-alice"
    with pytest.raises(PermissionError):
        reader.project_documents(context=context(()), project_id="project-1")
    with pytest.raises(MicrosoftConfigurationError, match="mapping"):
        reader.project_documents(context=context(("unmapped",)), project_id="unmapped")


def test_graph_honors_retry_after_with_bounded_retries():
    attempts = 0
    sleeps = []

    def transport(url, headers):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise GraphThrottleError(3)
        return {"value": []}

    graph = MicrosoftGraphReader(lambda: "token", transport=transport,
                                 sleeper=sleeps.append, max_retries=1)
    assert graph.recent_messages() == []
    assert attempts == 2
    assert sleeps == [3]


def test_console_connection_endpoints_are_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_ENV", "test")
    api = TestClient(create_console_app(data_dir=tmp_path))
    status = api.get("/v1/integrations/microsoft/status").json()
    assert status == {"enabled": False, "configured": False, "connected": False,
                      "scopes": ["User.Read", "Sites.Selected"],
                      "mapped_projects": [], "writes_enabled": False,
                      "account_label": None}
    assert api.post("/v1/integrations/microsoft/connect").status_code == 409


def test_console_exposes_authorization_url_without_token(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_ENV", "test")
    auth = FakeAuthClient()
    broker = MicrosoftConnectionBroker(settings=settings(), cache_path=Path("unused"),
                                       auth_client=auth)
    api = TestClient(create_console_app(data_dir=tmp_path, microsoft_broker=broker))
    response = api.post("/v1/integrations/microsoft/connect")
    assert response.json() == {"authorization_url": "https://login.microsoft.test/authorize"}
    assert "access_token" not in response.text


def test_two_users_receive_separate_encrypted_cache_paths_and_logout(tmp_path):
    counter = 0

    class FlowBroker:
        def __init__(self, path):
            nonlocal counter
            counter += 1
            self.path = path
            self.state = f"state-{counter}"

        def begin_with_state(self):
            return self.state, f"https://login.microsoft.test/{self.state}"

        def complete(self, response):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(b"encrypted-cache")
            return MicrosoftIdentity(
                tenant_id="tenant-id", user_id=response["user_id"],
                display_name=response["user_id"])

        def token(self, user_id=None):
            return f"token:{user_id}:{self.path.name}"

        def status(self, user_id=None):
            return MicrosoftConnectionStatus(
                enabled=True, configured=True, connected=self.path.exists(),
                scopes=["User.Read", "Sites.Selected"], mapped_projects=["project-1"],
                account_label=user_id)

        def disconnect(self, user_id=None):
            if self.path.exists():
                self.path.unlink()

    pool = MicrosoftUserConnectionBroker(
        settings=settings(), cache_dir=tmp_path / "caches",
        broker_factory=FlowBroker)
    pool.begin()
    pool.begin()
    pool.complete({"state": "state-1", "user_id": "derrick"})
    pool.complete({"state": "state-2", "user_id": "ryan"})

    derrick_path = pool._user_path("derrick")
    ryan_path = pool._user_path("ryan")
    assert derrick_path != ryan_path
    assert derrick_path.exists() and ryan_path.exists()
    assert "derrick" in pool.token("derrick")
    assert "ryan" in pool.token("ryan")

    pool.disconnect("ryan")
    assert not ryan_path.exists()
    assert derrick_path.exists()
    assert pool.status("derrick").connected is True
