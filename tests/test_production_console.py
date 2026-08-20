"""The console, mounted on the portal, running on real identity.

The synthetic console answered every request as one hardcoded user holding
every reviewer group at once. That is why it refused to start in production:
under it the review queue's separation of duties cannot bite, because the
author and the approver are the same person by construction.

These tests cover the replacement. They are written against the mounted portal
rather than the console alone, because the thing that has to hold is the whole
path: a browser presents the portal's session cookie, the console resolves it
to an Entra object ID and the groups Entra actually granted, and every
subsequent boundary — invitation list, project ACL, reviewer group — is decided
from that identity rather than from a fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessera_os.console import (
    ConsoleProject,
    PortalContextProvider,
    create_console_app,
    production_console_fixture,
)
from tessera_os.microsoft import MicrosoftConnectionBroker, MicrosoftPilotSettings
from tessera_os.portal import PortalProject, PortalSettings, create_portal_app
from tessera_os.sessions import COOKIE_NAME, SessionCodec

SECRET = "session-secret-long-enough-for-the-portal-validator"
DERRICK = "592a1eef-0000-0000-0000-000000000001"
RYAN = "592a1eef-0000-0000-0000-000000000002"
OUTSIDER = "592a1eef-0000-0000-0000-00000000dead"


class PortalAuthClient:
    """The portal tests' stand-in, reused so no test dials Microsoft."""

    def __init__(self) -> None:
        self.accounts: list[dict[str, str]] = []

    def initiate_auth_code_flow(self, scopes, redirect_uri):
        return {"state": "state-1", "auth_uri": "https://login.microsoft.test/authorize"}

    def acquire_token_by_auth_code_flow(self, auth_code_flow, auth_response):
        return {"access_token": "server-only", "id_token_claims": {}}

    def get_accounts(self):
        return []

    def acquire_token_silent(self, scopes, account):
        return {"access_token": "server-only"}

    def remove_account(self, account):
        return None


@pytest.fixture
def portal(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_ENV", "production")
    microsoft = MicrosoftPilotSettings(
        enabled=True, tenant_id="tenant-id", client_id="client-id",
        client_secret="secret", cache_key="unused-for-injected-client",
        redirect_uri="https://api.tesseraag.com/v1/integrations/microsoft/callback",
        project_resources={"internal-pilot": {
            "site_id": "site", "drive_id": "drive", "zone": "internal"}})
    broker = MicrosoftConnectionBroker(settings=microsoft, cache_path=Path("unused"),
                                       auth_client=PortalAuthClient())
    settings = PortalSettings(
        app_url="https://api.tesseraag.com", api_url="https://api.tesseraag.com",
        session_secret=SECRET, allowed_user_ids={DERRICK, RYAN},
        projects={"internal-pilot": PortalProject(
            id="internal-pilot", name="Internal Pilot", summary="First live project")},
        data_dir=tmp_path)
    app = create_portal_app(portal_settings=settings, microsoft_settings=microsoft,
                            broker=broker)
    return TestClient(app)


def sign_in(client: TestClient, user_id: str, *, groups: list[str] | None = None,
            name: str = "Derrick Carlisle") -> None:
    token = SessionCodec(SECRET).issue(user_id=user_id, tenant_id="tenant-1",
                                       display_name=name, group_ids=groups or [])
    client.cookies.set(COOKIE_NAME, token)


# --- the guard ---------------------------------------------------------------

def test_production_still_refuses_the_synthetic_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_ENV", "production")
    with pytest.raises(RuntimeError, match="authenticated context provider"):
        create_console_app(data_dir=tmp_path)


def test_production_is_permitted_with_a_real_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_ENV", "production")
    app = create_console_app(
        data_dir=tmp_path,
        fixture=production_console_fixture([ConsoleProject(
            id="p1", client_id="tessera-internal", name="P1", phase="active",
            status="active", manager_agent_id="structure_manager", summary="")]),
        context_provider=PortalContextProvider(
            codec=SessionCodec(SECRET), project_ids={"p1"},
            allowed_user_ids=frozenset({DERRICK})))
    assert app is not None


def test_a_production_catalog_carries_no_fixture_findings():
    """A review queue seeded with fixtures would put invented findings in front
    of a reviewer through the same interface, and with the same weight, as real
    ones."""
    fixture = production_console_fixture([ConsoleProject(
        id="p1", client_id="tessera-internal", name="P1", phase="active",
        status="active", manager_agent_id="structure_manager", summary="")])
    assert fixture.review_items == []
    assert fixture.pilot_templates == []
    # And it must not carry the sandbox's "everything here is invented" banner,
    # which would read as a disclaimer over real client work.
    assert fixture.notice.lower().startswith("live")


# --- identity ----------------------------------------------------------------

def test_the_console_refuses_an_unauthenticated_caller(portal):
    """And refuses it with a 401, so the interface can send the user to sign in
    rather than quietly rendering its sample dataset."""
    response = portal.get("/console/v1/console/bootstrap")
    assert response.status_code == 401


def test_a_valid_session_for_an_uninvited_account_is_refused(portal):
    """A structurally valid cookie is not an invitation. Mounting the console
    must not widen who may reach the system."""
    sign_in(portal, OUTSIDER)
    assert portal.get("/console/v1/console/bootstrap").status_code == 403


def test_a_tampered_session_is_refused(portal):
    sign_in(portal, DERRICK)
    portal.cookies.set(COOKIE_NAME, portal.cookies[COOKIE_NAME][:-4] + "aaaa")
    assert portal.get("/console/v1/console/bootstrap").status_code == 401


def test_the_session_reports_the_real_user_not_a_fixture_persona(portal):
    sign_in(portal, DERRICK, name="Derrick Carlisle")
    body = portal.get("/console/v1/session").json()
    assert body["user_id"] == DERRICK
    assert body["display_name"] == "Derrick Carlisle"
    assert body["environment"] == "production"
    assert body["synthetic"] is False


def test_privileged_groups_come_from_entra_and_not_from_code(portal):
    """The synthetic identity carried every reviewer group. A real one carries
    what the directory granted, and nothing else."""
    sign_in(portal, DERRICK)
    plain = portal.get("/console/v1/session").json()
    assert plain["groups"] == ["tessera_user"]

    sign_in(portal, RYAN, groups=["qualified_counsel"])
    counsel = portal.get("/console/v1/session").json()
    assert set(counsel["groups"]) == {"tessera_user", "qualified_counsel"}


def test_an_absent_groups_claim_grants_nothing(portal):
    """Entra omits the groups claim entirely once a user exceeds the token's
    group limit. The correct reading is no privilege, never an assumption."""
    sign_in(portal, DERRICK, groups=[])
    assert portal.get("/console/v1/session").json()["groups"] == ["tessera_user"]


# --- the synthetic surfaces stay closed --------------------------------------

@pytest.mark.parametrize("path,body", [
    ("/console/v1/workspace/run", {"project_id": "internal-pilot",
                                   "workflow": "entity_structuring"}),
    ("/console/v1/workspace/reset", {"confirmation": "RESET SYNTHETIC"}),
])
def test_fixture_backed_surfaces_refuse_in_production(portal, path, body):
    """Their output is pre-authored fiction, and in the interface it would be
    indistinguishable from a real engine result."""
    sign_in(portal, DERRICK)
    response = portal.post(path, json=body)
    assert response.status_code == 409
    assert "synthetic" in response.json()["detail"].lower()


# --- the real surface --------------------------------------------------------

def intake(project_id: str = "internal-pilot", **venture) -> dict:
    base = {"venture": "Harbor Point Holdings", "home_state": "Texas",
            "activity": "real_estate_hold", "real_property": True,
            "active_principals": 2, "initial_capital": 2_000_000,
            "capital_source": "founders_only", "exit_intent": "sale",
            "expected_hold_years": 5}
    base.update(venture)
    return {"project_id": project_id, "venture": base}


def test_structure_intake_runs_the_engine_on_the_stated_facts(portal):
    sign_in(portal, DERRICK)
    response = portal.post("/console/v1/structure/intake", json=intake())
    assert response.status_code == 200, response.text
    artifact = response.json()
    assert "Harbor Point Holdings" in str(artifact)


def test_the_intake_evidence_says_it_is_a_statement_not_a_document(portal):
    """StructureRequest requires evidence so nothing enters the record without a
    provenance. The honest provenance for typed facts is the person who typed
    them, and the record should not dress it as a source document."""
    sign_in(portal, DERRICK, name="Derrick Carlisle")
    artifact = portal.post("/console/v1/structure/intake", json=intake()).json()
    evidence = artifact["evidence"]
    assert any("intake" in item["locator"] for item in evidence)
    assert any("stated by Derrick Carlisle" in item["title"] for item in evidence)


def test_intake_refuses_a_project_outside_the_authenticated_scope(portal):
    sign_in(portal, DERRICK)
    response = portal.post("/console/v1/structure/intake",
                           json=intake(project_id="someone-elses-engagement"))
    assert response.status_code == 403


def test_intake_rejects_an_incoherent_venture_rather_than_guessing(portal):
    sign_in(portal, DERRICK)
    response = portal.post("/console/v1/structure/intake",
                           json=intake(home_state=""))
    assert response.status_code == 422


# --- the interface -----------------------------------------------------------

def test_the_console_interface_is_served_on_the_portal_origin(portal):
    """Same origin, because the session cookie is SameSite=Lax and a browser
    will not attach it anywhere else."""
    response = portal.get("/console/", follow_redirects=True)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_the_interface_sends_a_logged_out_visitor_to_sign_in(portal):
    """Rather than to its sample dataset, which would render a populated console
    of invented clients and findings to someone who is merely logged out."""
    page = portal.get("/console/", follow_redirects=True).text
    assert "r.status===401" in page
    assert 'window.location.assign(API.base ? "/"' in page


def test_the_interface_never_hardcodes_an_api_host(portal):
    page = portal.get("/console/", follow_redirects=True).text
    assert "api.tesseraag.com" not in page
    assert 'API.base + path' in page


def test_the_portal_policy_does_not_break_the_console_interface(portal):
    """The portal's script-src is 'self' with no inline allowance, and its
    middleware wraps the mount. Applied to the console -- one inline script with
    fonts embedded as data URIs -- it would render a blank page whose only
    explanation was in the browser console."""
    portal_csp = portal.get("/health").headers["content-security-policy"]
    console_csp = portal.get("/console/", follow_redirects=True).headers[
        "content-security-policy"]

    assert "'unsafe-inline'" not in portal_csp.split("script-src")[1].split(";")[0]
    assert "'unsafe-inline'" in console_csp.split("script-src")[1].split(";")[0]
    assert "font-src 'self' data:" in console_csp
