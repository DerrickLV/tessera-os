"""Phase 2 read-only workflows that always produce reviewable drafts."""

from datetime import UTC, datetime, timedelta

from .integrations import MicrosoftGraphReader
from .knowledge import KnowledgeIndex
from .review import ReviewQueue
from .schemas import Evidence, ReviewItem, UserContext


class PilotWorkflows:
    def __init__(self, *, graph: MicrosoftGraphReader, knowledge: KnowledgeIndex,
                 review_queue: ReviewQueue) -> None:
        self.graph, self.knowledge, self.review_queue = graph, knowledge, review_queue

    def morning_briefing(self, *, context: UserContext,
                         now: datetime | None = None) -> ReviewItem:
        now = now or datetime.now(UTC)
        events = self.graph.calendar_events(start=now.isoformat(),
                                            end=(now + timedelta(days=1)).isoformat())
        messages = self.graph.recent_messages(limit=10)
        lines = ["Morning briefing (draft — human review required)", "", "Calendar"]
        lines.extend(f"- {e.get('start', {}).get('dateTime', 'time unavailable')}: "
                     f"{e.get('subject', 'Untitled')}" for e in events)
        lines.append("\nRecent messages")
        lines.extend(f"- {m.get('subject', 'No subject')} — {m.get('bodyPreview', '')[:160]}"
                     for m in messages)
        evidence = [Evidence(source_id=e["id"], title=e.get("subject", "Calendar event"),
                             locator=e.get("webLink")) for e in events]
        evidence += [Evidence(source_id=m["id"], title=m.get("subject", "Email"),
                              locator=m.get("webLink")) for m in messages]
        return self.review_queue.submit(tenant_id=context.tenant_id, project_id=None,
            created_by=context.user_id, workflow="morning_briefing", title="Morning briefing",
            body="\n".join(lines), evidence=evidence)

    def project_status(self, *, context: UserContext, project_id: str,
                       query: str = "status milestone risk decision") -> ReviewItem:
        hits = self.knowledge.search(query, context=context, project_id=project_id)
        lines = [f"Project status: {project_id} (draft — human review required)", ""]
        evidence: list[Evidence] = []
        if not hits:
            lines.append("No authorized supporting documents were found.")
        for hit in hits:
            lines.append(f"- {hit.title}: {hit.excerpt} [{hit.source_id}]")
            evidence.append(Evidence(source_id=hit.source_id, title=hit.title,
                locator=hit.locator, excerpt=hit.excerpt,
                retrieved_at=datetime.now(UTC).isoformat()))
        return self.review_queue.submit(tenant_id=context.tenant_id, project_id=project_id,
            created_by=context.user_id, workflow="project_status",
            title=f"Project status — {project_id}", body="\n".join(lines), evidence=evidence)
