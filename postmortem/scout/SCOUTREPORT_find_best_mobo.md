# Reconnaissance scout pass — find_best_mobo

**Pass:** reconnaissance scout only. This report says what evidence exists and
how to get it. It extracts no data and writes no timeline. A later extraction
pass does that, using this report.

**Date of the pass:** 2026-08-26

**Repository:** GrimsVerk/find_best_mobo

**Branches examined (all four in scope), at these tips:**

| Branch | Tip SHA read |
| --- | --- |
| `run/local` | `5f0e37242539c6068241ee50dbb75282b3cec39c` |
| `run/web` | `9525e3e6be747c972d3e046a3f0a22367416274b` |
| `chore/test-report-local` | `2f779a82d1e12b8693ee67d162a7705413f7647a` |
| `chore/test-report-web` | `bfc25c1a53dcb1a5e06f22136eb290c2645f5348` |
| `main` (reference only) | `52735f8c9f3fd95464074d7dace83c4c32b4690b` |

**SHAs read individually during this pass.** Sampling, not a full walk. About
5–10 commits per branch, as instructed.

Window boundary and cleanup SHAs:

| SHA | Committed (ISO) | Why it was read |
| --- | --- | --- |
| `88400b8036bb20b4a2eb6233d98731f4821a4723` | 2026-08-19T10:48:16+00:00 | shared merge-base of all four branches with `main`; last pre-experiment commit |
| `51b359f600f8f04985a26ac2b5cfe17947c9f585` | 2026-08-20T10:28:50+02:00 | `run/local` first experiment commit |
| `89351d71b44fcc5382f2708cbeba6c2c905c7ae0` | 2026-08-20T13:51:03+00:00 | `run/local` last experiment commit |
| `b443caac811620d1e0a359d72ff435ede55bd35a` | 2026-08-24T08:58:00+00:00 | post-experiment cleanup, parent 1 of the merge |
| `eeeafab5afa8d5ab4b0e91fdc7b53dc514972a88` | 2026-08-24T08:58:08+00:00 | post-experiment cleanup, parent 2 of the merge |
| `5f0e37242539c6068241ee50dbb75282b3cec39c` | 2026-08-24T10:58:24+02:00 | **the post-experiment cleanup merge — exclude** |
| `fde89035d9b59bc8ce4154fd0bfc2c6a3fdcac84` | 2026-08-20T10:26:14+00:00 | `run/web` first experiment commit |
| `9525e3e6be747c972d3e046a3f0a22367416274b` | 2026-08-20T15:46:32+00:00 | `run/web` last experiment commit |
| `9809e6ddaea0287141e08ec803df33f25219f8c7` | 2026-08-20T10:26:20+02:00 | `chore/test-report-local` first experiment commit |
| `2f779a82d1e12b8693ee67d162a7705413f7647a` | 2026-08-20T18:32:20+02:00 | `chore/test-report-local` last experiment commit |
| `d5b551cf726eb1c081c3175d269824793d93f5e3` | 2026-08-20T08:25:07+00:00 | `chore/test-report-web` first experiment commit |
| `bfc25c1a53dcb1a5e06f22136eb290c2645f5348` | 2026-08-20T16:29:04+00:00 | `chore/test-report-web` last experiment commit |

Commits whose full message or content was read:

| SHA | Committed (ISO) | Why it was read |
| --- | --- | --- |
| `d6c5485dd477bbfea973465dcdaf24ac8ebab15d` | 2026-08-20T11:15:51+02:00 | source of quoted **Ruling B — OD-15** |
| `e86c39525be0440f0d99daa84cc7dae8ba23fd4f` | 2026-08-20T14:09:51+02:00 | source of quoted **Ruling A — OD-18** |
| `721f1e95964909225a2080fb2a7caad6516ff578` | 2026-08-20T15:00:46+02:00 | source of quoted **Ruling C — OD-21** |
| `797e839b1104f04aed4fa4344667919cff0f9816` | 2026-08-20T11:01:17+02:00 | commit-trailer sample, `run/local` oracle commit |
| `6db1c6a53c47c7b5122488024a784d578eb6090c` | 2026-08-20T14:48:11+02:00 | commit-trailer sample, `run/local` oracle commit |
| `f2cf072d4ae5112c707814d07cc8e5251e44259c` | 2026-08-20T08:50:46+00:00 | merge-commit shape check (2 parents, `(#98)` subject) |
| `b41d8a13390ef3b69c8f6c68bbb9fc25dc0f66b8` | 2026-08-20T10:30:28+00:00 | commit-trailer sample, `run/web` (`Claude-Session:`) |
| `ba0e5da7c1529cce87f1615575df530ea23dd546` | 2026-08-20T10:33:09+00:00 | merge-commit body sample, `run/web` PR #108 |
| `d82581122081f552cffa443fbde8057adf60a35f` | 2026-08-20T15:44:46+00:00 | `.pr-request.json` content, web-lane PR-open mechanism |
| `e042049d767a686da4b843e6a81411ccd4c3f0e8` | 2026-08-20T12:49:49+00:00 | worker-log base commit referenced by `steward-od-5.log` |

Files read at a branch tip (not at a specific commit): `docs/DESIGN.oracle.md`,
`docs/DESIGN.md`, `docs/BACKLOG.md`, `docs/DECISIONS.md`, `docs/escapes.md`,
`docs/escapes.done.md`, `docs/oracle/handoff-2026-08-20-5.md`,
`docs/runs/20260820T112543Z/run.md`,
`docs/runs/20260820T112543Z/workers/steward-od-5.log`,
`docs/runs/operator/local.md`, `docs/runs/operator/web.md`, and
`docs/runs/operator/runner-2026-08-20.md` (on `main`).

**Note for whoever fetches this.** Only `run/web` was present in the scout's
checkout at session start. Run this first or nothing below reproduces:

    git fetch origin 'refs/heads/*:refs/remotes/origin/*'

Everything below this line is the report exactly as delivered, unedited.

---

# Scout report — find_best_mobo experiment evidence

Reconnaissance only. No data extracted, no timeline written.
Read-only. No commits, no branches, no pushes were made.

All four branches were fetched with:

    git fetch origin 'refs/heads/*:refs/remotes/origin/*'

Note: only `run/web` was present at session start. The other three had to be
fetched. Anyone repeating this must run the fetch above first.

---

## 0. Window boundaries

All four branches share ONE merge-base with `main`:

    88400b8036bb20b4a2eb6233d98731f4821a4723
    2026-08-19T10:48:16+00:00
    "File BL-14: OD-5 is overruled; the capped plan must not build as merged (#97)"

Command used:

    git merge-base origin/main origin/<branch>

That commit is the last PRE-experiment commit. Everything after it on each of
the four branches is the experiment, with one exception (the cleanup merge,
below). **My words:** I confirmed this two ways — (a) each branch's first commit
after the merge-base is a lane-setup act ("Update from template v0.4.37",
"Open the local-lane operator ledger", "Start WEB lane operator ledger"), and
(b) both operator ledgers open their own first timeline row at 2026-08-20T08:2xZ,
which matches those same commits.

### Boundary table

| Branch | First experiment commit | ISO timestamp | Last experiment commit | ISO timestamp |
| --- | --- | --- | --- | --- |
| `run/local` | `51b359f600f8f04985a26ac2b5cfe17947c9f585` | 2026-08-20T10:28:50+02:00 | `89351d71b44fcc5382f2708cbeba6c2c905c7ae0` | 2026-08-20T13:51:03+00:00 |
| `run/web` | `fde8903...` (see below) | 2026-08-20T10:26:14+00:00 | `9525e3e...` (see below) | 2026-08-20T15:46:32+00:00 |
| `chore/test-report-local` | `9809e6d...` | 2026-08-20T10:26:20+02:00 | `2f779a8...` | 2026-08-20T18:32:20+02:00 |
| `chore/test-report-web` | `d5b551c...` | 2026-08-20T08:25:07+00:00 | `bfc25c1...` | 2026-08-20T16:29:04+00:00 |

Full SHAs of the abbreviated entries, obtained by `git rev-parse`:

- `run/web` first: `fde8903` — subject `Update from template v0.4.41 and reopen the run/web lane`
- `run/web` last: `9525e3e` — subject `File BL-20, BL-21, BL-22: three HIGH uncertainties block the calibration milestone (#141)`
- `chore/test-report-local` first: `9809e6d` — `Open the local-lane operator ledger`
- `chore/test-report-local` last: `2f779a8` — `F35-F36: R26 reversal closed out; driver console log preserved (not landed by the template)`
- `chore/test-report-web` first: `d5b551c` — `Start WEB lane operator ledger`
- `chore/test-report-web` last: `bfc25c1` — `Log F21 (detector HIGH branch unreachable) and F22 (self-recorded operator error)`

Reproduce the whole table with:

    cd /home/user/find_best_mobo
    MB=88400b8036bb20b4a2eb6233d98731f4821a4723
    for b in run/local run/web chore/test-report-local chore/test-report-web; do
      echo "=== $b ==="
      git log --reverse --pretty='%H %ad %s' --date=iso-strict $MB..origin/$b | head -1
      git log          --pretty='%H %ad %s' --date=iso-strict $MB..origin/$b | head -1
    done

Commit counts in the window: `run/local` 57, `run/web` 46,
`chore/test-report-local` 17, `chore/test-report-web` 44.

### THE POST-EXPERIMENT CLEANUP MERGE ON `run/local` — EXCLUDE THESE

Three commits, four days after the experiment ended:

| SHA | ISO timestamp | Author | Subject |
| --- | --- | --- | --- |
| `b443caac811620d1e0a359d72ff435ede55bd35a` | 2026-08-24T08:58:00+00:00 | Claude | Redact machine-local paths from landed run evidence |
| `eeeafab5afa8d5ab4b0e91fdc7b53dc514972a88` | 2026-08-24T08:58:08+00:00 | Claude | Redact machine-local paths from the 2026-08-20 run reports |
| `5f0e37242539c6068241ee50dbb75282b3cec39c` | 2026-08-24T10:58:24+02:00 | GrimsVerk | **Redact machine-local paths from landed run evidence (#143)** — the merge commit |

`5f0e372` is the merge (2 parents: `89351d7` + `eeeafab`).

What it touched — 9 files, 105 insertions, 105 deletions, all under `docs/runs/`:

    docs/runs/20260818T222639Z/run.md
    docs/runs/20260818T225124Z/run.md
    docs/runs/20260819T001105Z/run.md
    docs/runs/20260820T085531Z/run.md
    docs/runs/20260820T102917Z/run.md
    docs/runs/20260820T112543Z/run.md
    docs/runs/manual-20260819/driver-state/run.md
    docs/runs/manual-20260819/worker-logs/corpus-and-checkpoint-1.log
    docs/runs/manual-20260819/worker-logs/steward-od-6.log

Verify with:

    git diff --stat 89351d7 origin/run/local

Its own message says what it did:

> Replaces every `/home/<user>/code/GrimsVerk` prefix in landed run
> evidence with its identity-register key `<repos_root>`.

**Important side effect.** This cleanup EDITS three of the experiment's own
run logs. If the extraction reads `docs/runs/20260820T*/run.md` at
`origin/run/local` (the branch tip), it gets the redacted text. If it reads at
`89351d7`, it gets the original text with real machine paths. Text content of
event lines is unaffected — only the path token changes. **Recommended: use
`89351d7` as the `run/local` end-of-window tree.**

### Ambiguity to flag

- The four `Update from template vX.Y.Z` commits inside the window
  (`51b359f`, `d6416f3`, `9565cb7`, `59db673` on `run/local`; `fde8903`,
  `75000ab` on `run/web`) are experiment *mechanics*, not project work. They
  are inside the window and they are the ONLY window commits that touch code
  outside `docs/`. Whether they count as "events" is a judgement call for the
  extraction, not a fact I can settle.
- `main` also carries `docs/runs/operator/runner-2026-08-20.md` (runner notes,
  `RN-1`..`RN-3`), written during the experiment by a third session that is on
  none of the four branches. See "Gaps and risks".

---

## 1. Does an append-only event or worker log exist in-repo?

**Yes, but only for the LOCAL lane. The web lane has none.**

### Local lane — machine-shaped driver log (the best source in the repo)

Path scheme, on `run/local`:

    docs/runs/<STAMP>/run.md                 # driver event log, append-only, one line per event
    docs/runs/<STAMP>/workers/<WORKER_ID>.log  # per-worker transcript
    docs/runs/<STAMP>/reviews/<BRANCH_SLUG>/{meta,payload,reply,verdict}.txt
    docs/runs/<STAMP>/reviews/index.md

`<STAMP>` is `YYYYMMDDTHHMMSSZ`. Three stamps fall in the window:

    docs/runs/20260820T085531Z/
    docs/runs/20260820T102917Z/
    docs/runs/20260820T112543Z/

Plus two setup logs:

    docs/runs/setup/setup-github-20260820T084514Z.log
    docs/runs/setup/setup-github-20260820T084804Z.log

List them:

    git ls-tree -r --name-only origin/run/local -- docs/runs/20260820 docs/runs/setup

### Local lane — operator ledger (hand-written)

    origin/chore/test-report-local : docs/runs/operator/local.md   (911 lines)

### Web lane — operator ledger ONLY

    origin/chore/test-report-web : docs/runs/operator/web.md   (1295 lines)

**MISSING:** `run/web` has NO `docs/runs/<STAMP>/` directory from the window.
Confirm:

    git ls-tree -r --name-only origin/run/web -- docs/runs | sed 's#/[^/]*$##' | sort -u

That returns only pre-experiment stamps (`20260818T*`, `20260819T*`,
`manual-20260819`). The web lane's driver was a Claude web session; its
driver log was never landed in git. **My words:** the web ledger is a
hand-written reconstruction of it, not a machine log.

### Outside git

The local ledger's last commit subject says so plainly:

> `F35-F36: R26 reversal closed out; driver console log preserved (not landed by the template)`

But the console log WAS then landed by hand on the ledger branch:

    docs/runs/.../driver-logs/run-20260820T112543Z-console.log   (194 lines)

Exact path:

    git ls-tree -r --name-only origin/chore/test-report-local | grep driver-logs

Also landed on that branch:

    ...salvage/steward-od-6-stranded-plan.patch   (562 lines)

Nothing else is known to sit outside git. `/tmp/anvil-env-setup.log` is
referenced in `web.md` and is **not reachable** — the container is gone.

---

## 2. Is the phase recorded in a parseable form?

**Local lane: YES, fully machine-parseable.** In `docs/runs/<STAMP>/run.md`.

Verbatim, from `origin/run/local:docs/runs/20260820T112543Z/run.md`:

    - 11:25:53Z iteration 1: phase STEWARD
    - 11:25:53Z dispatch steward worker (steward-od-8)
    spawn-worker[steward-od-8]: the worker moved its work to 'docs/oracle-plan-description-signal' (this script created 'worker/steward-od-8'); reporting the branch that carries the commits
    WORKER_RESULT id=steward-od-8 branch=docs/oracle-plan-description-signal worktree=<repos_root>/find_best_mobo/.worktrees/steward-od-8 engine=claude exit=0 commits=1
    - 11:36:08Z iteration 2: phase WAIT
    - 11:36:08Z waiting on PR #121 (docs/oracle-plan-od-8--run-local) — mechanical watch, no model budget
    - 11:39:12Z PR #121 merged

Extract every phase transition:

    git show origin/run/local:docs/runs/20260820T112543Z/run.md \
      | grep -E '^- [0-9:]+Z iteration [0-9]+: phase [A-Z]+'

Extract every worker result:

    git show origin/run/local:docs/runs/20260820T112543Z/run.md \
      | grep -E '^WORKER_RESULT '

Extract every PR merge:

    git show origin/run/local:docs/runs/20260820T112543Z/run.md \
      | grep -E 'PR #[0-9]+ merged'

Note the timestamps in `run.md` are **time-of-day only** (`11:25:53Z`). The date
comes from the header line, verbatim:

    # Delivery run 20260820T112543Z

    Started 2026-08-20T11:25:43Z.
    Base branch: run/local (branch suffix '--run-local').

**Web lane: YES, but hand-copied into the ledger.** `docs/runs/operator/web.md`
carries 28 `PHASE=` strings, copied from the phase detector's stdout. Verbatim
examples:

    PHASE=ORACLE BASE=run/web REASON=evidence UNCITED=BL-14
    PHASE=WAIT BASE=run/web PR=100 HEADREF=docs/oracle-20260820085103--run-web
    PHASE=STEWARD BASE=run/web ODS=OD-6 OD-7 OD-8 OD-9 OD-10 OD-11
    PHASE=ORACLE REASON=uncertainties
    PHASE=PLAN
    PHASE=ORACLE REASON=evidence UNCITED=BL-20 BL-21 BL-22

Command:

    git show origin/chore/test-report-web:docs/runs/operator/web.md | grep -oE 'PHASE=[A-Z]+[^|`]*'

Web ledger tables ALSO carry a dedicated PHASE column. Header rows, verbatim:

    | Time | Iteration | PHASE | Detail |

at lines 181, 341, 438, 981, 1181 of `web.md`.

**Local ledger** uses a different, coarser shape — a `## Phases` table with
free-text phase names (`SETUP/UPDATE`, `RIG/GATED`, `DRIVER START`, `ORACLE`,
`RUN STOPPED`, `MID WRAP-UP`). Header row, verbatim:

    | Timestamp (UTC) | Phase | Key fields |

**Not on commits.** No commit carries a phase trailer. Confirmed: the only
trailers present are `Co-Authored-By:` and `Claude-Session:`.

---

## 3. Do uncertainties and rulings carry stable IDs? Where do they appear?

**Yes. `BL-<n>` for uncertainties/backlog, `OD-<n>` for oracle rulings.**

The rule is written down. Verbatim from `docs/BACKLOG.md`:

> **Every item carries a `BL-<n>` id**, the next unused integer, and ids are never
> reused — a resolved item keeps its number rather than freeing it, so a citation
> written today still means the same thing in six months.

**They appear in BOTH commit messages and document bodies**, but NOT on every
commit. Counts of commit SUBJECTS in the window carrying any id
(`BL-`, `OD-`, `ESC-`, `R<n>`, `F<n>`, `RN-`):

    run/local:               30 / 57
    run/web:                 28 / 46
    chore/test-report-local: 16 / 17
    chore/test-report-web:   33 / 44

Command:

    MB=88400b8036bb20b4a2eb6233d98731f4821a4723
    git log --format='%s' $MB..origin/run/local | grep -cE '\b(BL-|OD-|ESC-|R[0-9]{1,4}\b|F[0-9]+\b|RN-)'

Real commit subjects, verbatim:

    Rule on BL-14 and BL-15: supersede OD-5's cap, warn on listing shape (OD-13, OD-14)
    OD-13: supersede OD-5/R1001 per the owner's uncapped clustering ruling (BL-14)
    Oracle: rule BL-22 (OD-21) and hand off

**MISSING / unreliable:** the ~45% of commits with no id in the subject are
merge commits, "Request the pull request" commits, and template updates. For
those, the id must come from the document diff, not the subject.

---

## 4. Can an uncertainty be matched to the ruling that closed it, mechanically?

**Yes. This is the strongest link in the repository.**

Every `OD-<n>` entry in `docs/DESIGN.oracle.md` carries a fixed 8-field block.
Verbatim from the schema section of that file:

    ## OD-<n> — one line saying what was decided

    - **Date:** YYYY-MM-DD
    - **Evidence:** ESC-<n>, BL-<n>
    - **Requirements added:** R1000, R1001   (or "(none)")
    - **Requirements superseded:** R1000     (or "(none)")
    - **Vision statement relied on:** V<n> — "<the FULL sentence, verbatim>"
    - **Vision statements against:** V<n> — "<the statement that most nearly
      forbids this>", and why it does not   (or "(none — no statement in
      docs/VISION.md tells against this)")
    - **Alternatives considered:** what else was weighed, and why not
    - **Rationale:** why this, given that evidence and that statement

The `**Evidence:**` field is the BL → OD link. All 22 entries have one.
Build the whole map with one command:

    git show origin/run/local:docs/DESIGN.oracle.md \
      | grep -E '^## OD-|^- \*\*Evidence:\*\*|^- \*\*Requirements (added|superseded):\*\*'

That yields, for example (verbatim output):

    ## OD-15 — R1002 applies within one cue; a cross-cue split is counted, never matched
    - **Evidence:** BL-16, BL-8
    - **Requirements added:** R1010
    - **Requirements superseded:** (none)

Supersession is equally mechanical: `**Requirements superseded:** R1001` on
OD-13 retires R1001 from OD-5.

**Caveat, and it is a real one.** The `**Evidence:**` field mixes two ID
families — `BL-<n>` and `ESC-<n>` — and the ESC family is ambiguous
(see question 6 and "Gaps and risks").

---

## 5. Is actor/role recoverable per commit?

**Partly. Git author is NOT the role. Do not use it as one.**

Author counts in the window:

    run/local:                28 GrimsVerk <github@grimsverk.com>
                              27 autogrims[bot] <...@users.noreply.github.com>
                               2 Claude <noreply@anthropic.com>
    run/web:                  31 Claude <noreply@anthropic.com>
                              15 autogrims[bot] <...>
    chore/test-report-local:  17 GrimsVerk <github@grimsverk.com>
    chore/test-report-web:    44 Claude <noreply@anthropic.com>

**My words:** on `run/local` the local driver commits under the owner's own git
identity, so `GrimsVerk` is the machine, not a human decision. The same name
covers oracle workers, steward workers and hand edits.

What IS mechanically recoverable per commit:

1. **PR-merge vs work commit** — merge commits have 2 parents and a subject
   ending `(#N)`:

       git log --pretty='%h %p %s' $MB..origin/run/local | awk 'NF>=4'

   Parent-count histogram: `run/local` 29 single / 28 merge; `run/web` 31 / 15.

2. **Lane** — the `Claude-Session:` trailer appears on 11 of 46 `run/web`
   commits and only 2 of 57 `run/local` commits. Not a reliable lane marker on
   its own; the branch name is reliable.

3. **Engine model** — `Co-Authored-By:` values in the window:

       run/local:  7 Claude Fable 5, 3 Claude Opus 5, 2 Claude
       run/web:    6 Claude Fable 5, 5 Claude Opus 5
       chore/*:    none

4. **Worker id and role — the real source.** From `run.md` on `run/local`:

       WORKER_RESULT id=steward-od-5 branch=docs/bl-22-superseded-decision-dispatch worktree=<repos_root>/find_best_mobo/.worktrees/steward-od-5 engine=claude exit=0 commits=1

   Worker ids are `oracle-<TIMESTAMP>` or `steward-od-<n>`. Role is the prefix.
   The worker log file name carries it too:

       docs/runs/20260820T112543Z/workers/steward-od-5.log
       docs/runs/20260820T112543Z/workers/oracle-20260820120730.log

5. **Branch slug** — head branch names encode the role:
   `docs/oracle-<stamp>--run-local`, `docs/oracle-plan-od-<n>--run-local`,
   `docs/bl-<n>-<slug>`. These appear in the merge-commit body and in `run.md`.

**MISSING for `run/web`:** there is no `WORKER_RESULT` line anywhere for the
web lane. Role there must be read out of `web.md` prose or from the branch slug
in the merge commit.

---

## 6. Where are identifier definitions authored? One path per family.

| Family | Defining file | Form |
| --- | --- | --- |
| `R1` – `R99` (product requirements) | `docs/DESIGN.md` | `- **R1** — <text>` |
| `R1000`+ (oracle requirements) | `docs/DESIGN.oracle.md` | `**R1000** — <text>` |
| `OD-<n>` (oracle rulings) | `docs/DESIGN.oracle.md` | `## OD-<n> — <headline>` |
| `BL-<n>` (backlog / uncertainties) | `docs/BACKLOG.md` | `- **BL-1** — **<headline>** <text>` |
| `ESC-17` – `ESC-23` (PROJECT escapes) | `docs/escapes.md` | markdown table row `\| ESC-17 \| 2026-08-14 \| …` |
| `ESC-7` (closed project escape) | `docs/escapes.done.md` | same table form |
| `V<n>` (vision statements) | `docs/VISION.md` | quoted in full inside each OD entry |
| `F<n>` (lane findings) | `docs/runs/operator/local.md` and `docs/runs/operator/web.md` | `### F1 — <headline>` |
| `RN-<n>` (runner notes) | `docs/runs/operator/runner-2026-08-20.md` **on `main` only** | `## RN-1 — <headline>` |
| `S<n>` (success criteria) | `docs/acceptance.md` + `acceptance/S<n>.sh` | — |

The R-id split is stated in `docs/DESIGN.oracle.md`, verbatim:

> Oracle requirements therefore start at **R1000**,

Commands, one per family:

    git show origin/run/local:docs/DESIGN.md          | grep -nE '^- \*\*R[0-9]+\*\* —'
    git show origin/run/local:docs/DESIGN.oracle.md   | grep -nE '^\*\*R[0-9]+\*\* —'
    git show origin/run/local:docs/DESIGN.oracle.md   | grep -nE '^## OD-[0-9]+ —'
    git show origin/run/local:docs/BACKLOG.md         | grep -nE '^- \*\*BL-[0-9]+\*\*'
    git show origin/run/local:docs/escapes.md         | grep -nE '^\| ESC-[0-9]+'
    git show origin/chore/test-report-local:docs/runs/operator/local.md | grep -nE '^### F[0-9]+ —'
    git show origin/chore/test-report-web:docs/runs/operator/web.md     | grep -nE '^### F[0-9]+ —'
    git show origin/main:docs/runs/operator/runner-2026-08-20.md        | grep -nE '^## RN-[0-9]+ —'

**BROKEN FAMILY — `ESC-`.** Two disjoint registers share the prefix.

    In-repo (docs/escapes.md):  ESC-7, ESC-17, ESC-18, ESC-19, ESC-20, ESC-21, ESC-22, ESC-23
    Cited by local ledger:      ESC-17 21 26 35 36 40 42 43 45 55 66 72 74 75
    Cited by web ledger:        ESC-14 17 21 26 35 36 45 50 52 55 63 68 69 71 72 73 74 75 76 77

`ESC-26` upward, and `ESC-14`, are **the template's / anvil's** escape register.
That file is not in this repository and is **not reachable** from this session
(the web ledger records the access denial as its own finding F1). `ESC-201` is
even cited in the runner notes on `main`.

Worse, `ESC-17` and `ESC-21` exist in BOTH registers with different meanings:

- `docs/escapes.md` ESC-17 = "`template-sync` cannot pass for any `copier update` that conflicts…"
- `web.md` ESC-17 = a cross-lane merge rewriting an open pull request's commit list

**Any glossing pass must decide ESC- meaning by which document cites it, never
by the number alone.**

---

## 7. Is the code-vs-docs distinction derivable from paths alone?

**Yes, and the answer is unusually clean: NO PRODUCT SOURCE CODE CHANGED AT ALL
during the experiment window, on any of the four branches.**

Verified:

    MB=88400b8036bb20b4a2eb6233d98731f4821a4723
    for b in run/local run/web chore/test-report-local chore/test-report-web; do
      echo "$b: $(git diff --name-only $MB origin/$b | grep -cE '^(src|tests|acceptance|data)/')"
    done

Output: `0` for all four.

### The rule

    docs/**                       -> DOCUMENT
    src/**, tests/**,
    acceptance/**, data/**        -> PRODUCT SOURCE CODE   (zero changes in window)
    .claude/**, .github/**,
    scripts/**, pyproject.toml,
    uv.lock, .pre-commit-config.yaml,
    .copier-answers.yml,
    AGENTS.md, README.md          -> TEMPLATE MACHINERY (third class — not product code,
                                     not project docs)
    .pr-request.json              -> PR-OPEN REQUEST MARKER (web lane only)

**The third class only ever moves in template-update commits.** On `run/local`,
exactly four commits touch anything outside `docs/`:

    59db673 Update from template v0.4.42
    9565cb7 Update from template v0.4.41
    d6416f3 Update from template v0.4.39
    51b359f Update from template v0.4.37

Command:

    git log --format='%h %s' --name-only $MB..origin/run/local \
      -- '.claude' '.github' 'scripts' 'pyproject.toml' 'uv.lock' 'AGENTS.md' 'README.md' \
      | grep -E '^[0-9a-f]{7} '

On `run/web` the same list adds the 15 `Request the pull request` commits, which
touch `.pr-request.json` and nothing else. `chore/test-report-local` and
`chore/test-report-web` touch **only** `docs/`.

So a simple two-way `docs/` vs not-`docs/` test is correct for the docs column,
but it will label template updates as "code changed" when no product code moved.
**Recommendation (my words): use the three-class rule above, not a two-way split.**

---

## 8. Do the two lanes differ in layout or log format?

**Yes, substantially. They are not symmetric and cannot be parsed by one parser.**

| | LOCAL lane | WEB lane |
| --- | --- | --- |
| Driver log in git | **Yes** — `docs/runs/<STAMP>/run.md` on `run/local`, 3 stamps in window | **No** — none landed |
| Worker logs in git | **Yes** — `docs/runs/<STAMP>/workers/*.log` | **No** |
| Review artifacts in git | **Yes** — `docs/runs/<STAMP>/reviews/<slug>/{meta,payload,reply,verdict}.txt` | **No** |
| Ledger path | `docs/runs/operator/local.md` on `chore/test-report-local` | `docs/runs/operator/web.md` on `chore/test-report-web` |
| Ledger phase section | `## Phases`, header `\| Timestamp (UTC) \| Phase \| Key fields \|`, **newest first** | `## Timeline` + per-round `\| Time \| Iteration \| PHASE \| Detail \|`, **oldest first** |
| Ledger section names | `## RESTART — v0.4.39` etc. | `## RESTART — round 2, template v0.4.39` etc. |
| Ledger phase vocabulary | free text: `SETUP/UPDATE`, `RIG/GATED-BOTH`, `PRE-DRIVER`, `DRIVER START`, `RUN STOPPED`, `LANE CLEAR`, `MID WRAP-UP` | machine vocabulary: `ORACLE`, `STEWARD`, `WAIT`, `PLAN` |
| Ledger timestamps | full ISO with `Z`, UTC | mixed: full `2026-08-20T08:24:10Z` and short `08:26Z` / `10:12:54Z` |
| Ledger extras | `driver-logs/run-...-console.log`, `salvage/...patch` | none |
| PR opened by | driver pushes; auto-PR | **explicit commit** `Request the pull request` writing `.pr-request.json`, then the server `open-pr` workflow |
| Commit author | `GrimsVerk` (work) + `autogrims[bot]` (merges) | `Claude` (work) + `autogrims[bot]` (merges) |
| `Claude-Session:` trailer | 2 of 57 | 11 of 46 |
| Findings count | F1–F36 | F1–F22 |

**`F<n>` ids collide across lanes.** Local F1 and web F1 are different findings
(both happen to be about `update-from-template.sh`, but web F1 is about the
template API being unreadable). Every `F<n>` must be namespaced by lane.

Both ledgers begin by declaring the shared method. Verbatim from `web.md`:

> Mechanics follow the public anvil test plan
> (`test-kit/TESTPLAN.md` on GrimsVerk/grimsverk-anvil, Parts 1 and 2) with the
> operator's overrides for this project

---

## Three Oracle rulings, quoted verbatim

All three live in `docs/DESIGN.oracle.md` on branch `run/local`.

### Ruling A — OD-18

- **SHA:** `e86c39525be0440f0d99daa84cc7dae8ba23fd4f` (2026-08-20T14:09:51+02:00)
- **Path:** `docs/DESIGN.oracle.md`
- **Retrieve:** `git show e86c395:docs/DESIGN.oracle.md | sed -n '/^## OD-18 /,/^## OD-19 /p'`

> ## OD-18 — `--help` after a subcommand is forwarded: the subcommand's help prints
>
> - **Date:** 2026-08-20
> - **Evidence:** BL-19, BL-5
> - **Requirements added:** (none)
> - **Requirements superseded:** (none)
> - **Vision statement relied on:** (no vision statement decided this)
> - **Vision statements against:** (none — no statement in docs/VISION.md tells against this; which help screen a CLI prints is below the vision's altitude, exactly as OD-10 recorded for the dispatch mechanics this elaborates)
> - **Alternatives considered:** (1) Keep today's behaviour — the top-level parser owns `-h/--help` everywhere, so `find-best-mobo aliases --help` prints the dispatcher's help — rejected: R1006's first sentence is that every flag a subcommand *documents* is reachable from the CLI, and a help screen nobody can reach documents nothing — `--check` would stay documented only in source, which is BL-19's own statement of the problem. Worse than the omission, the output is affirmatively wrong: a question asked about `aliases` is answered with a screen that never mentions `aliases` or any flag it takes. And it makes `-h/--help` the one token permanently exempt from R1006's forwarding rule — a special case the dispatcher contract would carry forever, for a screen still reachable as `find-best-mobo --help`. (2) Print both helps, the dispatcher's then the subcommand's — rejected: two usage lines under two prog names read as an error, and no widely-used multi-command CLI answers one question with two screens. (3) Split the pair — keep `-h` top-level, forward `--help` — rejected: the two spellings are one flag everywhere argparse appears, and splitting them turns a convention into a trap. (4) Forward it — the steward's default — chosen.
> - **Rationale:** BL-19 is right that R1006 and the shipped CLI disagree on exactly this token: argparse auto-registers `-h/--help` on the top-level parser and consumes it before dispatch, so the one flag R1006 could not reach was the one that documents all the others. Forwarding is also the convention of every multi-command CLI the owner already uses — `git`, `pip`, `uv` all print the subcommand's help after its name — so the chosen behaviour is the one a user will guess first. Nothing reachable is lost: `find-best-mobo --help` and a bare `find-best-mobo` keep today's output and exit codes (0 and 2), as the merged plan pins. The risk class is as filed: one console output, reversible by deleting one branch in `cli.py`, and a wrong ruling here is superseded at the cost of one entry. This is the next-cycle review `AGENTS.md` promises a LOW default, ratifying it.
>
> Downstream: `docs/plans/oracle/subcommand-flag-forwarding.md` builds as merged
> — no re-cut, no covers change. Its sequencing note stands: it shares every
> command module with `docs/plans/oracle/refuse-on-missing-artifact.md`, and the
> two are never built in parallel. Measurement: the plan's own tests pin both
> sides — `main(["aliases", "--help"])` exits 0 and the output names `--check`,
> `main(["--help"])` prints the top-level help, `main([])` still returns 2 —
> and slice 2's package-walking guard test extends the property to every future
> stage, so the behaviour this ruling changes is observed by the suite on every

*(The entry continues past this point; the quote is truncated at the last line I
read. — my note, not the source's.)*

### Ruling B — OD-15

- **SHA:** `d6c5485dd477bbfea973465dcdaf24ac8ebab15d` (2026-08-20T11:15:51+02:00)
- **Path:** `docs/DESIGN.oracle.md`
- **Retrieve:** `git show d6c5485:docs/DESIGN.oracle.md | sed -n '/^## OD-15 /,/^## OD-16 /p'`

> ## OD-15 — R1002 applies within one cue; a cross-cue split is counted, never matched
>
> - **Date:** 2026-08-20
> - **Evidence:** BL-16, BL-8
> - **Requirements added:** R1010
> - **Requirements superseded:** (none)
> - **Vision statement relied on:** "When a decision alters behaviour that no existing check, test, run report or review artifact would notice, adding the thing that notices is part of the decision — not a follow-up, and not optional." — this is what decides the measurement half of this ruling (R1010's counter). The within-cue/cross-cue binary itself is a mechanism question no vision statement decides, and **Alternatives considered** carries that weighing.
> - **Vision statements against:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not." — the nearest, because scoping out cross-cue splits leaves a class of real mentions unfound. It does not forbid this: the two damage classes differ in kind. Speech-to-text mangling is systematic per name — every utterance of "Tomahawk" arrives as `toma hawk` — so before R1002 the board was invisible *everywhere*, which is the total loss BL-8 measured. A cue boundary falls where the caption timing happens to fall, so a name straddling a break in one utterance is whole in its others (and its within-cue splits now match under R1002); title hits have no cues and description hits (R1004) have none either, so neither include signal is touched. The residue is a per-occurrence fraction, not a per-board blindness — and R1010's counter is what turns "the residue is small" from an assumption into a per-run measurement, so if V1 is in fact being shortchanged, the evidence to say so arrives by design instead of never.
> - **Alternatives considered:** (1) Cross-cue matching now — scan cue-joined normalized text and map every match offset back to its source cue — rejected: no cross-cue failure has ever been measured (BL-8's three failures were all tested as within-cue text), the shape change reshapes `find_mentions` and the plan's slice boundaries, and it forces an unforced answer to which cue's `start_seconds` a spanning mention carries — the field R5 cuts every excerpt window from and R14's timestamped links are built on, exactly the expensive-to-reverse decision BL-16 flags. Adopting that structural cost to chase an unquantified marginal recall, while R1002's measured wins land regardless, is backwards. (2) The steward's literal default — scope cross-cue splits out with nothing added — rejected: the loss is silent by construction; no recall report, selection count, fixture or run artifact would ever show a cross-cue miss, so the ruling could never be evaluated against evidence or superseded by it. (3) Merge all cues into one text at parse time and keep per-cue offsets — rejected as (1) in different clothes: the offset mapping and the timestamp question are identical, only moved into the parser. (4) Within-cue rule plus a boundary counter that detects, reports, and never emits — chosen.
> - **Rationale:** BL-16 is right that OD-6 fixed the join rule without naming the text the rule runs over, and the shipped fixture confirms the missing case is real: auto-caption cues break mid-phrase (`...Taichi board` / `has a twelve phase VRM`). But plausible and measured are different states of evidence, and the reversal costs are asymmetric: ruling within-cue today and widening later costs one superseding entry and a contained code change; ruling cross-cue today commits `find_mentions`'s shape and a guessed timestamp semantics before any measurement says the case matters. So the ruling takes the cheap, reversible side and instruments the boundary: the counter is one extra scan over adjacent-cue joins, pure CPU, offline, no token spend — V3 is untouched. Confidence is high on the scoping; the counter is the hedge. This also moots BL-16's second question — no mention ever spans cues, so `start_seconds` is always the start of the single cue containing the match — and answers its last one: the plan gains the counter work, and whether that is a fourth slice or folds into an existing one is the steward's sizing call.
>
> **R1010** — Mention matching applies R1002's token-join rule within one cue's
> normalized text: a mention is never synthesized from text spanning a cue
> boundary, so every mention's `start_seconds` is the start of the one cue
> containing it — the anchor R5's excerpt windows are cut from and R14's
> timestamped links point at. The scoping is measured, not assumed: the matching
> stage also detects matches that exist only in the normalized concatenation of
> adjacent cues — a match that starts in one cue's text and ends in the next's —
> and reports the count per run (zero included) in the selection report, without
> ever emitting a mention for one. The suite pins the distinguishing pair: an
> alias split across a cue boundary yields no mention and increments the
> counter, and the same split within one cue yields a mention and does not.

*(Entry continues. Truncated here. — my note.)*

### Ruling C — OD-21

- **SHA:** `721f1e95964909225a2080fb2a7caad6516ff578` (2026-08-20T15:00:46+02:00)
- **Path:** `docs/DESIGN.oracle.md`
- **Retrieve:** `git show 721f1e9:docs/DESIGN.oracle.md | sed -n '/^## OD-21 /,/^## OD-22 /p'`

> ## OD-21 — A steward dispatch for a decision whose every added requirement is superseded is false: the steward writes no plan, cites this decision, and stops
>
> - **Date:** 2026-08-20
> - **Evidence:** BL-22, BL-21
> - **Requirements added:** (none)
> - **Requirements superseded:** (none)
> - **Vision statement relied on:** V3 — "Cost is about not being *stupid* — not spending budget I could have used on other projects — rather than a hard constraint." — this is what the conduct half of the ruling turns on: BL-22 measures each false dispatch costing a full unattended session that re-derives the supersession from the ledger before stopping, and the ruling converts that recurring spend into one citation. The dispatch mechanics themselves are process below the vision's altitude, and **Alternatives considered** carries that weighing.
> - **Vision statements against:** V12 — "Silence has to read as silence." — the nearest, as OD-20 read it one level down: a steward instructed to write nothing and stop could make a stuck loop read as a quiet, healthy one — absence of artifacts reading as absence of trouble. It does not forbid this because every dispatch is already durably recorded (the run reports under `docs/runs/` log the driver's phase decisions, which is precisely the mechanism that measured BL-22), and the ruling requires the stopping steward to name this decision in its report, so each recurrence lands in the committed record as a symptom of the known livelock, never as silence.
> - **Alternatives considered:** (1) Let some plan clear the gap by naming R1001 in its `covers:` — rejected by name in OD-20 and again here: the behaviour R1001 describes (the cap, the excerpt-fallback above it) is deliberately not being built, so the claim is false the day it is written, and the pressure to make it is exactly the harm BL-21 warned the false gap would create. (2) Fix the scripts from here — `coverage.sh` (subtract superseded ids; BL-22's own preferred direction, since the dispatch reads that script's gap list and nothing else, so one parser learns supersession rather than two) or `deliver-phase.sh` step 4 (skip a decision whose every added requirement is superseded) — rejected: `.github/scripts/` and `.claude/scripts/` are owner-owned gate paths, the same ground OD-1 and OD-20 declined to touch; the recommended shapes are recorded below for the owner and belong upstream in the template as both filings say. (3) Game the dispatch's mapping — a new ledger entry whose `**Requirements added:**` line repeats R1001 so the driver's grep resolves the gap to a different decision — rejected outright: it is parser-gaming, it merely renames the livelock (the driver dispatches a steward for the new decision instead), and an added-requirements line asserting an addition that is not one is a false record. (4) A halt — no tenet is at stake and a decision exists. (5) Record the steward's conduct in the design layer, as OD-19 did for the orchestrator's false dispatch — chosen: this ledger is the one durable, oracle-writable text every steward reads at dispatch and the review gate reads at every pull request's base commit.
> - **Rationale:** BL-22 is verified against the tree, and it is measured rather than predicted — PR #129, opened mechanically as "Plan for OD-5", contains no plan and only the BL-22 filing itself. The mechanism: `deliver-phase.sh` step 4 takes `coverage.sh`'s gap list, maps each R≥1000 gap back to the decision whose `**Requirements added:**` line names it, and emits `PHASE=STEWARD` before the plan walk and before `PHASE=PLAN`; `coverage.sh` reads no `**Requirements superseded:**` line, so R1001 is a permanent gap, the map permanently yields OD-5, and the driver can never again reach orchestration, milestone planning or acceptance. No agent-writable path can break the loop: this ledger is append-only, both scripts are owner-owned, and the one write that would green the report is the over-claim OD-20 forbids. What this ledger can do is what OD-19 did for BL-20's inevitable dispatch — make it harmless, and now also cheap. The ruling is stated generally because the mechanism is general: a `PHASE=STEWARD` dispatch naming a decision all of whose added requirements are superseded is a false dispatch, and the dispatched steward has nothing lawful to cut. The correct motion is to write no plan, report this decision, and stop — without re-deriving the supersession from the ledger, which is the session-sized spend V3 rules out paying on every cycle. A plan written on such a dispatch implements behaviour the owner reversed and contradicts the surviving design at its base commit (in OD-5's case: R5 and R28 as amended, R1000, R1008); the review gate should block it citing this decision, exactly as OD-19 binds the orchestrator's case. This does not unstick the driver — nothing an oracle may write can — so the unlock is named for the owner below with its priority raised: what OD-20 recorded as the recommended script fix, BL-22 turns into the single edit standing between the driver and any further unattended progress.
>
> **The standing rule:** a steward dispatched for an `OD-<n>` whose every id on
> its `**Requirements added:**` line is named on some later decision's
> `**Requirements superseded:**` line writes no plan and stops, citing this
> decision. Today that set is exactly OD-5 — R1001, retired by R1008 (OD-13) —
> and the rule is stated generally so the next supersession does not need a
> BL-22 of its own.

*(Entry continues with a numbered "For the owner, in priority order:" list.
Truncated here. — my note.)*

---

## Gaps and risks — what the extraction CANNOT reconstruct

Listed worst first.

1. **The web lane has no machine driver log.** `run/web` landed no
   `docs/runs/<STAMP>/` for the window. Every web-lane phase, iteration number,
   worker id and PR-wait duration exists ONLY as hand-typed prose in
   `docs/runs/operator/web.md`. It is a reconstruction. The two lanes are
   therefore NOT comparable at equal evidence quality. **Any claim of lane
   symmetry is unsupported.**

2. **The `ESC-` namespace is broken.** Two registers share the prefix; `ESC-17`
   and `ESC-21` mean different things in each. The high-numbered register
   (`ESC-26`+, `ESC-14`, `ESC-201`) lives in `GrimsVerk/grimsverk-template` or
   `GrimsVerk/grimsverk-anvil` and is **not reachable** — this session's GitHub
   access is scoped to `grimsverk/find_best_mobo` only. The web ledger records
   the exact denial text as its finding F1. **Those ESC ids cannot be glossed
   from this repository.**

3. **`F<n>` ids collide across lanes.** F1–F36 (local) and F1–F22 (web) are
   independent series. Namespace them or they merge into nonsense.

4. **Actor/role is NOT the git author.** On `run/local` the owner's identity
   `GrimsVerk <github@grimsverk.com>` signs oracle-worker, steward-worker and
   hand-edit commits alike. Role must come from the worker id
   (`WORKER_RESULT id=…`) or the branch slug, which exist only for the local lane.

5. **The 2026-08-24 cleanup merge rewrites experiment evidence in place.**
   `5f0e372` (+ `b443caa`, `eeeafab`) edits three window `run.md` files. Reading
   at the branch tip silently gives you post-hoc text. Use `89351d7`.

6. **A third evidence file is on `main` only.** `docs/runs/operator/runner-2026-08-20.md`
   (`RN-1`..`RN-3`), written during the experiment by a runner session on
   neither lane. It CORRECTS a landed local-lane finding — RN-1 says local F27's
   premise ("This repository is private") is false. **An extraction that reads
   only the four named branches will miss this correction and will carry a
   finding its own author later retracted.**

7. **`run.md` timestamps are time-of-day only** (`11:25:53Z`). The date must be
   joined from the file header (`Started 2026-08-20T11:25:43Z.`) or the
   directory stamp. Wall-clock gaps that cross midnight would break naive
   parsing — none do here, but the parser must still join the date.

8. **Web ledger timestamps are inconsistent in precision.** Some rows are
   `2026-08-20T08:24:10Z`, some are `08:26Z`, some are ranges
   (`08:34-08:46Z`). Wall-clock gap calculations on the web lane will be
   minute-granular at best, and undefined across range rows.

9. **~45% of window commits carry no id in the subject.** Merge commits,
   `Request the pull request` commits and template updates. Their ids must come
   from the diff, not the message.

10. **One malformed table row in `web.md`.** Line 27 area contains two rows
    joined on one line (`… disturb the ledger checkout. || 2026-08-20T08:26Z | …`).
    A strict markdown-table parser will drop or mangle it.

11. **No product source code changed at all** (0 files under `src/`, `tests/`,
    `acceptance/`, `data/` across all four branches). The "did source change?"
    column will be uniformly false unless template machinery is counted as code.
    **State the choice explicitly; it decides the answer.**

12. **PR check results are not in the repo.** Check names, durations and
    pass/fail are recorded only as prose in the two ledgers. The web ledger's
    F6 records that CI logs were unreadable from that session. GitHub API
    reads would be needed, and older check runs may have aged out.
