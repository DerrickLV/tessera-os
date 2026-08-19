import json

from tessera_os import cli
from tessera_os.m365_readiness import microsoft_readiness


def complete_environment() -> dict[str, str]:
    return {
        "TESSERA_M365_TENANT_ID": "tenant",
        "TESSERA_M365_CLIENT_ID": "client",
        "TESSERA_M365_CLIENT_SECRET": "secret",
        "TESSERA_M365_CACHE_KEY": "cache-key",
        "TESSERA_SESSION_SECRET": "session-secret",
        "TESSERA_ALLOWED_USER_IDS": "derrick-id,ryan-id",
        "TESSERA_PROJECT_CATALOG": json.dumps({
            "internal-pilot": {"id": "internal-pilot", "name": "Internal Pilot"}}),
        "TESSERA_USER_PROJECTS": json.dumps({
            "derrick-id": ["internal-pilot"], "ryan-id": ["internal-pilot"]}),
        "TESSERA_M365_PROJECT_RESOURCES": json.dumps({
            "internal-pilot": {"site_id": "site", "drive_id": "drive",
                               "folder_item_id": "root", "zone": "internal"}}),
        "TESSERA_M365_GROUP_MAP": json.dumps({"partners-group": "tessera_partner"}),
        "TESSERA_M365_REDIRECT_URI": (
            "https://api.tesseraag.com/v1/integrations/microsoft/callback"),
    }


def test_complete_local_configuration_leaves_only_manual_microsoft_gates():
    report = microsoft_readiness(complete_environment())
    assert report.configuration_ready is True
    assert not [item for item in report.checks if item.status == "fail"]
    assert [item for item in report.checks if item.status == "manual"]


def test_checker_fails_closed_on_missing_zone_group_and_second_user():
    env = complete_environment()
    env["TESSERA_ALLOWED_USER_IDS"] = "derrick-id"
    env["TESSERA_USER_PROJECTS"] = json.dumps({"derrick-id": ["internal-pilot"]})
    env["TESSERA_M365_PROJECT_RESOURCES"] = json.dumps({
        "internal-pilot": {"site_id": "site", "drive_id": "drive"}})
    env["TESSERA_M365_GROUP_MAP"] = json.dumps({"other": "tessera_user"})
    report = microsoft_readiness(env)
    assert report.configuration_ready is False
    details = " ".join(item.detail for item in report.checks if item.status == "fail")
    assert "requires two" in details
    assert "zone" in details
    assert "tessera_partner" in details


def test_cli_prints_json_without_disclosing_secret_values(monkeypatch, capsys):
    for key, value in complete_environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["tessera", "m365-check", "--json"])
    cli.main()
    output = capsys.readouterr().out
    assert json.loads(output)["configuration_ready"] is True
    assert "session-secret" not in output
    assert '"secret"' not in output
