"""Typed loaders for the YAML configuration in ``config/``.

Historically the files in ``config/`` (models.yaml, security.yaml,
integrations.yaml) documented intent but nothing in ``src/`` parsed them —
model selection and approval policy were hardcoded separately, so editing a
YAML file had no effect on runtime behavior. This module makes those files
the single source of truth: it loads and validates them, and callers (the
orchestrator, the CLI) read the parsed result instead of duplicating values.

``config/routing.json`` and ``agents/*.json`` remain the source of truth for
routing and agent manifests respectively (loaded by :mod:`router` and
:mod:`registry`); this module only covers the three YAML files that were
previously unused.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .paths import project_root

# Matches shell-style ${NAME:-default} and ${NAME} placeholders used in the
# YAML config (e.g. config/models.yaml's `${TESSERA_MODEL_DEFAULT:-gpt-5.6-terra}`).
# PyYAML has no notion of this syntax on its own -- it would otherwise load the
# literal placeholder string -- so it is resolved explicitly here against the
# process environment before validation.
_ENV_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-(?P<default>[^}]*))?\}")


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        def substitute(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group("default")
            return os.environ.get(name, default if default is not None else "")
        return _ENV_PLACEHOLDER.sub(substitute, value)
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    return value


class ModelProfile(BaseModel):
    model: str
    reasoning_effort: str
    temperature: float | None = None


class ModelPolicies(BaseModel):
    max_turns: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    capture_usage: bool = True
    tracing: bool = True


class ModelSettings(BaseModel):
    default: ModelProfile
    high_reasoning: ModelProfile
    cost_optimized: ModelProfile
    policies: ModelPolicies

    def profile(self, name: str) -> ModelProfile:
        """Return the named profile, falling back to ``default`` if unknown."""
        return getattr(self, name, None) or self.default


class SecurityDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_access: str
    external_writes: str
    destructive_actions: str
    cross_project_retrieval: str
    pii_logging: str
    production_writes: str


class AuthenticationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    required_claims: list[str]
    production_algorithms: list[str]
    required_group: str


class AuthorizationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    central_policy_gateway: str
    fail_closed: bool
    qualified_reviewer_groups: dict[str, str]


class RuntimeControlSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_limit_per_minute: int = Field(gt=0)
    usage_budget: str
    trace_dlp: str
    artifact_encryption: str
    encryption_key_source: str
    legal_hold_overrides_retention: bool
    tenant_scoped_backup: bool


class ApprovalTiers(BaseModel):
    none: list[str] = Field(default_factory=list)
    manager: list[str] = Field(default_factory=list)
    executive: list[str] = Field(default_factory=list)


class RetentionPolicy(BaseModel):
    raw_prompt_days: int = Field(gt=0)
    audit_event_days: int = Field(gt=0)
    generated_artifact_days: int = Field(gt=0)


class SecuritySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaults: SecurityDefaults
    authentication: AuthenticationPolicy
    authorization: AuthorizationPolicy
    approval_tiers: ApprovalTiers
    retention: RetentionPolicy
    runtime_controls: RuntimeControlSettings


class IntegrationEntry(BaseModel):
    status: str
    mode: str | None = None
    auth: str | None = None
    scopes: list[str] = Field(default_factory=list)
    write_scopes_enabled: bool | None = None


class IntegrationSettings(BaseModel):
    integrations: dict[str, IntegrationEntry]


def _load(filename: str, model: type[BaseModel], *, config_dir: Path | None = None) -> BaseModel:
    path = (config_dir or project_root() / "config") / filename
    data = yaml.safe_load(path.read_text()) or {}
    data = _resolve_env_placeholders(data)
    return model.model_validate(data)


def load_model_settings(config_dir: Path | None = None) -> ModelSettings:
    return _load("models.yaml", ModelSettings, config_dir=config_dir)


def load_security_settings(config_dir: Path | None = None) -> SecuritySettings:
    return _load("security.yaml", SecuritySettings, config_dir=config_dir)


def load_integration_settings(config_dir: Path | None = None) -> IntegrationSettings:
    return _load("integrations.yaml", IntegrationSettings, config_dir=config_dir)
