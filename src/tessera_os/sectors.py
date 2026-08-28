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

REAL_ESTATE_HOLD = SectorPattern(
    sector="real_estate_hold",
    label="Real estate holding and income property",
    unit_noun="property",
    layers=[
        SectorLayer(
            suffix="Property Management LLC", role="Property management entity",
            holds="Management contracts with each property-owning entity, the leasing and "
                  "maintenance relationship, and vendor and staff agreements",
            why="Management and ownership are different jobs with different liability. A "
                "leasing dispute, a vendor claim, or an employment claim at the management "
                "level should not put title to the real estate at risk, and a manager can be "
                "replaced without touching who owns the property."),
    ],
    reserved_matters=[
        ("Refinancing, extending, or modifying any loan secured by real property, or agreeing "
         "to any lender covenant"),
        "Any transaction between a property-owning entity and the property manager or its affiliate",
        "Selling, exchanging, or contributing any property, including any like-kind exchange",
        ("Admitting or removing any independent manager or springing member a lender requires "
         "as a condition of its loan"),
    ],
    failure_modes=[
        ("Title held in the wrong name",
         ("The deed, the insurance policy, and the loan documents were never checked against "
          "each other after a restructuring, and a lender refuses to close -- or a claim goes "
          "unanswered -- because the entity on title is not the entity anyone thought owned "
          "the property.")),
        ("One claim reaches every property",
         ("Two properties were left in the same entity to save a filing fee, and a judgment "
          "or an environmental claim against one reaches the other along with it.")),
        ("The operating agreement loses to the loan documents",
         ("The operating agreement was drafted without reading the loan documents, and on the "
          "point where they conflict -- transfers, distributions, additional debt -- the loan "
          "documents win, because the lender is a third party who never agreed to the "
          "operating agreement's terms.")),
        ("Insurance named an entity that no longer exists",
         ("The entity was renamed or restructured and nobody told the carrier; a claim is "
          "denied because the named insured is not the entity that actually holds title.")),
    ],
    open_questions=[
        (("Is there debt on this property, and does the lender require a single-purpose "
          "entity with an independent manager or springing member?"),
         ("SPE requirements are non-negotiable loan covenants, not preferences, and violating "
          "one can be a default independent of whether a payment was ever missed."),
         "The entity's governing documents and the loan's SPE covenant."),
        ("Is each property held for income or for eventual sale?",
         ("It changes the tax treatment, the hold entity's structure, and whether like-kind "
          "exchange treatment is available on disposition."),
         "Tax treatment and the exit architecture."),
        ("Who signs the carve-out guaranty, and has that person actually read the carve-out events?",
         ("A \"non-recourse\" loan is rarely fully non-recourse -- the carve-outs (fraud, "
          "waste, an unauthorized transfer, a bankruptcy filing) turn it personal, and the "
          "guarantor is often the last person to read them."),
         "The loan documents and the guarantor's own independent advice."),
        ("Do title, the insurance policy, and the entity's legal name all match exactly?",
         "A mismatch is usually invisible until a claim or a closing, at which point it stops one.",
         "Title, insurance, and any pending financing or sale."),
    ],
    positions=[
        ("Property management separated from ownership",
         ("Hold management contracts, leasing, and vendor relationships in a management "
          "entity distinct from the entities that hold title."),
         ("Management is where the operational claims arise. Keeping it apart means a vendor "
          "dispute or an employment claim at the management level cannot reach title to the "
          "real estate.")),
        ("One entity per property",
         "Title to each property sits in its own entity, financed and insured on its own.",
         ("Isolation is only real if the properties are not pooled -- a lender lending "
          "against one property does not want its collateral cross-defaulted with an asset "
          "it never underwrote.")),
        ("SPE covenants are non-negotiable",
         ("Treat any lender's single-purpose-entity and independent-manager requirements as "
          "fixed inputs to the governing documents, not points to negotiate around."),
         ("Violating an SPE covenant can itself be an event of default, independent of "
          "whether a payment was ever missed.")),
    ],
    counsel_notes=[
        ("Real estate counsel in the property's state confirms title, entity-name, and "
         "insured-name consistency before closing, and reviews the loan documents' SPE and "
         "transfer covenants against the operating agreement for conflicts."),
        ("Confirm like-kind exchange eligibility and timing with a qualified intermediary "
         "before structuring any disposition intended to be tax-deferred."),
    ],
)

DEVELOPMENT = SectorPattern(
    sector="development",
    label="Ground-up and value-add development",
    unit_noun="project",
    layers=[
        SectorLayer(
            suffix="Development LLC", role="Development entity", per_unit=True,
            holds="Entitlements, the construction contract and design-professional "
                  "agreements, the construction loan, and the risk of construction until "
                  "completion or stabilization",
            why="Construction is the highest-risk period in the asset's life, and the "
                "contractor and design-professional relationship is where most disputes "
                "start. Isolating it in its own entity means a construction claim, a "
                "mechanic's lien, or a contractor dispute on one project does not reach a "
                "completed, stabilized asset or the next project in the pipeline."),
    ],
    reserved_matters=[
        ("Executing or materially amending the construction contract, or approving any change "
         "order above the ordinary-course threshold"),
        "Any transaction with the general contractor, a design professional, or a principal's affiliate",
        ("Refinancing the construction loan with permanent debt, or transferring the "
         "completed asset to a hold entity"),
        "Settling or commencing any claim against the contractor or design professional, or any lien claim",
    ],
    failure_modes=[
        ("The permanent loan inherits construction liability",
         ("The completed asset was transferred to a hold entity without a clean release, and "
          "a latent construction defect claim reaches the asset in the new owner's hands "
          "along with the debt that financed it.")),
        ("A change order signed by the wrong person",
         ("A superintendent or a principal without authority approved a change order that "
          "blew the budget or the schedule, because the reserved-matter threshold that should "
          "have caught it was never checked against actual field practice.")),
        ("Dissolved before the statute of repose has run",
         ("The development entity was dissolved at completion to save on franchise fees, and "
          "a defect claim filed years later -- still within the statute of repose -- has no "
          "solvent entity or insurance tail to answer it.")),
        ("Liens stack faster than draws release",
         ("A subcontractor was not paid on schedule and filed a lien; the title company would "
          "not release the next construction draw until it was bonded off, stalling the "
          "project.")),
    ],
    open_questions=[
        (("What is the statute of repose for construction claims in this state, and will the "
          "entity survive it or is there a tail policy?"),
         ("A defect claim can arrive years after completion; a development entity dissolved "
          "too early has nothing left to answer it with."),
         "The entity's dissolution timing and any insurance placed at completion."),
        (("What triggers the transfer from the development entity to the eventual hold "
          "entity -- a sale, a merger, or a distribution?"),
         ("Each has different tax consequences and a different effect on the construction "
          "lender's security and any warranty claims that are supposed to survive the "
          "transfer."),
         "Tax treatment, permanent financing, and any warranty assignment."),
        (("Who has authority to approve a change order, and at what dollar threshold does it "
          "require more than one signature?"),
         ("Field authority routinely exceeds what the governing documents actually grant, "
          "and that gap is where budget overruns start."),
         "The reserved-matter list and the construction contract's change-order provision."),
        ("Is the general contractor bonded, and does the construction lender require it?",
         ("An unbonded contractor's failure mid-project can stall completion and expose the "
          "project to lien claims with no recourse."),
         "The construction contract and the construction loan's conditions."),
    ],
    positions=[
        ("Development held apart from the hold entity",
         ("The project is developed in its own entity, separate from whatever entity "
          "eventually holds the stabilized asset."),
         ("Construction risk and permanent-hold risk are different risks with different "
          "insurance, different lenders, and different timelines; collapsing them into one "
          "entity means a construction dispute can reach an asset that has nothing to do "
          "with it.")),
        ("Change orders are a reserved matter above the threshold",
         "Any change order above the ordinary-course threshold requires the same consent as any other reserved matter.",
         ("Budget overruns on development projects are overwhelmingly a story of change "
          "orders nobody with real authority approved.")),
        ("Dissolution timed to the statute of repose, not to the closing",
         ("Keep the development entity in existence, or place a tail policy, through the "
          "state's statute of repose for construction claims."),
         "A claim filed within the statute needs someone or something solvent to answer it."),
    ],
    counsel_notes=[
        ("Construction counsel confirms lien and bonding requirements in the project's state, "
         "and reviews the construction contract's change-order and dispute provisions before "
         "execution."),
        ("Confirm the statute of repose in the project's state and coordinate dissolution "
         "timing and tail coverage with insurance counsel -- this pattern states the risk, "
         "not the number of years."),
    ],
)

FUND = SectorPattern(
    sector="fund",
    label="Pooled investment fund",
    unit_noun="fund",
    layers=[
        SectorLayer(
            suffix="Fund LLC", role="Fund entity", per_unit=True,
            holds="Investor capital commitments, the investment portfolio, and the "
                  "obligation to return capital and profit according to the fund documents",
            why="The fund is the vehicle investors actually commit capital to. Keeping it "
                "distinct from the entity that manages it and the entity that earns carried "
                "interest is what lets each be capitalized, taxed, and made liable on its "
                "own terms, and what lets a new fund vintage be raised without touching the "
                "one before it."),
        SectorLayer(
            suffix="GP LLC", role="General partner entity",
            holds="The general partner interest in each fund, and the fiduciary and "
                  "management authority over fund-level decisions",
            why="The general partner carries fiduciary exposure that should not sit inside "
                "the fund itself or inside the entity that earns the management fee -- a "
                "claim against the general partner's conduct should not automatically reach "
                "fee income, and a dispute over fee income should not automatically reach "
                "the fiduciary relationship with investors."),
        SectorLayer(
            suffix="Management Company LLC", role="Management company",
            holds="The management agreement with each fund, the management fee, employees, "
                  "and operating overhead",
            why="Carried interest and management-fee income are taxed differently and should "
                "not be earned by the same entity or booked through the same set of books -- "
                "collapsing them is how a fund's economics become impossible to audit and how "
                "carry risks being taxed as ordinary income by mistake."),
    ],
    reserved_matters=[
        ("Admitting a new limited partner, or accepting any capital commitment on terms "
         "different from the fund's governing documents"),
        "Declaring a capital call, or invoking any default remedy against a limited partner who fails to fund",
        "Any investment above the fund's stated concentration or diversification limits",
        ("Removing the general partner, or any transaction between the fund and the general "
         "partner, the management company, or an affiliate"),
    ],
    failure_modes=[
        ("Carried interest earned by the wrong entity",
         ("Carry was paid to or booked through the management company rather than the "
          "general partner, and what should have been capital-gain-eligible carried interest "
          "is taxed as ordinary management-fee income instead.")),
        ("A default remedy nobody can actually enforce",
         ("A limited partner missed a capital call and the fund documents named a remedy -- "
          "dilution, forfeiture -- that was never tested against the state's actual "
          "enforceability rules for that kind of penalty.")),
        ("Portfolio-company governance leaking into fund governance",
         ("A portfolio company's day-to-day decision was treated as a fund-level reserved "
          "matter, or vice versa, and neither the fund's investors nor the portfolio "
          "company's other stakeholders could tell who actually had authority over what.")),
        ("An offering that exceeded its own exemption",
         ("Interests were sold to more investors, or to investors who did not meet the "
          "exemption's requirements, than the offering exemption the fund was relying on "
          "actually permits.")),
    ],
    open_questions=[
        (("Is the offering relying on Regulation D, and has the investor base been checked "
          "against that exemption's accredited-investor and counting requirements?"),
         ("The exemption is what makes the offering lawful at all; exceeding its limits or "
          "admitting an ineligible investor can taint the whole offering."),
         "The private placement memorandum and subscription documents -- securities counsel's work."),
        ("What is the carried interest percentage, the hurdle rate, and does the general partner invest alongside the limited partners?",
         ("These terms decide whether the general partner's incentives actually align with "
          "the fund's investors, and they are heavily negotiated market terms this engine "
          "does not set."),
         "The fund's economics and the limited partnership agreement."),
        ("Is the management company also providing services to portfolio companies, and are those fees offset against the management fee?",
         ("Fee offsets are a major, heavily negotiated limited-partner protection, and "
          "getting the mechanics wrong changes what investors actually net."),
         "The management agreement and the fee provisions in the fund's governing documents."),
        ("Could the fund's investor base trigger ERISA plan-asset rules?",
         ("If pension-plan money exceeds the relevant threshold, the fund and its manager "
          "can become subject to ERISA fiduciary duties the structure was not built around."),
         "The offering structure and any ERISA counsel review."),
    ],
    positions=[
        ("Three entities, three purposes",
         ("The fund, the general partner, and the management company are three separate "
          "entities, each earning and risking only what belongs to its own role."),
         ("Carried interest, management fees, and fiduciary exposure are taxed and litigated "
          "differently. Collapsing the entities collapses the distinctions that make each of "
          "those work correctly.")),
        ("Reserved matters separate fund governance from portfolio governance",
         ("The fund's own reserved-matter list governs decisions about the fund and its "
          "investors; it does not reach into how a portfolio company runs its own business."),
         ("A fund whose governance cannot tell the two apart cannot tell its investors, or a "
          "portfolio company's other stakeholders, who actually has authority over what.")),
        ("Securities counsel frames every commercial term",
         "This pattern names the questions -- the exemption, the carry, the hurdle, the fee offset -- without answering any of them.",
         ("Answering them here would be legal advice dressed as a structuring pattern, in "
          "the one area of this engine's work where that mistake is least excusable.")),
    ],
    counsel_notes=[
        ("Securities counsel confirms the offering exemption, investor eligibility, and every "
         "disclosure document before a single dollar is raised -- nothing in this pattern "
         "substitutes for that review."),
        ("Tax counsel confirms the carried interest structure and its treatment before the "
         "fund documents are finalized; the difference between capital gain and ordinary "
         "income here is not a drafting nicety."),
        "ERISA counsel reviews the offering if plan-asset money is expected to approach the regulatory threshold.",
    ],
)

IP_LICENSING = SectorPattern(
    sector="ip_licensing",
    label="Intellectual property licensing",
    unit_noun="licence line",
    layers=[
        SectorLayer(
            suffix="IP Holdings LLC", role="IP portfolio entity", supersedes="ip",
            holds="Patents, trademarks, copyrights, trade secrets, and the licence "
                  "agreements granting rights to use them",
            why="The intangibles are usually the durable, saleable asset, and the entity "
                "that owns them should not be exposed to an operating dispute, a "
                "product-liability claim, or an operating company's own creditors."),
        SectorLayer(
            suffix="Licensing LLC", role="Licensing and royalty administration entity",
            holds="Licence negotiations, royalty collection and audit rights, and the "
                  "day-to-day licensing relationships with licensees",
            why="Negotiating deals, chasing royalty payments, and running audits is an "
                "operating function with its own disputes and counterparties. Keeping it "
                "apart from the entity that owns the underlying IP means a licensing "
                "dispute cannot put the underlying asset at risk, and the IP can be "
                "relicensed or sold without unwinding the operating relationships built "
                "around it."),
    ],
    reserved_matters=[
        "Granting an exclusive licence, or any licence extending beyond the ordinary-course term",
        "Assigning, encumbering, or abandoning any patent, trademark, or copyright registration",
        "Settling or commencing any infringement claim, whether as plaintiff or defendant",
        "Any change to a licence's royalty rate, audit rights, or change-of-control provision",
    ],
    failure_modes=[
        ("Improvements vest in the wrong entity",
         ("The operating entity built improvements or derivative works on licensed-in IP, "
          "and the licence agreement was silent on who owns them -- so the improvements sit "
          "with whichever entity happened to build them rather than with the entity that "
          "should hold all the IP.")),
        ("A licence that dies on change of control",
         ("A key licence terminates or requires consent on a change of control, and nobody "
          "found the clause until a buyer's diligence team did -- at which point it becomes "
          "a condition to closing rather than a known, priced-in fact.")),
        ("No audit rights, no way to know if royalties are right",
         ("Royalty agreements were signed without an audit right, and the licensor has no "
          "way to verify a licensee's self-reported sales are accurate.")),
        ("The licence stream was valued as if it were the asset",
         ("The business was built and financed around a licence-in relationship rather than "
          "owned IP, and the licence itself -- not any asset behind it -- turned out to be "
          "exactly what could be revoked or not renewed.")),
    ],
    open_questions=[
        ("Is the value in the IP itself, or in a licence to someone else's IP?",
         ("A licensee's business is only as durable as the licence, and its term, renewal, "
          "and termination provisions deserve the same scrutiny as an owned asset would."),
         "The entity chart and every valuation or financing built on the licensing relationship."),
        ("Do any licence agreements terminate or require consent on a change of control?",
         ("It is discovered most often during diligence on a sale, at which point it is a "
          "closing condition instead of a known, priced-in fact."),
         "Any sale, financing, or restructuring, and the transfer provisions in the operating agreement."),
        ("Does the company have audit rights over licensees' royalty reporting, and has it ever exercised them?",
         "Self-reported royalties without a tested audit right are effectively unverified revenue.",
         "The licensing entity's revenue recognition and any royalty dispute."),
        ("Who owns improvements or derivative works created using licensed-in IP?",
         "Silence in the licence agreement does not mean the answer is favorable -- it means the answer is unresolved.",
         "The licence agreement and the IP holding entity's asset schedule."),
    ],
    positions=[
        ("Holding separated from licensing administration",
         ("Own the underlying IP in a holding entity, and run licence negotiation, royalty "
          "collection, and audits through a separate licensing entity."),
         ("One is a passive asset with no operating counterparties; the other has disputes, "
          "deadlines, and people. Mixing them exposes the asset to disputes that have "
          "nothing to do with owning it.")),
        ("Change-of-control provisions inventoried, not assumed",
         ("Every material licence -- in or out -- is reviewed for change-of-control and "
          "assignment restrictions before any transaction is priced."),
         "A licence that dies on a sale has to be priced into the deal, not discovered by the buyer's counsel first."),
        ("Audit rights as a standard term, not an afterthought",
         "Every licence-out agreement includes a royalty audit right, exercised on a regular schedule.",
         "Unverified self-reported royalties are effectively unverified revenue."),
    ],
    counsel_notes=[
        ("IP counsel confirms chain of title, registration status, and change-of-control "
         "provisions on every material licence before any financing or sale."),
        ("Confirm whether any licensed-in technology carries open-source or field-of-use "
         "restrictions that limit how it can be sublicensed or commercialized."),
    ],
)

PROFESSIONAL_SERVICES = SectorPattern(
    sector="professional_services",
    label="Licensed professional services",
    unit_noun="practice location",
    layers=[
        SectorLayer(
            suffix="Professional PLLC", role="Professional entity",
            holds="The licensed practice, client relationships, and the professional "
                  "services themselves",
            why="Many states require the entity providing licensed professional services to "
                "be owned only by licensed practitioners, organized as a PLLC or PC rather "
                "than an ordinary LLC. Keeping the practice in that entity, and everything "
                "else in entities not subject to that ownership restriction, is what lets "
                "outside capital or non-practitioner owners participate in the business at all."),
        SectorLayer(
            suffix="Management Company LLC", role="Management services entity",
            holds="Non-clinical staff, equipment, real estate, marketing, billing, and the "
                  "management services agreement with the professional entity",
            why="A management company can be owned by anyone, including outside capital, "
                "because it does not provide the licensed service itself -- it provides "
                "administrative and business support to the entity that does. Separating "
                "the two is what makes outside investment in a licensed practice possible "
                "without violating corporate-practice-of-the-profession restrictions."),
    ],
    reserved_matters=[
        ("Admitting or removing any owner of the professional entity, or any transfer of an "
         "ownership interest in it"),
        "Amending the management services agreement, or any fee paid under it",
        ("Any change to the scope of services the management company provides, where that "
         "change could be read as control over clinical or professional judgment"),
        ("Hiring or terminating a licensed practitioner whose departure would trigger a "
         "client-notice or non-solicitation obligation"),
    ],
    failure_modes=[
        ("An owner the licensing board would not allow",
         ("An outside investor was admitted directly into the professional entity, and the "
          "licensing board's ownership restriction -- which does not bend for a good "
          "structure on paper -- puts the licence itself at risk.")),
        ("A fee-splitting violation wearing a management fee's name",
         ("The management company's fee was structured as a percentage of professional "
          "revenue in a state whose fee-splitting rule prohibits exactly that, turning a "
          "management services agreement into an unlawful arrangement.")),
        ("The management company started practicing",
         ("Day-to-day decisions that are supposed to belong to the licensed professionals -- "
          "staffing clinical roles, setting clinical protocols -- were made by the "
          "management company, which is exactly the corporate-practice-of-the-profession "
          "problem the split was built to avoid.")),
        ("A departing owner takes the client relationships with them",
         ("A licensed owner left without a written buyout or non-solicitation mechanism, and "
          "the practice discovered its client relationships were personal to that "
          "practitioner, not to the entity.")),
    ],
    open_questions=[
        ("Does this state require the professional entity to be a PLLC or PC, and who is permitted to own it?",
         "The answer sets a hard ceiling on who may hold equity in the professional entity, regardless of preference.",
         "The entity chart and every proposed owner's licensure."),
        ("Is the management fee structured as a flat or cost-plus fee, or does it vary with professional revenue?",
         ("Many states' fee-splitting rules prohibit a management fee that varies with "
          "revenue from the professional services themselves."),
         "The management services agreement and the fee mechanism."),
        (("What happens to a departing licensed owner's interest, and is there a "
          "non-solicitation or non-compete this state will actually enforce?"),
         ("Professional non-competes are restricted or unenforceable in a number of states, "
          "and the buyout mechanics have to work without relying on one where it will not hold."),
         "The buy-sell provisions and any restrictive covenant."),
        ("Does the management company's authority over hiring, scheduling, or protocols ever reach into clinical or professional judgment?",
         "That line is exactly what separates a lawful management arrangement from an unlawful corporate practice of the profession.",
         "The management services agreement's scope of services."),
    ],
    positions=[
        ("Professional entity and management company kept distinct",
         ("Licensed practice sits in a PLLC or PC owned only by licensed practitioners; "
          "everything else -- staff, equipment, marketing, billing -- sits in a management "
          "company that can be owned by anyone."),
         ("It is what makes outside capital or non-practitioner ownership possible in a "
          "licensed practice without violating corporate-practice-of-the-profession "
          "restrictions.")),
        ("Management fee structured to survive fee-splitting scrutiny",
         ("Fix the management fee as a flat amount or a cost-plus arrangement, not as a "
          "percentage of professional revenue, until counsel confirms this state permits "
          "otherwise."),
         ("A revenue-based management fee is the most common way a management services "
          "agreement becomes an unlawful fee-splitting arrangement.")),
        ("A written departure mechanism for every licensed owner",
         ("Buyout terms, client-notice obligations, and any enforceable restrictive covenant "
          "are documented before a licensed owner joins, not negotiated after one leaves."),
         "A practice's client relationships are often personal to the practitioner until a written mechanism makes them the entity's."),
    ],
    counsel_notes=[
        ("Confirm this state's professional-entity ownership rules, corporate-practice-of-"
         "the-profession doctrine, and fee-splitting rule before structuring any management "
         "company relationship -- these vary significantly by state and by licensed profession."),
        ("Confirm enforceability of any non-compete or non-solicitation against a departing "
         "licensed owner under this state's law before relying on one."),
    ],
)

OPERATING = SectorPattern(
    sector="operating",
    label="General operating business",
    # Deliberately no layers. This is the default when nothing more specific
    # applies (D2/4.7), and `_entity_layers()` treats any sector with a
    # pattern as needing a HoldCo split (`sector is not None`) -- forcing an
    # entity onto every plain operating business, the single most common
    # case, is exactly the padding this phase argues against. See
    # docs/BUILD_BRIEF_PHASE_4_SECTOR_COVERAGE.md D4 and
    # tests/test_sector_coverage.py for why this is a deliberate exception to
    # "every pattern has layers", not an oversight.
    layers=[],
    reserved_matters=[
        ("Entering any customer or vendor contract representing more than a stated share of "
         "revenue or spend"),
        "Adopting, amending, or terminating any employee benefit or equity incentive plan",
        "Reducing insurance coverage below what the business currently carries",
    ],
    failure_modes=[
        ("Customer concentration nobody priced in",
         ("A majority of revenue runs through one or two customers, and losing either is "
          "treated as a normal-course risk rather than the existential one it actually is.")),
        ("Key people with no restrictive covenant and no assignment obligation",
         ("Work product, client relationships, and institutional knowledge walk out with "
          "whoever built them, because nothing in writing assigned the work or restricted "
          "where they could take it.")),
        ("Insurance that quietly stopped matching the business",
         ("Coverage was bound for the business as it existed at formation and never "
          "revisited as it grew, so a claim arrives against exposure the policy was never "
          "priced for.")),
        ("The business outgrew being generic without anyone noticing",
         ("The venture drifted into activity that a licensed trade, a regulated product, or "
          "a real-estate-heavy model actually governs, and it kept being treated as a plain "
          "operating business because nobody re-asked the sector question.")),
    ],
    open_questions=[
        ("What share of revenue or spend runs through the largest customer or vendor, and what is the contract term?",
         "Concentration risk is invisible in a generic operating summary and decisive in a diligence process or a downturn.",
         "The financial model and any representations in a financing or sale."),
        ("Does every employee and contractor have a written work-product assignment and confidentiality agreement?",
         "Without one, work created for the business may legally belong to the person who created it.",
         "The work-product recommendation and any IP diligence."),
        ("When was insurance coverage last reviewed against the business as it actually operates today?",
         "A policy bound at formation rarely matches a business a few years and several employees later.",
         "The risk register and the insurance program."),
        ("Has anything about this business started to look like a licensed trade, a regulated product, or a real-estate-heavy model?",
         ("Sector-specific structuring exists because a generic structure stops being enough "
          "once one of those applies, and the trigger is usually gradual rather than a "
          "single decision."),
         "Whether this recommendation should be re-run under a different activity."),
    ],
    positions=[
        ("Generic by design, not by neglect",
         ("This structure carries the things every operating business needs -- reserved "
          "matters, work-product assignment, insurance discipline -- and nothing "
          "sector-specific, because nothing sector-specific was stated."),
         ("An operating business in a licensed trade, a regulated product, or a "
          "real-estate-heavy model should be routed to the sector that actually governs it, "
          "not left here by default.")),
        ("Customer and vendor concentration is a governance question",
         "Any contract representing an outsized share of revenue or spend is treated as a matter the owners see, not one that clears on ordinary signing authority.",
         "Concentration is where a normal-course business becomes a single-point-of-failure business."),
        ("Work product assigned as a matter of course",
         "Every employee and contractor signs a written assignment and confidentiality agreement before, not after, they start creating anything.",
         "Ownership of what the business is built on should not depend on an unwritten understanding with whoever happened to build it."),
    ],
    counsel_notes=[
        ("This pattern is deliberately generic. If the business's activity is better "
         "described by a specific sector this engine already covers -- real estate, "
         "development, a fund, IP licensing, a licensed profession, film, skilled trades, or "
         "hospitality -- re-run the recommendation under that activity instead of relying on "
         "this one."),
        "Employment counsel confirms restrictive covenant enforceability in the applicable state before relying on any non-compete or non-solicitation.",
    ],
)

SECTOR_PATTERNS: dict[str, SectorPattern] = {
    pattern.sector: pattern for pattern in (
        FILM, SKILLED_TRADES, HOSPITALITY, REAL_ESTATE_HOLD, DEVELOPMENT, FUND, IP_LICENSING,
        PROFESSIONAL_SERVICES, OPERATING)}


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

FOOD_SERVICE = RegimePattern(
    regime="food_service",
    label="Food service and health department permitting",
    reserved_matters=[
        ("Any change to the food service permit, the certified food manager designation, or "
         "a health department's approved menu or process"),
        "Opening a new location or a mode of service (delivery, catering, mobile) not covered by the current permit",
    ],
    positions=[
        ("Permit continuity",
         ("Name a certified food manager for every location and keep the designation current "
          "independent of any single employee's tenure."),
         ("A lapsed or unassigned certification can suspend service at a location with no "
          "warning beyond the inspection that catches it.")),
        ("Inspection and violation tracking",
         ("Track health department inspection results and violation history at the "
          "governance level, not only at the location level."),
         "A pattern of violations across locations is a brand-level risk long before it becomes a single location's crisis."),
    ],
    open_questions=[
        ("Who is the certified food manager at each location, and what happens if that person leaves?",
         ("Some jurisdictions require continuous certified coverage during hours of "
          "operation, and a gap can suspend service."),
         "Location operations and any staffing contingency plan."),
        ("Does the concept include catering, delivery, or a mobile unit not covered by the base permit?",
         "Each mode of service often requires its own permit or endorsement.",
         "The permitting scope and any new-location or new-service rollout."),
    ],
    counsel_notes=[
        ("Confirm health department permitting, certified food manager requirements, and "
         "inspection appeal procedures in every jurisdiction of operation before opening or "
         "adding a mode of service."),
    ],
)

TRANSPORTATION = RegimePattern(
    regime="transportation",
    label="Transportation and DOT operating authority",
    reserved_matters=[
        ("Any action affecting the company's DOT or MC operating authority, including a "
         "change in the designated safety official"),
        ("Adding a vehicle class or a hauling activity (hazmat, passengers, oversized loads) "
         "not covered by current authority or insurance"),
    ],
    positions=[
        ("Authority and insurance matched to the fleet",
         ("Keep operating authority, cargo and liability insurance, and the vehicles "
          "actually in service in sync, and review them together whenever the fleet "
          "changes."),
         ("A vehicle or a hauling activity outside what the authority and insurance actually "
          "cover can void coverage exactly when it is needed.")),
        ("Driver qualification file discipline",
         ("Maintain a complete, current qualification file for every driver, and treat a "
          "lapse as an operational stop, not paperwork to catch up on later."),
         ("A missing or expired qualification file is one of the most common causes of a "
          "fleet being placed out of service during an audit.")),
    ],
    open_questions=[
        ("Does current operating authority and insurance actually cover every vehicle class and hauling activity in use?",
         "A gap here is usually invisible until a claim or a roadside inspection.",
         "The insurance program and the fleet's operating authority."),
        ("Who is the designated safety official, and is the driver qualification file program current for every driver?",
         "An expired or incomplete file is a leading cause of an out-of-service order during a compliance review.",
         "Fleet operations and any DOT audit exposure."),
    ],
    counsel_notes=[
        ("Confirm DOT/MC authority scope, required insurance filings, and driver "
         "qualification requirements with transportation regulatory counsel before adding a "
         "vehicle class or a hauling activity."),
    ],
)

REGIME_PATTERNS: dict[str, RegimePattern] = {
    pattern.regime: pattern
    for pattern in (CANNABIS, HEMP, LIQUOR, CONTRACTOR, FOOD_SERVICE, TRANSPORTATION)}


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
