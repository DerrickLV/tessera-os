from datetime import UTC, datetime

import pytest

from tessera_os.integrations import IntegrationError, MicrosoftGraphReader
from tessera_os.knowledge import KnowledgeIndex, ScopeDenied
from tessera_os.pilot import PilotWorkflows
from tessera_os.review import InvalidReviewTransition, ReviewAccessDenied, ReviewQueue
from tessera_os.schemas import SourceDocument, UserContext


def context() -> UserContext:
    return UserContext(tenant_id="tenant-a", user_id="alice",
                       project_ids={"project-1"}, group_ids={"project-team"})


def test_retrieval_preserves_tenant_project_and_source_acls():
    index = KnowledgeIndex()
    index.ingest([
        SourceDocument(source_id="allowed", tenant_id="tenant-a", project_id="project-1",
                       title="Status", content="Milestone is on schedule",
                       allowed_group_ids={"project-team"}),
        SourceDocument(source_id="wrong-tenant", tenant_id="tenant-b", project_id="project-1",
                       title="Secret", content="Milestone secret",
                       allowed_group_ids={"project-team"}),
        SourceDocument(source_id="no-acl", tenant_id="tenant-a", project_id="project-1",
                       title="Unclassified", content="Milestone private"),
    ])
    assert [hit.source_id for hit in index.search(
        "milestone", context=context(), project_id="project-1")] == ["allowed"]


def test_retrieval_rejects_project_before_search():
    with pytest.raises(ScopeDenied):
        KnowledgeIndex().search("anything", context=context(), project_id="project-2")


def test_graph_client_rejects_pagination_to_another_origin():
    calls = 0

    def transport(url, headers):
        nonlocal calls
        calls += 1
        return {"value": [], "@odata.nextLink": "https://attacker.invalid/token"}

    graph = MicrosoftGraphReader(lambda: "secret", transport=transport)
    with pytest.raises(IntegrationError):
        graph.recent_messages()
    assert calls == 1


def test_project_status_is_cited_and_queued(tmp_path):
    index = KnowledgeIndex()
    index.ingest([SourceDocument(
        source_id="doc-1", tenant_id="tenant-a", project_id="project-1",
        title="Weekly report", content="The milestone is complete; risk is low.",
        web_url="https://example.invalid/doc-1", allowed_user_ids={"alice"})])
    graph = MicrosoftGraphReader(lambda: "unused", transport=lambda url, headers: {"value": []})
    queue = ReviewQueue(tmp_path / "review.db")
    item = PilotWorkflows(graph=graph, knowledge=index, review_queue=queue).project_status(
        context=context(), project_id="project-1")
    assert item.status == "pending"
    assert item.evidence[0].source_id == "doc-1"
    assert "[doc-1]" in item.body
    assert queue.list_pending(context=context())[0].id == item.id


def test_morning_briefing_is_draft_with_graph_evidence(tmp_path):
    def transport(url, headers):
        if "calendarView" in url:
            return {"value": [{"id": "event-1", "subject": "Project review",
                                "start": {"dateTime": "2026-08-17T09:00:00"}}]}
        return {"value": [{"id": "mail-1", "subject": "Risk update",
                            "bodyPreview": "The permit was approved."}]}

    workflow = PilotWorkflows(
        graph=MicrosoftGraphReader(lambda: "token", transport=transport),
        knowledge=KnowledgeIndex(), review_queue=ReviewQueue(tmp_path / "review.db"))
    item = workflow.morning_briefing(
        context=context(), now=datetime(2026, 8, 17, tzinfo=UTC))
    assert "human review required" in item.body
    assert {e.source_id for e in item.evidence} == {"event-1", "mail-1"}


def test_projectless_review_items_are_visible_only_to_their_creator(tmp_path):
    queue = ReviewQueue(tmp_path / "review.db")
    alice_item = queue.submit(tenant_id="tenant-a", project_id=None, created_by="alice",
                              workflow="morning_briefing", title="Alice brief", body="draft",
                              evidence=[])
    bob_item = queue.submit(tenant_id="tenant-a", project_id=None, created_by="bob",
                            workflow="morning_briefing", title="Bob brief", body="draft",
                            evidence=[])

    pending = queue.list_pending(context=context())

    assert [item.id for item in pending] == [alice_item.id]
    assert bob_item.id not in {item.id for item in pending}


def test_review_disposition_is_authorized_audited_and_final(tmp_path):
    queue = ReviewQueue(tmp_path / "review.db")
    item = queue.submit(tenant_id="tenant-a", project_id=None, created_by="alice",
                        workflow="morning_briefing", title="Brief", body="draft", evidence=[])
    bob = UserContext(tenant_id="tenant-a", user_id="bob", project_ids={"project-2"})

    with pytest.raises(ReviewAccessDenied):
        queue.accept(item_id=item.id, context=bob, reason="Looks good")

    accepted = queue.accept(item_id=item.id, context=context(), reason="Reviewed source evidence")
    assert accepted.status == "accepted"
    assert accepted.reviewed_by == "alice"
    assert accepted.reviewed_at is not None
    assert accepted.review_reason == "Reviewed source evidence"
    assert queue.list_pending(context=context()) == []

    with pytest.raises(InvalidReviewTransition):
        queue.reject(item_id=item.id, context=context(), reason="Changed my mind")


def test_project_review_can_be_rejected_by_authorized_project_member(tmp_path):
    queue = ReviewQueue(tmp_path / "review.db")
    item = queue.submit(tenant_id="tenant-a", project_id="project-1", created_by="author",
                        workflow="project_status", title="Status", body="draft", evidence=[])
    unauthorized = UserContext(tenant_id="tenant-a", user_id="bob", project_ids={"project-2"})

    with pytest.raises(ReviewAccessDenied):
        queue.reject(item_id=item.id, context=unauthorized, reason="Not my project")

    rejected = queue.reject(item_id=item.id, context=context(), reason="Needs newer evidence")

    assert rejected.status == "rejected"
    assert rejected.reviewed_by == "alice"
