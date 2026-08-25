# Tessera OS — working agreement

Read this before changing anything. It is short on purpose: it records the
constraints that are expensive to rediscover, not the things you can read off
the code.

## What this is

A policy-aware operating system for a capital advisory firm. It produces
structure recommendations and draft agreements, holds them in a durable review
queue, and requires a second human to accept anything. Two people use it:
Derrick Carlisle and Ryan Strasshofer.

Production runs on Azure Container Apps at
`https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io`
— the portal at `/`, the console mounted at `/console`. See `docs/DEPLOY.md`.

## Commands

```bash
python -m pytest -q          # ~610 tests, seconds
ruff check .                 # CI runs this; keep it clean
python scripts/security_scan.py   # committed-credential scan; CI runs it
```

All three must pass before a commit. CI runs the same three plus `pip-audit`.

## Invariants

These are not preferences. Each one exists because of a specific failure, and
several were violated at least once already.

**Provenance is the product.** Every position carries a `basis`:
`tessera_adopted`, `synthetic_reference`, or `scaffold`. Never promote a
position to `tessera_adopted` in code — that happens only through
`config/adopted_positions.yaml`, which requires two named partners and a
citation. Adoption is data, not a ratchet.

**No real agreement text in the repository.** Clause language is synthetic or
generic. Positions Tessera has actually adopted are recorded in the ledger *by
reference* — never by reproducing the source document.

**The memo and the document must agree.** A value appearing in both travels
through `StructureRecommendation.derived_values()`. `expected_clause_categories()`
is the engine declaring what its own advice requires the paper to contain, and
`tests/test_memo_document_parity.py` enforces it. Seven categories once went
missing while the memo kept promising them and every coverage check passed.

**Separation of duties is enforced, not displayed.** The review queue refuses to
let an author disposition their own item. Privileged groups come from Entra
through `EntraGroupMap` — never from code, never defaulted. An absent groups
claim grants nothing; that is the groups-overage case and it fails closed.

**Trust zones are checked on every read.** Zone 01 (Internal) resources are
readable only by `tessera_partner`. An unmapped resource is Internal by default.
Internal originals never leave zone 01 — a copy goes to the engagement
workspace and the copy gets cited.

**Nothing acts outside the system.** No sending, filing, publishing, executing,
or SharePoint writes. `ExternalActionDisabled` is the default and adding a scope
is a policy decision with a named owner, not an environment variable. The
Microsoft scopes are `User.Read` and `Sites.Selected`, and nothing else.

**Synthetic surfaces stay closed in production.** `workspace/run`,
`workspace/compare`, and `workspace/reset` return or restore pre-authored
fixture content; in production their output would be indistinguishable in the
interface from a real engine result. `refuse_in_production()` guards them.

**The console must never show fabricated data to a signed-out user.** The
interface falls back to its embedded sample dataset only when served standalone.
On the portal origin a failed bootstrap is an error, and a 401 is a redirect to
sign in.

## Production constraints that look like preferences

- **`maxReplicas` is pinned to 1.** SQLite on an SMB share is safe with one
  writer and unsafe with several. Raising it requires PostgreSQL first.
- **SQLite opens through `sqlite_store.connect()`** — `unix-dotfile` VFS, because
  Azure Files does not implement the byte-range locks SQLite uses. Never call
  `sqlite3.connect()` directly for a durable store, and never enable WAL.
- **The console is mounted on the portal, not deployed beside it.** The session
  cookie is `SameSite=Lax`; a separate origin signs in successfully and then
  401s on every call.
- **Each app states its own Content-Security-Policy.** The portal's middleware
  wraps the mount and uses `setdefault` so it does not impose `script-src 'self'`
  on the console, whose interface is one inline script.
- **Never regenerate `TESSERA_M365_CACHE_KEY`** once Microsoft 365 is connected.
  It decrypts the stored token cache.
- **No credential in a file.** `scripts/deploy-azure.sh` reads every secret at a
  prompt. A "FILL IN" line for a secret is a shape that invites a leak; one
  happened.

## Style

- Line length 100, `py311`, ruff-clean.
- Comments explain *why*, and name the failure being prevented. A comment that
  restates the code is noise; a comment that says "this was 1, which deadlocked
  the system" is why the next person doesn't undo it.
- Docstrings on non-obvious functions carry the reasoning, not a signature
  restatement.
- Tests assert the invariant and say so in the docstring. Prefer a test that
  demonstrates the behaviour over one that asserts about it.

## Deploying

`docs/DEPLOY.md` is authoritative. Two machines: `git` on the Mac, `az` in Azure
Cloud Shell. Pushing to `main` builds and deploys the SHA it built, then fails
the run if `/health` does not report `"console":"ok"`.

A failed revision keeps the previous one serving — a bad deploy is not an
outage. Roll back by deploying an older `sha-` tag.
