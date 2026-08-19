"""Offline Microsoft 365 launch-readiness checks.

The checker never calls Microsoft, prints secrets, or changes configuration. It
turns the deployment environment into a short pass/fail list and keeps the few
administrator-only confirmations visible as manual gates.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: Literal["pass", "fail", "manual"]
    detail: str


@dataclass(frozen=True)
class MicrosoftReadinessReport:
    checks: tuple[ReadinessCheck, ...]

    @property
    def configuration_ready(self) -> bool:
        return not any(item.status == "fail" for item in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "configuration_ready": self.configuration_ready,
            "checks": [asdict(item) for item in self.checks],
        }

    def render(self) -> str:
        labels = {"pass": "PASS", "fail": "FIX", "manual": "YOU"}
        lines = ["Microsoft 365 launch readiness", ""]
        lines.extend(
            f"[{labels[item.status]}] {item.name}: {item.detail}" for item in self.checks)
        lines.extend([
            "",
            ("Local configuration is complete. Finish every [YOU] item in Microsoft, "
             "then run the two-user acceptance test."
             if self.configuration_ready else
             "Complete every [FIX] item, then run this check again."),
        ])
        return "\n".join(lines)


def _json_object(environment: Mapping[str, str], name: str) -> tuple[dict, ReadinessCheck]:
    raw = environment.get(name, "")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}, ReadinessCheck(name, "fail", "must contain one-line JSON")
    if not isinstance(value, dict) or not value:
        return {}, ReadinessCheck(name, "fail", "must be a non-empty JSON object")
    return value, ReadinessCheck(name, "pass", f"{len(value)} mapping(s) configured")


def microsoft_readiness(
    environment: Mapping[str, str] | None = None,
) -> MicrosoftReadinessReport:
    env = environment if environment is not None else os.environ
    checks: list[ReadinessCheck] = []
    for name, label in (
        ("TESSERA_M365_TENANT_ID", "Entra tenant ID"),
        ("TESSERA_M365_CLIENT_ID", "Entra application/client ID"),
        ("TESSERA_M365_CLIENT_SECRET", "pilot application credential"),
        ("TESSERA_M365_CACHE_KEY", "encrypted token-cache key"),
        ("TESSERA_SESSION_SECRET", "portal session secret"),
    ):
        checks.append(ReadinessCheck(
            label, "pass" if env.get(name) else "fail",
            "configured" if env.get(name) else f"set {name} in Render (never in GitHub)"))

    users = {item.strip() for item in env.get("TESSERA_ALLOWED_USER_IDS", "").split(",")
             if item.strip()}
    checks.append(ReadinessCheck(
        "Invited users", "pass" if len(users) >= 2 else "fail",
        f"{len(users)} user(s) configured; the Derrick/Ryan pilot requires two"))

    catalog, catalog_check = _json_object(env, "TESSERA_PROJECT_CATALOG")
    checks.append(catalog_check)
    user_projects, user_check = _json_object(env, "TESSERA_USER_PROJECTS")
    checks.append(user_check)
    resources, resource_check = _json_object(env, "TESSERA_M365_PROJECT_RESOURCES")
    checks.append(resource_check)
    group_map, group_check = _json_object(env, "TESSERA_M365_GROUP_MAP")
    checks.append(group_check)

    if users and user_projects:
        assigned_users = set(user_projects)
        valid_lists = all(isinstance(values, list) and bool(values)
                          and all(isinstance(project, str) for project in values)
                          for values in user_projects.values())
        assigned_projects = {project for values in user_projects.values()
                             if isinstance(values, list) for project in values}
        exact = valid_lists and assigned_users == users and assigned_projects <= set(catalog)
        checks.append(ReadinessCheck(
            "Per-user project isolation", "pass" if exact else "fail",
            "every invited user has only known projects" if exact else
            "TESSERA_USER_PROJECTS must list every invited user and only catalog projects"))

    if resources:
        explicit = all(isinstance(item, dict) and item.get("zone") in {
            "internal", "engagement", "collaborator"} for item in resources.values())
        outward_named = all(
            item.get("zone") == "internal" or bool(item.get("client_id"))
            for item in resources.values() if isinstance(item, dict))
        matches = set(resources) == set(catalog)
        checks.append(ReadinessCheck(
            "SharePoint trust-zone mappings",
            "pass" if explicit and outward_named and matches else "fail",
            "every project has an explicit safe zone" if explicit and outward_named and matches
            else "resource keys must match the catalog; every zone must be explicit and outward "
                 "zones need client_id"))

    if group_map:
        mapped_roles = set(group_map.values())
        checks.append(ReadinessCheck(
            "Entra partner group", "pass" if "tessera_partner" in mapped_roles else "fail",
            "tessera_partner is mapped" if "tessera_partner" in mapped_roles else
            "map the Tessera Partners Entra group to tessera_partner"))

    expected_redirect = "https://api.tesseraag.com/v1/integrations/microsoft/callback"
    redirect = env.get("TESSERA_M365_REDIRECT_URI")
    checks.append(ReadinessCheck(
        "Production redirect URI", "pass" if redirect == expected_redirect else "fail",
        "exact production callback configured" if redirect == expected_redirect else
        f"set it exactly to {expected_redirect}"))

    checks.extend([
        ReadinessCheck("Entra permissions", "manual",
                       "confirm delegated User.Read + Sites.Selected and admin consent"),
        ReadinessCheck("Group claim", "manual",
                       "confirm security groups are included in the ID token"),
        ReadinessCheck("Enterprise-app assignment", "manual",
                       "require assignment and assign Derrick and Ryan only"),
        ReadinessCheck("Selected SharePoint access", "manual",
                       "grant the app read access to the sanitized Tessera Pilot site only"),
        ReadinessCheck("Production domains", "manual",
                       "confirm app.tesseraag.com and api.tesseraag.com both show valid HTTPS"),
    ])
    return MicrosoftReadinessReport(tuple(checks))
