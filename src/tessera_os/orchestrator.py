"""Manager-style orchestration with an optional OpenAI Agents SDK runtime."""

import hashlib
import os

from .paths import project_root
from .policy import Environment, PolicyGateway, PolicyOutcome, RuntimeAction
from .registry import AgentDefinition, AgentRegistry
from .router import Router
from .schemas import AgentRequest, RouteDecision, UserContext
from .settings import ModelSettings, load_model_settings

SHARED_PROMPT_PATH = project_root() / "prompts" / "_shared.md"


def compose_instructions(definition: AgentDefinition) -> str:
    """Return the full instruction text a specialist actually runs with.

    Every specialist prompt is written to sit on top of ``prompts/_shared.md``
    (citation discipline, evidence labelling, untrusted-content handling, and
    the hard action limits) and refers to it by name. Nothing was loading that
    file, so the shared rules never reached the model and each prompt pointed
    at a document the model could not see. Composing here keeps the two files
    separately reviewable while guaranteeing they are delivered together.
    """
    specialist = definition.prompt_path.read_text()
    if not SHARED_PROMPT_PATH.is_file():
        return specialist
    return f"{SHARED_PROMPT_PATH.read_text().rstrip()}\n\n---\n\n{specialist}"


def instructions_digest(definition: AgentDefinition) -> str:
    """Stable version marker for the composed instructions, for audit traces.

    Hashing the specialist file alone would not change when the shared rules
    change, so a shared-rule edit would be invisible in the audit trail.
    """
    return hashlib.sha256(compose_instructions(definition).encode()).hexdigest()[:16]


class TesseraOrchestrator:
    def __init__(self, registry: AgentRegistry | None = None, router: Router | None = None,
                 model_settings: ModelSettings | None = None,
                 policy_gateway: PolicyGateway | None = None):
        self.registry = registry or AgentRegistry()
        self.router = router or Router()
        self.model_settings = model_settings or load_model_settings()
        self.policy_gateway = policy_gateway or PolicyGateway()

    def plan(self, request: AgentRequest) -> RouteDecision:
        return self.router.route(request.task)

    def resolve_model(self, model_profile: str) -> str:
        """Resolve an agent manifest's model_profile to a concrete model name.

        Reads config/models.yaml via self.model_settings. The default and
        high_reasoning profiles embed a ${TESSERA_MODEL_*:-fallback} placeholder
        that settings.load_model_settings() resolves against the environment,
        so TESSERA_MODEL_DEFAULT / TESSERA_MODEL_HIGH_REASONING (per
        README.md and .env.example) are honored automatically here.
        """
        return self.model_settings.profile(model_profile).model

    async def run(self, request: AgentRequest, *, context: UserContext) -> str:
        """Execute a scoped draft after central policy authorization."""
        if not request.project_id:
            raise ValueError("project_id is required for live execution")
        if request.user_id and request.user_id != context.user_id:
            raise PermissionError("Request user does not match authenticated context")

        decision = self.plan(request)
        definition = self.registry.get(decision.primary_agent)
        environment = Environment(os.getenv("TESSERA_ENV", "sandbox"))
        policy = self.policy_gateway.evaluate(RuntimeAction(
            tenant_id=context.tenant_id, project_id=request.project_id,
            user_id=context.user_id, agent_id=definition.id, action="draft",
            environment=environment), context=context, agent=definition)
        if policy.outcome != PolicyOutcome.ALLOW:
            raise PermissionError(policy.reason)
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for live execution")

        from agents import Agent, Runner

        instructions = compose_instructions(definition)
        model = self.resolve_model(definition.model_profile)
        policies = self.model_settings.policies

        specialist = Agent(name=definition.name, instructions=instructions, model=model)
        envelope = (
            f"Task: {request.task}\nProject: {request.project_id or 'not supplied'}\n"
            f"Allowed actions: {', '.join(request.allowed_actions)}\n"
            "Return a decision-ready response and do not perform external writes."
        )
        result = await Runner.run(specialist, envelope, max_turns=policies.max_turns)
        return str(result.final_output)
