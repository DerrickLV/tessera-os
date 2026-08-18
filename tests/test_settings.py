import pytest

from tessera_os.settings import (
    load_integration_settings,
    load_model_settings,
    load_security_settings,
)


def test_model_settings_resolve_env_placeholder_default(monkeypatch):
    monkeypatch.delenv("TESSERA_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("TESSERA_MODEL_HIGH_REASONING", raising=False)
    settings = load_model_settings()
    assert settings.default.model == "gpt-5.6-terra"
    assert settings.high_reasoning.model == "gpt-5.6-sol"
    assert settings.cost_optimized.model == "gpt-5.6-luna"


def test_model_settings_env_placeholder_honors_override(monkeypatch):
    monkeypatch.setenv("TESSERA_MODEL_DEFAULT", "gpt-5.6-custom")
    settings = load_model_settings()
    assert settings.default.model == "gpt-5.6-custom"


def test_model_settings_policies_loaded():
    settings = load_model_settings()
    assert settings.policies.max_turns == 8
    assert settings.policies.timeout_seconds == 180


def test_model_settings_profile_falls_back_to_default_for_unknown_name():
    settings = load_model_settings()
    assert settings.profile("not_a_real_profile") == settings.default


def test_security_settings_defaults_are_deny_by_default():
    settings = load_security_settings()
    assert settings.defaults.tool_access == "deny"
    assert settings.defaults.cross_project_retrieval == "deny"
    assert settings.defaults.production_writes == "deny"
    assert settings.authentication.required_group == "tessera_user"
    assert settings.authorization.fail_closed is True
    assert settings.runtime_controls.artifact_encryption == "aes_gcm"
    assert "execute_contract" in settings.approval_tiers.executive


def test_integration_settings_lists_known_systems():
    settings = load_integration_settings()
    assert settings.integrations["microsoft_graph"].status == "pilot"
    assert settings.integrations["github"].status == "planned"


def test_env_placeholder_without_default_resolves_to_empty_string(tmp_path, monkeypatch):
    (tmp_path / "models.yaml").write_text(
        "default:\n"
        "  model: ${TESSERA_UNSET_TEST_VAR}\n"
        "  reasoning_effort: medium\n"
        "high_reasoning:\n"
        "  model: gpt-5.6-sol\n"
        "  reasoning_effort: high\n"
        "cost_optimized:\n"
        "  model: gpt-5.6-luna\n"
        "  reasoning_effort: low\n"
        "policies:\n"
        "  max_turns: 8\n"
        "  timeout_seconds: 180\n"
    )
    monkeypatch.delenv("TESSERA_UNSET_TEST_VAR", raising=False)
    settings = load_model_settings(config_dir=tmp_path)
    assert settings.default.model == ""


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_model_settings(config_dir=tmp_path)
