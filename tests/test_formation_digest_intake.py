"""Three capabilities that each refuse to overstate what they know.

The formation checklist derives an order rather than reciting one, and leaves
fees blank because a stale number is worse than a blank. The digest opens with
what is waiting on a person rather than with volume. The intake proposer cites
every field it proposes and leaves unsupported fields alone instead of
defaulting them — a default laundered through an extraction step becomes an
assertion nobody made.
"""

from datetime import UTC, datetime, timedelta

from tessera_os.digest import STALE_AFTER_DAYS, build_run_digest
from tessera_os.formation import build_formation_checklist
from tessera_os.governance import VentureProfile, recommend_structure
from tessera_os.intake import propose_profile
from tessera_os.schemas import Evidence, RouteDecision, SourceDocument, UserContext
from tessera_os.workspace import PilotArtifact, PilotArtifactStore

PROJECT = "riverbend"


def venture(**overrides) -> VentureProfile:
    base = {"venture": "RiverBend Residential", "home_state": "Texas",
            "active_principals": 2, "equal_ownership": True, "real_property": True,
            "activity": "real_estate_hold", "business_lines": 2,
            "initial_capital": 3_000_000}
    base.update(overrides)
    return VentureProfile(**base)


# --- formation checklist -------------------------------------------------------

def checklist(**overrides):
    return build_formation_checklist(recommend_structure(venture(**overrides)))


def test_the_ein_cannot_precede_the_certificate():
    steps = checklist().steps
    for step in steps:
        if step.task == "Obtain an EIN":
            assert any("certificate" in dep for dep in step.depends_on)


def test_the_bank_account_waits_for_the_adopted_agreement():
    steps = {step.task: step for step in checklist().steps}
    bank = steps["Open bank accounts, one per entity"]
    assert "Operating agreement adopted" in bank.depends_on
    assert "one entity to a court" in bank.why


def test_adopting_the_agreement_is_a_gate():
    gates = {step.task for step in checklist().gates}
    assert "Adopt the operating agreement and Schedule A" in gates


def test_a_regulated_venture_clears_the_regulator_before_filing_anything():
    result = checklist(regulated_regime="cannabis")
    assert result.steps[0].gate
    assert "regulator" in result.steps[0].task.lower()
    filings = [step.order for step in result.steps if "certificate" in step.task]
    assert min(filings) > result.steps[0].order


def test_intercompany_agreements_appear_only_with_more_than_one_entity():
    multi = {step.task for step in checklist().steps}
    single = {step.task for step in checklist(
        real_property=False, business_lines=1, activity="operating",
        operating_liability=False).steps}
    assert any("intercompany" in task for task in multi)
    assert not any("intercompany" in task for task in single)


def test_fees_are_left_blank_rather_than_guessed():
    markdown = checklist().to_markdown()
    assert "| Fee |" in markdown
    assert "left blank on purpose" in markdown


def test_the_checklist_says_the_system_files_nothing():
    markdown = checklist().to_markdown()
    assert "Nothing in this checklist is filed by Tessera OS" in markdown


def test_the_dual_role_disclosure_precedes_adoption_when_tessera_holds():
    notes = " ".join(checklist(tessera_role="both").notes)
    assert "disclosure should be signed before the operating agreement" in notes


# --- run digest ------------------------------------------------------------------

def context() -> UserContext:
    return UserContext(tenant_id="t", user_id="derrick", project_ids={PROJECT},
                       group_ids={"tessera_user", "qualified_counsel"})


def artifact(tmp_path_store, *, title, status="draft", days_ago=0,
             workflow="entity_structuring", escalations=(), refusals=()):
    created = datetime.now(UTC) - timedelta(days=days_ago)
    item = PilotArtifact(
        tenant_id="t", client_id="c", project_id=PROJECT, created_by="derrick",
        task="t", title=title, workflow=workflow, agent_id="structure_manager",
        route=RouteDecision(primary_agent="structure_manager", rationale="r"),
        status=status, summary="s",
        evidence=[Evidence(source_id="e1", title="Evidence", locator="l")],
        escalations=list(escalations), refusal_reasons=list(refusals),
        required_reviewer_group="qualified_counsel",
        created_at=created, updated_at=created)
    return tmp_path_store.save(item)


def store(tmp_path) -> PilotArtifactStore:
    return PilotArtifactStore(tmp_path / "artifacts.db")


def test_a_quiet_window_says_so_plainly(tmp_path):
    digest = build_run_digest(store(tmp_path), context=context())
    assert digest.quiet
    assert "A quiet week is a real result" in digest.to_markdown()


def test_pending_work_leads_the_digest(tmp_path):
    data = store(tmp_path)
    artifact(data, title="Structure memo", status="draft")
    artifact(data, title="Accepted thing", status="accepted")
    markdown = build_run_digest(data, context=context()).to_markdown()
    assert markdown.index("Waiting on you") < markdown.index("## Produced")


def test_an_old_pending_item_is_reported_as_stuck_not_merely_counted(tmp_path):
    data = store(tmp_path)
    artifact(data, title="Forgotten memo", days_ago=STALE_AFTER_DAYS + 3)
    digest = build_run_digest(data, context=context())
    assert digest.stale_items
    assert digest.stale_items[0].age_days >= STALE_AFTER_DAYS
    assert "separation of duties" in digest.to_markdown().lower()


def test_a_pending_item_older_than_the_window_is_still_surfaced(tmp_path):
    """A seven-day window would hide the item that most needs attention."""
    data = store(tmp_path)
    artifact(data, title="Very old", days_ago=30)
    digest = build_run_digest(data, context=context(), window_days=7)
    assert [item.title for item in digest.pending] == ["Very old"]


def test_pending_items_are_ordered_oldest_first(tmp_path):
    data = store(tmp_path)
    artifact(data, title="Newer", days_ago=1)
    artifact(data, title="Older", days_ago=12)
    digest = build_run_digest(data, context=context())
    assert [item.title for item in digest.pending] == ["Older", "Newer"]


def test_refusals_are_framed_as_missing_inputs(tmp_path):
    data = store(tmp_path)
    artifact(data, title="Refused draft", status="insufficient_evidence",
             refusals=["Intake evidence is stale"])
    markdown = build_run_digest(data, context=context()).to_markdown()
    assert "Refused, and why" in markdown
    assert "missing input rather than a failure" in markdown


def test_the_digest_says_nothing_was_sent(tmp_path):
    data = store(tmp_path)
    artifact(data, title="Anything")
    assert "was sent, filed, or executed" in build_run_digest(
        data, context=context()).to_markdown()


# --- intake proposal ---------------------------------------------------------------

def document(content: str, *, title="Intake call notes",
             source_id="intake-1") -> SourceDocument:
    return SourceDocument(source_id=source_id, tenant_id="t", project_id=PROJECT,
                          title=title, content=content)


INTAKE = """
Call notes — RiverBend Residential.

Two equal partners, both working in the business day to day. They are married and
both have an estate plan they want respected. They will own real property — the
plan is to acquire the property and hold it. Roughly $3,000,000 going in from
friends and family. Investors are paid back first with a preferred return before
any split. They expect to refinance and pull cash out rather than sell.
"""


def test_every_proposed_field_carries_its_evidence():
    proposal = propose_profile([document(INTAKE)], venture="RiverBend Residential")
    assert proposal.proposals
    for item in proposal.proposals:
        assert item.phrase
        assert item.source_id == "intake-1"


def test_the_obvious_facts_are_proposed():
    values = propose_profile([document(INTAKE)],
                             venture="RiverBend").as_kwargs()
    assert values["active_principals"] == 2
    assert values["equal_ownership"] is True
    assert values["real_property"] is True
    assert values["spouses_involved"] is True
    assert values["estate_planning_relevant"] is True
    assert values["tiered_economics"] is True
    assert values["initial_capital"] == 3_000_000
    assert values["capital_source"] == "friends_family"


def test_an_unsupported_field_is_left_alone_rather_than_defaulted():
    proposal = propose_profile([document(INTAKE)], venture="RiverBend")
    assert "home_state" in proposal.unproposed
    assert "tessera_role" in proposal.unproposed
    assert "home_state" not in proposal.as_kwargs()


def test_an_ambiguous_reading_becomes_a_conflict_not_a_coin_flip():
    text = ("We run a consulting practice and also operate a restaurant with a "
            "second location planned.")
    proposal = propose_profile([document(text)], venture="Two Things")
    assert any(conflict.field == "activity" for conflict in proposal.conflicts)
    assert "activity" not in proposal.as_kwargs()


def test_nothing_is_applied_without_a_human_supplying_the_rest():
    proposal = propose_profile([document(INTAKE)], venture="RiverBend")
    profile = proposal.to_profile(home_state="Texas", tessera_role="both")
    assert profile.home_state == "Texas"
    assert profile.active_principals == 2
    assert profile.role == "both"


def test_the_proposal_states_that_nothing_is_applied():
    markdown = propose_profile([document(INTAKE)],
                               venture="RiverBend").to_markdown()
    assert "**Nothing here is applied.**" in markdown
    assert "The intake did not say" in markdown


def test_an_empty_intake_proposes_nothing_and_says_so():
    proposal = propose_profile([document("Nothing useful here.")], venture="Blank")
    assert proposal.as_kwargs() == {}
    assert len(proposal.unproposed) > 10
