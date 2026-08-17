from tessera_os.router import Router


def test_routes_contract_review():
    decision = Router().route("Review the indemnity clause in this contract")
    assert decision.primary_agent == "contract_manager"


def test_routes_unknown_to_knowledge():
    decision = Router().route("Help me understand this")
    assert decision.primary_agent == "knowledge_manager"


def test_supporting_agent_requires_multiple_matches():
    decision = Router().route("Assess project risk, milestone deadline, and construction schedule")
    assert decision.primary_agent == "project_manager"
    assert "construction_manager" in decision.supporting_agents
