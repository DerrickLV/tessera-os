# Tessera OS — Build & Operations Playbook

How a change to Tessera OS gets designed, built, reviewed, shipped, and verified.
Written from what actually worked, and what actually broke, between 19 and 26
August 2026.

Audience: Derrick, Ryan, and any engineer who joins later.
Companion document: `CLAUDE.md`, which Claude Code reads automatically and which
holds the invariants. This playbook holds the *process*.

---

## 1. The loop

Five steps. Skipping any one of them is where the bad evenings came from.

**1. Write a brief before writing code.** A build brief states what is wrong with
evidence (`file.py:line`), the design decisions that constrain the fix, numbered
work items with acceptance criteria, and the invariants that must not break.
`docs/BUILD_BRIEF_PHASE_2_LIBRARY_READING.md` is the reference standard.

The brief is the thinking. Handing Claude Code a vague instruction produces
plausible code that solves the wrong problem — and you find out at deploy time.

**2. Hand the brief to Claude Code, on a branch.**

```
Read CLAUDE.md and docs/<BRIEF>.md. Implement all work items in section 4.
Follow the design decisions in section 3 exactly. Write tests for every
acceptance criterion. Run the full suite, ruff, and the security scan before
committing. Commit to a branch named <name> and tell me what you changed before
pushing.
```

Always name the branch. Local `main` can silently be ahead of or behind
`origin/main`, and a commit lands wherever HEAD happens to be.

**3. Verify the diff against the brief — do not read it line by line.** Pick the
three or four properties that would hurt most if wrong and check those
specifically:

```
git fetch origin
git log --oneline main..origin/<branch>
git diff main..origin/<branch> --stat
git diff main..origin/<branch> -- src/tessera_os/<file-that-must-not-change>.py
git grep -n "<thing-that-must-not-appear>" origin/<branch> -- src/
git grep -h "def test_" origin/<branch> -- tests/<new-test-file>.py
```

Two of those should return **nothing**. An empty result is the pass condition.

**4. Merge and let the pipeline deploy.**

```
git checkout main && git pull origin main
git merge origin/<branch> && git push origin main
```

Push to main builds the image, deploys it, and fails the run if `/health` does
not report both `"status":"ok"` and `"console":"ok"`.

**5. Verify against reality, not against the tests.** A green suite means the
code does what the tests say. It does not mean the system does what you wanted.
Sign in and use the thing that changed.

---

## 2. What to check in a diff

Ranked by cost of being wrong.

| Check | Why |
|---|---|
| Provenance invariants | A `SourceDocument` carrying a `Basis` marks a real client document as invented, inside the field the review queue reads |
| Authorization defaults | `knowledge.py:37` fails closed on an empty ACL. Any change that loosens it is a security change wearing a bug-fix label |
| Cross-boundary tests | The golden rule — one client's document never surfaces in another's artifact — needs a test that tries and fails, not a test that succeeds |
| Bounded loops | Any recursion or retry must have a limit and log what it skipped |
| Honest empty states | "Nothing found" must be distinguishable from "couldn't look" and from "not allowed" |

That last row is the theme of this whole project. Nearly every failure in August
was a system reporting something untrue about itself.

---

## 3. Deploying

Normal path: merge to main. The pipeline does the rest.

By hand, when needed:

```
az containerapp update -n tessera-portal-api -g tessera-pilot-rg \
  --image ghcr.io/derricklv/tessera-os:sha-<short> --revision-suffix <label>
```

```
az containerapp revision list -n tessera-portal-api -g tessera-pilot-rg -o table
curl -s https://api.tesseraag.com/health
```

Rollback is by **tag**, never by revision name — revisions get cleaned up:

```
az containerapp update -n tessera-portal-api -g tessera-pilot-rg \
  --image ghcr.io/derricklv/tessera-os:sha-<last-good>
```

Known good: `sha-d2c3f97` (Phase 2), `sha-b41b4da` (Phase 1).

### Fixed facts

| | |
|---|---|
| App / group | `tessera-portal-api` / `tessera-pilot-rg` |
| Registry | `tesseraacr` (pull is still GHCR until cutover) |
| URL | `https://api.tesseraag.com` — the custom domain, always |
| Subscription | `1ce8bb84-5eaa-4b82-9262-705b70f9b117` |

---

## 4. Failure table

Every one of these cost real time. The symptom is what you see first.

| Symptom | Cause | Fix |
|---|---|---|
| Build dies in ~20s | `.dockerignore` excludes a directory the Dockerfile copies | Check `.dockerignore` against every `COPY` |
| App healthy, site dead | Ingress `targetPort` ≠ the port uvicorn listens on (8000) | `az containerapp ingress update --target-port 8000` |
| `ImagePullUnauthorized` | Registry credential stale or wrong scope | Classic PAT, `read:packages` **only** — `write:packages` auto-selects full `repo` |
| Revision never healthy, `database is locked` | SQLite on SMB; POSIX byte-range locks unsupported | Already fixed — `unix-dotfile` VFS. Never enable WAL |
| Sign-in 500s after a successful callback | `chmod` on Azure Files (no POSIX mode bits) | Already fixed — `persist()` tolerates the failure |
| Portal renders, console 404s | Console mount failed; `/health` says `"console":"unavailable"` | Read container logs; the reason is deliberately not in the response |
| `AADSTS700213` on deploy | GitHub sends an **immutable** OIDC subject: `repo:USER@ID/REPO@ID:ref:...` | Create a federated credential with the exact subject from the error |
| `The containerapp '' does not exist` | A shell variable evaluated empty | Use literal names in Cloud Shell — variables don't survive reconnects |
| `The containerapp '<name>' does not exist` from Actions | Deploy identity lacks `Reader` on the resource group | Azure reports unresolvable as *not found*, not *forbidden*. Grant Reader at group scope |
| Deploy job hangs then dies mid-poll | `az containerapp update` polling for minutes; connection drops | `--no-wait`; the next step already waits for health |
| Health check returns 400 repeatedly | Checking the default `*.azurecontainerapps.io` FQDN after a custom domain is bound | Check `https://api.tesseraag.com` |
| `ContainerAppOperationInProgress` | Two operations racing | Wait for the first; retry |
| Role grant "created" but nothing works | It silently didn't | `az role assignment list --assignee <sp> --all -o table`. Then wait 5–10 minutes |
| Pasted value is the wrong length | Cloud Shell interleaved your paste with streaming output | One command per paste. `echo "${#VAR} chars"` before using a secret |

---

## 5. Secrets

- Never in chat, never in a file, never in a screenshot. Password manager →
  Cloud Shell prompt only.
- `read -rsp "token: " VAR && echo` hides input. Nothing appears as you paste;
  that is correct.
- `echo "${#VAR} chars"` before use. A classic PAT is exactly 40.
- `unset VAR` when done.
- `scripts/security_scan.py` runs in CI and has already caught one committed
  credential. If it fires, the token is burned — revoke first, then fix the file.
- **Never regenerate `TESSERA_M365_CACHE_KEY`.** It decrypts the stored Microsoft
  token cache; a new one silently breaks sign-in.

---

## 6. Constraints that look like preferences

Each of these will read as something to optimise away. Each is load-bearing.

| Constraint | Why it cannot change casually |
|---|---|
| `maxReplicas: 1` | SQLite on a shared file is single-writer. Removing it means PostgreSQL first |
| `unix-dotfile` VFS, journal DELETE | SMB cannot do byte-range locks or WAL shared memory |
| Console served same-origin | The session cookie is `SameSite=Lax`; a browser won't attach it cross-origin |
| Per-app CSP | The portal's `script-src 'self'` renders the console blank |
| No external actions | A governance position, not a missing feature |
| Synthetic surfaces closed in production | Pre-authored fiction is indistinguishable from engine output in the interface |

---

## 7. Working with Claude Code

**What it does well.** Implements a precise brief, writes tests that state the
reason rather than the mechanism, runs its own gates before committing, catches
its own mistakes and stops to ask.

**Where it needs you.**

- *Give it the branch name.* It will otherwise commit wherever HEAD is.
- *Ask it to show evidence, not conclusions.* "Show me the tests that cover each
  of the three cases" surfaced verified answers where "did you check?" would have
  got a yes.
- *Watch for silent scope.* A brief item that produces no diff might be already
  satisfied — or skipped. Ask which.
- *It cannot see production.* Deploy state, Azure config, and whether the thing
  actually works for a user are yours.

**Budget note.** Usage is finite. Spend it on implementation from a good brief,
not on exploration you could do with `git grep`.

---

## 8. Open items

| Item | By when |
|---|---|
| ACR cutover — removes the last expiring credential | GHCR PAT expires **22 Nov 2026** |
| Pin `azure/login` to a commit SHA | When convenient |
| Rename `simple-hello-world-container` | Fold into another change |
| Phases 3–5 | See the briefs |
| Adoption ledger signatures | Blocks everything from being `tessera_adopted` |
