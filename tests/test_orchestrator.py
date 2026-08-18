import asyncio

import pytest

from tessera_os.orchestrator import TesseraOrchestrator
from tessera_os.registry import AgentRegistry
from tessera_os.router import Router
from tessera_os.schemas import AgentRequest, UserContext
from tessera_os.settings import load_model_settings


def test_plan_delegates_to_router():
    orchestrator = TesseraOrchestrator()
    decision = orchestrator.plan(AgentRequest(task="Review the indemnity clause"))
    assert decision.primary_agent == "contract_manager"


def test_resolve_model_uses_configured_default_profile():
    orchestrator = TesseraOrchestrator()
    assert orchestrator.resolve_model("default") == "gpt-5.6-terra"
    assert orchestrator.resolve_model("high_reasoning") == "gpt-5.6-sol"


def test_resolve_model_honors_env_override(monkeypatch):
    monkeypatch.setenv("TESSERA_MODEL_HIGH_REASONING", "gpt-5.6-override")
    orchestrator = TesseraOrchestrator(model_settings=load_model_settings())
    assert orchestrator.resolve_model("high_reasoning") == "gpt-5.6-override"


def test_resolve_model_falls_back_for_unknown_profile():
    orchestrator = TesseraOrchestrator()
    assert orchestrator.resolve_model("unknown_profile") == orchestrator.resolve_model("default")


def test_run_requires_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    orchestrator = TesseraOrchestrator()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        asyncio.run(orchestrator.run(
            AgentRequest(task="Prepare my morning briefing", project_id="project-1"),
            context=UserContext(tenant_id="tenant-a", user_id="alice",
                                project_ids={"project-1"})))


def test_run_enforces_authenticated_project_scope_before_model_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-only")
    orchestrator = TesseraOrchestrator()
    with pytest.raises(PermissionError, match="scope"):
        asyncio.run(orchestrator.run(
            AgentRequest(task="Prepare my morning briefing", project_id="project-other"),
            context=UserContext(tenant_id="tenant-a", user_id="alice",
                                project_ids={"project-1"})))


def test_orchestrator_accepts_injected_registry_router_and_settings():
    registry, router, settings = AgentRegistry(), Router(), load_model_settings()
    orchestrator = TesseraOrchestrator(registry=registry, router=router, model_settings=settings)
    assert orchestrator.registry is registry
    assert orchestrator.router is router
    assert orchestrator.model_settings is settings
