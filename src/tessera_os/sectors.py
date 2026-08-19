"""Sector patterns — the structuring that is specific to an industry.

Tessera's representative work runs across real estate, the skilled trades,
cannabis and hemp, film and independent media, and hospitality. Those are not
five flavours of the same problem. A film finances one production at a time and
the asset is a copyright. A trades business lives or dies on a licence held by a
named human being and a fleet of trucks. A restaurant's second location is a
different liability universe from its first, and the liquor licence is the thing
that cannot move.

Flattening all of them into "regulated" or "operating" is how a structure ends up
technically correct and practically useless. This module carries what each sector
adds: the entities it needs, the decisions that must be reserved, the way it
fails, and the questions nobody can answer from a generic intake form.

**Provenance.** Every pattern here is ``scaffold``. These are informed starting
points drawn from standard practice in each sector -- they are not yet Tessera
positions, and none has been reviewed by counsel or by a regulator in any
particular state. The memo says so, every time.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Sector = Literal[
    "operating",
    "real_estate_hold",
    "development",
    "fund",
    "ip_licensing",
    "professional_services",
    "film_production",
    "skilled_trades",
    "hospitality",
]


class SectorLayer(BaseModel):
    """An entity a sector needs that the general rules would not produce."""

    suffix: str
    role: str
    holds: str
    why: str
    per_unit: bool = Field(
        default=False,
        description="One of these per production, location, or asset rather than one total.")
    supersedes: Literal["", "licence", "ip"] = Field(
        default="",
        description=("Replaces the general-rule entity of this kind. A film's rights entity "
                     "IS the IP entity; a beverage entity IS the licence entity. Emitting "
                     "both is two filing fees for one job."))


class SectorPattern(BaseModel):
    """Everything an industry adds to a structure."""

    sector: Sector
    label: str
    unit_noun: str = Field(default="line of business",
                           description="What business_lines counts here — productions, "
                                       "locations, properties, service territories.")
    layers: list[SectorLayer] = Field(default_factory=list)
    reserved_matters: list[str] = Field(default_factory=list)
    failure_modes: list[tuple[str, str]] = Field(default_factory=list)
    open_questions: list[tuple[str, str, str]] = Field(default_factory=list)
    positions: list[tuple[str, str, str]] = Field(
        default_factory=list,
        description="(area, position, because) triples added to the recommendation.")
    counsel_notes: list[str] = Field(default_factory=list)


FILM = SectorPattern(
    sector="film_production",
    label="Film and independent media",
    unit_noun="production",
    layers=[
        SectorLayer(
            suffix="Productions LLC", role="Production vehicle", per_unit=True,
            holds="One picture: the chain of title, the production bank account, the crew "
                  "and talent agreements, and the completion obligations",
            why="A picture is financed, insured, and sued on its own. One entity per "
                "production means a claim on the last picture — a guild grievance, an "
                "injury on set, a rights dispute — cannot reach the next one or the slate, "
                "and it means an investor buys into one film rather than into everything "
                "the producer will ever make."),
        SectorLayer(
            suffix="Rights LLC", role="Rights and library entity", supersedes="ip",
            holds="Underlying rights, options, scripts, trademarks, and the library of "
                  "completed pictures once delivery is accepted",
            why="The library is the durable asset and the production vehicle is where the "
                "liability sits. Holding rights separately and licensing them into each "
                "production keeps the catalogue out of reach of any single picture's "
                "creditors, and keeps it saleable without selling the company."),
    ],
    reserved_matters=[
        "Greenlighting a production, or committing the company to a production budget",
        "Acquiring, optioning, or disposing of underlying rights",
        "Granting distribution rights, or entering any sales agency agreement",
        "Any final cut, credit, or approval right granted to a third party",
        "Any obligation to a completion guarantor, or any draw under a completion bond",
    ],
    failure_modes=[
        ("Chain of title with a hole in it",
         ("A rights assignment was never signed, a writer's work-for-hire was assumed rather "
          "than papered, or an option lapsed — and the picture cannot be delivered, insured, "
          "or sold because nobody can prove who owns it.")),
        ("Backend that nobody can compute",
         ("Net profit participations were promised in different documents on different "
          "definitions, and when revenue finally arrives no two participants agree on what "
          "they are owed.")),
        ("The last picture takes the next one",
         ("Everything was run through one company, so a claim arising on the completed film "
          "reaches the financing, the rights, and the picture in production.")),
    ],
    open_questions=[
        (("Is the chain of title complete and papered — every writer, every option, every "
          "underlying work?"),
         ("No distributor accepts delivery and no E&O carrier writes a policy without it. "
          "It is also the single most common reason an independent picture stalls at "
          "delivery."),
         "Financing, E&O insurance, and any distribution agreement."),
        (("Are participations defined on gross, adjusted gross, or net — and is there one "
          "written definition all of them point to?"),
         "Undefined backend is the most litigated term in independent film.",
         "The operating agreement's distribution waterfall, and every talent agreement."),
        ("Will a collection account manager hold and disburse revenue?",
         ("A CAM removes the producer from the middle of the money and is usually what makes "
          "third-party investors comfortable."),
         "The distribution mechanics and the investor package."),
        ("Are the guilds involved — SAG-AFTRA, WGA, DGA — and is the production a signatory?",
         ("Signatory status brings residual obligations that survive delivery and attach to "
          "the entity that made the picture."),
         "The production entity's ongoing obligations and any sale of the library."),
    ],
    positions=[
        ("Production vehicles",
         ("One special-purpose entity per picture, owned by the HoldCo, dissolved only after "
          "residual and participation obligations run out."),
         ("It is how independent film is financed, and it is what lets an investor back one "
          "picture without underwriting the producer's whole slate.")),
        ("Rights separation",
         ("Underlying rights and the completed library sit in a rights entity and are "
          "licensed into each production."),
         ("The catalogue is the asset that compounds. Nothing that happens on a set should "
          "be able to reach it.")),
        ("Participation definitions",
         ("Define gross, adjusted gross, and net once, in the operating agreement, and have "
          "every talent and investor document point at that definition."),
         ("Backend defined three different ways in three different documents is the most "
          "reliable way to end up in a dispute after the money finally arrives.")),
    ],
    counsel_notes=[
        ("Entertainment counsel confirms chain of title, guild signatory status, and whether "
         "the participation definitions survive scrutiny before any investor sees them."),
    ],
)

SKILLED_TRADES = SectorPattern(
    sector="skilled_trades",
    label="Skilled trades and home services",
    unit_noun="service territory",
    layers=[
        SectorLayer(
            suffix="Licensing LLC", role="Licence and qualifier entity", supersedes="licence",
            holds="The contractor licence, the qualifying individual's registration, and "
                  "the bonding relationship",
            why="A contractor licence is usually held by a named qualifying individual and "
                "attaches to one entity in one state. Isolating it means the licence "
                "survives a change in the operating company, and an ownership change does "
                "not silently put the licence in breach."),
        SectorLayer(
            suffix="Fleet LLC", role="Equipment and vehicle entity",
            holds="Trucks, trailers, and major equipment, leased to the operating company",
            why="Vehicles are the largest uninsured-excess exposure a trades business "
                "carries. Owning them apart and leasing them in keeps a catastrophic auto "
                "claim from reaching the operating company's receivables and contracts."),
    ],
    reserved_matters=[
        ("Any change to the licensed qualifying individual, or any action affecting the "
         "contractor licence or bond"),
        "Expanding into a state or trade that requires a new licence or reciprocity filing",
        "Any change to worker classification, or engaging crews as independent contractors",
        "Launching, repricing, or terminating a membership or service-plan programme",
    ],
    failure_modes=[
        ("The licence walks out with the qualifier",
         ("The licence is held by one named individual. That person leaves, is disqualified, "
          "or dies — and the company cannot legally pull a permit until a replacement "
          "qualifier is registered, which takes months.")),
        ("A truck ends the company",
         ("One at-fault accident with an injury exceeds the auto policy, and the judgment "
          "reaches an operating entity that holds every contract and every receivable.")),
        ("Misclassification, retroactively",
         ("Crews were paid as 1099 contractors. A state audit reclassifies them, and the "
          "assessment covers back payroll tax, penalties, and interest for every worker for "
          "every year still open.")),
        ("Memberships sold, service never funded",
         ("Prepaid maintenance plans were spent as revenue. The obligation to perform sits "
          "on the balance sheet as deferred revenue and nobody reserved against it.")),
    ],
    open_questions=[
        ("Who is the licensed qualifying individual, and what happens if that person leaves?",
         ("In most states the licence is theirs, not the company's, and the company cannot "
          "operate without one."),
         ("The licence entity, the succession plan, and any employment agreement with the "
          "qualifier.")),
        (("Are field crews W-2 employees or 1099 contractors, and does that classification "
          "survive the state's own test?"),
         ("Reclassification is retroactive and the assessment compounds across every open "
          "year."),
         "Payroll structure, the operating budget, and the reps in any sale."),
        (("Is there a membership or service-plan programme, and is the unearned portion "
          "reserved?"),
         ("Prepaid service is a liability that looks like revenue until someone calls for the "
          "service."),
         "The financial model and any capital raise."),
    ],
    positions=[
        ("Licence isolation",
         ("Hold the contractor licence and the qualifying individual's registration in an "
          "entity that holds nothing else, and paper the qualifier relationship in writing."),
         ("The licence is the permission to exist. It should not be exposed to a customer "
          "dispute, and its continuity should not depend on an unwritten understanding with "
          "one person.")),
        ("Fleet separation",
         ("Own vehicles and major equipment in a separate entity and lease them to the "
          "operating company at a market rate."),
         ("It is the single largest catastrophic exposure in the trades, and it is the "
          "cheapest one to wall off.")),
        ("Succession",
         ("Name a second qualifying individual, or a written plan to register one, before it "
          "is needed."),
         ("The gap between losing a qualifier and registering a replacement is measured in "
          "months, and the company cannot pull permits in the meantime.")),
    ],
    counsel_notes=[
        ("Confirm the contractor-licensing rules in every state of operation — whether the "
         "licence follows the entity or the individual, what an ownership change triggers, "
         "and whether reciprocity applies."),
        ("Confirm worker classification against the governing state's test, not the federal "
         "one; several states apply a materially stricter standard."),
    ],
)

HOSPITALITY = SectorPattern(
    sector="hospitality",
    label="Hospitality and consumer concepts",
    unit_noun="location",
    layers=[
        SectorLayer(
            suffix="Brand LLC", role="Brand and recipe entity", supersedes="ip",
            holds="Trademarks, recipes, operating manuals, and the licence out to each "
                  "location",
            why="The brand is what makes the second location worth more than the first, and "
                "it is what a franchise or licensing programme is eventually built on. "
                "Holding it apart means one location's failure does not encumber the name."),
        SectorLayer(
            suffix="Location LLC", role="Location operating entity", per_unit=True,
            holds="One site: the lease, the staff, the equipment, and the local permits",
            why="Restaurants fail one at a time. One entity per location means a closure, a "
                "personal-injury claim, or a landlord's remedy is contained to that site, "
                "and it means a location can be sold or a partner brought in at one address "
                "without touching the rest."),
        SectorLayer(
            suffix="Beverage LLC", role="Liquor licence entity", supersedes="licence",
            holds="The liquor licence and nothing else of value",
            why="A liquor licence is issued to a named entity at a named premises, is "
                "frequently non-transferable, and can be suspended by a commission rather "
                "than a court. It should not sit in the entity that also holds the lease and "
                "the equipment."),
    ],
    reserved_matters=[
        "Signing, assigning, or terminating a premises lease, or exercising a renewal option",
        "Any application for, transfer of, or action affecting a liquor licence",
        "Opening a new location, or committing to a site",
        "Granting any franchise, licence, or territory right in the brand",
        "Any personal guarantee of a lease or equipment financing",
    ],
    failure_modes=[
        ("The personal guarantee outlives the restaurant",
         ("The landlord required a personal guarantee. The location closes, the entity is "
          "wound up, and the guarantee follows the owner personally for the balance of a "
          "ten-year term.")),
        ("One bad location takes the brand",
         ("Everything ran through one company, so a judgment at the failing site reaches the "
          "trademark, the recipes, and the profitable locations.")),
        ("The licence cannot move",
         ("The concept relocates or restructures and the liquor licence does not come with "
          "it, because it was issued to a specific entity at a specific address.")),
    ],
    open_questions=[
        ("Is a personal guarantee required on any lease, and is it capped or burn-off?",
         ("An uncapped personal guarantee is usually the largest single risk an owner "
          "carries, and it is negotiable far more often than owners assume."),
         "The lease, and any statement of the owner's personal exposure."),
        (("Does the liquor licence transfer on a change of ownership, and what approval does "
          "that require?"),
         ("In most states it does not transfer freely, and the timeline for a new licence can "
          "outlast a purchase agreement."),
         "The licence entity, and any transfer or sale provision."),
        ("Is franchising or licensing a real intention within the hold period?",
         ("If so, the brand entity, the operating manual, and the quality-control provisions "
          "have to exist before the first licence is granted, not after."),
         "The brand entity and the intellectual property provisions."),
    ],
    positions=[
        ("One entity per location",
         ("Each site sits in its own operating entity under the HoldCo, with the brand "
          "licensed in."),
         ("Restaurants fail one at a time and are sold one at a time. The structure should "
          "let them do both without disturbing the rest.")),
        ("Brand held apart",
         ("Trademarks, recipes, and manuals sit in a brand entity and are licensed to each "
          "location on written terms."),
         ("It is what makes the concept worth more than the sum of the leases, and it is the "
          "foundation of any future franchising.")),
        ("Guarantee discipline",
         ("Treat any personal guarantee as a reserved matter, and negotiate a cap or a "
          "burn-off before signing."),
         ("It is the one obligation that survives the entity, and owners routinely sign it "
          "without pricing it.")),
    ],
    counsel_notes=[
        ("Confirm the liquor authority's rules on entity ownership, transfer, and change of "
         "control in the governing state before the structure is filed."),
        ("Any franchising intention triggers a separate disclosure regime — confirm with "
         "franchise counsel before the first licence is granted."),
    ],
)

SECTOR_PATTERNS: dict[str, SectorPattern] = {
    pattern.sector: pattern for pattern in (FILM, SKILLED_TRADES, HOSPITALITY)}


# --- regulated regimes ------------------------------------------------------

class RegimePattern(BaseModel):
    """What a specific licensing regime adds, beyond "it is regulated"."""

    regime: str
    label: str
    isolate_licence: bool = True
    reserved_matters: list[str] = Field(default_factory=list)
    positions: list[tuple[str, str, str]] = Field(default_factory=list)
    open_questions: list[tuple[str, str, str]] = Field(default_factory=list)
    counsel_notes: list[str] = Field(default_factory=list)


CANNABIS = RegimePattern(
    regime="cannabis",
    label="Adult-use or medical cannabis",
    reserved_matters=[
        ("Admitting any owner who would require disclosure, background check, or residency "
         "qualification under the cannabis regime"),
        ("Any transaction that would constitute a change of control requiring prior "
         "regulatory approval"),
    ],
    positions=[
        ("Ownership eligibility",
         ("Condition every transfer, issuance, and admission on the transferee first "
          "satisfying the regulator's disclosure, background, and residency requirements."),
         ("The regulator decides who may own this business, whatever the operating agreement "
          "says. Writing the condition in means a transfer cannot accidentally put the "
          "licence in breach.")),
        ("Banking and cash",
         ("Assume limited banking access and structure treasury, payroll, and distributions "
          "accordingly."),
         ("Cash-intensive operations change the controls the governance has to impose — dual "
          "authorisation, reconciliation cadence, and physical security are governance "
          "questions here, not just operational ones.")),
        ("Tax exposure",
         ("Model the entity's tax position separately from its economics, and confirm the "
          "treatment with a tax advisor who works in this industry."),
         ("Federal tax treatment of a plant-touching business differs materially from any "
          "other operating company, and it changes what is actually distributable.")),
    ],
    open_questions=[
        ("Which entity in the structure is plant-touching, and which is not?",
         ("The distinction drives the tax position, the banking relationship, and which "
          "entities the regulator has any interest in at all."),
         "The entity chart, the tax recommendation, and the treasury plan."),
        ("What ownership percentage triggers disclosure or a background check in this state?",
         ("It sets a hard ceiling on who can be admitted and on how small a passive stake can "
          "usefully be."),
         "The cap table and the transfer provisions."),
    ],
    counsel_notes=[
        ("Cannabis regulatory counsel in the licensing state confirms ownership disclosure "
         "thresholds, change-of-control triggers, and whether the proposed structure is "
         "permitted at all before anything is filed."),
        ("A tax advisor experienced with plant-touching businesses confirms the federal "
         "position before any distribution policy is adopted."),
    ],
)

HEMP = RegimePattern(
    regime="hemp",
    label="Hemp and hemp-derived products",
    isolate_licence=True,
    reserved_matters=[
        ("Any change to the product formulation, THC testing protocol, or certificate-of-"
         "analysis provider"),
        "Entering any state where the product's legal status differs from the home state",
    ],
    positions=[
        ("Testing and documentation chain",
         ("Treat the testing protocol and certificate-of-analysis chain as a governance "
          "matter, with a named responsible person and a reserved matter over changing it."),
         ("Compliance here is a documentation problem rather than a licensing one. The "
          "records are what stand between a product and a seizure, and they are produced by "
          "operations, so governance has to reach them.")),
        ("State-by-state divergence",
         ("Map the product's legal status in every state of sale before structuring "
          "distribution, and keep the entity that ships separate from the entity that "
          "manufactures."),
         ("Hemp's federal position and its state positions are not the same thing, and they "
          "move. Separating manufacture from distribution keeps a single state's action from "
          "reaching production.")),
    ],
    open_questions=[
        (("What is the THC threshold and testing methodology the product is tested against, "
          "and by whom?"),
         ("It determines whether the product is hemp or a controlled substance, and the "
          "answer varies by state and by test method."),
         "The compliance plan and any distribution agreement."),
        ("In which states will the product actually be sold or shipped?",
         "Several states restrict or ban hemp-derived products that are lawful federally.",
         "The distribution structure and the risk disclosure to investors."),
    ],
    counsel_notes=[
        ("Confirm the current federal and state position for this specific product class — "
         "hemp regulation has moved repeatedly and a structure built on last year's position "
         "may be wrong."),
    ],
)

LIQUOR = RegimePattern(
    regime="liquor",
    label="Alcoholic beverage licence",
    reserved_matters=[
        "Any application for, transfer of, or action affecting a liquor licence",
        "Any change of ownership requiring notice to or approval from the beverage authority",
    ],
    positions=[
        ("Licence entity",
         ("Hold the licence in an entity that holds nothing else, and treat any change of "
          "ownership as conditional on the authority's prior approval."),
         ("A liquor licence is issued to a named entity at a named premises and is suspended "
          "by a commission rather than a court. It should carry no other assets.")),
    ],
    open_questions=[
        (("Does this state permit the licence to transfer with a change of entity ownership, "
          "and how long does approval take?"),
         ("The approval timeline frequently outlasts a purchase agreement and has to be built "
          "into the closing conditions."),
         "The transfer provisions and any sale timeline."),
    ],
    counsel_notes=[
        ("Beverage-licensing counsel confirms the ownership and transfer rules in the "
         "licensing state before the structure is filed."),
    ],
)

CONTRACTOR = RegimePattern(
    regime="contractor_licensing",
    label="Contractor and trade licensing",
    reserved_matters=[
        ("Any change to the licensed qualifying individual, or any action affecting the "
         "licence or bond"),
    ],
    positions=[
        ("Qualifier continuity",
         ("Paper the relationship with the qualifying individual, and register a second "
          "qualifier before one is needed."),
         ("The licence usually belongs to a person rather than to the company. Losing that "
          "person stops permits until a replacement is registered.")),
    ],
    open_questions=[
        ("Does the licence follow the entity or the individual in each state of operation?",
         ("It determines whether an ownership change, a reorganisation, or a departure puts "
          "the company out of compliance."),
         "The licence entity and the succession plan."),
    ],
    counsel_notes=[
        ("Confirm licensing and reciprocity in every state of operation before the entity "
         "chart is finalised."),
    ],
)

REGIME_PATTERNS: dict[str, RegimePattern] = {
    pattern.regime: pattern
    for pattern in (CANNABIS, HEMP, LIQUOR, CONTRACTOR)}


def pattern_for(activity: str) -> SectorPattern | None:
    return SECTOR_PATTERNS.get(activity)


def regime_for(regime: str | None) -> RegimePattern | None:
    """Match a regime name loosely, so "adult-use cannabis" finds the cannabis pattern."""
    if not regime:
        return None
    key = regime.strip().lower().replace(" ", "_")
    if key in REGIME_PATTERNS:
        return REGIME_PATTERNS[key]
    for name, pattern in REGIME_PATTERNS.items():
        if name in key or key in name:
            return pattern
    return None
