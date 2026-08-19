"""Entra group mapping and trust-zone policy.

Two authorization gaps close here, and both matter more than they look.

**Reviewer groups come from the identity provider, not from code.** The review
queue enforces ``required_reviewer_group`` — a drafted agreement needs a
decision from ``qualified_counsel`` — but the portal used to hand every
signed-in user the same ``{"tessera_user"}`` set, so the separation of duties
was a convention the UI displayed rather than a boundary anything enforced.
The map below turns membership of a named Microsoft Entra security group into
a Tessera group. A user who is not in the Entra group physically cannot carry
the review, and adding a reviewer becomes an Entra admin action with an audit
trail rather than a code change.

**Trust zones are Tessera's own governance model, enforced.** The firm's
operating system is organized by trust boundary: zone 01 is Internal (partners
only — strategy, capital models, master templates), zone 02 is one workspace
per client, zone 03 is scoped collaborator folders. The golden rule is that
work originates in Internal and only copies move outward. Mapping a SharePoint
resource without saying which zone it belongs to leaves that rule resting
entirely on SharePoint permissions being configured correctly forever. Here
the zone is declared per resource and checked on every read, so an Internal
library can never be served into a client-facing project even when a
permission slips.

Fail-closed notes, because identity code must never guess:

- Entra omits the ``groups`` claim entirely when a user belongs to more groups
  than fit in the token (the "groups overage" case). Absent claim means no
  mapped groups — never an error, never an assumption.
- An unmapped Entra group grants nothing. Only groups named in the map exist.
- An Internal-zone resource with no partner group in context is a refusal,
  even for an invited user.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .schemas import UserContext

# The group every invited portal user carries. Grants read access to the
# user's own projects and nothing privileged.
BASE_GROUP = "tessera_user"

# Zone 01. Only members of the mapped partner Entra group may read these
# resources, mirroring "Derrick & Ryan only" in the governance model.
PARTNER_GROUP = "tessera_partner"

TrustZone = Literal["internal", "engagement", "collaborator"]

ZONE_LABEL: dict[TrustZone, str] = {
    "internal": "01 — Internal (Tessera only)",
    "engagement": "02 — Engagements (client-facing, walled per client)",
    "collaborator": "03 — Collaborators (counsel and co-advisors, scoped)",
}


class IdentityConfigurationError(ValueError):
    """Raised when the group map is malformed. A broken map must not load."""


class ZoneAccessError(PermissionError):
    """Raised when a read would cross a trust boundary."""


class EntraGroupMap(BaseModel):
    """Entra security-group object IDs mapped to Tessera group IDs.

    The mapping is deliberately explicit and flat. There is no wildcard, no
    role hierarchy, and no default: a Tessera group exists for a user only if
    an administrator put the Entra group's object ID in this map and the
    user's token carries it.
    """

    groups: dict[str, str] = Field(
        default_factory=dict,
        description="Entra group object ID -> Tessera group ID, e.g. "
                    '{"9f3c...": "qualified_counsel", "1ab2...": "tessera_partner"}')

    @model_validator(mode="after")
    def no_blank_entries(self) -> EntraGroupMap:
        for entra_id, tessera_id in self.groups.items():
            if not entra_id.strip() or not tessera_id.strip():
                raise IdentityConfigurationError(
                    "Group map entries must have a non-empty Entra object ID and "
                    "Tessera group ID")
        return self

    @classmethod
    def from_environment(cls) -> EntraGroupMap:
        raw = os.getenv("TESSERA_M365_GROUP_MAP", "{}")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IdentityConfigurationError(
                "TESSERA_M365_GROUP_MAP must be valid JSON") from exc
        if not isinstance(data, dict):
            raise IdentityConfigurationError("TESSERA_M365_GROUP_MAP must be an object")
        return cls(groups=data)

    def resolve(self, entra_group_ids: list[str] | None) -> frozenset[str]:
        """Tessera groups for a token's ``groups`` claim.

        ``None`` and ``[]`` both resolve to nothing. In the Entra groups-overage
        case the claim is absent, and the safe reading of "we do not know this
        user's groups" is "this user has no privileged groups".
        """
        if not entra_group_ids:
            return frozenset()
        return frozenset(self.groups[gid] for gid in entra_group_ids
                         if gid in self.groups)


def build_user_context(*, tenant_id: str, user_id: str,
                       entra_group_ids: list[str] | None,
                       project_ids: frozenset[str] | set[str],
                       group_map: EntraGroupMap) -> UserContext:
    """The one place a portal identity becomes a Tessera authorization boundary.

    Every privileged group — ``qualified_counsel``, ``tessera_partner`` — can
    enter a ``UserContext`` only through the Entra map. Nothing downstream may
    add one, which is what makes ``required_reviewer_group`` a real control.
    """
    return UserContext(
        tenant_id=tenant_id,
        user_id=user_id,
        project_ids=frozenset(project_ids),
        group_ids=frozenset({BASE_GROUP}) | group_map.resolve(entra_group_ids),
    )


class ZonePolicy(BaseModel):
    """Trust-boundary checks for mapped SharePoint resources.

    ``resource_zones`` carries the zone of each mapped project resource, and
    ``resource_clients`` the client an engagement resource is walled to.
    """

    resource_zones: dict[str, TrustZone] = Field(default_factory=dict)
    resource_clients: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def engagement_zones_name_their_client(self) -> ZonePolicy:
        for project_id, zone in self.resource_zones.items():
            if zone in {"engagement", "collaborator"} and not self.resource_clients.get(project_id):
                raise IdentityConfigurationError(
                    f"{zone.title()}-zone resource {project_id!r} must name its client or "
                    "engagement — the outward trust boundary must be explicit")
        return self

    def zone_of(self, project_id: str) -> TrustZone:
        """Unmapped means unknown, and unknown fails closed as Internal."""
        return self.resource_zones.get(project_id, "internal")

    def check_read(self, *, context: UserContext, project_id: str) -> TrustZone:
        """Refuse a read that crosses a trust boundary; return the zone if allowed."""
        zone = self.zone_of(project_id)
        if zone == "internal" and PARTNER_GROUP not in context.group_ids:
            raise ZoneAccessError(
                f"{ZONE_LABEL['internal']} resources are readable only by the "
                "partners' Entra group")
        return zone

    def check_citation(self, *, source_project_id: str,
                       artifact_project_id: str,
                       artifact_client_id: str | None) -> None:
        """The golden rule, enforced at citation time.

        A document read from one client's engagement zone must never surface in
        an artifact produced for a different client, and an Internal original
        must never surface in any client-facing artifact at all — a copy is
        placed in the engagement zone first, and that copy is what gets cited.
        """
        zone = self.zone_of(source_project_id)
        if source_project_id == artifact_project_id:
            return
        if zone == "internal":
            raise ZoneAccessError(
                "Internal originals never leave zone 01. Place a copy in the "
                "engagement workspace and cite the copy.")
        if zone in {"engagement", "collaborator"}:
            source_client = self.resource_clients.get(source_project_id)
            if artifact_client_id is None or source_client != artifact_client_id:
                raise ZoneAccessError(
                    f"A {zone}-zone document cannot be cited outside its named client")
