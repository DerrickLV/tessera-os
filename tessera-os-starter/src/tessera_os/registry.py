"""Agent registry loaded from versioned manifests."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    purpose: str
    model_profile: str
    prompt_path: Path
    tools: tuple[str, ...]
    approval_required: tuple[str, ...]


class AgentRegistry:
    def __init__(self, manifest_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.manifest_dir = manifest_dir or root / "agents"
        self._agents = self._load()

    def _load(self) -> dict[str, AgentDefinition]:
        agents: dict[str, AgentDefinition] = {}
        for path in sorted(self.manifest_dir.glob("*.json")):
            data = json.loads(path.read_text())
            prompt = (path.parents[1] / data["prompt"]).resolve()
            agent = AgentDefinition(
                id=data["id"], name=data["name"], purpose=data["purpose"],
                model_profile=data.get("model_profile", "default"), prompt_path=prompt,
                tools=tuple(data.get("tools", [])),
                approval_required=tuple(data.get("approval_required", [])),
            )
            if agent.id in agents:
                raise ValueError(f"Duplicate agent id: {agent.id}")
            agents[agent.id] = agent
        return agents

    def get(self, agent_id: str) -> AgentDefinition:
        return self._agents[agent_id]

    def all(self) -> list[AgentDefinition]:
        return list(self._agents.values())
