"""The adoption ledger: how a starting point becomes a Tessera position.

Two constraints have to hold at once, and they pull in opposite directions.

The repository must never contain the text of a real Tessera or client
agreement. That rule is right: this codebase is shared with collaborators,
run in CI, and may one day be public. Every clause and every sample stays
synthetic or generic.

But the engine's advice is only worth more than generic structuring if the
firm's actual decisions reach it. "Tessera has adopted this position" is not
agreement text -- it is a governance fact, and hiding it makes every memo
weaker than the firm actually is.

The ledger separates the two. It records *that* a position was adopted, *by
whom*, *when*, and *where the source lives* -- as a citation by reference
(``Tesserra Holdings LLC Operating Agreement §4.4``), never as reproduced
language. The file ships empty. Until the partners sign an entry, nothing in
the system claims to be a Tessera position, which preserves the rule this
codebase already enforces everywhere else: never invent a standard.

The ledger is an attestation, not a signature system. It requires both partner
names and a protected pull-request reference. Repository branch protection and
two independent GitHub approvals provide the actual two-person control; the
loader makes that external record traceable and refuses an unsupported
counsel-review claim.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from .paths import project_root

LEDGER_PATH = "config/adopted_positions.yaml"

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AdoptionError(ValueError):
    """Raised when the ledger is malformed. A broken ledger must never load
    partially -- half-adopted positions are worse than none."""


class AdoptedPosition(BaseModel):
    """One signed decision: this area is now a Tessera position."""

    area: str = Field(min_length=1)
    adopted_by: list[str] = Field(
        min_length=2,
        description="Firm positions require both partners. One name is a proposal.")
    date: str = Field(description="ISO date the decision was made, e.g. 2026-08-19.")
    source_ref: str = Field(
        min_length=1,
        description="Citation by reference only -- a document name and section, "
                    "never reproduced text.")
    approval_ref: HttpUrl = Field(
        description="Protected pull request recording independent partner approval.")
    counsel_reviewed: bool = Field(
        default=False,
        description="True only once qualified counsel has reviewed the position "
                    "for the jurisdictions Tessera works in.")
    counsel_review_ref: str | None = Field(
        default=None,
        description="Required when counsel_reviewed is true; identifies the review record.")
    note: str = ""

    @field_validator("date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        if not _DATE.match(value):
            raise ValueError(f"adoption date must be YYYY-MM-DD, got {value!r}")
        return value

    @field_validator("adopted_by")
    @classmethod
    def _distinct_adopters(cls, value: list[str]) -> list[str]:
        cleaned = [name.strip() for name in value if name.strip()]
        if len({name.casefold() for name in cleaned}) < 2:
            raise ValueError("adoption requires two distinct partners")
        return cleaned

    @model_validator(mode="after")
    def counsel_claim_has_evidence(self) -> AdoptedPosition:
        if self.counsel_reviewed and not self.counsel_review_ref:
            raise ValueError("counsel_reviewed requires a counsel_review_ref")
        return self

    def to_note(self) -> str:
        names = " and ".join(self.adopted_by)
        line = (f"Adopted by {names}, {self.date} — {self.source_ref}. "
                f"Approval: {self.approval_ref}.")
        if self.counsel_reviewed:
            line += f" Counsel reviewed: {self.counsel_review_ref}."
        return line


class AdoptionLedger(BaseModel):
    """Every adopted position, keyed by the recommendation area it upgrades."""

    positions: list[AdoptedPosition] = Field(default_factory=list)

    def for_area(self, area: str) -> AdoptedPosition | None:
        wanted = area.strip().casefold()
        for item in self.positions:
            if item.area.strip().casefold() == wanted:
                return item
        return None

    @property
    def areas(self) -> list[str]:
        return [item.area for item in self.positions]

    @classmethod
    def load(cls, path: Path | None = None) -> AdoptionLedger:
        """Load the ledger, or an empty one when the file does not exist.

        A missing file is a valid state -- it means nothing has been adopted
        yet. A malformed file is not: it raises rather than silently dropping
        the partners' decisions.
        """
        target = path or project_root() / LEDGER_PATH
        if not target.is_file():
            return cls()
        try:
            data = yaml.safe_load(target.read_text()) or {}
        except yaml.YAMLError as exc:
            raise AdoptionError(f"adoption ledger is not valid YAML: {exc}") from exc
        entries = data.get("positions", [])
        if not isinstance(entries, list):
            raise AdoptionError("adoption ledger 'positions' must be a list")
        try:
            ledger = cls(positions=[AdoptedPosition(**entry) for entry in entries])
        except (TypeError, ValueError) as exc:
            raise AdoptionError(f"adoption ledger entry is invalid: {exc}") from exc
        seen: set[str] = set()
        for item in ledger.positions:
            key = item.area.strip().casefold()
            if key in seen:
                raise AdoptionError(f"adoption ledger lists {item.area!r} twice")
            seen.add(key)
        return ledger
