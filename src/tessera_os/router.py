"""Transparent offline-first routing used before model execution."""

import json
from pathlib import Path

from .schemas import RouteDecision


class Router:
    def __init__(self, config_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        data = json.loads((config_path or root / "config/routing.json").read_text())
        self.routes: dict[str, list[str]] = data["routes"]
        self.fallback: str = data["fallback"]
        self.multi_agent_threshold: int = data["multi_agent_threshold"]

    def route(self, task: str) -> RouteDecision:
        normalized = task.casefold()
        matches = {
            agent: [term for term in terms if term in normalized]
            for agent, terms in self.routes.items()
        }
        matches = {agent: terms for agent, terms in matches.items() if terms}
        ranked = sorted(matches, key=lambda key: (-len(matches[key]), key))
        primary = ranked[0] if ranked else self.fallback
        supporting = [
            agent for agent in ranked[1:] if len(matches[agent]) >= self.multi_agent_threshold
        ]
        rationale = (
            f"Matched {', '.join(matches.get(primary, []))}"
            if matches else "No specialist keywords matched; used the knowledge fallback"
        )
        return RouteDecision(
            primary_agent=primary,
            supporting_agents=supporting,
            matched_terms=matches,
            rationale=rationale,
        )
