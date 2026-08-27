"""Phase 3: the numbers stop being invented.

Covers every acceptance criterion in
docs/BUILD_BRIEF_PHASE_3_REAL_NUMBERS.md section 3, items 3.1 through 3.5 --
the DerivedNumber type and its three states, the ordinary-course threshold and
approval-percentage proposals, confirmation and the drafting gate, and the
memo rendering the three states distinguishably. Item 3.6 (the ratchet sweep)
has its own file: test_no_invented_numbers.py.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tessera_os.drafting import StructureAdvisor, StructureRequest
from tessera_os.governance import (
    Basis,
    VentureProfile,
    recommend_structure,
    render_structure_memo,
)
from tessera_os.numbers import (
    APPROVAL_THRESHOLD_LABEL,
    ORDINARY_COURSE_THRESHOLD_LABEL,
    DerivedNumber,
    DerivedNumberConfirmation,
    NumberConfirmationStore,
)
from tessera_os.schemas import Evidence, UserContext
from tessera_os.workspace import PilotArtifactStore, PilotWorkspaceError

PROJECT = "harbor-fabrication"


def context(**overrides) -> UserContext:
    base = {"tenant_id": "tenant-synthetic", "user_id": "derrick",
            "project_ids": {PROJECT}, "group_ids": {"tessera_user", "qualified_counsel"}}
    base.update(overrides)
    return UserContext(**base)


# --- 3.1 -- a number that knows what it is --------------------------------------------------

def test_a_proposed_number_with_no_derivation_fails_validation():
    with pytest.raises(ValidationError, match="derivation"):
        DerivedNumber(label="x", value=10, state="proposed", derivation="")


def test_an_unresolved_number_with_a_value_fails_validation():
    with pytest.raises(ValidationError, match="unresolved"):
        DerivedNumber(label="x", value=10, state="unresolved")


def test_confirmed_by_set_while_not_stated_fails_validation():
    with pytest.raises(ValidationError, match="confirmed_by"):
        DerivedNumber(label="x", value=10, state="proposed", derivation="because",
                      confirmed_by="derrick")


def test_a_derived_number_never_carries_a_basis_because_it_is_a_different_concept():
    """D2 of the Phase 3 brief, the same trap as Phase 2's D2 for SourceDocument.

    Basis records whether a *position* is a Tessera standard. DerivedNumber
    records whether a *figure* has been confirmed by a person. Conflating them
    would let a confirmed number masquerade as an adopted firm position.
    """
    number = DerivedNumber(label="x", value=10, state="stated", confirmed_by="derrick",
                           confirmed_at=datetime.now(UTC))
    assert not hasattr(number, "basis")
    assert "basis" not in type(number).model_fields


def test_a_stated_number_needs_no_derivation_but_a_proposed_one_does():
    # Sanity check that the validator is not simply requiring derivation always.
    DerivedNumber(label="x", value=10, state="stated")
    with pytest.raises(ValidationError):
        DerivedNumber(label="x", value=10, state="proposed")


# --- 3.2 -- the threshold becomes a proposal --------------------------------------------------

def test_stated_capital_proposes_a_threshold_naming_the_coefficient_and_input():
    rec = recommend_structure(VentureProfile(
        venture="Cedar Fabrication", home_state="Texas", initial_capital=2_000_000))
    number = rec.control.ordinary_course_threshold
    assert isinstance(number, DerivedNumber)
    assert number.state == "proposed"
    assert number.value == 40_000  # 2% of $2,000,000
    assert "2%" in number.derivation
    assert "$2,000,000" in number.derivation
    assert "not a Tessera position" in number.derivation


def test_no_capital_leaves_the_threshold_unresolved_and_blocks():
    rec = recommend_structure(VentureProfile(venture="No Capital", home_state="Texas"))
    number = rec.control.ordinary_course_threshold
    assert number.state == "unresolved"
    assert number.value is None
    assert any("ordinary-course spending threshold" in q.question for q in rec.open_questions)


def test_the_threshold_coefficients_are_named_constants_with_unsourced_docstrings():
    """3.2: the floor and the cap are named constants whose docstrings say
    plainly that they are unsourced, or they are gone."""
    from tessera_os import governance

    assert governance._THRESHOLD_FLOOR == 10_000
    assert governance._THRESHOLD_CAP == 250_000
    assert governance._THRESHOLD_COEFFICIENT == 0.02
    # The old fabricated zero-capital default must be gone entirely, not just
    # unused -- its presence would invite a future call site to resurrect it.
    assert not hasattr(governance, "_SYNTHETIC_THRESHOLD")


def test_no_code_path_returns_a_bare_int_for_the_threshold():
    for capital in (0, 1, 500_000, 10_000_000):
        result = recommend_structure(
            VentureProfile(venture="X", home_state="Texas", initial_capital=capital),
        ).control.ordinary_course_threshold
        assert isinstance(result, DerivedNumber)
        assert not isinstance(result, int)


# --- 3.3 -- approval percentages become proposals -------------------------------------------

def test_a_supermajority_percentage_is_a_proposal_with_a_derivation():
    rec = recommend_structure(VentureProfile(
        venture="Quorum", home_state="Texas", active_principals=5, equal_ownership=True,
        initial_capital=1_000_000))
    number = rec.control.approval_threshold_percent
    assert rec.control.approval_rule == "supermajority"
    assert number.state == "proposed"
    assert number.value == 75
    assert "75%" in number.derivation
    assert "no Tessera position" in number.derivation


def test_a_bare_majority_percentage_is_also_a_proposal_not_a_settled_term():
    rec = recommend_structure(VentureProfile(
        venture="Split Co", home_state="Texas", active_principals=3, equal_ownership=False,
        initial_capital=1_000_000))
    number = rec.control.approval_threshold_percent
    assert rec.control.approval_rule == "majority_with_minority_veto"
    assert number.state == "proposed"
    assert number.value == 51


def test_the_memos_control_section_marks_an_unconfirmed_percentage_as_proposed():
    rec = recommend_structure(VentureProfile(
        venture="Quorum", home_state="Texas", active_principals=5, equal_ownership=True,
        initial_capital=1_000_000))
    memo = render_structure_memo(rec)
    assert "75% (proposed, not yet confirmed)" in memo


def test_the_memo_carries_a_figures_to_confirm_section_for_every_proposal():
    """D2: a proposed number renders with the rule that produced it, in plain
    language -- this is the memo-level version of the brief's own example."""
    rec = recommend_structure(VentureProfile(
        venture="Cedar Fabrication", home_state="Texas", initial_capital=2_000_000))
    memo = render_structure_memo(rec)
    assert "## Figures to confirm" in memo
    assert "Ordinary-course threshold — proposed: $40,000." in memo
    assert "Confirm or replace" in memo


# --- 3.4 -- confirmation, and the gate --------------------------------------------------------

def store(tmp_path) -> NumberConfirmationStore:
    return NumberConfirmationStore(tmp_path / "confirmations.db")


def test_confirming_records_who_and_when(tmp_path):
    confirmations = store(tmp_path)
    confirmation = confirmations.confirm(
        tenant_id="tenant-synthetic", project_id=PROJECT,
        label=ORDINARY_COURSE_THRESHOLD_LABEL, value=35_000, confirmed_by="derrick",
        confirmed_at=datetime(2026, 8, 26, tzinfo=UTC))
    assert isinstance(confirmation, DerivedNumberConfirmation)
    assert confirmation.confirmed_by == "derrick"
    assert confirmation.value == 35_000

    fetched = confirmations.for_project(tenant_id="tenant-synthetic", project_id=PROJECT)
    assert fetched[ORDINARY_COURSE_THRESHOLD_LABEL].confirmed_by == "derrick"
    assert fetched[ORDINARY_COURSE_THRESHOLD_LABEL].value == 35_000


def test_a_confirmed_number_moves_to_stated_with_the_confirmer_as_evidence(tmp_path):
    confirmations = store(tmp_path)
    confirmations.confirm(tenant_id="tenant-synthetic", project_id=PROJECT,
                          label=ORDINARY_COURSE_THRESHOLD_LABEL, value=35_000,
                          confirmed_by="derrick")
    rec = recommend_structure(
        VentureProfile(venture="Cedar Fabrication", home_state="Texas",
                       initial_capital=2_000_000),
        confirmations=confirmations.for_project(tenant_id="tenant-synthetic",
                                                 project_id=PROJECT))
    number = rec.control.ordinary_course_threshold
    assert number.state == "stated"
    assert number.value == 35_000  # confirm-or-replace: the confirmed value wins
    assert number.confirmed_by == "derrick"
    assert number.confirmed_at is not None


def test_confirmations_survive_a_restart(tmp_path):
    """3.4: confirmations live in the durable store, opened through
    sqlite_store.connect -- a fresh store instance over the same path must see
    what an earlier instance wrote, exactly as ReviewQueue does."""
    path = tmp_path / "confirmations.db"
    NumberConfirmationStore(path).confirm(
        tenant_id="tenant-synthetic", project_id=PROJECT,
        label=APPROVAL_THRESHOLD_LABEL, value=60, confirmed_by="ryan")

    reopened = NumberConfirmationStore(path)
    fetched = reopened.for_project(tenant_id="tenant-synthetic", project_id=PROJECT)
    assert fetched[APPROVAL_THRESHOLD_LABEL].value == 60
    assert fetched[APPROVAL_THRESHOLD_LABEL].confirmed_by == "ryan"


def advisor(tmp_path, *, number_confirmations=None) -> StructureAdvisor:
    from tessera_os.clauses import ClauseLibrary
    from tessera_os.review import ReviewQueue

    return StructureAdvisor(
        store=PilotArtifactStore(tmp_path / "artifacts.db"),
        review_queue=ReviewQueue(tmp_path / "reviews.db"),
        library=ClauseLibrary.load("fixtures/clause_library"),
        project_clients={PROJECT: "client-harbor"},
        number_confirmations=number_confirmations or store(tmp_path),
    )


def structure_request(**overrides) -> StructureRequest:
    venture = VentureProfile(
        venture="Cedar Fabrication", home_state="Texas", active_principals=2,
        equal_ownership=True, initial_capital=2_000_000)
    base = {"project_id": PROJECT, "venture": venture, "counterparty": "Meridian Capital",
            "evidence": [Evidence(
                source_id="synthetic-intake", title="Synthetic structure intake",
                locator="fixture://structure/harbor-intake", excerpt="Fictional intake facts.",
                retrieved_at=datetime.now(UTC).isoformat())]}
    base.update(overrides)
    ask = StructureRequest(**base)
    if "open_question_answers" not in overrides:
        rec = recommend_structure(ask.venture)
        ask.open_question_answers = {
            item.question: "Answered in the synthetic intake fixture."
            for item in rec.open_questions}
    return ask


def test_to_draft_request_names_every_unconfirmed_number(tmp_path):
    advice = advisor(tmp_path)
    ask = structure_request()
    memo = advice.recommend(ask, context=context())
    item = advice.review_queue.submit(
        tenant_id=memo.tenant_id, project_id=memo.project_id, created_by=memo.agent_id,
        workflow=memo.workflow, title=memo.title, body=memo.review_body(),
        evidence=memo.evidence, required_reviewer_group=memo.required_reviewer_group)
    memo.review_item_id = item.id
    advice.store.update(memo)
    advice.review_queue.accept(item_id=item.id, context=context(user_id="counsel-b"),
                              reason="Synthetic acceptance for the gate test.")

    with pytest.raises(PilotWorkspaceError, match=ORDINARY_COURSE_THRESHOLD_LABEL):
        advice.to_draft_request(ask, context=context(), approved_artifact_id=memo.id)


def test_confirming_outside_project_scope_is_refused_with_403(tmp_path):
    from fastapi.testclient import TestClient

    from tessera_os.console import create_console_app

    api = TestClient(create_console_app(data_dir=tmp_path))
    response = api.post("/v1/structure/numbers/confirm", json={
        "project_id": "a-project-nobody-authorized-for-this-user",
        "label": ORDINARY_COURSE_THRESHOLD_LABEL, "value": 40_000})
    assert response.status_code == 403


# --- 3.5 -- the memo says which is which ------------------------------------------------------

def test_a_stated_number_renders_plainly_with_its_confirmer():
    number = DerivedNumber(label=ORDINARY_COURSE_THRESHOLD_LABEL, value=35_000, state="stated",
                           confirmed_by="derrick", confirmed_at=datetime.now(UTC))
    rendered = number.render_inline(fmt=lambda v: f"${v:,}")
    assert rendered == "$35,000 (confirmed by derrick)"


def test_a_proposed_number_renders_with_an_explicit_call_to_confirm():
    number = DerivedNumber(label=ORDINARY_COURSE_THRESHOLD_LABEL, value=40_000, state="proposed",
                           derivation="Derived as 2% of stated initial capital.")
    rendered = number.render_inline(fmt=lambda v: f"${v:,}")
    assert rendered == "$40,000 (proposed, not yet confirmed)"


def test_an_unresolved_number_never_renders_as_blank_or_zero():
    number = DerivedNumber(label=ORDINARY_COURSE_THRESHOLD_LABEL, value=None, state="unresolved")
    rendered = number.render_inline(fmt=lambda v: f"${v:,}")
    assert rendered != ""
    assert "0" not in rendered
    assert "open questions" in rendered


def test_a_memo_with_any_proposal_cannot_report_status_draft(tmp_path):
    """3.5's own words: a memo containing any proposal cannot report status
    'draft'. Exercised through the real StructureAdvisor.recommend()."""
    advice = advisor(tmp_path)
    ask = structure_request()
    memo = advice.recommend(ask, context=context())
    assert memo.status == "insufficient_evidence"
    assert any("unconfirmed" in reason.lower() for reason in memo.refusal_reasons)


def test_once_every_number_is_confirmed_the_memo_reaches_draft_status(tmp_path):
    confirmations = store(tmp_path)
    ask = structure_request()
    for number in recommend_structure(ask.venture).derived_numbers():
        if number.state == "proposed":
            confirmations.confirm(tenant_id="tenant-synthetic", project_id=PROJECT,
                                  label=number.label, value=number.value,
                                  confirmed_by="derrick")
    advice = advisor(tmp_path, number_confirmations=confirmations)
    memo = advice.recommend(ask, context=context())
    assert memo.status == "draft"
    assert not memo.refusal_reasons


def test_the_basis_type_is_unaffected_and_stays_importable():
    """Confidence check that Basis (the position-provenance literal) and
    DerivedNumber's NumberState remain two distinct, non-interfering types."""
    assert Basis.__args__ == ("tessera_adopted", "synthetic_reference", "scaffold")
