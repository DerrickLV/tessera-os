# Tessera portal deployment

This guide adds a private Tessera OS pilot beside the existing public website:

- `www.tesseraag.com` remains the public Netlify marketing site.
- `app.tesseraag.com` is a second Netlify site containing the private portal UI.
- `api.tesseraag.com` is the Render-hosted Python API.
- Microsoft Entra signs in explicitly invited pilot users with per-user project scope.
- Microsoft Graph can read only explicitly mapped SharePoint project locations.

The repository is deployment-ready, but it cannot create or approve resources inside
Netlify, Porkbun, Render, Microsoft Entra, or SharePoint without an administrator signed
in to those services. Do not enter secrets in source control or support chat.

## Before starting

Create one empty, sanitized SharePoint pilot site and document library. Do not map a
live client site for the first test. Record these values in a password manager:

- Microsoft tenant ID;
- each pilot user's Entra **Object ID** (`oid`);
- the Tessera Partners security-group Object ID;
- one Tessera project ID, such as `internal-pilot`;
- SharePoint Graph site ID and document-library drive ID;
- optional folder item ID, otherwise use `root`.

## 1. Register Tessera in Microsoft Entra

1. Open **Microsoft Entra admin center → App registrations → New registration**.
2. Name it `Tessera OS Pilot`, choose **Accounts in this organizational directory
   only**, and register it.
3. Under **Authentication**, add a **Web** redirect URI:
   `https://api.tesseraag.com/v1/integrations/microsoft/callback`.
4. Under **API permissions**, add delegated Microsoft Graph permissions
   `User.Read` and `Sites.Selected` only. Do not add `Sites.Read.All`, any
   `ReadWrite` permission, mail, calendar, or broad `*.All` access.
5. Ask the Microsoft administrator to grant consent and then grant this application
   **read** access to only the sanitized pilot SharePoint site. `Sites.Selected` alone
   grants access to no sites.
6. Under **Token configuration**, add the security-groups claim to the ID token.
7. Under **Enterprise applications → Tessera OS Pilot → Properties**, require user
   assignment, then assign Derrick and Ryan directly.
8. Under **Certificates & secrets**, create a short-lived pilot client secret and copy its **Value**
   immediately. Store it in a password manager.
9. Record the **Application (client) ID** and **Directory (tenant) ID**.

Microsoft's selected-permissions procedure is documented at
<https://learn.microsoft.com/graph/permissions-selected-overview>.

## 2. Deploy the API on Render

1. Sign in to Render with GitHub and choose **New → Blueprint**.
2. Select the `DerrickLV/tessera-os` repository. Render reads `render.yaml` and creates
   `tessera-portal-api` with a small persistent encrypted-token disk.
3. Enter the secret values requested by the Blueprint:

   | Render variable | Value |
   |---|---|
   | `TESSERA_M365_TENANT_ID` | Directory/tenant ID |
   | `TESSERA_M365_CLIENT_ID` | Application/client ID |
   | `TESSERA_M365_CLIENT_SECRET` | Secret **Value**, not secret ID |
   | `TESSERA_ALLOWED_USER_IDS` | Comma-separated Object IDs for Derrick and Ryan |
   | `TESSERA_USER_PROJECTS` | Explicit per-user project mapping JSON shown below |
   | `TESSERA_M365_GROUP_MAP` | Entra group-to-Tessera role mapping shown below |
   | `TESSERA_M365_CACHE_KEY` | Output of `openssl rand -base64 32` |
   | `TESSERA_PROJECT_CATALOG` | Project display JSON shown below |
   | `TESSERA_M365_PROJECT_RESOURCES` | SharePoint mapping JSON shown below |

   Use compact one-line JSON:

   ```json
   {"internal-pilot":{"id":"internal-pilot","name":"Internal Pilot","summary":"Sanitized read-only SharePoint pilot"}}
   ```

   ```json
   {"internal-pilot":{"site_id":"YOUR_SITE_ID","drive_id":"YOUR_DRIVE_ID","folder_item_id":"root","zone":"internal"}}
   ```

   ```json
   {"DERRICK_OBJECT_ID":["internal-pilot"],"RYAN_OBJECT_ID":["internal-pilot"]}
   ```

   ```json
   {"PARTNERS_GROUP_OBJECT_ID":"tessera_partner"}
   ```

   The project keys must match exactly. The API refuses to start if they differ.
4. Deploy and confirm Render's health check reports healthy at
   `https://api.tesseraag.com/health`. It must return:
   `{"status":"ok","mode":"production"}`.
5. In Render, verify the custom domain `api.tesseraag.com`. Render will display the
   required DNS target and certificate status.

## 3. Add API DNS in Porkbun

In Porkbun **Domain Management → DNS Records** for `tesseraag.com`, add the exact CNAME
Render supplies:

- Type: `CNAME`
- Host: `api`
- Answer: the Render hostname shown for the service

Do not change the existing `www` or apex records. Wait for Render to show the custom
domain and TLS certificate as verified.

## 4. Deploy the private UI as a second Netlify site

1. In Netlify choose **Add new site → Import an existing project** and select the same
   GitHub repository.
2. Leave the build command empty. `netlify.toml` publishes the `web` directory.
3. Add the custom domain `app.tesseraag.com`. Netlify will display the site's
   `*.netlify.app` DNS target.
4. In Porkbun add:

   - Type: `CNAME`
   - Host: `app`
   - Answer: the exact `*.netlify.app` target Netlify supplied

5. Wait for Netlify to show the custom domain and TLS certificate as active, then open
   `https://app.tesseraag.com`.

This should be a **new Netlify site**, not a replacement for the public
`www.tesseraag.com` site.

## 5. Link the existing public website

In the source or visual editor for the current marketing website, add a header button
named **Client Portal** linking to `https://app.tesseraag.com`. The marketing-site
source is not in this repository, so this is the only website edit that must be made in
the existing Netlify project or the tool that generated it.

## 6. First controlled sign-in

1. Visit `https://app.tesseraag.com` and select **Sign in with Microsoft**.
2. Sign in separately as Derrick and Ryan. A different Microsoft Object ID is rejected,
   and each user receives only the projects listed in `TESSERA_USER_PROJECTS`.
3. Open the mapped project and confirm only the sanitized SharePoint documents appear.
4. Confirm that another project ID and an unapproved account are denied.
5. Use **Sign out** and confirm the encrypted Microsoft token cache is disconnected.

The browser receives only an eight-hour, API-host-only, HTTP-only session cookie. It
never receives a Microsoft access or refresh token. The initial API exposes only GET
operations for project documents; Microsoft, SharePoint, email, calendar, submission,
publishing, approval, and baseline writes remain disabled.

## Stop or roll back

1. Suspend the Render service.
2. Revoke the Entra client secret and the selected SharePoint site permission.
3. Remove the `app` and `api` CNAME records in Porkbun if the pilot is ending.
4. Delete the Render persistent disk only after confirming the pilot is closed; this
   irreversibly removes the encrypted token cache.

Do not expand beyond the two named pilot users until the identity and project mappings
receive another security review.
