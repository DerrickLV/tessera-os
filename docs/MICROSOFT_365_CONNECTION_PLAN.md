# Microsoft 365 and SharePoint connection plan

## Current state

Tessera is **not connected** to a Microsoft tenant. The console remains synthetic and
localhost-only by default. `MicrosoftGraphReader` is a GET-only adapter with an
injected token provider and offline contract tests. The connection broker and private
portal are implemented, but activate only when an administrator supplies the complete
Microsoft environment configuration.

## Proposed pilot architecture

Use a single-tenant Microsoft Entra application and a server-side connection broker.
The browser never receives a Graph refresh token, and no token is passed to an agent,
prompt, trace, fixture, or repository file.

1. Register a pilot Entra application with named owners and a reviewed redirect URI.
2. Use OAuth 2.0 authorization-code flow with PKCE through MSAL. Microsoft recommends
   authorization code plus PKCE for web and client applications.
3. Request only delegated `User.Read` and `Sites.Selected` for the initial signed-in
   pilot user. Mail and calendar scopes are outside this pilot.
4. Give the application explicit **read** access only to approved SharePoint pilot
   sites. `Sites.Selected` grants no site access until a resource permission is
   assigned, and the delegated user must also have access.
5. Store the token cache encrypted in the deployment secret/key service. Keep only
   opaque connection and account identifiers in application storage.
6. Map verified Entra `tid`, `oid`, and group/role claims to Tessera `UserContext`.
   Reject unknown tenants, missing roles, and unmapped projects before retrieval.
7. Maintain an administrator-approved mapping of Tessera project IDs to SharePoint
   site, library, folder, or list IDs. Do not accept arbitrary Graph paths from a task.
8. Retrieve only allowlisted fields and content. Resolve the effective user/group ACL
   for every document, retain source IDs and modification timestamps, and fail closed
   when ACL or project metadata is missing.
9. Index authorized content with tenant, project, user, and group boundaries intact.
   Recheck those boundaries before search, ranking, citation display, and review.
10. Respect `Retry-After` on Graph `429` responses, use bounded retries and correlation
    IDs, and expose a per-tenant integration kill switch.

Microsoft references:

- [Authorization code flow with PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Microsoft Graph permission reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Least-privilege Graph permission guidance](https://learn.microsoft.com/en-us/graph/best-practices-graph-permission)
- [Selected permissions for SharePoint and OneDrive](https://learn.microsoft.com/en-us/graph/permissions-selected-overview)
- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling)

## Pilot rollout gates

Do not connect the app until all of these are approved:

- tenant and application owner;
- pilot users, projects, sites, libraries, and retention period;
- permission manifest showing no write or broad `*.All` access;
- managed token storage and key rotation;
- identity, ACL, cross-project, revocation, throttling, and incident tests;
- a sanitized representative dataset and human acceptance criteria;
- a documented disconnect procedure that revokes consent and deletes retained tokens.

The implemented starter connection requests only `User.Read` and `Sites.Selected`.
The first live workflow should be one read-only cited project-status draft. Mail and
calendar access should be added only if a later workflow specifically requires them.
No send, update, delete, upload, sharing, filing, or external-delivery permission is
part of the initial pilot.

## Implemented connection foundation

- `MicrosoftConnectionBroker` performs a server-side MSAL authorization-code flow,
  validates the returned state, silently refreshes tokens, and never returns tokens to
  the console browser.
- The MSAL cache is encrypted with AES-GCM, stored under ignored runtime data, and
  removed on disconnect.
- `AllowlistedSharePointReader` accepts a Tessera project ID—not an arbitrary Graph
  path—and resolves the site, drive, and folder from administrator-approved settings.
- Microsoft Graph access is GET-only, checks pagination origins, honors `Retry-After`
  with bounded retries, selects only required fields, and preserves project/ACL data.
- The console exposes connection status, connect, callback, and disconnect endpoints.
  The integration remains disabled until all required environment values exist.

## Administrator setup

1. Register a single-tenant confidential web application in Microsoft Entra ID.
2. Add the exact redirect URI for the target environment: local console
   `http://127.0.0.1:8000/v1/integrations/microsoft/callback`, or private portal
   `https://api.tesseraag.com/v1/integrations/microsoft/callback`.
3. Add delegated Microsoft Graph permissions `User.Read` and `Sites.Selected` only.
   Do not add `Sites.Read.All`, `Files.ReadWrite*`, mail, calendar, or any write scope.
4. Grant this app **read** access to each approved SharePoint site through the
   administrator-controlled selected-permissions process.
5. Identify each approved site's Graph `site_id`, document library `drive_id`, and
   optional folder item ID. Map those IDs to Tessera project IDs in
   `TESSERA_M365_PROJECT_RESOURCES`.
6. Generate a 32-byte encryption key (for example `openssl rand -base64 32`) and place
   it in the local secret environment as `TESSERA_M365_CACHE_KEY`.
7. Populate the remaining `TESSERA_M365_*` variables from `.env.example`, set
   `TESSERA_M365_ENABLED=true`, restart `tessera serve`, and use **Guardrails →
   Microsoft 365 pilot → Connect Microsoft 365**.

Do not paste secrets into chat, source files, shell history, screenshots, or fixtures.
For the Netlify, Render, Porkbun, and production-domain sequence, use
`PORTAL_DEPLOYMENT.md`.
