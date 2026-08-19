# 05 — Sector Patterns

The structuring specific to an industry, and the reasoning behind each piece.

These exist because a film finances one picture at a time and the asset is a
copyright; a trades business lives on a licence held by a named human being and
a fleet of trucks; a restaurant's second location is a different liability
universe from its first, and the liquor licence is the thing that cannot move.
Flattening them into "regulated" or "operating" is how a structure ends up
technically correct and practically useless.

> **Every pattern here is `scaffold`, and none is proposed for adoption.** They
> are informed standard practice, not firm doctrine, and none has been reviewed
> by counsel or by a regulator in any state. Every memo says so.

---

## How a pattern attaches

Selected by `activity` (sector) or `regulated_regime` (regime, matched loosely
so "adult-use cannabis" finds the cannabis pattern). Both can apply at once, and
duplicate reserved matters collapse keeping the first wording.

Each contributes entity layers (with `per_unit` and `supersedes`), reserved
matters, failure modes, open questions, positions, and counsel notes.

`supersedes` matters more than it looks: a film's rights entity **is** the IP
entity, a beverage entity **is** the licence entity. Emitting both would be two
filing fees for one job, and a reader could not tell which one the assets belong
in.

---

## Film and independent media

`film_production` · unit: **production**

| Entity | Per unit | Why |
|---|---|---|
| `{Name} Productions {n} LLC` | One per picture | A picture is financed, insured, and sued on its own. A claim on the last picture cannot reach the next one or the slate — and an investor buys into **one film** rather than everything the producer will ever make |
| `{Name} Rights LLC` (supersedes IP) | No | The library is the durable asset; the production vehicle is where liability sits. Licensing rights in keeps the catalogue out of reach of any single picture's creditors, and saleable without selling the company |

No general OpCo — the per-picture vehicles are the operating entities.

**Reserved:** greenlighting a production or committing to a budget · acquiring,
optioning, or disposing of underlying rights · granting distribution rights ·
any final cut, credit, or approval right to a third party · any completion-bond
obligation.

**Fails as:** *chain of title with a hole in it* (an assignment never signed, a
work-for-hire assumed, an option lapsed — and the picture cannot be delivered,
insured, or sold) · *backend nobody can compute* (participations promised on
different definitions in different documents) · *the last picture takes the next
one*.

**Asks:** is chain of title complete and papered? · are participations defined
on gross, adjusted gross, or net, against one written definition? · will a
collection account manager hold and disburse revenue? · are the guilds involved
and is the production a signatory?

**Counsel:** entertainment counsel confirms chain of title, guild signatory
status, and whether the participation definitions survive scrutiny before any
investor sees them.

---

## Skilled trades and home services

`skilled_trades` · unit: **service territory**

| Entity | Why |
|---|---|
| `{Name} Licensing LLC` (supersedes licence) | A contractor licence is usually held by a named qualifying individual and attaches to one entity in one state. Isolating it means the licence survives a change in the operating company, and an ownership change does not silently put it in breach |
| `{Name} Fleet LLC` | Vehicles are the largest uninsured-excess exposure a trades business carries. Owning them apart and leasing them in keeps a catastrophic auto claim from reaching receivables and contracts |

**Reserved:** any change to the qualifying individual · expanding into a state
requiring a new licence · any change to worker classification · launching,
repricing, or terminating a membership programme.

**Fails as:** *the licence walks out with the qualifier* (permits stop until a
replacement is registered, which takes months) · *a truck ends the company* ·
*misclassification, retroactively* · *memberships sold, service never funded*.

**Asks:** who is the qualifying individual and what happens if they leave? · are
crews W-2 or 1099, and does that survive the **state's own** test? · is the
unearned portion of prepaid service reserved?

**Counsel:** licensing rules in every state of operation — whether the licence
follows the entity or the individual, what an ownership change triggers,
reciprocity. Worker classification against the governing state's test, not the
federal one.

---

## Hospitality and consumer concepts

`hospitality` · unit: **location**

| Entity | Per unit | Why |
|---|---|---|
| `{Name} Brand LLC` (supersedes IP) | No | The brand is what makes the second location worth more than the first, and what franchising is built on |
| `{Name} Location {n} LLC` | One per site | Restaurants fail one at a time. One entity per location contains a closure, an injury claim, or a landlord's remedy — and lets a site be sold without touching the rest |
| `{Name} Beverage LLC` (supersedes licence) | No | A liquor licence is issued to a named entity at a named premises, frequently non-transferable, and suspended by a commission rather than a court |

**Reserved:** signing, assigning, or terminating a lease · any liquor licence
action · opening a new location · granting any franchise or territory right ·
**any personal guarantee**.

**Fails as:** *the personal guarantee outlives the restaurant* (the location
closes, the entity winds up, the guarantee follows the owner for the balance of
a ten-year term) · *one bad location takes the brand* · *the licence cannot
move*.

**Asks:** is a personal guarantee required, and is it capped or burn-off? · does
the liquor licence transfer on a change of ownership, and how long does approval
take? · is franchising a real intention within the hold period?

**Counsel:** the liquor authority's rules on ownership, transfer, and change of
control. Any franchising intention triggers a separate disclosure regime.

---

## Regulated regimes

### Cannabis
Ownership eligibility (condition every transfer on the transferee satisfying
disclosure, background, and residency requirements) · banking and cash (assume
limited banking; dual authorisation and reconciliation cadence become
*governance* questions) · tax exposure modelled separately from economics.

**Asks:** which entity is plant-touching and which is not? · what ownership
percentage triggers disclosure?

### Hemp — deliberately not the same as cannabis
Cannabis is a **licensing** problem: a regulator decides who may own the
business. Hemp is a **documentation** problem: the testing protocol and
certificate-of-analysis chain are what stand between a product and a seizure,
and they are produced by operations, so governance has to reach them.

**Asks:** what THC threshold and method, tested by whom? · in which states will
it actually be sold?

**Counsel:** confirm the *current* position for this product class. Hemp
regulation has moved repeatedly and a structure built on last year's position
may be wrong.

### Liquor
Licence entity holding nothing else, with ownership change conditional on prior
approval. **Asks:** does the licence transfer, and how long does approval take —
the timeline frequently outlasts a purchase agreement.

### Contractor licensing
Qualifier continuity: paper the relationship and register a second qualifier
before one is needed. **Asks:** does the licence follow the entity or the
individual in each state?

---

## Adding a sector

`sectors.py` is pure data. Define a `SectorPattern`, register it, add the
activity to both literals, and add a test. Two generic tests already sweep every
registered pattern — completeness, and that it produces a readable memo — so a
new pattern is covered the moment it is registered.

Set `supersedes` on any layer that replaces a general-rule entity, and
`per_unit` on any that should exist once per production, location, or asset.

**Do not add sectors speculatively.** Add one when an engagement needs it.
