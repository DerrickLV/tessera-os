"""Local operator interface for discovery, routing, and live runs."""

import argparse
import asyncio
import json

from .orchestrator import TesseraOrchestrator
from .schemas import AgentRequest


def main() -> None:
    parser = argparse.ArgumentParser(prog="tessera")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List configured agents")
    route = commands.add_parser("route", help="Preview deterministic routing")
    route.add_argument("task")
    run = commands.add_parser("run", help="Run the selected specialist")
    run.add_argument("task")
    run.add_argument("--project-id")
    args = parser.parse_args()

    orchestrator = TesseraOrchestrator()
    if args.command == "list":
        for agent in orchestrator.registry.all():
            print(f"{agent.id}: {agent.name} — {agent.purpose}")
    elif args.command == "route":
        print(orchestrator.plan(AgentRequest(task=args.task)).model_dump_json(indent=2))
    else:
        output = asyncio.run(orchestrator.run(AgentRequest(task=args.task, project_id=args.project_id)))
        print(json.dumps({"output": output}, indent=2))


if __name__ == "__main__":
    main()
