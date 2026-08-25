# Build Brief — Phase 2 (Revised): Library-Shaped Document Reading

**Status:** ready to build
**Supersedes:** Phase 2 of `docs/BUILD_BRIEF_STRUCTURE_INTAKE.md` (cap table / parties /
effective date), which is not cancelled — it moves to Phase 2B and is unblocked by
nothing in this document.
**Prerequisite:** Phase 1 (`b41b4da`) — shipped, serving in production as revision
`tessera-portal-api--p10237`.

---

## 1. Why this jumped the queue

The portal reports **"No approved documents found"** for a project whose SharePoint
library is correctly configured, correctly permissioned, and reachable. Every layer
below the reader works: the Entra group map resolves, `ZonePolicy.check_read` passes,
the Graph token is valid, the `site_id` and `drive_id` in
`TESSERA_M365_PROJECT_RESOURCES` point at the right library.

The reader itself cannot see the library's contents, because it assumes a shape the
library does not have — and would not have in any real engagement.

This blocks every downstream document workflow: adoption, citation, review,
memo-to-document parity. It is worth doing before more intake fields.

---

## 2. Evidence

### 2.1 What the library actually looks like

Site: **Tessera Pilot** (`tesseragroup581.sharepoint.com,86c8bad2-…`) — the site the
configuration already names, correctly.

```
Documents/                      <- drive root; contains no files
├── Projects/
│   └── Internal Pilot/
│       ├── Approved/
│       ├── Drafts/
│       └── Source/
└── Templates/
```

The drive root holds **two folders and zero files**.

### 2.2 What the reader does

`src/tessera_os/integrations.py:95–119`, `sharepoint_documents()`:

| Line | Behaviour | Consequence for the library above |
|---|---|---|
| 100–101 | Requests `…/root/children` — one folder, no recursion | Sees `Projects` and `Templates`; never descends |
| 108 | `if fields.get("ProjectId") != project_id or "file" not in item: continue` | Folders lack `file`, so both are skipped. Result: `[]` |
| 112 | `content=fields.get("TesseraContent", "")` | Document body comes from a list column, never from the file. A real `.docx` yields empty content |
| 116–117 | `allowed_user_ids=frozenset(item.get("allowedUserIds", []))` | Graph returns no such property on a driveItem. Always empty |

`src/tessera_os/microsoft.py:29` — `folder_item_id: str = "root"`, and there is no
configuration expressing a path.

### 2.3 The latent consequence of 116–117

`src/tessera_os/knowledge.py:37` fails **closed** on an empty ACL:

```python
if not document.allowed_user_ids and not document.allowed_group_ids:
    return False
```

That is the correct direction to fail, and it should stay. But combined with 116–117 it
means **every document sourced from SharePoint is invisible to knowledge search**, for
everyone, permanently — while remaining visible in the portal listing, which does not
apply `_can_read`. Two read paths, two different answers, no error in either.

This has never been observed because no document has ever reached the reader.

---

## 3. Design decisions — read before implementing

### D1. The folder path *is* the project scope

`Projects/{project folder}/` replaces the `ProjectId` list column entirely. Scope
becomes a property of where a file lives, which is how the library is already organised
and how a person filing a document already thinks. No column to create, no tag to
forget, no silent exclusion when someone uploads without tagging.

Configuration names the path explicitly. Do **not** derive a folder name from
`project_id` by slugification — `internal-pilot` → `Internal Pilot` happens to work and
will stop working the first time a client's folder is named anything else. An explicit
mapping fails loudly; a guess fails silently into the wrong client's folder.

### D2. Lifecycle is **not** `Basis` — keep them separate

`Basis = Literal["tessera_adopted", "synthetic_reference", "scaffold"]`
(`governance.py:42`) describes the standing of a **Tessera position** — whether the
partners have adopted it, whether it is invented reference material, whether it is
placeholder scaffolding.

A document a client uploaded is **evidence**, not a position. It has no `Basis`. Writing
`Source/` → `synthetic_reference` would stamp a real client document as invented,
inside the exact field the review queue and the adoption ledger read to decide what is
real. That is a provenance violation, not a mapping convenience.

Introduce a distinct concept:

```python
Lifecycle = Literal["approved", "draft", "source"]
```

- `Approved/` → `approved`
- `Drafts/` → `draft`
- `Source/` → `source`
- any other folder → `source` (evidence is the safe default; it grants no standing)

A `SourceDocument` carries `lifecycle` in `metadata`. It never carries `basis`. If any
code path tries to set `basis` on a `SourceDocument`, that is a bug.

### D3. Content comes from the file

`TesseraContent` as the body source means the system can only read documents someone
retyped into a column. Fetch the file and extract text. Keep it narrow: `.docx`,
`.txt`, `.md` in this phase. Anything else lists with empty content and a
`content_available: false` marker — visible, honest, not silently blank.

### D4. ACLs must be populated deliberately

Do not paper over §2.3 by loosening `knowledge.py:37`. The fail-closed default is
correct and stays.

Populate the ACL from the trust zone the document was read under —
`ZonePolicy.check_read` already returns it, and `AllowlistedSharePointReader` already
has it in hand at `microsoft.py:404`. An internal-zone document is readable by the
partner group; an engagement-zone document by that engagement's group. This makes the
authorization explicit and identical on both read paths, rather than accidentally empty
on one.

---

## 4. Work items

### 2.1 — Path-based project resources

**Change.** Add `root_path: str` to `SharePointProjectResource` (`microsoft.py:24`).
Deprecate `folder_item_id`; accept it for one release, log when used, ignore it if
`root_path` is present.

**Acceptance.**
- A resource with `root_path: "Projects/Internal Pilot"` resolves via
  `/drives/{drive_id}/root:/{root_path}:` .
- A `root_path` naming a folder that does not exist raises
  `MicrosoftConfigurationError` at read time, naming the path — not an empty list.
- A `root_path` containing `..` or a leading `/` is rejected at validation.
- Both `root_path` and `folder_item_id` present → `root_path` wins, warning logged.

### 2.2 — Recursive walk

**Change.** Replace the single `children` call with a depth-bounded recursive walk
under `root_path`.

**Acceptance.**
- Files nested at any depth ≤ 5 below `root_path` are returned.
- Depth > 5 is not followed; the walk logs the skipped path and continues.
- Folders never appear as documents.
- Paging (`@odata.nextLink`) is followed at every level, not just the first.
- A library of 500 files across 40 folders completes in one call chain without
  unbounded fan-out.

### 2.3 — Lifecycle from folder, per D2

**Change.** Derive `lifecycle` from the first path segment below `root_path`. Record it
in `SourceDocument.metadata["lifecycle"]`, alongside
`metadata["folder_path"]` (the path relative to `root_path`, for provenance display).

**Acceptance.**
- `Projects/Internal Pilot/Approved/memo.docx` → `lifecycle == "approved"`.
- `Projects/Internal Pilot/Source/client-financials.xlsx` → `"source"`.
- `Projects/Internal Pilot/Misc/note.docx` → `"source"`.
- A file directly under `root_path` with no lifecycle folder → `"source"`.
- **A `SourceDocument` never has a `basis` field set.** Assert this explicitly in a
  test named for the reason, not the mechanism.

### 2.4 — Drop the `ProjectId` column requirement

**Change.** Remove the `fields.get("ProjectId") != project_id` filter. Scope is the
path (D1).

**Acceptance.**
- An untagged file inside the project's folder is returned.
- A file under a *different* project's folder is not returned, even with a
  `ProjectId` column claiming otherwise — the path is authoritative and a stale column
  cannot override it.
- Test the cross-project case directly. This is the golden-rule boundary
  (`ZonePolicy.check_citation`) and it must not regress.

### 2.5 — Content extraction, per D3

**Change.** Fetch file bytes for `.docx`, `.txt`, `.md`; extract text. `.docx` via the
existing document dependency — do not add a new one without saying why in the PR.

**Acceptance.**
- A `.docx` yields its paragraph text in `content`.
- An unsupported type yields `content == ""` and
  `metadata["content_available"] is False`.
- A file over 10 MB is listed but not fetched; `content_available` is `False` with
  `metadata["skipped_reason"] == "size"`.
- Extraction failure on one file does not abort the walk — that file is listed with
  `content_available: False` and the error is logged.

### 2.6 — Explicit ACLs, per D4

**Change.** In `AllowlistedSharePointReader.project_documents`
(`microsoft.py:390–410`), populate `allowed_group_ids` from the zone returned by
`check_read`. Remove the `item.get("allowedUserIds")` / `("allowedGroupIds")` reads —
they are dead code that reads properties Graph does not return.

**Acceptance.**
- An internal-zone document carries the partner group in `allowed_group_ids`.
- An engagement-zone document carries that engagement's group, and not the partner
  group alone.
- A document returned by the portal listing is also findable via knowledge search for
  the same user. **Write this as one test across both paths** — the divergence in §2.3
  is the defect, and a per-path test would not have caught it.
- `knowledge.py:37` is unchanged.

### 2.7 — Honest empty states

**Change.** The portal currently renders "No approved documents found" whether the
folder is empty, the path is misconfigured, or the zone refused. Distinguish them.

**Acceptance.**
- Folder exists and is empty → "No approved documents in this project yet."
- `root_path` does not resolve → a configuration error surfaced to an authenticated
  partner, naming the path. Not to an unauthenticated caller.
- Zone refusal → the existing refusal message, unchanged.
- These are distinguishable in the interface without reading logs.

---

## 5. Invariants that must not break

Verbatim from `CLAUDE.md`; the test suite already enforces most of them.

1. No `SourceDocument` ever carries a `Basis`. (D2 — new, and the most important line
   in this brief.)
2. `knowledge.py:37` fails closed on an empty ACL.
3. `ZonePolicy.check_read` runs before any Graph transport, not after.
4. `check_citation` — a document from one engagement never surfaces in another's
   artifact.
5. Synthetic surfaces stay closed in production.
6. Separation of duties in the review queue is untouched by this phase.
7. No credential in any file. `root_path` and `drive_id` are identifiers, not secrets.

---

## 6. Configuration migration

After the code lands, `TESSERA_M365_PROJECT_RESOURCES` becomes:

```json
{
  "internal-pilot": {
    "site_id": "tesseragroup581.sharepoint.com,86c8bad2-c144-4e3b-ac08-ed772e7c1f9c,788d6e24-cb4b-43e5-9eba-b483e730f5ea",
    "drive_id": "b!0rrIhkTBO06sCO13LnwfnCRujXhLy-VDnrq0g-cw9eqqVvbEY83hQ7p2jgEMSVl5",
    "root_path": "Projects/Internal Pilot",
    "zone": "internal"
  }
}
```

`folder_item_id` is removed. Applied with a single `az containerapp update`, per
`docs/DEPLOY.md`.

---

## 7. Out of scope

- Writing to SharePoint. The portal stays read-only; that is a governance position, not
  a limitation to fix here.
- `.pdf` and `.xlsx` extraction — list them, mark `content_available: false`, revisit.
- Automatic project discovery from folder names. Configuration stays explicit (D1).
- The hardcoded `"writes": "disabled"` in both `/health` endpoints
  (`portal.py:180`, `service.py:117`) — a health endpoint reporting a value it never
  computes. Real, small, unrelated. Separate commit.

---

## 8. Definition of done

- Full suite green; new tests for every acceptance criterion above.
- `ruff` clean, security scan clean.
- A document placed in `Projects/Internal Pilot/Approved/` appears in the portal with
  its text content, without any SharePoint column being created.
- The same document is findable via knowledge search by the same user.
- A document in `Drafts/` is present with `lifecycle: "draft"` and does **not** appear
  under "approved documents."
- Deployed, `/health` reports `"console":"ok"`, verified against the live library.
