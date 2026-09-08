# Tessera OS — Data Schema (v1)

Source of truth. Code conforms to this document.
Changes are made here first, then migrated.

## Conventions

- PostgreSQL. snake_case naming. UUID primary keys.
- Every table carries `created_at`, `updated_at`, `deleted_at` (soft delete).
- Documents are pointers only. No file bytes in the database.
- Retrieval filters on `conflict_group` at the query layer, enforced in the
  data access layer, not in callers.

## Locked Decisions (v1)

- **Engine:** PostgreSQL. Non-negotiable — array columns and GIN indexes are
  load-bearing for retrieval.
- **Conflict groups:** `food_hospitality_a` (Dirt Dog), `food_hospitality_b`
  (Rock N' Potato), `general` (all others). Assigned at engagement creation.
  Never reassigned. New engagements competing with an existing client receive
  a new group before any document is attached.
- **Arrays:** native `text[]` for `situation_tags`, `rejected`, `principals`.
  Join tables for `clause_usage`, `pattern_usage`, `pattern_decision`.
  `entity_shape` remains JSONB.
- **Soft delete:** `created_at`, `updated_at`, `deleted_at` on every table.
  Default query scope excludes `deleted_at IS NOT NULL`.

---

## engagement

```
id                UUID PK
client_org        text not null
conflict_group    text not null   -- tenancy key, see below
status            text            -- active | closed | prospective
phase             text
principals        text[]
opened_date       date
closed_date       date
```

`conflict_group`: engagements sharing a value may appear in the same retrieval
result. Engagements with different values must never appear together.
Conflicting clients get distinct values.

## entity

```
id                UUID PK
engagement_id     UUID FK -> engagement
legal_name        text not null
jurisdiction      text
entity_type       text            -- LLC | Corp | LP | other
formation_date    date
parent_entity_id  UUID FK -> entity (nullable, self-ref)
role              text            -- holdco | opco | spv | other
```

## document

```
id                UUID PK
engagement_id     UUID FK -> engagement
entity_id         UUID FK -> entity (nullable)
doc_type          text not null
title             text not null
m365_url          text not null
version           text
status            text            -- draft | final | executed
executed_date     date
counsel_reviewed  boolean default false
```

`doc_type`: `operating_agreement` | `nda` | `consulting_agreement` |
`deal_memo` | `investor_package` | `engagement_plan` | `finders_fee` | `other`

## decision

```
id                UUID PK
engagement_id     UUID FK -> engagement
decision_type     text not null   -- controlled vocab below
situation_tags    text[]
chosen            text not null
rejected          text[]
rationale         text not null
outcome           text
revisit_trigger   text
decision_date     date
author            text
```

`decision_type`: `entity_structure` | `governance_mechanism` |
`economic_split` | `capital_structure` | `regulatory_posture` |
`transfer_exit_mechanics` | `engagement_scope_pricing`

## clause

```
id                UUID PK
doc_type          text not null
clause_type       text not null
text              text not null
variant_of        UUID FK -> clause (nullable)
notes             text
```

## clause_usage

```
clause_id         UUID FK -> clause
engagement_id     UUID FK -> engagement
document_id       UUID FK -> document (nullable)
PK (clause_id, engagement_id)
```

## obligation

```
id                  UUID PK
engagement_id       UUID FK -> engagement
entity_id           UUID FK -> entity (nullable)
obligation_type     text not null
source_document_id  UUID FK -> document (nullable)
trigger_type        text not null   -- date | recurring | conditional
due_date            date
recurrence_rule     text            -- RRULE format
lead_time_days      integer default 30
condition_expr      text            -- for conditional triggers
status              text            -- pending | fired | resolved | void
owner               text
last_fired          timestamptz
```

## structure_pattern

```
id                UUID PK
name              text not null
situation_tags    text[]
entity_shape      jsonb
what_worked       text
what_broke        text
```

## pattern_usage

```
pattern_id        UUID FK -> structure_pattern
engagement_id     UUID FK -> engagement
PK (pattern_id, engagement_id)
```

## pattern_decision

```
pattern_id        UUID FK -> structure_pattern
decision_id       UUID FK -> decision
PK (pattern_id, decision_id)
```

---

## Index Requirements

- All foreign keys indexed.
- `engagement.conflict_group` indexed.
- GIN indexes on every `text[]` column.
- Check constraints on all controlled-vocabulary fields: `decision_type`,
  `doc_type`, `trigger_type`, `status`.
