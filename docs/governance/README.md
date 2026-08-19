# Entity Structuring and Governance — Documentation Set

The structuring capability in Tessera OS: an engine that takes a founder's facts
and returns an entity architecture, the control and exit terms that go with it,
the alternatives it rejected, and the questions nobody can answer yet — then
hands that straight to the clause library so the operating agreement that comes
out is the one the memo actually called for. Plus the other half of the
practice: reading an agreement that already exists and saying what it lacks.

| # | Document | Written for | Read it when |
|---|---|---|---|
| 00 | [Console sequence](00_CONSOLE_SEQUENCE.md) | Operators | You are running a recommendation through the API and need the gate order |
| 01 | [Architecture](01_ARCHITECTURE.md) | Codex, or a future engineer | You need to know what calls what, and where a change belongs |
| 02 | [Decision rules](02_DECISION_RULES.md) | **Derrick** | You want to argue with a threshold. Every rule, its trigger, and why |
| 03 | [Provenance ledger](03_PROVENANCE.md) | Derrick and Ryan | How a starting point becomes a Tessera position, and what is signed today |
| 04 | [Counsel packet](04_COUNSEL_PACKET.md) | Outside counsel | You are sending this out. Organised by question, not by clause |
| 05 | [Sector patterns](05_SECTOR_PATTERNS.md) | Derrick, sector counsel | Film, trades, hospitality, cannabis, hemp, liquor, contractor licensing |
| 06 | [Capital architecture](06_CAPITAL_ARCHITECTURE.md) | **Ryan** | The waterfall frame, and what the engine deliberately does not decide |
| 07 | [Operator guide](07_OPERATOR_GUIDE.md) | Derrick and Ryan | You are about to run this live. Includes the intake questionnaire |
| 08 | [Roadmap](08_ROADMAP.md) | Derrick | You are deciding what to build next |
| 09 | [Decision packet](09_DECISION_PACKET.md) | **Derrick + Ryan**, then counsel | Every open decision pre-drafted, with the ledger entry to paste. **Start here** |
| 10 | [Write-back spec](10_SHAREPOINT_WRITEBACK_SPEC.md) | Derrick and Codex | Before anyone asks to turn SharePoint writes on |

---

## Where this sits in the engagement

The Focus page describes four stages: **Diagnose → Architect → Capitalize →
Execute.**

```
Diagnose              Architect                 Capitalize          Execute
────────────          ─────────────────         ──────────────      ──────────────
intake.py             VentureProfile            CapitalArchitecture formation.py
 → cited profile       → StructureRecommendation  → waterfall frame   → filing order
   proposal              · entity topology        · tiers             · gates
diagnosis.py           · options menu            · protections        · dependencies
 → existing            · control + exit          · open points
   agreement screen    · failure modes                               digest.py
                       · conflicts                                    → what's waiting
                       → operating agreement
                       → branded DOCX
```

Every stage now has something in it. Capitalize is a frame rather than a model —
that boundary is deliberate and is explained in [06](06_CAPITAL_ARCHITECTURE.md).

---

## The three rules everything obeys

**Nothing is invented.** Every position carries a `basis`. `tessera_adopted`
means both partners signed it in `config/adopted_positions.yaml`, citing the
source by reference rather than reproducing its text. `synthetic_reference`
means it came from the offline evaluation fixture. `scaffold` means nobody has
adopted it — and the memo says so, under "Positions not yet adopted." **The
ledger ships empty**, so until the partners sign, the system claims no Tessera
standard at all.

**The reasoning is the deliverable.** A structure chart is not advice. Every
recommendation states what it prevents. The memo ends with the failure modes the
structure is built against, the conflicts detected between the choices
themselves, and the questions that block drafting until answered.

**The memo and the paper cannot disagree.** `expected_clause_categories()` is
the contract: any position the memo promises must be delivered as a section of
the assembled document, or the suite fails. This exists because seven categories
once went missing from the library while the memo kept promising all seven, and
every coverage check passed.

---

## Fastest way to see it work

```bash
python -c "
from tessera_os.governance import VentureProfile, recommend_structure
print(recommend_structure(VentureProfile(
    venture='Lantern Pictures', home_state='Oklahoma',
    activity='film_production', business_lines=3, material_ip=True,
    passive_investors=5, capital_source='private_placement',
    tiered_economics=True, tessera_role='both')).to_markdown())
"
```

Samples under `fixtures/clause_library/`: a structure recommendation, the
operating agreement it produces, a formation checklist, and a diagnosis of an
inbound agreement.

---

## Test coverage

| File | Covers |
|---|---|
| `test_governance.py` | The decision rules |
| `test_sectors_and_options.py` | Options menu, sector patterns, capital, dual-role, glossary |
| `test_adoption.py` | The two-key ledger; nothing claims adoption without an entry |
| `test_identity_zones.py` | Entra group mapping, groups-overage fail-closed, trust-zone golden rule |
| `test_memo_document_parity.py` | The memo never promises what the document lacks |
| `test_diagnosis.py` | The inbound-agreement screen, and that it never overclaims |
| `test_formation_digest_intake.py` | Filing order, the run digest, cited intake proposals |
| `test_structure_pipeline.py` | The governed artifact path and hand-off to drafting |
| `test_microsoft_integration.py` | Broker, scope boundary, allowlisted reads |

408 tests pass; `ruff` is clean.
