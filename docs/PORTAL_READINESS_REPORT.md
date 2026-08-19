# Phase 7C private portal readiness report

**Date:** 18 August 2026
**Decision:** code-ready for a sanitized, single-user deployment exercise; not approved
for real client data or multi-user production use.

## Implemented

- Separate Netlify portal and Render API deployment definitions for
  `app.tesseraag.com` and `api.tesseraag.com`.
- Single-tenant Microsoft authorization-code connection with state validation.
- Exact one-user Entra Object ID allowlist and tenant validation.
- Eight-hour secure, HTTP-only, API-host-only signed session.
- Server-only encrypted MSAL token cache on persistent storage.
- Delegated `User.Read` and `Sites.Selected` scope ceiling.
- Exact Tessera-project-to-SharePoint resource mapping with no browser-supplied Graph
  path.
- GET-only SharePoint document reads, bounded throttling retries, origin-checked
  pagination, and project/ACL preservation.
- CORS, trusted-host, cache, framing, referrer, MIME, and content-security headers.
- No send, upload, edit, delete, sharing, application submission, approval, payment,
  baseline change, or external-delivery endpoint.
- A rollback procedure and an administrator deployment guide.

## Verification performed

- Ruff: passed.
- Pytest: 200 passed.
- Python wheel build: passed.
- Secret-pattern scan: passed.
- Locked dependency audit: no known vulnerabilities.
- Git whitespace validation: passed.

The Docker image was not built locally because Docker is not installed in this
workspace. Render must build it successfully before deployment can proceed.

## External gates still required

1. Entra app registration, named owner, secret, exact redirect URI, and admin consent.
2. Read-only selected-site grant to a sanitized SharePoint pilot site.
3. Verified site, drive, folder, project, tenant, and one-user Object ID values.
4. Render deployment, health check, persistent disk, logs, alerting, and custom-domain
   verification.
5. Netlify second-site deployment and custom-domain verification.
6. Porkbun `app` and `api` CNAME records without changing existing public-site records.
7. Identity rejection, project denial, disconnect, backup/restore, and incident drills
   in the deployed environment.
8. Accessibility, browser, human acceptance, privacy, retention, and security review.

Do not add another pilot user. The current delegated-token broker is deliberately
limited to one account; multi-user operation requires isolated per-user token caches
and a separate security review.
