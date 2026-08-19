# Microsoft 365 launch path

This is the shortest safe path to a private Tessera pilot for Derrick and Ryan.
The first release connects Microsoft sign-in and one sanitized, read-only
SharePoint site. It does not connect email, calendars, Teams, or SharePoint
write-back.

## What Tessera now checks

Run this from the repository after activating the Python 3.12 environment:

```bash
tessera m365-check
```

`[FIX]` means a Render environment value is missing or inconsistent. `[YOU]`
means Microsoft requires an administrator to confirm the setting. The command
never contacts Microsoft, prints a secret, or changes configuration.

## Part 1 — Microsoft Entra

1. Open **Entra admin center → App registrations → Tessera OS Pilot**.
2. Confirm **this organizational directory only**.
3. Add the Web redirect URI exactly:
   `https://api.tesseraag.com/v1/integrations/microsoft/callback`.
4. Add delegated Microsoft Graph permissions `User.Read` and `Sites.Selected`
   only, then grant admin consent.
5. Under **Token configuration**, add the security-groups claim to the ID token.
6. Create security groups named **Tessera Partners** and **Tessera Qualified
   Counsel**. Put Derrick and Ryan in Partners. Leave Qualified Counsel empty
   until actual counsel is assigned.
7. Open **Enterprise applications → Tessera OS Pilot → Properties**, set
   **Assignment required** to Yes, and assign Derrick and Ryan directly.
8. Record the tenant ID, client ID, both user Object IDs, and the Partners group
   Object ID in the password manager.
9. For the internal pilot, create a short-lived client secret and store its
   value only in the password manager and Render. Before live client data, move
   the application to a certificate credential.

## Part 2 — SharePoint

1. Create a private site named **Tessera Pilot**.
2. Give Derrick and Ryan access.
3. Create `Projects/Internal Pilot/{Source,Drafts,Approved}` and
   `Templates/{Word,Excel}`.
4. Put synthetic documents in `Source`.
5. Grant the Tessera application the `read` role on this site through the
   `Sites.Selected` process.
6. Record the Graph site ID, drive ID, and optional folder item ID.

## Part 3 — Render

Set the secret and configuration values requested by `render.yaml`. Use these
shapes, replacing placeholders inside Render—not in GitHub:

```text
TESSERA_PROJECT_CATALOG={"internal-pilot":{"id":"internal-pilot","name":"Internal Pilot","summary":"Sanitized read-only pilot"}}
TESSERA_ALLOWED_USER_IDS=DERRICK_OBJECT_ID,RYAN_OBJECT_ID
TESSERA_USER_PROJECTS={"DERRICK_OBJECT_ID":["internal-pilot"],"RYAN_OBJECT_ID":["internal-pilot"]}
TESSERA_M365_GROUP_MAP={"PARTNERS_GROUP_OBJECT_ID":"tessera_partner"}
TESSERA_M365_PROJECT_RESOURCES={"internal-pilot":{"site_id":"SITE_ID","drive_id":"DRIVE_ID","folder_item_id":"root","zone":"internal"}}
```

Also set the tenant ID, client ID, credential value, cache key, and exact
production redirect URI. Never paste those secret values into chat or GitHub.

Run `tessera m365-check` in a local shell populated with the same values. It
must contain no `[FIX]` lines.

## Part 4 — domains and deployment

1. Deploy the Render Blueprint and connect `api.tesseraag.com` using the CNAME
   Render provides.
2. Deploy `web/` as a second Netlify site and connect `app.tesseraag.com` using
   Netlify's CNAME.
3. Do not alter the existing `www.tesseraag.com` marketing-site records.
4. Confirm `https://api.tesseraag.com/health` returns production mode with
   writes disabled.

## Part 5 — two-user acceptance test

Use separate browsers or private windows.

1. Derrick signs in and opens Internal Pilot documents.
2. Ryan signs in at the same time and opens the same permitted project.
3. Confirm logging Ryan out does not disconnect Derrick.
4. Confirm an unassigned Microsoft account is denied.
5. Remove Ryan from the Enterprise Application temporarily and confirm his next
   sign-in is denied; then restore the assignment.
6. Request an unmapped project and confirm it is denied.
7. Confirm no create, upload, update, delete, send, approval-bypass, or baseline
   mutation endpoint exists.

Only after these checks pass should the private two-user pilot be announced as
live. Live client documents, Office write-back, Outlook, Calendar, and Teams are
separate later gates.
