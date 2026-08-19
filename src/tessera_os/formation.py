"""The gap between advice and a company that exists.

A structure recommendation ends with an entity chart. Somebody then has to
actually file it, and the filing has an order that is not obvious: the EIN
needs the formation certificate, the bank account needs the EIN and the
operating agreement, and in a licensed business the regulator may want to see
the whole chart before any of it moves.

This produces that checklist from the recommendation itself, so the ordering
constraints are derived rather than remembered. It is deliberately mechanical.

**What it does not do.** It does not file anything, does not quote a state's
actual fees, and does not claim to know a jurisdiction's process. Filing fees
vary by state and change; a precise-looking wrong number is worse than an
obvious blank, so cost is left to the operator to fill from the state's own
schedule. Every step is a task for a human, and the regulated steps say plainly
that they gate everything downstream.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .governance import StructureRecommendation


class FormationStep(BaseModel):
    """One task, with what it blocks and what has to come first."""

    order: int
    entity: str
    task: str
    why: str
    depends_on: list[str] = Field(default_factory=list)
    owner: str = "Tessera"
    gate: bool = Field(
        default=False,
        description="A step nothing downstream may proceed past until it clears.")


class FormationChecklist(BaseModel):
    venture: str
    steps: list[FormationStep]
    notes: list[str] = Field(default_factory=list)

    @property
    def gates(self) -> list[FormationStep]:
        return [step for step in self.steps if step.gate]

    def to_markdown(self) -> str:
        out = [f"# Formation Checklist — {self.venture}", ""]
        out.append("> The order matters. An EIN needs the formation certificate; a "
                   "bank account needs the EIN and an adopted operating agreement. "
                   "Steps marked **gate** stop everything downstream until they "
                   "clear. Filing fees are left blank on purpose — take them from "
                   "the state's own current schedule rather than from here.")
        out.append("")
        if self.gates:
            out.append("## Gates")
            out.append("")
            for step in self.gates:
                out.append(f"- **{step.task}** ({step.entity}) — {step.why}")
            out.append("")
        out.append("## Steps")
        out.append("")
        out.append("| # | Entity | Task | Depends on | Owner | Fee |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for step in self.steps:
            depends = "; ".join(step.depends_on) or "—"
            mark = " **(gate)**" if step.gate else ""
            out.append(f"| {step.order} | {step.entity} | {step.task}{mark} "
                       f"| {depends} | {step.owner} | |")
        out.append("")
        out.append("## Why each step is where it is")
        out.append("")
        for step in self.steps:
            out.append(f"**{step.order}. {step.task}** — {step.why}")
            out.append("")
        if self.notes:
            out.append("## Before any of this starts")
            out.append("")
            out += [f"- {note}" for note in self.notes]
            out.append("")
        return "\n".join(out).rstrip() + "\n"


def build_formation_checklist(rec: StructureRecommendation) -> FormationChecklist:
    """Derive the filing sequence from the recommended structure."""
    profile = rec.profile
    steps: list[FormationStep] = []
    order = 0

    def add(**kwargs) -> None:
        nonlocal order
        order += 1
        steps.append(FormationStep(order=order, **kwargs))

    # A licensed business is the one case where filing first can be a mistake:
    # the regulator may need to approve the ownership chart before entities
    # exist that would have to be unwound.
    if profile.is_regulated:
        add(entity="All", gate=True, owner="Regulatory counsel",
            task=f"Confirm the {profile.regulated_regime} regulator will accept this "
                 "ownership chart",
            why="In a licensed business the regulator decides who may own what. "
                "Forming entities the regime will not approve means unwinding them, "
                "and an unwind can itself be a reportable change of control.")

    if rec.open_questions:
        blocking = [q for q in rec.open_questions
                    if "formation" in q.blocks.casefold()
                    or "schedule a" in q.blocks.casefold()]
        if blocking:
            add(entity="All", gate=True, owner="Derrick",
                task="Answer the open questions that block formation",
                why="Contributions, registered agent, and principal office all appear "
                    "in the filing or in Schedule A. Filing without them means "
                    "amending later, and an amendment is a public record of having "
                    "got it wrong the first time.")

    holdco = next((layer for layer in rec.layers if layer.role == "HoldCo"), None)
    ordered_layers = ([holdco] if holdco else []) + [
        layer for layer in rec.layers if layer is not holdco]

    for layer in ordered_layers:
        state = layer.entity_form.split()[1] if len(
            layer.entity_form.split()) > 1 else profile.home_state
        add(entity=layer.name, task=f"File the certificate of formation in {state}",
            why=f"Creates the entity that {layer.holds.lower()}.",
            depends_on=([holdco.name] if holdco and layer is not holdco else []),
            owner="Tessera / registered agent")
        add(entity=layer.name, task="Appoint a registered agent",
            why="Required by the state, and the address where service of process "
                "lands. A missed service is a default judgment.",
            depends_on=[f"{layer.name}: certificate"])
        add(entity=layer.name, task="Obtain an EIN",
            why="Needed for the bank account and for any tax election. The "
                "application asks for the formation details, so it cannot run first.",
            depends_on=[f"{layer.name}: certificate"])

    add(entity="All", task="Adopt the operating agreement and Schedule A",
        why="The certificate creates the entity; the operating agreement is what "
            "actually governs it. Until it is adopted, the state's default rules "
            "apply — which is precisely the outcome the structuring work exists to "
            "avoid.",
        depends_on=[f"{layer.name}: EIN" for layer in ordered_layers],
        owner="Derrick and counsel", gate=True)

    add(entity="All", task="Open bank accounts, one per entity",
        why="Separate entities that share a bank account are one entity to a court. "
            "This is the step that most often quietly undoes the whole structure.",
        depends_on=["Operating agreement adopted"])

    if len(rec.layers) > 1:
        add(entity="All", task="Execute the intercompany agreements the chart implies",
            why="A lease from the property entity to the operating entity, a licence "
                "from the brand or rights entity, a services agreement where one "
                "entity employs the staff. A structure that exists only on the chart "
                "and never in a signed document is the structure a plaintiff pierces.",
            depends_on=["Operating agreement adopted"], owner="Derrick and counsel")

    outside = [state for state in profile.states_of_operation
               if state != profile.home_state]
    if outside:
        add(entity="Operating entities",
            task=f"Qualify to do business in {', '.join(outside)}",
            why="Operating unqualified can bar the company from its own courts and "
                "accrues penalties from the first day of activity, not from the day "
                "anyone notices.",
            depends_on=["Operating agreement adopted"])

    if profile.is_regulated:
        add(entity="Licence-holding entity",
            task=f"File the {profile.regulated_regime} licence application or transfer",
            why="The licence is the permission to exist. Everything else in the chart "
                "is scaffolding around it.",
            depends_on=["Operating agreement adopted"], owner="Regulatory counsel")

    notes = [
        ("Nothing in this checklist is filed by Tessera OS. Every step is a human "
         "action, and the system records that it was taken rather than taking it."),
        ("Fees and processing times come from each state's current schedule. They "
         "change, and a stale number in a checklist is worse than a blank one."),
    ]
    if profile.role == "both":
        notes.append(
            "Tessera is both advising and holding equity here. The dual-role "
            "disclosure should be signed before the operating agreement is adopted, "
            "not after.")

    return FormationChecklist(venture=profile.venture, steps=steps, notes=notes)
