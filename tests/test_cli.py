import json

import pytest

from tessera_os import cli


def _run(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["tessera", *argv])
    cli.main()


def test_list_command_prints_all_agents(monkeypatch, capsys):
    _run(monkeypatch, "list")
    out = capsys.readouterr().out
    assert "executive_assistant: Executive Assistant" in out
    assert out.count("\n") == 13


def test_route_command_prints_route_decision_json(monkeypatch, capsys):
    _run(monkeypatch, "route", "Review the indemnity clause")
    decision = json.loads(capsys.readouterr().out)
    assert decision["primary_agent"] == "contract_manager"


def test_policy_command_prints_security_defaults(monkeypatch, capsys):
    _run(monkeypatch, "policy")
    out = capsys.readouterr().out
    assert "tool_access: deny" in out
    assert "execute_contract" in out


def test_integrations_command_prints_status(monkeypatch, capsys):
    _run(monkeypatch, "integrations")
    out = capsys.readouterr().out
    assert "microsoft_graph: pilot" in out
    assert "github: planned" in out


def test_run_command_requires_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        _run(monkeypatch, "run", "Prepare my morning briefing",
             "--project-id", "project-1", "--tenant-id", "tenant-a",
             "--user-id", "alice")


def test_missing_command_exits_nonzero(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tessera"])
    with pytest.raises(SystemExit):
        cli.main()


def test_log_level_env_var_is_read_without_error(monkeypatch, capsys):
    monkeypatch.setenv("TESSERA_LOG_LEVEL", "DEBUG")
    _run(monkeypatch, "list")
    assert "executive_assistant" in capsys.readouterr().out


def test_invalid_log_level_falls_back_to_info(monkeypatch, capsys):
    monkeypatch.setenv("TESSERA_LOG_LEVEL", "NOT_A_LEVEL")
    _run(monkeypatch, "list")
    assert "executive_assistant" in capsys.readouterr().out


def test_serve_starts_localhost_synthetic_console(monkeypatch):
    calls = []
    monkeypatch.setenv("TESSERA_ENV", "sandbox")
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: calls.append((args, kwargs)))
    _run(monkeypatch, "serve", "--port", "8123")
    assert calls == [(('tessera_os.console:create_console_app',), {
        "factory": True, "host": "127.0.0.1", "port": 8123,
    })]
