"""The weekly digest: what the system did, and what is waiting on a human.

An audit chain answers "what happened to this artifact." Nobody reads an audit
chain on a Monday. The question two partners actually have is "what did this
thing do last week, and what is waiting on me" — and until something answers
it, an unattended system is one you have to remember to check, which means one
you stop trusting.

Two design choices worth stating.

**Waiting-on-you comes first.** A digest that opens with volume — artifacts
produced, workflows run — trains the reader to skim. Opening with the queue,
oldest first, makes the document actionable in its first ten lines and useless
to skim, which is the correct incentive.

**Age is reported, not just count.** "4 items pending" is a number. "One has
been pending eleven days" is a prompt. Separation of duties means an artifact
can sit because the only person who may decide it has not looked, and that is
exactly the failure a digest exists to surface.

Derived entirely from the artifact store — no new state, nothing to keep in
sync, and it can be produced for any window on demand.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from .schemas import UserContext
from .workspace import PilotArtifact, PilotArtifactStore

# Past this, a pending item is not "in the queue", it is stuck. Chosen to be
# just past a normal working week so one weekend cannot trip it.
STALE_AFTER_DAYS = 8


class PendingItem(BaseModel):
    artifact_id: str
    title: str
    project_id: str
    workflow: str
    waiting_on: str = Field(description="The reviewer group that must decide it.")
    age_days: int
    stale: bool


class DigestSection(BaseModel):
    label: str
    count: int
    detail: list[str] = Field(default_factory=list)


class RunDigest(BaseModel):
    """One window of activity, ordered by what needs a person."""

    generated_at: datetime
    window_days: int
    pending: list[PendingItem]
    produced: list[DigestSection]
    refusals: list[str]
    escalations: list[str]
    quiet: bool = Field(
        default=False,
        description="Nothing happened and nothing is waiting. Worth saying plainly.")

    @property
    def stale_items(self) -> list[PendingItem]:
        return [item for item in self.pending if item.stale]

    def to_markdown(self) -> str:
        out = [f"# Tessera OS — last {self.window_days} days", ""]
        stamp = self.generated_at.strftime("%d %B %Y")
        out.append(f"*Generated {stamp}. Nothing in this digest was sent, filed, or "
                   "executed — the system produces drafts and waits.*")
        out.append("")

        if self.quiet:
            out.append("## Nothing waiting")
            out.append("")
            out.append("No artifacts were produced in this window and nothing is "
                       "pending a decision. A quiet week is a real result and is "
                       "reported as one rather than as an empty report.")
            return "\n".join(out) + "\n"

        out.append("## Waiting on you")
        out.append("")
        if not self.pending:
            out.append("Nothing is pending a decision.")
            out.append("")
        else:
            if self.stale_items:
                out.append(f"**{len(self.stale_items)} item"
                           f"{'s have' if len(self.stale_items) != 1 else ' has'} been "
                           f"waiting more than {STALE_AFTER_DAYS} days.** Separation of "
                           "duties means an item can sit because the one person who may "
                           "decide it has not looked.")
                out.append("")
            out.append("| Age | Title | Project | Waiting on |")
            out.append("| --- | --- | --- | --- |")
            for item in self.pending:
                age = f"**{item.age_days}d**" if item.stale else f"{item.age_days}d"
                out.append(f"| {age} | {item.title} | {item.project_id} "
                           f"| {item.waiting_on} |")
            out.append("")

        if self.refusals:
            out.append("## Refused, and why")
            out.append("")
            out.append("The system declined to produce a draft. Each of these is a "
                       "missing input rather than a failure.")
            out.append("")
            out += [f"- {reason}" for reason in self.refusals]
            out.append("")

        if self.escalations:
            out.append("## Raised for a human")
            out.append("")
            out += [f"- {item}" for item in self.escalations[:12]]
            if len(self.escalations) > 12:
                out.append(f"- …and {len(self.escalations) - 12} more, in the artifacts")
            out.append("")

        out.append("## Produced")
        out.append("")
        for section in self.produced:
            out.append(f"**{section.label}** — {section.count}")
            out += [f"  - {line}" for line in section.detail[:5]]
        out.append("")
        return "\n".join(out).rstrip() + "\n"


def _age_days(artifact: PilotArtifact, now: datetime) -> int:
    created = artifact.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return max(0, (now - created).days)


def build_run_digest(store: PilotArtifactStore, *, context: UserContext,
                     window_days: int = 7,
                     now: datetime | None = None) -> RunDigest:
    """Summarise a window of artifact activity for the partners.

    Scoped by the caller's ``UserContext``, so a digest never reveals a project
    the reader could not open directly.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    artifacts = store.list(context=context)

    pending: list[PendingItem] = []
    recent: list[PilotArtifact] = []
    refusals: list[str] = []
    escalations: list[str] = []

    for artifact in artifacts:
        created = artifact.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age = _age_days(artifact, now)

        # Pending is reported regardless of age. An item that has been waiting
        # three weeks is precisely the one a seven-day window would hide.
        if artifact.status in {"draft", "pending"}:
            pending.append(PendingItem(
                artifact_id=artifact.id, title=artifact.title,
                project_id=artifact.project_id, workflow=artifact.workflow,
                waiting_on=artifact.required_reviewer_group or "any reviewer",
                age_days=age, stale=age >= STALE_AFTER_DAYS))

        if created >= cutoff:
            recent.append(artifact)
            if artifact.refusal_reasons:
                refusals.extend(f"{artifact.title}: {reason}"
                                for reason in artifact.refusal_reasons)
            escalations.extend(f"{artifact.title}: {item}"
                               for item in artifact.escalations)

    pending.sort(key=lambda item: item.age_days, reverse=True)

    by_workflow = Counter(artifact.workflow for artifact in recent)
    produced = [
        DigestSection(
            label=workflow.replace("_", " ").title(), count=count,
            detail=[artifact.title for artifact in recent
                    if artifact.workflow == workflow])
        for workflow, count in sorted(by_workflow.items())
    ]

    return RunDigest(
        generated_at=now, window_days=window_days,
        pending=pending, produced=produced,
        refusals=refusals, escalations=escalations,
        quiet=not recent and not pending)
