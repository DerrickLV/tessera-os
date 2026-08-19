# 10 — SharePoint Write-Back Spec

**Status: write access is OFF, and this document exists so it stays off until
the gate has a definition rather than a debate.**

Everyone will want write-back opened early — it is the obvious next step after
reading works, and it is the step where a careful integration becomes a
dangerous one. Defining the gate before anyone wants through it is much easier
than defining it during the argument.

The current pilot requests delegated `User.Read` and `Sites.Selected` and
nothing else. `MicrosoftPilotSettings.validate_pilot_boundary` refuses any scope
outside that pair, and refuses any scope containing `write` or ending `.All`.
That refusal is a load-bearing safety property and should be the last thing
changed.

---

## The rule that shapes everything below

Your governance model already contains the answer: **work originates in
Internal, and a copy is placed in the zone where it will be shared. The original
never leaves.** Combined with the draft/final separation, that gives write-back
its whole specification. A write is only ever the placement of a *copy* into a
*drafts* folder in a zone that is *not* Internal.

---

## What write-back may do

| May | May not |
|---|---|
| Create a new file in a `*_DRAFTS` folder | Write anywhere in `*_EXECUTED`, `Final_Returned`, or `Master_Templates` |
| Write into an Engagement (zone 02) or Collaborator (zone 03) folder | Write into Internal (zone 01) — originals are authored by humans |
| Write a file whose name the system generated | Accept a filename from a task, a prompt, or a model |
| Write one file per accepted artifact | Overwrite, append to, or delete an existing file |
| Write after a recorded review acceptance | Write at draft time, or on any unreviewed artifact |

Deletion is out of scope permanently. A system that can create files in a
drafts folder is recoverable from; one that can remove them is not.

---

## Preconditions, all required

A write attempt that fails any of these is refused and logged, never retried
with a fallback:

1. **The artifact was accepted in the review queue**, by a reviewer in the
   artifact's `required_reviewer_group`, resolved from Entra rather than
   asserted. A drafted agreement therefore reaches SharePoint only after
   qualified counsel has accepted it.
2. **Separation of duties held** — the accepting reviewer is not the creating
   user.
3. **The target project's zone is `engagement` or `collaborator`.** Internal is
   refused with the golden-rule message.
4. **The target folder path ends in a drafts segment** from the approved list
   (`04_Contracts_DRAFTS`, `Working_Drafts_Return`, `02_Structuring_and_Governance`,
   `06_Shared_with_Client`).
5. **The client wall holds** — the artifact's `client_id` matches the target
   resource's `client_id`.
6. **The file does not already exist.** A name collision is a refusal, not an
   overwrite, and the version number is what resolves it.
7. **The write is enabled** for that tenant by an explicit setting, with a kill
   switch that takes effect without a redeploy.

---

## The filename is generated, never supplied

Your naming convention is the spec:

```
YYYY-MM-DD_ClientOrTopic_DocType_vNN_STATUS.ext
```

- **Date** — the acceptance date, from the review record, not from the model.
- **ClientOrTopic** — from the artifact's project mapping.
- **DocType** — from the artifact's workflow (`StructureMemo`,
  `OperatingAgreement`, `FormationChecklist`), from a fixed table.
- **vNN** — computed by listing the folder and incrementing past the highest
  existing version of the same DocType. Never assumed to be `v01`.
- **STATUS** — `REVIEW` for a structure memo, `COUNSEL` for a drafted
  agreement. Never `FINAL` or `EXECUTED`; those states are reached by a human
  moving the file, which is the act that makes them meaningful.

A filename assembled by a model is a filename that can collide, mislead, or
traverse. Generating it from typed fields removes the whole class.

---

## Scope change is a policy decision, not a config change

Write-back needs `Files.ReadWrite` scoped through `Sites.Selected` — a
materially different permission from anything the pilot holds today.

Requiring that change to pass the same review as an accepted artifact is the
point: adding a scope should be at least as deliberate as accepting a drafted
agreement, and today it would be an environment variable. The same applies to
`Mail.Read`, which is the scope that would quietly end the personal-email wall
the current configuration preserves by accident rather than by design.

**Recommendation: the approved scope set becomes a policy artifact with a named
owner**, and `validate_pilot_boundary` reads it rather than carrying a hardcoded
pair.

---

## Rollout, in order

1. **Dry run.** Compute the full target path, filename, and version for every
   accepted artifact and record it. Write nothing. Run for two weeks and read
   the log — this is where the naming and versioning bugs surface, for free.
2. **One folder, one type.** Enable writes for structure memos into a single
   engagement's `02_Structuring_and_Governance`. One project, one DocType.
3. **Add drafted agreements** into `04_Contracts_DRAFTS`, after counsel has
   accepted at least one through the queue.
4. **Add the second engagement**, which is the first real test of the client
   wall.

Each stage carries an explicit disconnect procedure: revoke consent, delete the
retained token cache, and confirm no further writes are possible.

---

## What is deliberately absent

- **No sync.** One-way placement of a copy at a moment of acceptance. A
  two-way sync makes SharePoint a source of truth for artifacts, which it is
  not, and creates conflict resolution nobody has specified.
- **No overwrite-on-update.** An amended artifact produces a new version, not a
  replacement. The history is the point.
- **No filing into Internal.** Ever. If a partner wants an original in zone 01,
  a partner puts it there.
