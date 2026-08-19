"""Microsoft Entra connection broker and allowlisted SharePoint project mapping."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field, SecretStr, model_validator

from .integrations import MicrosoftGraphReader
from .schemas import SourceDocument, UserContext


class MicrosoftConfigurationError(ValueError):
    """Raised when the connection requests unsafe or incomplete configuration."""


class SharePointProjectResource(BaseModel):
    site_id: str = Field(min_length=1)
    drive_id: str = Field(min_length=1)
    folder_item_id: str = "root"


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
        self.path.chmod(0o600)

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

    def status(self) -> MicrosoftConnectionStatus:
        accounts = self._auth_client.get_accounts() if self._auth_client else []
        account = accounts[0] if accounts else {}
        return MicrosoftConnectionStatus(
            enabled=self.settings.enabled,
            configured=bool(self.settings.enabled and self._auth_client),
            connected=bool(accounts),
            scopes=list(self.settings.scopes),
            mapped_projects=sorted(self.settings.project_resources),
            account_label=account.get("username") or account.get("name"),
        )

    def begin(self) -> str:
        if not self.settings.enabled or self._auth_client is None:
            raise MicrosoftConfigurationError("Microsoft integration is not enabled")
        flow = self._auth_client.initiate_auth_code_flow(
            scopes=list(self.settings.scopes), redirect_uri=self.settings.redirect_uri)
        state, auth_uri = flow.get("state"), flow.get("auth_uri")
        if not state or not auth_uri:
            raise MicrosoftConfigurationError("Microsoft did not return a valid authorization flow")
        self._flows[state] = flow
        return str(auth_uri)

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
        return MicrosoftIdentity(tenant_id=tenant_id, user_id=user_id,
            username=claims.get("preferred_username"), display_name=claims.get("name"))

    def token(self) -> str:
        if self._auth_client is None:
            raise MicrosoftConfigurationError("Microsoft integration is not configured")
        accounts = self._auth_client.get_accounts()
        if not accounts:
            raise MicrosoftConfigurationError("Microsoft connection requires sign-in")
        result = self._auth_client.acquire_token_silent(list(self.settings.scopes), accounts[0])
        if not result or "access_token" not in result:
            raise MicrosoftConfigurationError("Microsoft token refresh requires sign-in")
        if self._cache:
            self._cache.persist()
        return str(result["access_token"])

    def disconnect(self) -> None:
        if self._auth_client:
            for account in self._auth_client.get_accounts():
                self._auth_client.remove_account(account)
        self._flows.clear()
        if self._cache:
            self._cache.clear()


class AllowlistedSharePointReader:
    """Resolve Graph targets exclusively through administrator-approved project mappings."""

    def __init__(self, *, settings: MicrosoftPilotSettings,
                 graph_factory: Callable[[Callable[[], str]], MicrosoftGraphReader],
                 token_provider: Callable[[], str]) -> None:
        self.settings = settings
        self.graph_factory = graph_factory
        self.token_provider = token_provider

    def project_documents(self, *, context: UserContext,
                          project_id: str) -> list[SourceDocument]:
        if project_id not in context.project_ids:
            raise PermissionError("Project is outside authenticated scope")
        try:
            resource = self.settings.project_resources[project_id]
        except KeyError as exc:
            raise MicrosoftConfigurationError(
                "Project has no approved SharePoint resource mapping") from exc
        return self.graph_factory(self.token_provider).sharepoint_documents(
            site_id=resource.site_id, drive_id=resource.drive_id,
            folder_item_id=resource.folder_item_id, context=context, project_id=project_id)
