#!/usr/bin/env bash
#
# One-time bootstrap for the Azure Container App.
#
# Routine deploys no longer run this: pushing to main builds the image and
# deploys it, and docs/DEPLOY.md describes that loop. What remains here is the
# first-run wiring -- registry credentials, secrets, and configuration -- and
# the same commands if any of it has to be re-established.
#
#   bash scripts/deploy-azure.sh
#
# Run it as a file, never pasted into an interactive shell: this sets -e, and in
# an interactive shell the first failing command closes the session, which looks
# exactly like a dropped connection.
#
# ─────────────────────────────────────────────────────────────────────────────
# NOTHING SECRET IS WRITTEN IN THIS FILE, AND NOTHING SECRET MAY BE ADDED TO IT.
#
# An earlier version had a "FILL IN" line for the GitHub token. It was filled
# in, committed, and pushed, and the token then lived in the repository's
# history until it was revoked. The file could not have prevented that, but its
# shape invited it. Every secret below is now read at the prompt, held in a
# shell variable, and unset -- so there is no version of this file that is
# dangerous to commit.
#
# scripts/security_scan.py fails CI on a committed credential. It caught that
# one. Do not work around it.
# ─────────────────────────────────────────────────────────────────────────────

set -uo pipefail

APP=tessera-portal-api
RG=tessera-pilot-rg
API_URL="https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io"
GITHUB_USER="DerrickLV"
SP_SITE_ID="tesseragroup581.sharepoint.com,86c8bad2-c144-4e3b-ac08-ed772e7c1f9c,788d6e24-cb4b-43e5-9eba-b483e730f5ea"

die() { echo; echo "STOPPED: $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }

step "Reading what Azure already knows"
TENANT_ID="$(az account show --query tenantId -o tsv 2>/dev/null)" \
  || die "Not signed in to Azure CLI."
MY_OID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null)" \
  || die "Could not read your Entra object ID."
SP_DRIVE_ID="$(az rest --method GET \
  --url "https://graph.microsoft.com/v1.0/sites/${SP_SITE_ID}/drives" \
  --query "value[0].id" -o tsv 2>/dev/null)"
[ -n "${SP_DRIVE_ID:-}" ] || die "Could not read the pilot site's document library."
echo "  tenant $TENANT_ID / drive ${SP_DRIVE_ID:0:18}..."

echo
echo "Four values are needed. Input is hidden and nothing is written to disk."
echo
read -rsp "GitHub PAT (classic, read:packages only): " GITHUB_TOKEN; echo
[ -n "$GITHUB_TOKEN" ] || die "No GitHub token entered."
read -rp  "Entra Application (client) ID:            " M365_CLIENT_ID
[ -n "$M365_CLIENT_ID" ] || die "No client ID entered."
read -rsp "Entra client secret VALUE:                " M365_CLIENT_SECRET; echo
[ -n "$M365_CLIENT_SECRET" ] || die "No client secret entered."
read -rp  "Second reviewer's Entra object ID:        " SECOND_OID
ALLOWED_USER_IDS="$MY_OID"
[ -n "${SECOND_OID:-}" ] && ALLOWED_USER_IDS="$MY_OID,$SECOND_OID"

# GHCR speaks the Docker registry token handshake: Basic credentials buy a
# scoped bearer token, and only that token reads a manifest. Sending the PAT
# straight at /v2/ returns 401 with a message blaming the credential.
step "Checking the image is reachable before changing anything"
GHCR_TOKEN="$(curl -s -u "$GITHUB_USER:$GITHUB_TOKEN" \
  "https://ghcr.io/token?service=ghcr.io&scope=repository:derricklv/tessera-os:pull" \
  | jq -r '.token // empty')"
curl -sf -H "Authorization: Bearer $GHCR_TOKEN" \
  "https://ghcr.io/v2/derricklv/tessera-os/tags/list" >/dev/null \
  || die "GHCR rejected that token, or the package does not exist. Nothing was changed."
echo "  image reachable"

step "Registering registry credentials"
az containerapp registry set -n "$APP" -g "$RG" \
  --server ghcr.io --username "$GITHUB_USER" --password "$GITHUB_TOKEN" >/dev/null \
  || die "Could not register GHCR credentials."

step "Storing secrets"
EXISTING="$(az containerapp secret list -n "$APP" -g "$RG" --query "[].name" -o tsv 2>/dev/null)"
SECRET_ARGS=("m365-client-secret=$M365_CLIENT_SECRET")
if echo "$EXISTING" | grep -qx "session-secret"; then
  echo "  session-secret preserved"
else
  SECRET_ARGS+=("session-secret=$(openssl rand -base64 48 | tr -d '\n')")
fi
# Regenerating this makes every stored Microsoft token unreadable and forces
# everyone to reconnect, so an existing one is never replaced.
if echo "$EXISTING" | grep -qx "m365-cache-key"; then
  echo "  m365-cache-key preserved -- the token cache stays readable"
else
  SECRET_ARGS+=("m365-cache-key=$(openssl rand -base64 32 | tr -d '\n')")
fi
az containerapp secret set -n "$APP" -g "$RG" --secrets "${SECRET_ARGS[@]}" >/dev/null \
  || die "Could not store secrets."

step "Setting configuration"
PROJECT_CATALOG='{"internal-pilot":{"id":"internal-pilot","name":"Internal Pilot","summary":"First live project"}}'
PROJECT_RESOURCES="{\"internal-pilot\":{\"site_id\":\"$SP_SITE_ID\",\"drive_id\":\"$SP_DRIVE_ID\",\"folder_item_id\":\"root\",\"zone\":\"internal\"}}"

az containerapp update -n "$APP" -g "$RG" \
  --set-env-vars \
    "TESSERA_ENV=production" \
    "TESSERA_APP_URL=$API_URL" \
    "TESSERA_API_URL=$API_URL" \
    "TESSERA_PORTAL_DATA_DIR=/var/data/tessera" \
    "TESSERA_SESSION_SECRET=secretref:session-secret" \
    "TESSERA_ALLOWED_USER_IDS=$ALLOWED_USER_IDS" \
    "TESSERA_PROJECT_CATALOG=$PROJECT_CATALOG" \
    "TESSERA_M365_ENABLED=true" \
    "TESSERA_M365_TENANT_ID=$TENANT_ID" \
    "TESSERA_M365_CLIENT_ID=$M365_CLIENT_ID" \
    "TESSERA_M365_CLIENT_SECRET=secretref:m365-client-secret" \
    "TESSERA_M365_CACHE_KEY=secretref:m365-cache-key" \
    "TESSERA_M365_REDIRECT_URI=$API_URL/v1/integrations/microsoft/callback" \
    "TESSERA_M365_PROJECT_RESOURCES=$PROJECT_RESOURCES" >/dev/null \
  || die "The container app update failed."

unset GITHUB_TOKEN M365_CLIENT_SECRET GHCR_TOKEN

step "Result"
echo -n "  image:  "; az containerapp show -n "$APP" -g "$RG" \
  --query "properties.template.containers[0].image" -o tsv
echo -n "  health: "; curl -s "$API_URL/health"; echo

cat <<EOF

Expected: {"status":"ok",...,"console":"ok"}.

"console":"unavailable" means the portal is up and the console did not mount.
That is a degraded state, not an outage -- the reason is in the container logs:
  az containerapp logs show -n $APP -g $RG --tail 60

The Entra redirect URI must be exactly:
  $API_URL/v1/integrations/microsoft/callback
EOF
