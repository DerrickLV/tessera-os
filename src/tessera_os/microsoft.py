"""Microsoft Entra connection broker and allowlisted SharePoint project mapping."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field, SecretStr, model_validator

from .identity import PARTNER_GROUP, ZONE_LABEL, TrustZone, ZonePolicy
from .integrations import MicrosoftGraphReader, SharePointPathNotFoundError
from .schemas import SourceDocument, UserContext


class MicrosoftConfigurationError(ValueError):
    """Raised when the connection requests unsafe or incomplete configuration."""


class SharePointProjectResource(BaseModel):
    site_id: str = Field(min_length=1)
    drive_id: str = Field(min_length=1)
    # The project's scope within the drive (D1): "Projects/{client folder}".
    # Configuration names it explicitly rather than deriving it from
    # project_id -- a slugified guess happens to work until a client's folder
    # is named anything else, and then it fails silently into the wrong
    # client's folder instead of loudly.
    root_path: str | None = None
    # Deprecated in favor of root_path. Accepted for one release; see
    # MicrosoftGraphReader.sharepoint_documents, which logs every time this
    # fallback is actually used.
    folder_item_id: str = "root"
    # Which trust boundary of the Tessera governance model this resource sits
    # in. Defaults to Internal — the most restrictive zone — so a mapping that
    # forgets to declare its zone fails closed rather than open.
    zone: TrustZone = "internal"
    client_id: str | None = Field(
        default=None,
        description="Required for engagement-zone resources: the one client this "
                    "workspace is walled to.")

    @model_validator(mode="after")
    def engagement_names_its_client(self) -> SharePointProjectResource:
        if self.zone in {"engagement", "collaborator"} and not self.client_id:
            raise MicrosoftConfigurationError(
                f"A {self.zone}-zone SharePoint resource must name its client or engagement")
        return self

    @model_validator(mode="after")
    def root_path_is_relative_and_contained(self) -> SharePointProjectResource:
        if self.root_path is not None and (
            self.root_path.startswith("/")
            or any(segment == ".." for segment in self.root_path.split("/"))
        ):
            raise MicrosoftConfigurationError(
                "root_path must be a relative path within the drive: no leading "
                "'/' and no '..' segments")
        return self


class MicrosoftPilotSettings(BaseModel):
    enabled: bool = False
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None
    redirect_uri: str = "http://127.0.0.1:8000/v1/integrations/microsoft/callback"
    scopes: tuple[str, ...] = ("User.Read", "Sites.Selected")
    cache_key: SecretStr | None = None
    project_resources: dict[str, SharePointProjectResource] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_pilot_boundary(self) -> MicrosoftPilotSettings:
        allowed = {"User.Read", "Sites.Selected"}
        if set(self.scopes) - allowed:
            raise MicrosoftConfigurationError(
                "The initial pilot permits only User.Read and Sites.Selected")
        if any("write" in scope.lower() or scope.endswith(".All") for scope in self.scopes):
            raise MicrosoftConfigurationError("Broad or write Microsoft scopes are prohibited")
        if self.enabled and not all((self.tenant_id, self.client_id,
                                     self.client_secret, self.cache_key)):
            raise MicrosoftConfigurationError(
                "Enabled Microsoft integration requires tenant, client, secret, and cache key")
        if self.enabled and not self.project_resources:
            raise MicrosoftConfigurationError(
                "At least one approved project-to-SharePoint mapping is required")
        return self

    def zone_policy(self) -> ZonePolicy:
        """The trust-boundary policy implied by the approved resource map."""
        return ZonePolicy(
            resource_zones={project: resource.zone
                            for project, resource in self.project_resources.items()},
            resource_clients={project: resource.client_id
                              for project, resource in self.project_resources.items()
                              if resource.client_id})

    @classmethod
    def from_environment(cls) -> MicrosoftPilotSettings:
        raw_resources = os.getenv("TESSERA_M365_PROJECT_RESOURCES", "{}")
        try:
            resources = json.loads(raw_resources)
        except json.JSONDecodeError as exc:
            raise MicrosoftConfigurationError(
                "TESSERA_M365_PROJECT_RESOURCES must be valid JSON") from exc
        return cls(
            enabled=os.getenv("TESSERA_M365_ENABLED", "false").lower() == "true",
            tenant_id=os.getenv("TESSERA_M365_TENANT_ID"),
            client_id=os.getenv("TESSERA_M365_CLIENT_ID"),
            client_secret=os.getenv("TESSERA_M365_CLIENT_SECRET"),
            cache_key=os.getenv("TESSERA_M365_CACHE_KEY"),
            redirect_uri=os.getenv(
                "TESSERA_M365_REDIRECT_URI",
                "http://127.0.0.1:8000/v1/integrations/microsoft/callback",
            ),
            project_resources=resources,
        )


class AuthClient(Protocol):
    def initiate_auth_code_flow(self, scopes: list[str], redirect_uri: str) -> dict[str, Any]: ...
    def acquire_token_by_auth_code_flow(
        self, auth_code_flow: dict[str, Any], auth_response: dict[str, str]
    ) -> dict[str, Any]: ...
    def get_accounts(self) -> list[dict[str, Any]]: ...
    def acquire_token_silent(self, scopes: list[str], account: dict[str, Any]) -> dict[str, Any]: ...
    def remove_account(self, account: dict[str, Any]) -> None: ...


class EncryptedTokenCache:
    """Encrypt an MSAL serializable cache at rest; never expose cache contents."""

    def __init__(self, path: Path, key: SecretStr) -> None:
        try:
            raw_key = base64.urlsafe_b64decode(key.get_secret_value())
        except Exception as exc:
            raise MicrosoftConfigurationError("Microsoft cache key must be URL-safe base64") from exc
        if len(raw_key) != 32:
            raise MicrosoftConfigurationError("Microsoft cache key must decode to 32 bytes")
        try:
            import msal
        except ImportError as exc:
            raise MicrosoftConfigurationError("Install the msal package to enable Microsoft") from exc
        self.path = path
        self._cipher = AESGCM(raw_key)
        self.cache = msal.SerializableTokenCache()
        if path.exists():
            encrypted = path.read_bytes()
            if len(encrypted) < 13:
                raise MicrosoftConfigurationError("Microsoft token cache is malformed")
            serialized = self._cipher.decrypt(
                encrypted[:12], encrypted[12:], b"tessera-m365").decode()
            self.cache.deserialize(serialized)

    def persist(self) -> None:
        if not self.cache.has_state_changed:
            return
        nonce = os.urandom(12)
        payload = self.cache.serialize().encode()
        encrypted = nonce + self._cipher.encrypt(nonce, payload, b"tessera-m365")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(encrypted)
        # Owner-only permissions where the filesystem implements them. In
        # production the cache sits on an Azure Files (SMB) mount, which has no
        # POSIX mode bits, so chmod returns EPERM after a write that succeeded.
        # Failing here would abort a completed sign-in over a hardening step
        # that cannot apply -- and the resulting 500 blames the callback rather
        # than the filesystem. The file's confidentiality does not rest on the
        # mode bits in any case: the contents are AES-GCM encrypted with a key
        # held outside the share, and access to the share is controlled by its
        # own credentials.
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def clear(self) -> None:
        self.cache.deserialize("{}")
        if self.path.exists():
            self.path.unlink()


class MicrosoftConnectionStatus(BaseModel):
    enabled: bool
    configured: bool
    connected: bool
    scopes: list[str]
    mapped_projects: list[str]
    writes_enabled: bool = False
    account_label: str | None = None


class MicrosoftIdentity(BaseModel):
    tenant_id: str
    user_id: str
    username: str | None = None
    display_name: str | None = None
    # Entra security-group object IDs from the token's ``groups`` claim. Absent
    # in the groups-overage case, in which case this is empty and the user
    # carries no privileged Tessera groups — fail closed, never guess.
    entra_group_ids: list[str] = Field(default_factory=list)


class MicrosoftConnectionBroker:
    """Server-side delegated OAuth broker with state-bound auth-code flows."""

    def __init__(self, *, settings: MicrosoftPilotSettings, cache_path: Path,
                 auth_client: AuthClient | None = None) -> None:
        self.settings = settings
        self._flows: dict[str, dict[str, Any]] = {}
        self._cache: EncryptedTokenCache | None = None
        self._auth_client = auth_client
        if settings.enabled and auth_client is None:
            self._cache = EncryptedTokenCache(cache_path, settings.cache_key)  # type: ignore[arg-type]
            try:
                import msal
            except ImportError as exc:
                raise MicrosoftConfigurationError("Install the msal package") from exc
            self._auth_client = msal.ConfidentialClientApplication(
                settings.client_id,
                authority=f"https://login.microsoftonline.com/{settings.tenant_id}",
                client_credential=settings.client_secret.get_secret_value(),  # type: ignore[union-attr]
                token_cache=self._cache.cache,
            )

    @staticmethod
    def _account_matches(account: dict[str, Any], user_id: str) -> bool:
        """Match the signed-in Entra object ID to one MSAL account.

        MSAL exposes the tenant-local object ID as ``local_account_id``.  Some
        test and legacy cache shapes retain it only in ``id_token_claims``.
        Never fall back to the first account when a user was requested: that is
        how one portal user's token can be used for another user's Graph call.
        """
        claims = account.get("id_token_claims") or {}
        home_id = str(account.get("home_account_id") or "").split(".", 1)[0]
        return (account.get("local_account_id") == user_id
                or claims.get("oid") == user_id or home_id == user_id)

    def _account(self, user_id: str | None = None) -> dict[str, Any] | None:
        accounts = self._auth_client.get_accounts() if self._auth_client else []
        if user_id is not None:
            return next((item for item in accounts if self._account_matches(item, user_id)), None)
        if len(accounts) > 1:
            raise MicrosoftConfigurationError(
                "A user ID is required when more than one Microsoft account is connected")
        return accounts[0] if accounts else None

    def status(self, user_id: str | None = None) -> MicrosoftConnectionStatus:
        account = self._account(user_id) or {}
        return MicrosoftConnectionStatus(
            enabled=self.settings.enabled,
            configured=bool(self.settings.enabled and self._auth_client),
            connected=bool(account),
            scopes=list(self.settings.scopes),
            mapped_projects=sorted(self.settings.project_resources),
            account_label=account.get("username") or account.get("name"),
        )

    def begin(self) -> str:
        _, auth_uri = self.begin_with_state()
        return auth_uri

    def begin_with_state(self) -> tuple[str, str]:
        if not self.settings.enabled or self._auth_client is None:
            raise MicrosoftConfigurationError("Microsoft integration is not enabled")
        flow = self._auth_client.initiate_auth_code_flow(
            scopes=list(self.settings.scopes), redirect_uri=self.settings.redirect_uri)
        state, auth_uri = flow.get("state"), flow.get("auth_uri")
        if not state or not auth_uri:
            raise MicrosoftConfigurationError("Microsoft did not return a valid authorization flow")
        self._flows[state] = flow
        return str(state), str(auth_uri)

    def complete(self, response: dict[str, str]) -> MicrosoftIdentity:
        state = response.get("state", "")
        flow = self._flows.pop(state, None)
        if flow is None or self._auth_client is None:
            raise MicrosoftConfigurationError("Microsoft authorization state is invalid or expired")
        result = self._auth_client.acquire_token_by_auth_code_flow(flow, response)
        if "access_token" not in result:
            raise MicrosoftConfigurationError(
                f"Microsoft authorization failed: {result.get('error', 'unknown_error')}")
        if self._cache:
            self._cache.persist()
        claims = result.get("id_token_claims") or {}
        tenant_id = claims.get("tid")
        user_id = claims.get("oid") or claims.get("sub")
        if tenant_id != self.settings.tenant_id or not user_id:
            self.disconnect()
            raise MicrosoftConfigurationError("Microsoft identity tenant or user is invalid")
        groups = claims.get("groups")
        return MicrosoftIdentity(tenant_id=tenant_id, user_id=user_id,
            username=claims.get("preferred_username"), display_name=claims.get("name"),
            entra_group_ids=list(groups) if isinstance(groups, list) else [])

    def token(self, user_id: str | None = None) -> str:
        if self._auth_client is None:
            raise MicrosoftConfigurationError("Microsoft integration is not configured")
        account = self._account(user_id)
        if account is None:
            raise MicrosoftConfigurationError("Microsoft connection requires this user to sign in")
        result = self._auth_client.acquire_token_silent(list(self.settings.scopes), account)
        if not result or "access_token" not in result:
            raise MicrosoftConfigurationError("Microsoft token refresh requires sign-in")
        if self._cache:
            self._cache.persist()
        return str(result["access_token"])

    def disconnect(self, user_id: str | None = None) -> None:
        if self._auth_client:
            accounts = self._auth_client.get_accounts()
            if user_id is not None:
                accounts = [item for item in accounts if self._account_matches(item, user_id)]
            for account in accounts:
                self._auth_client.remove_account(account)
        if user_id is None:
            self._flows.clear()
        if self._cache and user_id is None:
            self._cache.clear()
        elif self._cache:
            self._cache.persist()


class MicrosoftUserConnectionBroker:
    """One encrypted MSAL cache per Entra user, with isolated login flows.

    A login starts before the user's object ID is known, so each authorization
    flow gets a temporary encrypted cache. After Entra returns and the identity
    is validated, that cache moves to a deterministic, hashed per-user path.
    Graph token lookup and logout always require the authenticated user ID.
    """

    def __init__(self, *, settings: MicrosoftPilotSettings, cache_dir: Path,
                 broker_factory: Callable[[Path], MicrosoftConnectionBroker] | None = None) -> None:
        self.settings = settings
        self.cache_dir = cache_dir
        self._broker_factory = broker_factory or (
            lambda path: MicrosoftConnectionBroker(settings=settings, cache_path=path))
        self._flows: dict[str, tuple[MicrosoftConnectionBroker, Path]] = {}
        self._users: dict[str, MicrosoftConnectionBroker] = {}

    def _user_path(self, user_id: str) -> Path:
        digest = hashlib.sha256(user_id.encode()).hexdigest()[:24]
        return self.cache_dir / "users" / f"microsoft-{digest}.bin"

    def _user_broker(self, user_id: str) -> MicrosoftConnectionBroker:
        broker = self._users.get(user_id)
        if broker is None:
            broker = self._broker_factory(self._user_path(user_id))
            self._users[user_id] = broker
        return broker

    def begin(self) -> str:
        path = self.cache_dir / "flows" / f"flow-{uuid4().hex}.bin"
        broker = self._broker_factory(path)
        state, auth_uri = broker.begin_with_state()
        self._flows[state] = (broker, path)
        return auth_uri

    def complete(self, response: dict[str, str]) -> MicrosoftIdentity:
        state = response.get("state", "")
        pending = self._flows.pop(state, None)
        if pending is None:
            raise MicrosoftConfigurationError("Microsoft authorization state is invalid or expired")
        broker, temporary_path = pending
        try:
            identity = broker.complete(response)
            target = self._user_path(identity.user_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not temporary_path.exists():
                raise MicrosoftConfigurationError("Microsoft did not persist the user token cache")
            temporary_path.replace(target)
            self._users[identity.user_id] = self._broker_factory(target)
            return identity
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def token(self, user_id: str) -> str:
        return self._user_broker(user_id).token(user_id)

    def status(self, user_id: str) -> MicrosoftConnectionStatus:
        return self._user_broker(user_id).status(user_id)

    def disconnect(self, user_id: str) -> None:
        broker = self._users.pop(user_id, None)
        if broker is None and self._user_path(user_id).exists():
            broker = self._broker_factory(self._user_path(user_id))
        if broker is not None:
            broker.disconnect()


class AllowlistedSharePointReader:
    """Resolve Graph targets exclusively through administrator-approved project mappings."""

    def __init__(self, *, settings: MicrosoftPilotSettings,
                 graph_factory: Callable[[Callable[[], str]], MicrosoftGraphReader],
                 token_provider: Callable[[str], str]) -> None:
        self.settings = settings
        self.graph_factory = graph_factory
        self.token_provider = token_provider
        self.zones = settings.zone_policy()

    def project_documents(self, *, context: UserContext,
                          project_id: str) -> list[SourceDocument]:
        if project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        try:
            resource = self.settings.project_resources[project_id]
        except KeyError as exc:
            raise MicrosoftConfigurationError(
                "Project has no approved SharePoint resource mapping") from exc
        # Trust boundary before transport: an Internal-zone library is readable
        # only by the partners' group, whatever SharePoint's own ACLs say today.
        zone = self.zones.check_read(context=context, project_id=project_id)
        try:
            documents = self.graph_factory(
                lambda: self.token_provider(context.user_id)).sharepoint_documents(
                site_id=resource.site_id, drive_id=resource.drive_id,
                root_path=resource.root_path, folder_item_id=resource.folder_item_id,
                context=context, project_id=project_id)
        except SharePointPathNotFoundError as exc:
            # An empty result here is indistinguishable from an empty folder --
            # the failure mode that hid this whole class of bug. Name the path.
            raise MicrosoftConfigurationError(
                f"SharePoint project folder not found: {exc.path!r}") from exc
        # D4: the ACL is explicit and identical on every read path, derived
        # from the zone the document was actually read under -- never left
        # empty for knowledge.py's fail-closed check to silently swallow.
        acl_group = PARTNER_GROUP if zone == "internal" else f"engagement:{resource.client_id}"
        for document in documents:
            document.metadata.setdefault("trust_zone", zone)
            document.metadata.setdefault("trust_zone_label", ZONE_LABEL[zone])
            if resource.client_id:
                document.metadata.setdefault("client_id", resource.client_id)
            document.allowed_group_ids = frozenset({acl_group})
        return documents
