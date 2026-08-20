#!/usr/bin/env bash
#
# Point the Azure Container App at the real Tessera OS image.
#
# Until this runs, tessera-portal-api serves Microsoft's k8se/quickstart
# placeholder. The infrastructure is correct; the application has never been
# deployed into it.
#
# HOW TO USE
#   1. Fill in every ►► FILL IN ◄◄ value below.
#   2. Paste the whole file into Azure Cloud Shell (bash), or upload and run it.
#   3. Do not commit this file with real values in it.
#
# The app validates its own configuration on startup and refuses to boot if
# anything is missing or inconsistent. That is deliberate — a portal that starts
# with half its identity configuration is more dangerous than one that does not
# start at all — but it means everything here has to be right together.

set -euo pipefail

APP=tessera-portal-api
RG=tessera-pilot-rg
API_URL="https://tessera-portal-api.delightfulground-393766a4.westus2.azurecontainerapps.io"

# ── 1. GitHub token, so Azure can pull from your private package ──────────────
# github.com → Settings → Developer settings → Personal access tokens (classic)
# → Generate new token → tick ONLY `read:packages`.
GITHUB_USER="DerrickLV"
GITHUB_TOKEN="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"

# ── 2. Microsoft Entra ────────────────────────────────────────────────────────
# Entra admin center → App registrations → your app → Overview
M365_TENANT_ID="eb991bbe-f3f2-4a09-8a2e-20ee2984d030"     # "Directory (tenant) ID"
M365_CLIENT_ID="ed1bf367-56b6-48cd-b20b-dba0aefdaec6"     # "Application (client) ID"
M365_CLIENT_SECRET="bV88Q~dt1mgVCS3Jw~dL~9.-qhX30idQ2xtPyauZ" # Certificates & secrets → the secret VALUE
# Comma-separated Entra Object IDs. Yours alone works for a first boot, but the
# review queue refuses to let an author approve their own draft, so a second
# reviewer is required before anything can actually be accepted.
ALLOWED_USER_IDS="592a1eef-eeaa-4470-9db0-38b78fbd91d0,cb82cae5-4dfd-43ab-9dae-b3062534d0fa"   # e.g. "your-oid" or "your-oid,ryans-oid"

# ── 3. SharePoint pilot site ──────────────────────────────────────────────────
# See scripts/find-sharepoint-ids.md for how to get these two.
SP_SITE_ID="tesseragroup581.sharepoint.com,86c8bad2-c144-4e3b-ac08-ed772e7c1f9c,788d6e24-cb4b-43e5-9eba-b483e730f5ea"
SP_DRIVE_ID="b!0rrIhkTBO06sCO13LnwfnCRujXhLy-VDnrq0g-cw9eqqVvbEY83hQ7p2jgEMSVl5"

# ── 4. Generated secrets — leave as-is, these create themselves ───────────────
SESSION_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
M365_CACHE_KEY="$(openssl rand -base64 32 | tr -d '\n')"

echo "==> Registering GitHub Container Registry credentials"
az containerapp registry set -n "$APP" -g "$RG" \
  --server ghcr.io --username "$GITHUB_USER" --password "$GITHUB_TOKEN" >/dev/null

echo "==> Storing secrets in the container app"
az containerapp secret set -n "$APP" -g "$RG" --secrets \
  "session-secret=$SESSION_SECRET" \
  "m365-client-secret=$M365_CLIENT_SECRET" \
  "m365-cache-key=$M365_CACHE_KEY" >/dev/null

echo "==> Setting configuration"
# One project, internal zone. The zone defaults to the most restrictive value so
# a mapping that forgets to declare one fails closed. A client engagement folder
# would be zone "engagement" and would also have to name its client.
PROJECT_CATALOG='{"internal-pilot":{"id":"internal-pilot","name":"Internal Pilot","summary":"First live project"}}'
PROJECT_RESOURCES="{\"internal-pilot\":{\"site_id\":\"$SP_SITE_ID\",\"drive_id\":\"$SP_DRIVE_ID\",\"folder_item_id\":\"root\",\"zone\":\"internal\"}}"

az containerapp update -n "$APP" -g "$RG" \
  --image ghcr.io/derricklv/tessera-os:latest \
  --set-env-vars \
    "TESSERA_ENV=production" \
    "TESSERA_APP_URL=$API_URL" \
    "TESSERA_API_URL=$API_URL" \
    "TESSERA_PORTAL_DATA_DIR=/var/data/tessera" \
    "TESSERA_SESSION_SECRET=secretref:session-secret" \
    "TESSERA_ALLOWED_USER_IDS=$ALLOWED_USER_IDS" \
    "TESSERA_PROJECT_CATALOG=$PROJECT_CATALOG" \
    "TESSERA_M365_ENABLED=true" \
    "TESSERA_M365_TENANT_ID=$M365_TENANT_ID" \
    "TESSERA_M365_CLIENT_ID=$M365_CLIENT_ID" \
    "TESSERA_M365_CLIENT_SECRET=secretref:m365-client-secret" \
    "TESSERA_M365_CACHE_KEY=secretref:m365-cache-key" \
    "TESSERA_M365_REDIRECT_URI=$API_URL/v1/integrations/microsoft/callback" \
    "TESSERA_M365_PROJECT_RESOURCES=$PROJECT_RESOURCES" >/dev/null

echo "==> Waiting for the new revision"
sleep 30

echo "==> Health"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" "$API_URL/health" || true

echo "==> Running image"
az containerapp show -n "$APP" -g "$RG" \
  --query "properties.template.containers[0].image" -o tsv

echo
echo "If health is not 200, read the logs:"
echo "  az containerapp logs show -n $APP -g $RG --tail 60"
echo
echo "To roll back to the placeholder while you investigate:"
echo "  az containerapp update -n $APP -g $RG --image mcr.microsoft.com/k8se/quickstart:latest"
