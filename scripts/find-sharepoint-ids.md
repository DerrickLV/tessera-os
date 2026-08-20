# Finding your SharePoint site and drive IDs

Two values are needed before the portal can start. Both come from Microsoft
Graph Explorer, which signs in as you and requires no setup.

**Create an empty pilot site first.** Do not point the first run at a live
client folder — SharePoint → Create site → Team site → name it `Tessera Pilot`.

Then open **developer.microsoft.com/graph/graph-explorer** and sign in with the
same Microsoft account.

## 1. Site ID

Run this, substituting your tenant name and the site name:

```
https://graph.microsoft.com/v1.0/sites/YOURTENANT.sharepoint.com:/sites/TesseraPilot
```

In the response, copy the `id` field. It is long and comma-separated, like:

```
yourtenant.sharepoint.com,8f2c...,4a91...
```

Copy the **whole thing**, commas included.

## 2. Drive ID

Using the site ID you just copied:

```
https://graph.microsoft.com/v1.0/sites/PASTE_SITE_ID_HERE/drives
```

Find the drive named **Documents** and copy its `id`.

## 3. Grant the app access to this site

`Sites.Selected` gives your app no access to anything until a specific site is
granted. That grant is a separate administrative step — without it the portal
signs in successfully and then returns no documents, which reads like a bug and
is not one.

Your Microsoft 365 admin does this, or you do it if you hold the role. Confirm
it before assuming a document-listing failure is a code problem.
