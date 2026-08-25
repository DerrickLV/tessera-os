import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessera_os.integrations import IntegrationError, MicrosoftGraphReader
from tessera_os.microsoft import (
    AllowlistedSharePointReader,
    MicrosoftConnectionBroker,
    MicrosoftPilotSettings,
)
from tessera_os.portal import PortalSettings, create_portal_app


class PortalAuthClient:
    def __init__(self, *, user_id="user-1") -> None:
        self.user_id = user_id
        self.accounts = []

    def initiate_auth_code_flow(self, scopes, redirect_uri):
        return {"state": "state-1", "auth_uri": "https://login.microsoft.test/authorize"}

    def acquire_token_by_auth_code_flow(self, auth_code_flow, auth_response):
        self.accounts = [{
            "username": "pilot@example.test",
            "local_account_id": self.user_id,
        }]
        return {"access_token": "server-only", "id_token_claims": {
            "tid": "tenant-id", "oid": self.user_id,
            "preferred_username": "pilot@example.test", "name": "Pilot User",
        }}

    def get_accounts(self):
        return list(self.accounts)

    def acquire_token_silent(self, scopes, account):
        return {"access_token": "server-only"}

    def remove_account(self, account):
        self.accounts.remove(account)


def portal_settings(tmp_path, *, allowed=("user-1",), projects=None):
    return PortalSettings(app_url="https://app.tesseraag.com",
        api_url="https://api.tesseraag.com",
        session_secret="s" * 48, allowed_user_ids=set(allowed),
        projects=projects or {"project-1": {
            "id": "project-1", "name": "Pilot Project", "summary": "Synthetic pilot",
        }}, data_dir=tmp_path)


def microsoft_settings():
    return MicrosoftPilotSettings(enabled=True, tenant_id="tenant-id", client_id="client-id",
        client_secret="secret", cache_key="unused-for-injected-client",
        redirect_uri="https://api.tesseraag.com/v1/integrations/microsoft/callback",
        project_resources={"project-1": {"site_id": "site", "drive_id": "drive"}})


def app_client(tmp_path, *, user_id="user-1", allowed=("user-1",)):
    microsoft = microsoft_settings()
    broker = MicrosoftConnectionBroker(settings=microsoft, cache_path=Path("unused"),
        auth_client=PortalAuthClient(user_id=user_id))
    app = create_portal_app(portal_settings=portal_settings(tmp_path, allowed=allowed),
                            microsoft_settings=microsoft, broker=broker)
    return TestClient(app)


def sign_in(api):
    start = api.get("/v1/auth/microsoft/start", follow_redirects=False)
    assert start.status_code == 302
    callback = api.get(
        "/v1/integrations/microsoft/callback?state=state-1&code=one-time-code",
        follow_redirects=False)
    return callback


def test_portal_is_invite_only_and_sets_secure_server_session(tmp_path):
    api = app_client(tmp_path)
    assert api.get("/v1/session").status_code == 401
    callback = sign_in(api)
    assert callback.status_code == 303
    assert callback.headers["location"].startswith("https://app.tesseraag.com")
    cookie = callback.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "Domain=" not in cookie
    token = cookie.split(";", 1)[0].split("=", 1)[1]
    session = api.get("/v1/session", headers={"Cookie": f"tessera_session={token}"})
    assert session.status_code == 200
    assert session.json()["projects"][0]["id"] == "project-1"
    assert "server-only" not in session.text


def test_session_selects_signed_in_user_when_cache_has_multiple_accounts(tmp_path):
    microsoft = microsoft_settings()
    auth_client = PortalAuthClient()
    broker = MicrosoftConnectionBroker(settings=microsoft, cache_path=Path("unused"),
        auth_client=auth_client)
    app = create_portal_app(portal_settings=portal_settings(tmp_path),
                            microsoft_settings=microsoft, broker=broker)
    api = TestClient(app)
    callback = sign_in(api)
    token = callback.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    auth_client.accounts.append({
        "username": "other@example.test",
        "local_account_id": "user-2",
    })

    session = api.get("/v1/session", headers={"Cookie": f"tessera_session={token}"})
    status_response = api.get("/v1/integrations/microsoft/status",
        headers={"Cookie": f"tessera_session={token}"})

    assert session.status_code == 200
    assert session.json()["microsoft_connected"] is True
    assert status_response.status_code == 200
    assert status_response.json()["connected"] is True


def test_portal_rejects_uninvited_microsoft_identity(tmp_path):
    api = app_client(tmp_path, user_id="attacker", allowed=("user-1",))
    api.get("/v1/auth/microsoft/start", follow_redirects=False)
    response = api.get(
        "/v1/integrations/microsoft/callback?state=state-1&code=code",
        follow_redirects=False)
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_portal_rejects_tampered_session_and_multiple_user_configuration(tmp_path):
    api = app_client(tmp_path)
    response = api.get(
        "/v1/session",
        headers={"Cookie": "tessera_session=attacker-controlled"},
    )
    assert response.status_code == 401
    assert "invalid or expired" in response.json()["detail"]
    with pytest.raises(ValueError, match="at most 5 items"):
        portal_settings(tmp_path, allowed=tuple(f"user-{n}" for n in range(6)))


def test_portal_requires_exact_project_mapping_and_https(tmp_path):
    with pytest.raises(ValueError, match="HTTPS"):
        PortalSettings(app_url="http://app.tesseraag.com", api_url="https://api.tesseraag.com",
            session_secret="s" * 48,
            allowed_user_ids={"user-1"}, projects={"project-1": {
                "id": "project-1", "name": "Pilot"}}, data_dir=tmp_path)
    microsoft = microsoft_settings()
    broker = MicrosoftConnectionBroker(settings=microsoft, cache_path=Path("unused"),
        auth_client=PortalAuthClient())
    mismatched = portal_settings(tmp_path, projects={"other": {"id": "other", "name": "Other"}})
    with pytest.raises(RuntimeError, match="match exactly"):
        create_portal_app(portal_settings=mismatched, microsoft_settings=microsoft, broker=broker)


def test_portal_health_discloses_no_configuration(tmp_path):
    """It reports that the console is up, and never why it is not.

    /health is unauthenticated, and the reason a console failed to build is a
    SQLite error carrying a filesystem path. The state belongs here so a
    degraded deployment announces itself; the detail belongs in the logs."""
    body = app_client(tmp_path).get("/health").json()
    assert body == {"status": "ok", "mode": "production", "writes": "disabled",
                    "console": "ok"}


def test_a_broken_console_degrades_the_portal_instead_of_killing_it(tmp_path, monkeypatch):
    """A locked SQLite file under the console's data directory once took the
    whole portal down -- nobody could sign in, reach SharePoint, or read the
    review queue, over a subsystem none of those depend on."""
    import tessera_os.console as console_module

    def refuse(**_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(console_module, "create_console_app", refuse)
    api = app_client(tmp_path)
    assert api.get("/health").json()["console"] == "unavailable"
    assert api.get("/health").status_code == 200
    assert api.get("/console/").status_code == 404
    # The reason is retained, out of reach of an unauthenticated caller.
    assert "locked" in api.app.state.console_error


def test_portal_has_no_document_write_or_approval_bypass_route(tmp_path):
    api = app_client(tmp_path)
    assert api.post("/v1/projects/project-1/documents").status_code == 405
    assert api.delete("/v1/projects/project-1/documents/doc-1").status_code == 404
    assert api.post("/v1/approvals/bypass").status_code == 404


# --- 2.7: honest empty states for the document listing --------------------------------------
#
# The portal used to render "No approved documents found" whether the folder
# was empty, misconfigured, or the read crossed a trust boundary -- three
# different failures with one indistinguishable message. These exercise all
# three through the real /v1/projects/{id}/documents endpoint.


class PartnerAuthClient(PortalAuthClient):
    """A signed-in identity that carries the mapped partner Entra group."""

    def acquire_token_by_auth_code_flow(self, auth_code_flow, auth_response):
        result = super().acquire_token_by_auth_code_flow(auth_code_flow, auth_response)
        result["id_token_claims"]["groups"] = ["partner-entra-id"]
        return result


def signed_in_cookie(api) -> str:
    callback = sign_in(api)
    return callback.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]


def partner_app(tmp_path, monkeypatch, *, transport):
    monkeypatch.setenv("TESSERA_M365_GROUP_MAP", '{"partner-entra-id": "tessera_partner"}')
    microsoft = MicrosoftPilotSettings(
        enabled=True, tenant_id="tenant-id", client_id="client-id", client_secret="secret",
        cache_key="unused-for-injected-client",
        redirect_uri="https://api.tesseraag.com/v1/integrations/microsoft/callback",
        project_resources={"project-1": {
            "site_id": "site", "drive_id": "drive", "root_path": "Projects/Internal Pilot",
        }})
    broker = MicrosoftConnectionBroker(settings=microsoft, cache_path=Path("unused"),
        auth_client=PartnerAuthClient())
    reader = AllowlistedSharePointReader(
        settings=microsoft, token_provider=broker.token,
        graph_factory=lambda provider: MicrosoftGraphReader(provider, transport=transport))
    app = create_portal_app(portal_settings=portal_settings(tmp_path),
                            microsoft_settings=microsoft, broker=broker, sharepoint=reader)
    return TestClient(app)


def test_an_empty_project_folder_returns_an_empty_list(tmp_path, monkeypatch):
    def transport(url, headers):
        if "root:/" in url:
            return {"id": "root-item", "folder": {}}
        return {"value": []}

    api = partner_app(tmp_path, monkeypatch, transport=transport)
    token = signed_in_cookie(api)
    response = api.get("/v1/projects/project-1/documents",
                       headers={"Cookie": f"tessera_session={token}"})
    assert response.status_code == 200
    assert response.json() == []


def test_a_draft_document_does_not_appear_under_approved_documents(tmp_path, monkeypatch):
    def transport(url, headers):
        if "root:/" in url:
            return {"id": "root-item", "folder": {}}
        if "items/root-item/children" in url:
            return {"value": [
                {"id": "approved-folder", "name": "Approved", "folder": {}},
                {"id": "drafts-folder", "name": "Drafts", "folder": {}},
            ]}
        if "items/approved-folder/children" in url:
            return {"value": [{"id": "memo", "name": "memo.docx", "file": {}, "size": 3}]}
        if "items/drafts-folder/children" in url:
            return {"value": [{"id": "draft1", "name": "draft.docx", "file": {}, "size": 3}]}
        raise AssertionError(f"unexpected url {url}")

    api = partner_app(tmp_path, monkeypatch, transport=transport)
    token = signed_in_cookie(api)
    response = api.get("/v1/projects/project-1/documents",
                       headers={"Cookie": f"tessera_session={token}"})
    titles = {item["title"] for item in response.json()}
    assert titles == {"memo.docx"}


def test_a_misconfigured_root_path_is_a_named_error_only_for_an_authenticated_partner(
        tmp_path, monkeypatch):
    def transport(url, headers):
        raise IntegrationError("simulated 404")

    api = partner_app(tmp_path, monkeypatch, transport=transport)
    token = signed_in_cookie(api)
    response = api.get("/v1/projects/project-1/documents",
                       headers={"Cookie": f"tessera_session={token}"})
    assert response.status_code == 409
    assert "Projects/Internal Pilot" in response.json()["detail"]

    anonymous = api.get("/v1/projects/project-1/documents")
    assert anonymous.status_code == 401
    assert "Projects/Internal Pilot" not in anonymous.text


def test_zone_refusal_uses_the_existing_refusal_message(tmp_path):
    api = app_client(tmp_path)
    callback = sign_in(api)
    token = callback.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    response = api.get("/v1/projects/project-1/documents",
                       headers={"Cookie": f"tessera_session={token}"})
    assert response.status_code == 403
    assert "partners" in response.json()["detail"]


def test_portal_static_site_avoids_inline_script_handlers():
    root = Path(__file__).parents[1]
    html = (root / "web" / "tessera-portal.html").read_text()
    javascript = (root / "web" / "assets" / "portal.js").read_text()
    assert 'src="/assets/portal.js"' in html
    assert "onclick=" not in html
    # Same-origin, and provably so. A hardcoded API host was what made the
    # deployed portal unusable: every call went to a domain that did not exist,
    # and even had it existed the SameSite=Lax session cookie would not have
    # been attached to it.
    assert "https://api.tesseraag.com" not in javascript
    assert 'const API = "";' in javascript


def test_the_portal_serves_its_own_interface_on_one_origin(tmp_path):
    """The session cookie is SameSite=Lax, which a browser will not attach to a
    cross-origin request. A UI on a separate host produces a sign-in that looks
    successful followed by silent 401s on every call. One origin removes the
    failure mode instead of configuring around it."""
    api = app_client(tmp_path)
    response = api.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_the_interface_carries_its_own_content_security_policy(tmp_path):
    """The policy used to live in netlify.toml, describing a host that was never
    used. Served from here, it has to travel with the response."""
    api = app_client(tmp_path)
    policy = api.get("/health").headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "login.microsoftonline.com" in policy


def test_serving_the_interface_shadows_no_api_route(tmp_path):
    """A StaticFiles mount at "/" would swallow every route declared above it."""
    api = app_client(tmp_path)
    assert api.get("/health").status_code == 200
    assert api.get("/v1/session").status_code in (200, 401)
    assert api.get("/v1/projects").status_code in (200, 401)



def test_the_allowlist_admits_the_second_reviewer_the_queue_requires(tmp_path):
    """A single permitted user deadlocks the whole system.

    Every drafted agreement and structure recommendation carries a
    required_reviewer_group, and ReviewQueue refuses to let an author
    disposition their own item. Cap the allowlist at one and the only person who
    can draft is the only person who cannot approve — so nothing is ever
    approved. The cap has to leave room for the reviewer the queue insists on.
    """
    settings = portal_settings(tmp_path, allowed=("derrick-oid", "ryan-oid"))
    assert settings.allowed_user_ids == frozenset({"derrick-oid", "ryan-oid"})


def test_the_allowlist_still_refuses_an_empty_configuration(tmp_path):
    """Raising the ceiling must not open the floor. An unset variable means
    nobody signs in, not everybody."""
    with pytest.raises(ValueError):
        portal_settings(tmp_path, allowed=())
