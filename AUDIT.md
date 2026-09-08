# Repository audit

Audited **2026-09-08**, with network and Azure checks approximately **15:03–15:07 UTC**.

- Repository: `DerrickLV/tessera-os`, local checkout `/Users/derrickcarlisle/Documents/GitHub/tessera-os`.
- Audited HEAD: `b973729729ac353eccb22e30ef145ec54315e292`, branch `phase-6-adoption-scope`, one commit ahead of its locally recorded tracking branch. Working tree was clean before this audit.
- Verified serving image: `ghcr.io/derricklv/tessera-os:sha-c71e3fa`, two ancestor commits behind audited HEAD. Do not confuse this checkout with production.
- Scope: tracked source, configuration, fixtures, frontend, tests, packaging and deployment workflows; ignored local database files inspected separately, read-only. No code, configuration, dependency, deployment, credential, or existing database changes were made. Tests and additional reproductions used disposable copies outside the repository. `AUDIT.md` is the only repository file change.

## Verdict

**This is a running private pilot with real authentication, persistence, deterministic structure recommendations, clause assembly and review APIs. It is not a fully connected multi-agent operating system.** The live portal and console are reachable. The test suite is substantial: **641 tests passed**. Most named managers remain library implementations exercised with fixtures, not live workflows connected to production data and tools.

The distinctions that matter:

1. **A real deployment exists**, on Azure Container Apps at [api.tesseraag.com](https://api.tesseraag.com/). It is serving an older commit; the new adoption-scope implementation in HEAD is not in the image tag Azure reports.
2. **Human review is implemented but its separation-of-duties guarantee is broken on the artifact submission path.** A local reproduction created a draft as `author`, submitted it, and accepted it as that same user with `qualified_counsel`: all returned HTTP 200. Submission stores `created_by=artifact.agent_id`, not the human author, so the queue compares the reviewer against `contract_manager`. See `console.py:898–922` and `review.py:144–178`.
3. **Project authorization is broader than documented.** Every invited portal/console user receives the entire configured project catalog. `TESSERA_USER_PROJECTS` is checked by the readiness helper but is not applied by either production context provider. SharePoint's internal-zone partner gate exists; that does not make the console's artifacts, project listing and other project APIs per-user scoped. See `portal.py:118–135,220–250`, `console.py:232–267`, `m365_readiness.py:88–106`.
4. **Anonymous logout clears the shared Microsoft broker.** `POST /v1/auth/logout` has no authentication dependency and calls `broker.disconnect()` without a user ID. Reproduced locally: HTTP 303 and an unscoped disconnect call. This removes all cached accounts and pending flows, not just one user's connection. A rejected portal login also calls unscoped disconnect. The per-user broker exists but is not wired into the portal. See `portal.py:195–218`, `microsoft.py:314–395`.
5. **The advertised audit chain and encryption do not cover the production review/artifact stores.** A draft and review generated zero `RuntimeAuditStore` traces in the reproduction. Review decisions update ordinary SQLite rows; artifact events are JSON in ordinary SQLite. The hash-chain store lives in the unconnected sandbox automation subsystem, and `SecureArtifactStore` is not used by the console. The production notice saying “every decision is written to the audit chain” is false for this path. See `console.py:270–271,415–460,898–922,964–987`, `workspace.py:207–283`, `runtime_controls.py:237–327`, `automation.py:254–292`.
6. **The Dockerfile omits `prompts/`.** Agent manifests point to that directory, and `/v1/route` calls `instructions_digest()`, which reads a specialist prompt. Reproducing the Docker COPY layout caused `FileNotFoundError` for `prompts/contract_manager.md`. This predicts a route failure in an image built exactly this way even when health is green; no authenticated production POST was performed. It also prevents live specialist execution. See `Dockerfile`, `registry.py:28–38`, `orchestrator.py:16–41`, `service.py:146–152`.
7. **Agreement drafting really assembles clauses, but the clause language is synthetic evaluation material.** `config/adopted_positions.yaml` contains `positions: []`. Passing tests or a functioning draft endpoint does not turn this into adopted, counsel-approved language. `AgreementDrafter` explicitly labels that limitation, including in production.

## 1. Every HTTP endpoint

### Inventory and status convention

Routes were enumerated from Python decorators and checked against the live console OpenAPI document. There are **48 explicit routes in the mounted portal deployment**: nine portal routes and 39 console routes (37 console declarations plus two inherited service routes), before static-file mounts and framework redirects/preflight handling.

- **Implemented** means a substantive code path exists, with local test evidence where described. It does **not** mean an authenticated live transaction was exercised.
- **Conditional** means actual external configuration/credentials or required review state is necessary.
- **Synthetic/disabled** means a real sandbox handler with fixture content, explicitly refused in production; not an unfinished `pass` handler.
- **Metadata** means configuration/fixture data, not a measured operational state.
- Portal business routes use the signed session unless marked public. Console business routes use the injected context provider: a portal session in production, a fixed synthetic identity in sandbox/test. Scope/reviewer qualifications remain subject to the bugs above.

There are no application-declared PUT, PATCH or DELETE routes. The portal does not automatically expose `/docs`, `/redoc` or `/openapi.json`.

### Portal root routes — `src/tessera_os/portal.py`

Paths below are relative to the live origin `https://api.tesseraag.com`.

| Method | Path | Actual behavior | Status / authentication |
|---|---|---|---|
| GET | `/` | Serves `web/tessera-portal.html`; 404 if absent. | Implemented; public; live 200. |
| GET | `/health` | Returns `status=ok`, `mode=production`, and console construction state. Does not test a database query, Graph read, token refresh, or model call. | Implemented shallow check; public; live 200, console `ok`. |
| GET | `/v1/auth/microsoft/start` | Starts MSAL authorization-code flow, saves flow state in memory, redirects to Microsoft; 503 on configuration error. | Conditional real OAuth; public. Starting it changes broker memory, so not exercised live in this audit. |
| GET | `/v1/integrations/microsoft/callback` | Consumes stored OAuth state, exchanges code, validates tenant/invitation, maps groups, issues secure eight-hour cookie, redirects to app URL. | Conditional real OAuth; public callback. Uninvited identity clears shared cache. |
| POST | `/v1/auth/logout` | Clears the entire broker, deletes this browser's cookie, redirects. | Implemented **with shared logout defect**; public. |
| GET | `/v1/session` | Returns identity, display name, all catalog projects, and whether this user's account exists in MSAL cache. | Implemented; session required; live anonymous 401. “Connected” is cache presence, not successful Graph access. |
| GET | `/v1/projects` | Returns catalog projects visible in context; context currently includes all catalog IDs. | Implemented metadata; session required; live anonymous 401. |
| GET | `/v1/projects/{project_id}/documents` | Reads administrator-mapped SharePoint tree using the user's delegated token, enforces scope/internal zone, returns only items labeled `approved`. | Conditional real Graph implementation; session required. No authenticated live document read established. |
| GET | `/v1/integrations/microsoft/status` | Broker configuration, scope, project and current-account cache status. | Implemented metadata; session required; no Graph health probe. |

Public static mounts, when their directories exist: **GET/HEAD `/ui/{path}`** serves the `web/` tree (including both HTML interfaces); **GET/HEAD `/assets/{path}`** serves `web/assets/`. Live `/assets/portal.js` returned 200. `/ui` is not a separate API and does not protect static HTML. StaticFiles rejects unsupported methods and missing files; it is not a write endpoint. CORS middleware answers qualifying OPTIONS preflights; slash redirects are framework behavior, not extra business APIs.

### Console routes — `src/tessera_os/console.py` and inherited `service.py`

**Every path in this table has the `/console` prefix in production.** For example, `/v1/artifacts` below is `https://api.tesseraag.com/console/v1/artifacts`. In standalone `tessera serve` mode the prefix is absent. The console can fail construction and be absent while the portal remains up; the current deployment reports it mounted.

| Method | Console-relative path | Actual behavior | Implementation status |
|---|---|---|---|
| GET | `/` | Serves console HTML. | Implemented, public; live `/console/` 200. Frontend subsequently needs session. |
| GET | `/favicon.ico` | Empty 204 response. | Intentional no-op, public. |
| GET | `/health` | Inherited service health: `ok` and selected environment. | Implemented shallow check, public; live 200. |
| POST | `/v1/route` | Keyword-based specialist selection, project/policy checks, per-user in-memory rate limit, UUID correlation ID, prompt digest, SQLite trace. Does not execute a model. | Implemented locally; **packaging defect** described above. |
| GET | `/v1/session` | Current context, projects, groups, environment and synthetic flag. | Implemented; live anonymous 401. |
| GET | `/v1/agents` | Cards from 13 JSON manifests, including declared tool names. | Metadata; not agent execution or tool connectivity. Live anonymous 401. |
| GET | `/v1/policy` | Serializes `config/security.yaml`. | Metadata; several declared controls are not enforced across all routes. |
| GET | `/v1/integrations` | Cards from `config/integrations.yaml`. | Metadata: `pilot`/`planned` labels are not connection tests. |
| GET | `/v1/integrations/microsoft/status` | Current user's broker cache/configuration status. | Conditional metadata; no transport health check. |
| POST | `/v1/integrations/microsoft/connect` | Begins OAuth and returns authorization URL; 409 on configuration error. | Conditional real broker; session required. |
| GET | `/v1/integrations/microsoft/callback` | Consumes flow, exchanges code, redirects to `/?microsoft=connected`; does not issue portal session or check portal invitation. | Conditional; public callback. Root-relative redirect leaves console mount; normal portal login uses the separate root callback. |
| POST | `/v1/integrations/microsoft/disconnect` | Removes the authenticated user's cached account and returns status. | Implemented scoped disconnect, unlike portal logout. |
| GET | `/v1/clients` | Clients corresponding to visible catalog projects. | Metadata; production names derived from IDs, sandbox fixture-backed. |
| GET | `/v1/projects` | Visible console catalog. | Metadata; production uses portal catalog. |
| GET | `/v1/projects/{project_id}` | Single scoped project or 403/404. | Implemented metadata. |
| GET | `/v1/projects/{project_id}/controls` | Fixture control snapshot, or empty registers and zero variance when absent. | **Scaffolding in production**: production fixture has no controls. Zero is a default, not verified on-budget/on-time performance. |
| GET | `/v1/reviews` | Scoped durable queue; optional `status` query. | Implemented SQLite reads. |
| GET | `/v1/reviews/{item_id}` | Scoped review or 403/404. | Implemented SQLite read. |
| POST | `/v1/workspace/run` | Runs pre-authored fixture workflow, or real structure engine on a hardcoded synthetic venture. Optional sandbox live drafting branch. | **Synthetic; production 409.** |
| POST | `/v1/workspace/compare` | Compares fixture draft and optional live draft. | **Synthetic; production 409**; live comparison requires configured drafter. |
| POST | `/v1/structure/intake` | Runs deterministic structure rules on supplied venture facts; records operator-statement evidence and saves artifact. | Implemented; production entry point; tested with fake production identity. Input facts are not independently verified. |
| POST | `/v1/structure/recommendations` | Builds and saves structure memo from supplied `StructureRequest`, evidence, confirmations and menu selections. | Implemented; no production guard despite “synthetic” docstring. Caller-supplied evidence is not fetched/verified against Graph. |
| POST | `/v1/structure/recommendations/{artifact_id}/draft` | Requires accepted structure review, matching input fingerprint, adequate evidence/confirmed terms, then assembles agreement. | Implemented review-gated handoff; review-author bug weakens that gate. |
| POST | `/v1/structure/numbers/confirm` | Upserts a human-confirmed integer by tenant/project/label. | Implemented durable mutation; context scope required. Replaces earlier value rather than retaining a decision history. |
| POST | `/v1/structure/menus/select` | Upserts selected option by tenant/project/menu area. | Implemented durable mutation; not a mocked confirmation. API accepts nonempty strings; it does not itself validate membership in a particular menu. |
| GET | `/v1/projects/{project_id}/workflows` | Available fixture templates plus an entity-structuring option. | Metadata; production normally offers structure only because templates are empty. |
| GET | `/v1/artifacts` | Reads scoped artifacts, optional project filter; refreshes persisted status from review queue. | Implemented; **GET can write** updated artifact JSON/status/events. |
| GET | `/v1/artifacts/{artifact_id}` | Reads one artifact with the same review refresh. | Implemented; **GET can write**. |
| POST | `/v1/artifacts/{artifact_id}/submit` | Creates review, links artifact, records submit event; existing link is reused. | Implemented **with human-author loss**. Queue and artifact updates are in separate database transactions. |
| GET | `/v1/clause-library` | Returns loaded clause library and variants. | Implemented fixture-library read, not approved production precedent retrieval. |
| POST | `/v1/workspace/draft-agreement` | Assembles clauses, checks coverage, saves draft; direct operating agreement/JV requests require prior structural handoff. | Implemented deterministic assembly; synthetic clause text; no model call or external send. |
| POST | `/v1/workspace/reset` | Deletes/restores synthetic artifacts, reviews, traces/budgets. | Implemented destructive sandbox reset; **production 409**. Never called against original data during audit. |
| POST | `/v1/reviews/{item_id}/accept` | Checks tenant/project, required group, pending status and nonblank reason, updates review. | Implemented local acceptance; separation-of-duties defect on artifact submissions. No external publication. |
| POST | `/v1/reviews/{item_id}/reject` | Same scope/role/status checks; records rejection. | Implemented local mutation; no external rollback. |
| POST | `/v1/reviews/{item_id}/amend-and-accept` | Same checks, requires amendment text, stores amendment and disposition. | Implemented local mutation. Structural handoff specifically requires `accepted`, not `amended_and_accepted`. |
| GET | `/v1/pilot/export` | Returns completed review labels, reasons, bodies, reviewers and source IDs as JSON. | Implemented read; no file, DOCX or spreadsheet generation. |
| GET | `/v1/console/bootstrap` | Aggregates session, cards, catalog, reviews, artifacts and workflow/control metadata. | Implemented mixed real/metadata response; artifact refresh can write. “Active agents” is manifest count, not running workers. |
| GET | `/api/openapi.json` | Returns console contract. | Implemented **public**, also in production; live 200 with 35 schema-visible paths. |
| GET | `/api/docs` | Returns small static guidance page. | Implemented public; live 200. Stale “offline synthetic sandbox” text and `/api/openapi.json` root link are wrong for mounted production console. |

Console source locations: factory/setup `356–538`; route implementations `555–1039`; inherited service routes `service.py:114–157`.

### Standalone routing service

`service.create_app()` can also be deployed independently and exposes the same **GET `/health`** and **POST `/v1/route`** without `/console`, using the bearer-JWT authenticator rather than portal cookies. This is not the Docker entry point. Both `service.py` and `portal.py` set module-level `app = None`; deploy the factory, not `uvicorn ...:app`.

With the explicit Python option `enable_docs=True`, the standalone service additionally enables public **GET/HEAD `/api/openapi.json`**, **GET/HEAD `/api/docs`**, and FastAPI's Swagger OAuth redirect **GET/HEAD `/docs/oauth2-redirect`**. These are framework documentation routes, disabled by default. Console uses its own two documentation handlers, not this option.

There is no API for creating users/projects, document upload, knowledge search/ingestion, DOCX export, automatic filing, CRM update, email sending, payments, signatures, external approval execution, deployment management, or an automation worker. Declaration of these capabilities in prompts/manifests does not create endpoints.

## 2. Database, migrations and actual state

### Engine and ownership

**SQLite**, through Python's standard `sqlite3`; no PostgreSQL/MySQL server, ORM or vector database is configured in runtime source. Stores contain normal scalar columns and substantial serialized JSON. Microsoft tokens are a separate AES-GCM encrypted MSAL file, not a database table. Catalogs, groups, project resources, routing, clauses and adopted positions come from environment/configuration/files, not relational user/project tables. `KnowledgeIndex` is an in-memory dictionary with word-count ranking, not persistent or embedding-based retrieval.

`sqlite_store.connect()` selects `unix-dotfile` VFS, DELETE rollback journaling, a 30-second busy timeout and a process-wide reentrant lock around transaction context managers. This is deliberate accommodation for Azure Files SMB. There is no WAL configuration. Tests cover the local locking/transaction behavior; they do not prove network-filesystem fault tolerance or a recovery SLA.

### Local databases actually inspected

Opened using SQLite URI **`mode=ro`**, queried `sqlite_master`, counted rows, ran `PRAGMA quick_check`, and compared SHA-256 before/after. All three files were unchanged and returned `ok`.

| Existing ignored file | Tables and observed rows | Interpretation |
|---|---|---|
| `data/runtime/console-artifacts.db` (12,288 bytes) | `pilot_artifacts`: 0 | No stored local artifacts. |
| `data/runtime/console-audit.db` (20,480 bytes) | `usage_budgets`: 0; `traces`: 0 | No recorded local budgets or traces. |
| `data/runtime/console-review.db` (20,480 bytes) | `review_items`: 6; all tenant `tenant-synthetic` | Synthetic queue data, not evidence of real customer reviews. |

No number-confirmation or menu-selection database was present under this checkout's `data/` tree. No Tessera/uvicorn process was visible among TCP listeners, and no listener on the default port 8000 appeared. SQLite needs no server daemon: these files exist locally, but that does not mean the application is currently serving locally. No `TESSERA_*` or `OPENAI_API_KEY` variables were present in the audit shell (names-only inspection; this says nothing about another process's environment).

### Deployed persistence evidence

Read-only Azure Resource Manager responses confirmed:

- Container App `tessera-portal-api`, resource group `tessera-pilot-rg`, West US 2.
- Volume `tessera-data`, type `AzureFile`, storage link `tessera-data`, mounted at `/var/data`.
- Managed environment `tessera-pilot-env` has storage link to account `tesseradata2026`, share `tessera-data`, access `ReadWrite`.
- Replica min/max both **1**. Current active revision is healthy and receives 100% traffic.
- `TESSERA_PORTAL_DATA_DIR` is configured; code/default and deployment record use `/var/data/tessera`. Console appends `/console`, with five database files listed below.

This establishes real deployed storage wiring and successful console construction, **not a live dump of database contents**. No container shell, mounted-share download, or authenticated application data retrieval was performed. Deployed row counts, exact live `sqlite_master`, backup contents, restore history and retention execution remain unverified. Health does not continuously test persistence. The deployed commit has no database-source changes relative to HEAD, so the schema below is the serving revision's code-defined schema too; existing live-file drift was not ruled out.

### Migrations

There is **no versioned migration directory, Alembic configuration, migration ledger, rollback migration or startup schema-version check**. Constructors run `CREATE TABLE IF NOT EXISTS`. `ReviewQueue.__init__` additionally reads `PRAGMA table_info(review_items)` and adds any missing `reviewed_by`, `reviewed_at`, `review_reason`, `required_reviewer_group`, `review_reason_category`, `amended_body` columns as nullable TEXT. That is an ad hoc forward migration, not a migration framework. Existing incompatible types/constraints elsewhere will not be repaired by `IF NOT EXISTS`.

### Current schema

The first four tables below were verified against existing local files and match constructor DDL. The two confirmation/selection tables are current constructor schema, created in fresh test stores; they were absent in original local runtime data. The remaining seven are implemented library-store schemas **not instantiated by the portal/console production path**.

Full column types, nullability, defaults and keys are reproduced in Appendix A. There are no declared foreign keys or explicit secondary `CREATE INDEX` statements in these stores. Primary/unique keys create SQLite autoindexes. Relations such as artifact-to-review are enforced in application code across separate files, not by database constraints.

| Store / runtime file | Tables | Connected to serving app? |
|---|---|---|
| `PilotArtifactStore`, `console-artifacts.db` | `pilot_artifacts` | Yes, console. |
| `ReviewQueue`, `console-review.db` | `review_items` | Yes, console. |
| `RuntimeAuditStore`, `console-audit.db` | `usage_budgets`, `traces` | Yes, but route trace path is sparse; budget enforcement is not wired to model runs. Standalone service defaults to `tessera-runtime.db`. |
| `NumberConfirmationStore`, `console-number-confirmations.db` | `number_confirmations` | Yes, console. |
| `MenuSelectionStore`, `console-menu-selections.db` | `menu_selections` | Yes, console. |
| `SecureArtifactStore`, caller-supplied path | `secure_artifacts` | No production caller; library/tests only. |
| `ActionControlStore`, caller-supplied path | `approval_packets`, `consumed_tokens`, `receipts`, `dead_letters`, `kill_switches`, `audit_events` | No portal/console caller; sandbox automation/tests only. `sqlite_sequence` is SQLite's internal AUTOINCREMENT bookkeeping if instantiated. |

**Data durability limits:** plaintext review body/evidence and artifact JSON; no connected retention scheduler, legal-hold service, backup job or restore check; reviews and artifact links are not atomic across files; confirmation/menu rows overwrite earlier choices; no independent append-only ledger for production decisions. Azure volume configuration alone does not close these gaps.

## 3. Authentication and authorization

### Implemented

- **Portal:** MSAL confidential-client delegated OAuth authorization-code flow; fixed tenant authority; server-side code exchange; single-use flow lookup by state; ID-token tenant/user checks; 1–5 explicitly invited Entra object IDs; mapped Entra groups with absent/unmapped groups granting no privileged roles.
- **Browser session:** signed HS256 JWT with fixed issuer/audience, required identity/time claims and eight-hour expiry. Cookie is HttpOnly, Secure, SameSite=Lax. This differs from the asymmetric bearer-JWT service and is an actual implemented session system, not a fake login screen.
- **Bearer service:** issuer/audience/signature/expiry verification; required identity/project/group claims; `tessera_user` required; algorithm allowlist; symmetric algorithm rejected for production settings. Verification uses the configured key, with no dynamic JWKS discovery/rotation implementation.
- **Console:** `PortalContextProvider` checks session and invitation; production refuses startup with the synthetic default identity. Sandbox has a fixed powerful synthetic user and localhost restrictions; CLI `serve` is not a production authentication mode.
- **Stores/reviews:** tenant/project filtering, reviewer group, pending-only transitions, required reasons, amendment content checks, SQLite transaction for review transition. Structure handoff verifies accepted review and exact input fingerprint.
- **Graph read boundary:** tokens selected by authenticated user; configured project/resource resolution; scope restriction; internal-zone partner gate; tenant/project/group ACL metadata on returned documents.

### Incomplete or misleading

- **Per-user project mapping is not enforced**, as explained in the verdict. `ZonePolicy.check_read()` only denies non-partners for `internal`; engagement/collaborator membership depends on upstream project scope, which is currently all projects for invited users. Production console store access does not use the SharePoint zone gate.
- **Review role enforcement is real; author/reviewer separation is not reliable through API submission.** Tests on `ReviewQueue` do not detect changing the creator to the agent at the API boundary.
- **Logout does not revoke an already issued JWT server-side.** It deletes a browser cookie and clears Microsoft cache; a copied signed session remains usable for local APIs until expiry unless invitation or secret changes. No session revocation table exists. Group changes are reflected at next sign-in, not continuously fetched.
- **Global broker has shared state/cache.** Portal logout and rejected identity paths can disrupt other users. Flow state is in memory and lost on restart; it is not bound to a browser-session cookie by application code, and no application-level flow expiry/cleanup is visible. MSAL handles its own protocol validation, but a dictionary keyed by state is not browser binding.
- **CSRF protection is limited to browser cookie/CORS behavior.** No explicit Origin/CSRF token validation on mutation handlers. Anonymous logout does not need a cookie at all. CORS is not authorization.
- **Health and documentation are public**; that is actual behavior, not a claim all endpoints require authentication.
- **Policy settings are not universal enforcement.** The policy gateway is called on route/model paths, while most console handlers directly use context/store checks. Rate limiting applies to `/v1/route`, not globally. Declared usage limits, retention and encrypted artifact controls are not automatically active because YAML lists them.

No real Entra sign-in, token refresh, group membership, selected-site permission or SharePoint document access was exercised. Do not read passing fake-provider tests as proof those tenant-side settings work.

## 4. External dependencies and credentials

### Runtime packages

`pyproject.toml`: Python >=3.11; `cryptography>=50,<51`, `fastapi>=0.116,<1`, `msal>=1.34,<2`, `openai-agents>=0.8,<1`, `pydantic>=2.8,<3`, `python-docx>=1.2,<2`, `PyJWT[crypto]>=2.10.1,<3`, `pyyaml>=6,<7`, `uvicorn>=0.35,<1`. Dev extras: httpx, pip-audit, pytest, ruff. `requirements.lock` pins transitive/build/dev packages; CI and Docker install that lock. Docker therefore also installs development dependencies. Local `pip check` found no broken requirements. No fresh vulnerability-service audit was run, so this is not a current CVE clearance.

### Services and configuration

| Dependency | Actual integration | Expected credentials/configuration |
|---|---|---|
| Microsoft Entra / MSAL | Real delegated OAuth and encrypted token caching. | `TESSERA_M365_ENABLED`, `TESSERA_M365_TENANT_ID`, `TESSERA_M365_CLIENT_ID`, `TESSERA_M365_CLIENT_SECRET`, `TESSERA_M365_REDIRECT_URI`, `TESSERA_M365_CACHE_KEY` (base64url-decoded 32-byte AES key). |
| Microsoft Graph / SharePoint | Actual GET transport, pagination, throttling retries for listing, scoped recursive traversal to depth 5; text extraction for DOCX paragraphs, TXT and MD. Other formats list with unavailable content. 10 MiB metadata-based size cutoff; downloaded response is not stream-limited. No Graph write transport. | Delegated access token supplied by broker; scopes limited to `User.Read` and `Sites.Selected`; actual selected-site grant required; `TESSERA_M365_PROJECT_RESOURCES` maps site/drive/root path/zone/client. `TESSERA_M365_GROUP_MAP` maps Entra groups. |
| OpenAI | `TesseraOrchestrator.run()` constructs one SDK `Agent` and calls `Runner.run`. Not a complete tool-equipped manager network. Manifests' `tools` are not bound as callable SDK tools. | `OPENAI_API_KEY`; `TESSERA_MODEL_DEFAULT` / `TESSERA_MODEL_HIGH_REASONING`; model names in `config/models.yaml`. No model availability or billable call tested. `TESSERA_PILOT_LIVE_DRAFTING=true` only enables appropriate injected/sandbox path; standard production creation supplies no live drafter and disables fallback. |
| Portal | Real cookie/session and catalog. | `TESSERA_APP_URL`, `TESSERA_API_URL` (HTTPS), `TESSERA_SESSION_SECRET` (min 32 characters), `TESSERA_ALLOWED_USER_IDS`, `TESSERA_PROJECT_CATALOG`, `TESSERA_PORTAL_DATA_DIR`. `TESSERA_USER_PROJECTS` is currently readiness-only, not runtime ACL. |
| Standalone JWT service | Real static-key verifier, not used for portal-cookie auth. | `TESSERA_OIDC_ISSUER`, `TESSERA_OIDC_AUDIENCE`, `TESSERA_OIDC_VERIFICATION_KEY`, `TESSERA_OIDC_ALGORITHM`. |
| Azure Container Apps / Azure Files | Verified hosting and persistent mount. | App secrets observed by **name only**: `ghcrio-derricklv`, `m365-cache-key`, `m365-client-secret`, `session-secret`. Four secret entries, not proof of validity/rotation. No Key Vault or managed-secret retrieval is implemented in Python. |
| GitHub Actions / GHCR / Azure deploy | Actual image build/push and deployment workflow. | Actions `GITHUB_TOKEN`; federated Azure login using `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` secret references. Bootstrap script prompts for GHCR PAT/client secret. Azure registry credentials are configured outside application source. |
| HubSpot | Configuration label only, `planned`. | No runtime client or credential reader. |
| n8n | Configuration label only, `planned`. | No webhook/worker/client integration. Sandbox action executor operates on an in-memory record dictionary. |
| GitHub as an agent tool | Configuration label only, `planned`, despite real CI use. | No repository-scoped runtime connector bound to agents. |
| Render / Netlify | Legacy deployment definitions/documentation. | `render.yaml` and `netlify.toml`; no evidence they serve this application's current API/UI. |

Other process settings: `TESSERA_ENV` controls environment (console defaults to sandbox); `TESSERA_ROOT` locates required repository assets; `TESSERA_CONSOLE_DATA_DIR` overrides standalone console storage; `TESSERA_LOG_LEVEL` affects CLI logging. Production portal reports “production” independently of console's environment variable, so configuration must still set `TESSERA_ENV=production` to activate console production guards.

Credentials are expected in process/deployment environment; `.env.example` is documentation, not a loader. No dotenv loader was found. The existing local `.venv` works, but that does not establish populated production secrets. The audit did not print secret values. `scripts/security_scan.py` passed on the tracked snapshot; it detects a few token/private-key patterns, not all secrets or git-history exposure. `deploy-azure.sh` records a historical committed-and-revoked token incident; revocation was not independently verified.

Model settings such as timeout, usage capture, tracing, reasoning effort and temperature are present in configuration; the orchestrator explicitly passes model and max turns, not all those settings. Budgets/encrypted retention should not be reported as applied to model execution.

## 5. Deployment state and reachability

### Verified live, not inferred from a README

Read-only Azure ARM queries on the app, revisions and environment storage returned:

| Property | Observed value |
|---|---|
| Subscription | `1ce8bb84-5eaa-4b82-9262-705b70f9b117` |
| Resource group / environment | `tessera-pilot-rg` / `tessera-pilot-env` |
| App / region | `tessera-portal-api` / West US 2 |
| Custom domain | `api.tesseraag.com` |
| Active revision | `tessera-portal-api--c71e3fa` |
| State / health / traffic | `RunningAtMaxScale` / `Healthy` / 100% |
| Image | `ghcr.io/derricklv/tessera-os:sha-c71e3fa` |
| Scaling | min 1, max 1 |
| Persistent volume | AzureFile `tessera-data`, `/var/data`; account/share confirmed above |

Anonymous HTTPS probes used valid TLS and did not follow login flows or call mutating endpoints:

| URL/path | Observation |
|---|---|
| [API origin `/`](https://api.tesseraag.com/) | 200, portal HTML, 3,313 bytes. |
| [API `/health`](https://api.tesseraag.com/health) | 200: `{"status":"ok","mode":"production","console":"ok"}`. |
| [Console `/console/`](https://api.tesseraag.com/console/) | 200, HTML, 217,354 bytes. |
| [Console health](https://api.tesseraag.com/console/health) | 200: `{"status":"ok","mode":"production"}`. |
| `/v1/session`, `/v1/projects` | 401, Microsoft sign-in required. |
| `/console/v1/session`, `/console/v1/agents` | 401, console sign-in required. |
| [Console OpenAPI](https://api.tesseraag.com/console/api/openapi.json) | 200; version `0.9.0`; 35 schema-visible paths matching local route inventory. |
| [Console docs](https://api.tesseraag.com/console/api/docs) | 200; stale sandbox guidance. |
| `/assets/portal.js` | 200, JavaScript. |
| `https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io/health` | 400, `Invalid host header`; infrastructure is reachable, application host allowlist rejects this old origin. Other probed paths on that hostname also returned 400. |
| `https://app.tesseraag.com` | 302 to `https://tesseraag-com.l.ink/`; redirect not followed. This is not evidence of the private portal being hosted there. |

The web reader initially could not open these origins; that was a tool limitation, **not outage evidence**. Direct HTTPS checks after network permission established the results above.

### Build/deployment reality

`Dockerfile` runs `uvicorn tessera_os.portal:create_portal_app --factory` on `${PORT:-8000}` as uid 10001. It copies source, config, agents, fixtures and web assets, but omits prompts. The package is not self-contained: `paths.project_root()` requires repository assets. A wheel installation alone outside a suitable root is not a complete deployment.

`.github/workflows/publish-container.yml` builds GHCR `latest` and `sha-` tags on main and deploys the exact short-SHA image via Azure federated login. It waits for the named revision and 100% traffic and performs health validation. `azure/login@v3` is tag-pinned while several other actions are commit-pinned. The publish/deploy workflow is **separate from CI**; its `deploy` depends on `publish`, not on the test workflow. Repository branch protections were not inspected, so passing CI cannot be assumed as an enforced precondition for every image publication.

GitHub confirmed [successful publish/deploy run 33207033169](https://github.com/DerrickLV/tessera-os/actions/runs/33207033169) and [CI run 33207033352](https://github.com/DerrickLV/tessera-os/actions/runs/33207033352), both for `c71e3fa` on 2026-08-28. The latest six runs inspected also include September 1 CI/Dependabot activity on other SHAs; they do not establish CI for this unpushed HEAD commit. Local HEAD is two commits beyond the serving tag: `ca6b921` documentation and `b973729` adoption-scope changes.

Documentation drift is substantial: `docs/DEPLOYMENT.md` says no Azure workflow/custom domain while both now exist; `docs/DEPLOY.md` describes a manual deploy loop and the rejected Azure origin; `docs/PORTAL_DEPLOYMENT.md`, `render.yaml`, `netlify.toml`, and parts of `.env.example` describe superseded split hosting. Treat verified Azure/API evidence as current. No redeploy, image build, rollback, sign-in, external write or credential change was performed.

## 6. Tests and coverage

### Executed

Tracked files were copied to a disposable directory; commands ran there using the repository's existing Python **3.12.14** virtual environment, with bytecode writes disabled and pytest's cache provider disabled. This prevented test-created SQLite files, fixture output or caches from changing the original checkout.

| Check | Result |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src <venv>/python -m pytest -p no:cacheprovider -q` | **641 passed in 5.13s**; no skips/failures reported. |
| `<venv>/ruff check --no-cache .` | All checks passed on tracked snapshot. |
| `<venv>/python scripts/security_scan.py` | Secret-pattern scan passed on tracked snapshot. |
| `<venv>/python -m pip check` | No broken requirements found. |
| Existing local SQLite read-only inspection | All three files `quick_check=ok`; content hashes unchanged. |
| Additional isolated API reproduction | Same human author could create, submit and accept a qualified-counsel draft; 200 responses, review creator `contract_manager`; zero route traces. |
| Additional isolated logout reproduction | No session supplied; 303 and unscoped broker disconnect. |
| Docker file-layout reproduction, without building image | Prompt absent; digest raises `FileNotFoundError`. |

These extra reproductions were not added to the repository as tests. No second full suite run was needed after report-only work.

### What the suite actually covers

- Routing/registry, CLI/configuration, JWT verification, policy denial, tenant/project boundaries, rate/budget/encryption primitives and SQLite serialization.
- Fake MSAL providers and injected Graph transports: consent/configuration rules, cache encryption, pagination, throttling, recursive library traversal, content extraction, zone/ACL behavior.
- Console/portal TestClient requests, production cookie-context simulation, synthetic guards, review transitions, artifacts and drafting, structure/intake, confirmed numbers, menu/sector/adoption rules, clause/document consistency and generated DOCX content.
- Fixture-driven proposal, development, diligence, contract, capital, construction, intelligence, engineering, assurance and sandbox automation library logic.

### Gaps

**No trustworthy line/branch coverage percentage is available.** `coverage`/`pytest-cov` are not installed in the audited venv and no coverage configuration/threshold/report is wired into CI. Test count is not a coverage percentage.

No live Microsoft/OpenAI end-to-end proof, production browser automation, deployed SMB fault/recovery test, load test, migration-version/rollback test or fresh vulnerability audit was run. Frontend tests frequently inspect source strings rather than driving a browser. CI declares Python 3.11 and 3.12, secret-pattern scan, ruff, pytest, wheel build and pip-audit; only local Python 3.12 checks listed above were executed here. Existing successful remote CI is for other commits. Health and fake-provider tests miss packaging, cross-layer author identity, audit integration and deployed credential validity.

## 7. Dead/unreferenced code and disconnected scaffolding

“Not connected to the deployed application” is more accurate than “useless” for much of this repository. Static import reachability was traced from `portal`, `console`, `service` and `cli`, then references were checked. Dynamic external consumers cannot be ruled out; test use is distinguished from runtime use. Exception classes with `pass` and Protocol method ellipses are normal declarations, not stub endpoint implementations.

### Implemented libraries with no entry-point import path

The following tracked modules are not reachable from those application entry points through imports:

| Modules | What exists / why it is not a live product capability |
|---|---|
| `capital.py`, `construction.py`, `contracts.py`, `development.py`, `diligence.py`, `manager_controls.py` | Real validated manager calculations/drafts and refusal controls, exercised in fixture tests. Not invoked by HTTP/CLI workflows. Routing to a similarly named prompt does not instantiate these managers. |
| `proposals.py` | Proposal library/manager, comparisons and document-related output; tests and disconnected intake library consumers. Not a proposal production endpoint. |
| `assurance.py`, `engineering.py`, `intelligence.py` | Assessment/release/monitoring packet logic with tests; no live monitoring loop, engineering worker, repository-write executor or alert delivery. |
| `automation.py` | Substantial approval/token/idempotency/kill-switch/receipt/hash-chain code, but only synthetic `sandbox.record.tag/restore` actions against in-memory records. No n8n or production executor/worker. |
| `diagnosis.py` | Agreement text diagnosis, tested; no API/CLI caller. |
| `intake.py` | Document-to-profile proposals, tested; not the `/structure/intake` endpoint, which accepts manual `VentureProfile` facts directly. |
| `formation.py` | Formation checklist builder, tested; no filing integration or API. |
| `digest.py` | Run-digest construction, tested; no scheduled job or digest endpoint. |
| `pilot.py` | Pilot workflows over Graph calendar/messages and knowledge index; tests only, no current production caller. Calendar/mail scopes are not permitted by current pilot settings. |
| `agreement_docx.py` | Working renderer used by tests and `scripts/generate_synthetic_structure_fixtures.py`; no production DOCX download API. |

`__init__.py` was excluded from this “disconnected” classification because package initialization is implicit. Referenced prompts, JSON manifests and dynamically loaded clause/config files are not dead merely because static Python imports do not name them.

### Disconnected functionality inside reachable modules

- `MicrosoftUserConnectionBroker` (`microsoft.py`) is tested but never constructed by portal/console; production still uses `MicrosoftConnectionBroker` with shared cache.
- `identity.build_user_context()` is tested but portal/console duplicate identity assembly rather than calling it.
- `SecureArtifactStore` and `RuntimeAuditStore.reserve_usage()` are implemented and tested, but the application paths do not use them for artifacts/model budgeting. Retention/backup/legal-hold claims belong to the unused secure store, not current production artifacts.
- `KnowledgeIndex` is imported indirectly for a scope exception, but no portal/console ingest/search pipeline constructs it. SharePoint content listing does not automatically populate a searchable runtime index or feed the LLM.
- `MicrosoftGraphReader.calendar_events()` and `recent_messages()` are used by the disconnected pilot helper/tests, not the live portal, and need permissions outside current allowed scopes.
- JSON agent `tools` names are displayed/loaded but not registered with SDK `Agent`; no function-tool/handoff network is assembled. Live orchestration chooses a single prompt/model.
- `agents/structure_manager.yaml` is not loaded by `AgentRegistry`, which only globs `*.json`. Its presence is not active agent configuration.
- Model-policy timeout/usage/trace settings and security-policy retention/encryption declarations should not be mistaken for universal runtime middleware.
- The console frontend has no calls to the menu-selection, approved-structure-to-draft or draft-agreement endpoints. Those APIs exist, but the current UI does not expose the entire backend workflow. The frontend does call real intake, number confirmation, review and artifact APIs.

### Local ignored leftovers and obsolete material

Five ignored conflict-copy source files exist locally: `governance 2.py`, `identity 2.py`, `intake 2.py`, `m365_readiness 2.py`, `sectors 2.py`. They are not tracked or imported through ordinary module names. Ignored `_to_delete/`, `.tessera-*.tar.gz`, `.env 2.example`, a failed old virtual environment and caches are local leftovers, not current tracked implementation. **They were left untouched.** `.dockerignore` does not mirror every gitignore conflict-copy/archive rule; a manual Docker build from this dirty-on-disk checkout may include ignored files in its context, unlike the clean GitHub checkout.

`render.yaml`/`netlify.toml` are obsolete deployment scaffolding relative to verified Azure hosting. Older readiness/build briefs describe intent and historical test states; they are evidence of plans, not proof of production execution. `fixtures/` is mixed: many test datasets are only evaluation assets, but the **clause library is actually loaded in production**, so deleting all fixtures as “dead code” would break drafting.

## Appendix A — exact constructor schema

Each block below is source constructor DDL, normalized only for surrounding indentation. The local observations and deployment limits above govern which tables were actually observed on disk. Review migration adds the same nullable columns if missing. No schema mutation was performed to inspect existing files.

### ReviewQueue — `src/tessera_os/review.py`

```sql
CREATE TABLE IF NOT EXISTS review_items (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT,
                created_by TEXT NOT NULL, workflow TEXT NOT NULL, title TEXT NOT NULL,
                body TEXT NOT NULL, evidence_json TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT,
                review_reason TEXT, required_reviewer_group TEXT,
                review_reason_category TEXT, amended_body TEXT)
```

### PilotArtifactStore — `src/tessera_os/workspace.py`

```sql
CREATE TABLE IF NOT EXISTS pilot_artifacts (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, client_id TEXT NOT NULL,
                project_id TEXT NOT NULL, created_by TEXT NOT NULL, artifact_json TEXT NOT NULL,
                status TEXT NOT NULL, review_item_id TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)
```

### RuntimeAuditStore — `src/tessera_os/runtime_controls.py`

```sql
CREATE TABLE IF NOT EXISTS usage_budgets (
                    tenant_id TEXT NOT NULL, workflow TEXT NOT NULL, day TEXT NOT NULL,
                    token_limit INTEGER NOT NULL, cost_limit REAL NOT NULL,
                    tokens_used INTEGER NOT NULL DEFAULT 0, cost_used REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (tenant_id, workflow, day)
                );
                CREATE TABLE IF NOT EXISTS traces (
                    correlation_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL, user_id TEXT NOT NULL, workflow TEXT NOT NULL,
                    agent_id TEXT NOT NULL, model_version TEXT NOT NULL,
                    prompt_version TEXT NOT NULL, policy_outcome TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL, tokens INTEGER NOT NULL,
                    cost_units REAL NOT NULL, error TEXT, created_at TEXT NOT NULL
                );
```

### SecureArtifactStore — `src/tessera_os/runtime_controls.py`

```sql
CREATE TABLE IF NOT EXISTS secure_artifacts (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT NOT NULL,
                category TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                legal_hold INTEGER NOT NULL DEFAULT 0)
```

### NumberConfirmationStore — `src/tessera_os/numbers.py`

```sql
CREATE TABLE IF NOT EXISTS number_confirmations (
                tenant_id TEXT NOT NULL, project_id TEXT NOT NULL, label TEXT NOT NULL,
                value INTEGER NOT NULL, confirmed_by TEXT NOT NULL, confirmed_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, project_id, label))
```

### MenuSelectionStore — `src/tessera_os/terms.py`

```sql
CREATE TABLE IF NOT EXISTS menu_selections (
                tenant_id TEXT NOT NULL, project_id TEXT NOT NULL, area TEXT NOT NULL,
                label TEXT NOT NULL, selected_by TEXT NOT NULL, selected_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, project_id, area))
```

### ActionControlStore — `src/tessera_os/automation.py`

```sql
CREATE TABLE IF NOT EXISTS approval_packets (
                    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, project_id TEXT NOT NULL,
                    request_json TEXT NOT NULL, request_digest TEXT NOT NULL,
                    approver_group TEXT NOT NULL, state TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    approved_by TEXT, approved_at TEXT, approval_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS consumed_tokens (
                    nonce TEXT PRIMARY KEY, packet_id TEXT NOT NULL, consumed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    id TEXT PRIMARY KEY, packet_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL, request_digest TEXT NOT NULL,
                    state TEXT NOT NULL, result_json TEXT NOT NULL,
                    rollback_json TEXT NOT NULL, executed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dead_letters (
                    id TEXT PRIMARY KEY, packet_id TEXT NOT NULL, request_digest TEXT NOT NULL,
                    error TEXT NOT NULL, attempts INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kill_switches (
                    tenant_id TEXT NOT NULL, action_type TEXT NOT NULL, active INTEGER NOT NULL,
                    reason TEXT NOT NULL, changed_by TEXT NOT NULL, changed_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, action_type)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
```
