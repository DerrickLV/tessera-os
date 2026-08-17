# Integration contracts

Integrations are typed capabilities, not arbitrary API access. Each adapter must
authenticate using the acting identity or a narrowly scoped service principal and
enforce project authorization independently of the model.

## Standard tool envelope

```json
{
  "correlation_id": "uuid",
  "tenant_id": "tenant",
  "project_id": "project",
  "actor_id": "user",
  "action": "calendar.events.list",
  "arguments": {},
  "idempotency_key": null,
  "approval_id": null
}
```

Every response returns a status, source record IDs, timestamps, classification,
and a redacted error. Write tools also return a durable audit ID and before/after
references. Never pass raw access tokens through an agent prompt.

## Planned adapters

| System | Phase 1 capability | Later gated capability |
|---|---|---|
| Microsoft Graph | Read calendar and selected mail | Send mail, update events |
| SharePoint | Search/read permitted files | Publish metadata or documents |
| HubSpot | Read companies, contacts, deals | Update records and activities |
| n8n | Read definitions and run logs | Enable workflows or production runs |
| GitHub | Read repository, issues, checks | Create branch/PR or dispatch deployment |

## Adapter requirements

- Pagination, retries with jitter, timeouts, and rate-limit handling
- Idempotency keys for every write
- Schema validation at both boundaries
- Read-after-write verification where supported
- Structured, redacted logging with correlation IDs
- Contract tests against recorded or sandbox fixtures
- Kill switch per integration and action
