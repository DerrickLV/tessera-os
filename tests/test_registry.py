from tessera_os.registry import AgentRegistry


def test_all_core_agents_are_registered():
    registry = AgentRegistry()
    assert len(registry.all()) == 12
    assert registry.get("executive_assistant").prompt_path.exists()


def test_high_risk_agents_use_high_reasoning_profile():
    registry = AgentRegistry()
    assert registry.get("contract_manager").model_profile == "high_reasoning"
    assert registry.get("due_diligence_manager").model_profile == "high_reasoning"
