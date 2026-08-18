# Phase 2 pilot operations

## Deployment checklist

- Register a Microsoft Entra application for delegated access only.
- Grant `Mail.Read`, `Calendars.Read`, and `Sites.Selected`; do not grant write scopes.
- Explicitly approve each pilot SharePoint site and map its documents to one project ID.
- Resolve user and group ACLs during ingestion. Missing ACLs fail closed.
- Store tokens in the deployment secret manager; never persist or log them.
- Set retention, backup, ownership, and access policy for the review queue.
- Run cross-tenant, cross-project, citation, latency, and cost acceptance tests.

## Support

The pilot owner handles access and output-quality reports. Identity or suspected
scope-leak reports are security incidents. Drafts remain in the review queue until
an authorized human accepts or rejects them; the pilot has no send or publish path.

## Incident procedure

1. Disable the affected integration or remove its selected-site grant.
2. Preserve relevant review items and sanitized request/response metadata.
3. Revoke delegated sessions and rotate any affected application credentials.
4. Identify exposed tenants, projects, sources, and users from source IDs and ACLs.
5. Correct authorization or ingestion state and rerun isolation tests.
6. Obtain security-owner approval before restoring access.

## Known pilot boundaries

The included knowledge index is in-memory and intended for pilot evaluation. A
production search backend must enforce the same tenant, project, user, and group
filters before ranking. The Graph adapter expects an injected delegated-token
provider and an ingestion transport that resolves file content and effective ACLs.
