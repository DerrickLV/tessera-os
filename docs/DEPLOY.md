# Deploying a change

Every deploy is the same five steps. Two machines are involved and mixing them
up is the most common way to lose half an hour: **`git` runs on the Mac**,
because that is where the repository is, and **`az` runs in Azure Cloud Shell**,
because that is where you are signed in to Azure. Neither can do the other's
job.

---

## 1. Commit and push — Mac terminal

```bash
cd ~/Documents/GitHub/tessera-os
python -m pytest -q && ruff check .
git add -A && git commit -m "<what changed and why>"
git push origin main
git log --oneline -1
```

The first token of that last line is the **short SHA**. It is the only thing you
carry to the next step.

Do not skip the tests. The container validates its own configuration at startup
and refuses to boot when something is inconsistent, so a bad change costs a full
build-and-deploy cycle to discover rather than four seconds.

## 2. Wait for the build

github.com/DerrickLV/tessera-os/actions → the run for that commit → green.
About 70 seconds.

A red run means **no image was published**, so there is nothing to deploy and
the currently running revision is unaffected. Read the failing step before
touching Azure.

## 3. Deploy — Cloud Shell

```bash
az containerapp update -n tessera-portal-api -g tessera-pilot-rg \
  --image ghcr.io/derricklv/tessera-os:sha-<short-sha>
```

Pin the SHA rather than using `latest`. Not fastidiousness: with `latest` there
is no way to say "go back to the build that worked", because `latest` has
already moved. With a SHA, rollback is this same command with an older one.

## 4. Verify — Cloud Shell

```bash
az containerapp revision list -n tessera-portal-api -g tessera-pilot-rg \
  --query "[].{name:name,state:properties.runningState,traffic:properties.trafficWeight,image:properties.template.containers[0].image}" -o table

curl -s https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io/health; echo
```

Healthy is: newest revision `RunningAtMaxScale`, traffic `100`, your SHA, and
`"console":"ok"`.

`"console":"unavailable"` means the portal came up and the console did not. That
is a deliberate degraded state rather than an outage — sign-in and SharePoint
still work — and the reason is in the logs.

## 5. Open it

A **fresh private window**, because the browser caches aggressively here and a
stale tab has more than once looked like a deployment failure.

Sign in at the portal root first, then go to `/console/`. Going straight to a
console URL while signed out returns 401 or bounces you back, by design.

---

## When a revision fails

The previous revision keeps serving, so a failed deploy is not an outage. Read
the reason before changing anything:

```bash
az containerapp logs show -n tessera-portal-api -g tessera-pilot-rg --tail 40 \
  | grep -iE "error|locked|traceback" | tail -10
```

| What you see | What it means |
|---|---|
| `RuntimeError: TESSERA_... must contain valid JSON` | Startup validation. An environment variable is missing or malformed. The message names it. |
| `database is locked` | A previous replica has not released its lock on the file share. Deactivate the non-serving revisions (below) and restart. |
| Revision stuck `Activating`, no application logs | The image could not be pulled. Check the tag exists and that the GHCR registry credential on the container app is still valid. |
| `Microsoft authorization state is invalid or expired` after sign-in | Not a deploy failure. The sign-in began on the previous revision and finished on this one; the flow state is held in memory. Sign in again. |

Clear stale revisions:

```bash
az containerapp revision list -n tessera-portal-api -g tessera-pilot-rg \
  --query "[?properties.trafficWeight==\`0\`].name" -o tsv \
  | xargs -I{} az containerapp revision deactivate -n tessera-portal-api -g tessera-pilot-rg --revision {}
```

## Rolling back

```bash
az containerapp update -n tessera-portal-api -g tessera-pilot-rg \
  --image ghcr.io/derricklv/tessera-os:sha-<last-good-sha>
```

`git log --oneline` on the Mac lists the candidates. This is the entire reason
step 3 pins a SHA.

## Changing configuration without changing code

Environment variables and secrets are set on the container app, not in the
repository, and each change creates a new revision on the current image:

```bash
az containerapp update -n tessera-portal-api -g tessera-pilot-rg \
  --set-env-vars "TESSERA_ALLOWED_USER_IDS=<oid>,<oid>"
```

One exception worth remembering: **never regenerate `TESSERA_M365_CACHE_KEY`
once Microsoft 365 is connected.** It decrypts the stored token cache, and a new
key makes every stored token unreadable — everyone has to reconnect, and the
failure presents as a Microsoft problem rather than a key rotation.
