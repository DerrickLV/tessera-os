# Deployment Record

Tessera OS runs on **Microsoft Azure**, built out with Codex's help in the Azure
portal. This document exists because that build is not described anywhere else:
there is no Bicep, no `azure.yaml`, and no Azure workflow in this repository, so
the only record of how production is wired was a Codex session and one person's
memory. That is the gap this file closes.

> **Sections marked `TO RECORD` are blanks Derrick fills from the Azure portal.**
> They are deliberately empty rather than guessed — a plausible-looking wrong
> resource name in a deployment record is worse than an obvious blank.

---

## What is verifiable from the repository

**Container image.** `.github/workflows/publish-container.yml` builds on every
push to `main` and publishes to:

```
ghcr.io/derricklv/tessera-os:latest
ghcr.io/derricklv/tessera-os:sha-<commit>
```

That image is what Azure pulls. The `sha-` tags matter: pinning to a specific
SHA rather than `latest` is what makes a rollback a one-line change.

**What the image runs.** `Dockerfile` → `uvicorn tessera_os.portal:create_portal_app
--factory --host 0.0.0.0 --port ${PORT:-8000}`, as a non-root user (uid 10001).

**What the running app requires, regardless of host:**

| Requirement | Why it constrains the hosting choice |
|---|---|
| **Persistent disk** at `TESSERA_PORTAL_DATA_DIR` | SQLite artifact store — the review queue, every decision, the audit chain — plus the encrypted MSAL token cache. Ephemeral storage loses all of it on redeploy. |
| **Stable HTTPS origin** | The Entra redirect URI is registered against an exact URL. It cannot be a per-deploy hostname. |
| **Seven secrets** | Listed below. None may live in the repository. |
| `/health` | Health probe endpoint. |

**Environment variables** (names are authoritative; values are not in the repo):

`TESSERA_ENV` · `TESSERA_APP_URL` · `TESSERA_API_URL` · `TESSERA_PORTAL_DATA_DIR` ·
`TESSERA_SESSION_SECRET` · `TESSERA_M365_ENABLED` · `TESSERA_M365_REDIRECT_URI` ·
`TESSERA_M365_TENANT_ID` · `TESSERA_M365_CLIENT_ID` · `TESSERA_M365_CLIENT_SECRET` ·
`TESSERA_M365_CACHE_KEY` · `TESSERA_M365_GROUP_MAP` · `TESSERA_M365_PROJECT_RESOURCES` ·
`TESSERA_PROJECT_CATALOG` · `TESSERA_ALLOWED_USER_IDS`

---

## Azure topology — `TO RECORD`

| Item | Value |
|---|---|
| Subscription | `1ce8bb84-5eaa-4b82-9262-705b70f9b117` |
| Resource group | `tessera-pilot-rg` |
| Service hosting the API | Azure Container Apps |
| Managed environment | `tessera-pilot-env` |
| Container app | `tessera-portal-api` |
| Region | `westus2` |
| Public URL | `https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io` |
| Portal UI | Served by the same container app at `/`. No separate static host. |
| Replicas | min 1, max 1 — pinned, see note below |
| Custom domains | None yet. `tesseraag.com` is on Porkbun and unconnected. |

**Persistent storage — `TO RECORD`**

| Item | Value |
|---|---|
| Storage account | `tesseradata2026` (Standard_LRS, westus2) |
| File share | `tessera-data`, 5 GB quota |
| Environment storage link | `tessera-data`, ReadWrite |
| Mount path in container | `/var/data` |
| `TESSERA_PORTAL_DATA_DIR` | `/var/data/tessera` — inside the mounted share |

**History, recorded because it will otherwise be repeated.** Until 20 August 2026
there was no storage account in this subscription at all, and `minReplicas` was
`0`. The artifact store — the review queue, every decision, the audit chain —
and the encrypted Microsoft token cache were written to the container's own
disk, and Azure recycles that disk whenever the app scales to zero. State was
being destroyed several times a day, not merely on deploy. Nothing of record was
lost because no real decisions had been entered yet.

**Why `maxReplicas` is also 1.** The artifact store is SQLite on an SMB file
share. SQLite is safe there with a single writer and unsafe with several. The
replica ceiling is a correctness constraint, not a cost decision — raising it
requires moving the store to PostgreSQL first.

**Secrets — `TO RECORD`** (record *where they live*, never the values)

| Item | Value |
|---|---|
| Key Vault name, or Container App secrets | |
| Managed identity used to read them | |
| `TESSERA_M365_CACHE_KEY` rotation plan | |

**How a deploy happens today — `TO RECORD`**

- [ ] Azure pulls `ghcr.io/derricklv/tessera-os` automatically on new image, or
- [ ] Deploy is triggered manually — by what command or click?
- [ ] Image tag in use: `latest` / pinned `sha-`
- [ ] How to roll back:

**Entra redirect URI — must match exactly**

```
https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io/v1/integrations/microsoft/callback
```

Registered in Entra → App registrations → Authentication, and mirrored in the
container app's `TESSERA_M365_REDIRECT_URI`. A mismatch produces a sign-in
failure that does not name its own cause. When a custom domain is added, this
value changes in both places or sign-in breaks.

---

## Now-vestigial files

Both describe a deployment that was designed and then not used. They should
either be deleted or annotated, because the next person to read the repository
will believe them:

| File | Status |
|---|---|
| `render.yaml` | Describes a Render service with a 1GB disk. Superseded by Azure. |
| `netlify.toml` | Superseded. The portal UI is served by the container app itself; its CSP now lives in `portal.py`. |

Neither is in use. The portal UI is served from the container app at `/`,
deliberately: the session cookie is issued `SameSite=Lax`, and a browser will not
attach a Lax cookie to a cross-origin request. A UI on Netlify or Vercel would
have produced a sign-in that appeared to succeed followed by silent 401s on every
subsequent call. One origin removes the failure mode rather than configuring
around it.

---

## Why this record is worth keeping current

The system holds a review queue with legal significance, an encrypted token
cache, and an audit chain. Three consequences follow:

1. **The volume is load-bearing.** Confirming it is mounted is a five-minute
   check that prevents silent data loss.
2. **The Entra redirect URI is a coupling** between an Azure hostname and an app
   registration. Change either and sign-in breaks with an error that does not
   name the cause.
3. **Rebuilding from memory does not work.** Infrastructure built by hand in a
   portal, guided by a session that has since ended, exists only as long as it
   keeps running. Recording it — or better, exporting it to Bicep — is what
   makes it survivable.

**Suggested next step:** run `az group export --name <resource-group>` and commit
the resulting template. It is not beautiful infrastructure-as-code, but it turns
"built by hand in the portal" into something that can be read, diffed, and
rebuilt.
