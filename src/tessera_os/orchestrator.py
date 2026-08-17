"""Manager-style orchestration with an optional OpenAI Agents SDK runtime."""

import os
from pathlib import Path

from .registry import AgentRegistry
from .router import Router
from .schemas import AgentRequest, RouteDecision


class TesseraOrchestrator:
    def __init__(self, registry: AgentRegistry | None = None, router: Router | None = None):
        self.registry = registry or AgentRegistry()
        self.router = router or Router()

    def plan(self, request: AgentRequest) -> RouteDecision:
        return self.router.route(request.task)

    async def run(self, request: AgentRequest) -> str:
        """Execute the selected specialist. Requires OPENAI_API_KEY."""
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for live execution")

        from agents import Agent, Runner

        decision = self.plan(request)
        definition = self.registry.get(decision.primary_agent)
        instructions = definition.prompt_path.read_text()
        model = os.getenv("TESSERA_MODEL_DEFAULT", "gpt-5.6-terra")
        if definition.model_profile == "high_reasoning":
            model = os.getenv("TESSERA_MODEL_HIGH_REASONING", "gpt-5.6-sol")

        specialist = Agent(name=definition.name, instructions=instructions, model=model)
        envelope = (
            f"Task: {request.task}\nProject: {request.project_id or 'not supplied'}\n"
            f"Allowed actions: {', '.join(request.allowed_actions)}\n"
            "Return a decision-ready response and do not perform external writes."
        )
        result = await Runner.run(specialist, envelope, max_turns=8)
        return str(result.final_output)
