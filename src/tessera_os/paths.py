"""Resolve Tessera's repository-backed configuration and synthetic assets."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Find the checkout, supporting normal installs launched from that checkout."""
    configured = os.getenv("TESSERA_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend([Path.cwd(), Path(__file__).resolve().parents[2]])
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "config" / "routing.json").is_file() and (resolved / "agents").is_dir():
            return resolved
    raise RuntimeError(
        "Tessera repository root was not found; run from the checkout or set TESSERA_ROOT"
    )
