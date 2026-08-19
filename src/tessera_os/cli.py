"""Local operator interface for discovery, routing, and live runs."""

import argparse
import asyncio
import json
import logging
import os

from .m365_readiness import microsoft_readiness
from .orchestrator import TesseraOrchestrator
from .schemas import AgentRequest, UserContext
from .settings import load_integration_settings, load_security_settings


def _configure_logging() -> None:
    level_name = os.getenv("TESSERA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _print_policy() -> None:
    security = load_security_settings()
    print("Security defaults (config/security.yaml):")
    for field, value in security.defaults.model_dump().items():
        print(f"  {field}: {value}")
    print("\nApproval tiers:")
    for tier, actions in security.approval_tiers.model_dump().items():
        print(f"  {tier}: {', '.join(actions) if actions else '(none)'}")
    print("\nRetention (days):")
    for field, value in security.retention.model_dump().items():
        print(f"  {field}: {value}")


def _print_integrations() -> None:
    integrations = load_integration_settings()
    for name, entry in sorted(integrations.integrations.items()):
        detail = entry.mode or entry.auth or ""
        print(f"{name}: {entry.status}" + (f" ({detail})" if detail else ""))


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="tessera")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List configured agents")
    route = commands.add_parser("route", help="Preview deterministic routing")
    route.add_argument("task")
    run = commands.add_parser("run", help="Run the selected specialist")
    run.add_argument("task")
    run.add_argument("--project-id", required=True)
    run.add_argument("--tenant-id", required=True)
    run.add_argument("--user-id", required=True)
    commands.add_parser("policy", help="Show the active security policy (config/security.yaml)")
    commands.add_parser("integrations", help="Show integration status (config/integrations.yaml)")
    m365 = commands.add_parser(
        "m365-check", help="Check Microsoft 365 launch configuration without changing anything")
    m365.add_argument("--json", action="store_true", dest="as_json")
    serve = commands.add_parser("serve", help="Run the synthetic localhost operator console")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    serve.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    if args.command == "policy":
        _print_policy()
        return
    if args.command == "integrations":
        _print_integrations()
        return
    if args.command == "m365-check":
        report = microsoft_readiness()
        print(json.dumps(report.to_dict(), indent=2) if args.as_json else report.render())
        return
    if args.command == "serve":
        if os.getenv("TESSERA_ENV", "sandbox") not in {"sandbox", "test"}:
            raise RuntimeError("The synthetic console only runs in sandbox or test")
        os.environ.setdefault("TESSERA_ENV", "sandbox")
        import uvicorn

        uvicorn.run("tessera_os.console:create_console_app", factory=True,
                    host=args.host, port=args.port)
        return

    orchestrator = TesseraOrchestrator()
    if args.command == "list":
        for agent in orchestrator.registry.all():
            print(f"{agent.id}: {agent.name} — {agent.purpose}")
    elif args.command == "route":
        print(orchestrator.plan(AgentRequest(task=args.task)).model_dump_json(indent=2))
    else:
        context = UserContext(tenant_id=args.tenant_id, user_id=args.user_id,
                              project_ids={args.project_id})
        request = AgentRequest(task=args.task, project_id=args.project_id,
                               user_id=args.user_id)
        output = asyncio.run(orchestrator.run(request, context=context))
        print(json.dumps({"output": output}, indent=2))


if __name__ == "__main__":
    main()
