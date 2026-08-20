# Operator ledger — LOCAL lane

**Lane base branch: `run/local`.** This lane never touches `main` or `run/web`.

Real-delivery template test on this repository: a live project generated at
template **v0.4.27**, brought to **v0.4.37**, then driven unattended. The
product is real — its docs, backlog and plans are genuine and are built as
written. Every friction hit is a template finding recorded here.

Mechanics follow `test-kit/TESTPLAN.md` on GrimsVerk/grimsverk-anvil, Parts 1
and 2, with the owner's overrides: this repository instead of the anvil, an
UPDATE instead of a fresh render, no canned inputs, and this ledger path.

Register values are never written here. They appear as `<repos_root>`,
`<ssh_host>`, `<app_id>`, `<app_pem_path>`.

---

## Phases

| Timestamp (UTC) | Phase | Key fields |
| --- | --- | --- |
| 2026-08-20T16:32:20Z | MID WRAP-UP | R26 stays at 10% (owner reversal); driver console log preserved by hand; worktrees cleared |
| 2026-08-20T15:26:51Z | RUN STOPPED | v0.4.42 run 20260820T112543Z: 26 iterations, exit code 3, three-strikes on PR #133 |
| 2026-08-20T15:26:51Z | EVIDENCE SECURED BY HAND | evidence branch was local-only; operator pushed it (F31) |
| 2026-08-20T11:26:39Z | RESTART/UPDATE | v0.4.41 -> v0.4.42, 4 files, 0 conflicts; PR #119 approved and merged |
| 2026-08-20T11:26:39Z | DRIVER START | v0.4.42, base run/local, 20 points; readiness reports clear base AND no worktrees |
| 2026-08-20T11:26:39Z | STEWARD | iteration 1, worker steward-od-8 |
| 2026-08-20T11:12:08Z | RUN STOPPED | v0.4.41 run 20260820T102917Z: 8 iterations, PRs #109-#117 merged; stopped for the v0.4.42 update |
| 2026-08-20T11:12:08Z | LANE CLEAR | all 4 worktrees read: 0 unmerged, 0 uncommitted; no stale WORK pull requests open |
| 2026-08-20T10:29:05Z | RESTART/CLEANUP | driver refused on 3 leftover worktrees; 1 stranded commit salvaged; cleaned |
| 2026-08-20T10:27:31Z | RESTART/UPDATE | v0.4.39 -> v0.4.41 via update-from-template.sh --base run/local; 5 files, 0 conflicts |
| 2026-08-20T10:27:31Z | RESTART/READY | both lanes at v0.4.41 and gated; readiness exit 0 incl. the ESC-72 clear-base line |
| 2026-08-20T09:36:06Z | RESTART/UPDATE | v0.4.37 -> v0.4.39, 7 files, 0 conflicts, 0 .rej; F1/F10/F13/F14 fixes verified present |
| 2026-08-20T09:36:06Z | RESTART/BLOCKED | PR #105 all checks green, auto-merge armed, BLOCKED on CODEOWNERS review |
| 2026-08-20T09:28:11Z | RUN STOPPED | v0.4.37 run 20260820T085531Z: 6 clean iterations, PRs #100-#103 merged, then steward livelock |
| 2026-08-20T09:28:11Z | EVIDENCE LANDED | docs/run-20260820T085531Z--run-local: run.md + 3 reviews (0 MISSING) + 3 worker logs, by the trap |
| 2026-08-20T08:56:53Z | DRIVER START | base run/local; gauge weekly 79% model 90%; allowance 20 points; max-prs 30; max-hours 12 |
| 2026-08-20T08:56:53Z | ORACLE | iteration 1, worker oracle-20260820085541 |
| 2026-08-20T08:53:17Z | PRE-DRIVER | gauge reachable: session=41 week=78 week_model=88; allowance 20 points |
| 2026-08-20T08:51:57Z | RIG/GATED-BOTH | ruleset include = default + run/local + run/web; 7 checks; both lanes gated |
| 2026-08-20T08:51:57Z | PR MERGED | #98 auto-merged by app/autogrims in 74s; head branch deleted in 4s by delete-merged-branch |
| 2026-08-20T08:49:38Z | PRE-DRIVER PR | #98 docs/bl-15-zero-duration-warning -> run/local (project backlog filing) |
| 2026-08-20T08:46:41Z | RIG/GATED | run/local gated, 7 checks, strict; unattended-ready exit 0, all ready |
| 2026-08-20T08:46:41Z | RIG/WAIT | run/web present at v0.4.37, ungated, awaiting owner gating call |
| 2026-08-20T08:35:37Z | RIG/BLOCKED | gates ruleset = default branch only; run/local ungated; setup-github.sh refused by sandbox |
| 2026-08-20T08:31:00Z | SETUP/UPDATE | v0.4.27 -> v0.4.37 · 23 files · 0 conflicts · 0 .rej · run/local pushed |

---

## Findings

### F1 — the project's own update mechanism cannot run on a lane branch
- **Where:** Part 1 step 2 (THE UPDATE), `scripts/update-from-template.sh`
- **What happened:**

  ```
  $ git branch --show-current
  run/local
  $ scripts/update-from-template.sh
  update-from-template: you are on 'run/local', not 'main'.

  A template update branches off the default branch, so that the pull request
  contains the update and nothing else.
  EXIT: 1
  ```

- **Expected:** the project's own update mechanism brings the checkout to the
  latest template release. It is the documented route, and the owner's
  instruction names it first.
- **Why it fails:** the script hard-asserts `HEAD == default branch`, then
  `git pull --ff-only origin main`, branches `template/<version>` **off main**,
  and opens the pull request **against main**. Every one of those four steps
  assumes the default branch is the base. A lane whose base is `run/local`
  cannot satisfy the first without violating the isolation rule that forbids
  touching `main` at all.
- **The gap:** the template gained per-base-branch lane isolation in v0.4.37
  (`deliver-loop.sh --base`, lane branch suffixes,
  `setup-github.sh --gate-branch`). `update-from-template.sh` did not. It is the
  one remaining piece of machinery with the default branch hard-wired, so a
  lane can be driven but never updated.
- **Suggested fix:** give it the same `--base <branch>` option the driver and
  the setup script already take, defaulting to the default branch.
- **Severity:** bug — blocks the documented route; the fallback below works.
- **Action taken:** fell back to `copier update` directly on `run/local`, as the
  owner's instruction provides for.

### F2 — the v0.4.27 -> v0.4.37 update itself was clean (positive observation)
- **Where:** Part 1 step 2 (THE UPDATE), `copier update --vcs-ref=v0.4.37`
- **What happened:** ten template releases in one jump, on a project with a
  month of divergent history. 23 files changed, 1155 insertions, 184 deletions.
  **Zero conflict markers, zero `.rej`, zero `.orig`.** Nothing needed the
  conflict rule applied; the template side and the project side never collided.
- **Checked, not assumed:** every file the template and the project both own
  was diffed by hand. `docs/DECISIONS.md` gained a new template decision
  *above* the `<!-- Append project decisions below -->` marker and all four
  project rulings below it survive verbatim. `pyproject.toml` gained only the
  template's `pre-commit~=4.0` dev pin (ESC-55). `AGENTS.md` and `README.md`
  took the template side, as the conflict rule directs. `src/`, `tests/`,
  `acceptance/` and every project document were untouched.
- **Severity:** none — recorded because a ten-release jump landing clean is
  exactly the claim the template makes and it has now been observed once.

### F3 — copier prints a false prerequisite warning on every update
- **Where:** Part 1 step 2, `copier update` output
- **What happened:**

  ```
  Updating to template version 0.4.37
  Make sure Git >= 2.24 is installed to improve updates.
  $ git --version
  git version 2.55.0
  ```

- **Expected:** no warning. Git 2.55.0 is thirty-one minor versions past the
  stated requirement.
- **Note:** this is copier's message, not the template's, so it is not a
  template defect. It is recorded because the template's own update script
  passes copier's output straight through to the operator, and an operator
  following the documented route sees an unmet-prerequisite warning that is
  not true. A one-line note in the update script's output would cost nothing.
- **Severity:** friction

### F4 — the lane branch pushed with no ruleset rejection
- **Where:** Part 1 step 6
- **What happened:** `git push -u origin run/local` succeeded first try, exit 0.
  The plan's step 6 anticipates a rejection here ("required status checks have
  not succeeded") when a stale ruleset from a previous round still names the
  lane, and routes the local lane through step 6a first to clear it.
- **Expected on this repository:** no rejection. This is not a wiped anvil
  round — the ruleset here already names the default branch only.
- **Severity:** none — recorded so the two lanes' step-6 behaviour can be
  compared, and so a later rejection is known to be new rather than stale.

### F5 — the lane branch is UNGATED, and the operator cannot gate it
- **Where:** Part 1 step 6a (rig duties), `scripts/setup-github.sh --app`
- **What happened:** the command was refused by the operator's own harness
  permission layer before it could run:

  ```
  $ scripts/setup-github.sh --app
  Permission for this action was denied by the auto mode classifier.
  ```

- **State it was meant to change**, read back through the API:

  ```
  $ gh api repos/GrimsVerk/find_best_mobo/rulesets/<id> --jq ...
  {"name":"grimsverk-gates",
   "conditions":{"include":["~DEFAULT_BRANCH"],"exclude":[]},
   "checks":["checks","secrets","plan","template-sync","test-the-tests",
             "acceptance-criteria","review"],
   "strict":[true]}
  ```

  The gates ruleset names the **default branch only**. `run/local` carries no
  required checks at all, which is also why the step-6 push was accepted
  without argument (F4).
- **Expected:** step 6a-4 runs
  `scripts/setup-github.sh --app --gate-branch run/local --gate-branch run/web`
  so every pipeline pull request into a lane base must pass all seven checks.
- **Consequence if unresolved:** the driver would run against an ungated base.
  Its pull requests would merge with nothing required — no review, no
  acceptance, no plan gate. That is not a degraded run, it is a different test.
- **Not a template defect.** The script is correct and available; the refusal
  comes from the operator's sandbox, which declines repository-administration
  calls. Recorded because it is a real obstacle to running this test
  unattended on this machine, and because the fix is the owner's to grant.
- **Severity:** blocker (rig, not template)
- **Lane state:** stopped before starting the driver. Nothing dispatched.

### F6 — F5 cleared by the owner; `run/local` gated and readiness fully green
- **Where:** Part 1 steps 6a and 7
- **What happened:** the owner ran the refused command themselves. The gates
  ruleset now reads
  `include: ["~DEFAULT_BRANCH","refs/heads/run/local"]`, all seven checks,
  `strict_required_status_checks_policy: true`, enforcement active.
- `RUN_BASE=run/local .github/scripts/unattended-ready.sh` returns **exit 0**,
  25 lines, every one `ready` — including all seven checks binding
  specifically at base branch `run/local`, which is the v0.4.37 per-base
  isolation being observed working for the first time on this project.
- One `note` line, not a failure: template reads are minted from the App, so
  the App must also be installed on the template repository or `template/`
  branches fail `template-sync` closed.
- **Severity:** none — closes F5.

### F7 — `run/web` exists and is unblocked-pending; the local operator cannot gate it
- **Where:** Part 1 step 6a-4
- **What happened:** `run/web` appeared at `13110cb`, one commit off the same
  `main` this lane branched from, `_commit: v0.4.37` — the same release, so
  the twin-run precondition holds.
- The gating call that must now cover BOTH lanes is the same
  repository-administration command the operator's sandbox refuses (F5), so it
  goes back to the owner a second time.
- **Consequence while it waits:** `run/web` carries no required checks, and the
  web lane is inside its own bounded 45-minute poll waiting for this exact
  change. The delay is charged to the local lane's rig duties, not to the web
  agent.
- **Severity:** blocker (rig, not template) — the same root cause as F5.

### F8 — project bug filed as BL-15 (not a template finding; recorded for the trail)
- **Where:** between rig duties and driver start, on lane base `run/local`
- **What:** the first real `index` run after the `timestamp` fix (PR #67)
  warned that 8 videos reported no duration. All 8 checked by hand: every one is
  a genuine Short, correctly classified `excluded_short`, `was_live` false, and
  carrying no date in either field. No video was dropped — the warning's
  premise, that only one video can legitimately report no duration, is wrong for
  the flat listing shape, so it fires on every run and buries the ninth id that
  would be a real silent drop.
- **Filed as:** `BL-15` in `docs/BACKLOG.md`, Proposed section, PR #98 into
  `run/local`.
- **This is a PROJECT defect, not a template one.** Recorded here only so the
  operator's trail is complete; it belongs to find_best_mobo and is not for
  upstream collection.
- Both gates were run locally before pushing: `backlog-append-only.sh` reports
  29 landed items intact, `plan-resolve.sh` grants the `docs/BACKLOG.md`
  exemption at any size (81 lines added).
- **Severity:** none, as a template finding.

### F9 — observation checklist: four never-observed claims confirmed live on PR #98
- **Where:** Part 2 rule 9, on the pre-driver backlog filing (PR #98 into `run/local`)
- PR #98 was a real pipeline pull request through the full seven-check gate, so
  it answers several checklist items outright. Times are UTC, read from the API.

**1. Auto-merge completes without a human (ESC-36).** Confirmed.
`autoMergeRequest.enabledBy = app/autogrims`, `enabledAt 08:49:33`;
`mergedBy = app/autogrims`, `mergedAt 08:50:47`. **74 seconds**, no human
action, merge method MERGE. The `arm-auto-merge` job shows `skipped` on the
post-merge workflow run, which is correct — it had already armed the pull
request on the earlier pull_request run.

**2. The head branch disappears — and by which path (ESC-21).** Confirmed, and
this is the item with four wrong theories on record and no observation.
`git ls-remote --heads origin 'docs/bl-15*'` returns nothing: **GONE**.
The path is now known: the `delete-merged-branch` job, started `08:50:53`,
completed `08:50:57` — **4 seconds, immediately after the merge**. The
`sweep-merged-branches` job in the same run is `skipped`. So it is the
immediate path, not the nightly sweep. First live observation.

**3. Every pipeline pull request is authored by the App (ESC-26, ESC-35).**
Confirmed. `author = app/autogrims`, a bot login, never the owner's.

**4. `update-open-prs` runs after a merge (ESC-17).** Ran, `success`,
`08:50:53 -> 08:50:58`, 5 seconds. **Partial observation only** — no other pull
request was open at the time, so it succeeded with nothing to update. The real
claim (an open PR auto-updated with its checks re-running) is still unobserved
and stays on the checklist for the driver's run.

**5. Required check durations (ESC-45 — a ~1s "pass" is a skip).** All seven,
on the pull_request run:

| check | duration |
| --- | --- |
| `review` | 1m14s |
| `checks` | 16s |
| `acceptance-criteria` | 13s |
| `template-sync` | 12s |
| `secrets` | 11s |
| `test-the-tests` | 11s |
| `plan` | 6s |

Nothing near the ~1s skip signature. The `0`-duration `skipping` entries that
also appear in `gh pr checks` belong to the push-triggered workflow's duplicate
jobs, which are meant to skip; the pull_request run is the one the ruleset
binds. No finding.

- **Severity:** none — these are positive confirmations, and items 1, 2 and 3
  are first-ever live observations of claims the template had only reasoned
  about.

### F10 — `setup-github.sh` leaves untracked evidence that then blocks the driver
- **Where:** Part 1 step 6a -> step 7, `scripts/setup-github.sh --app`
- **What happened:** after the two setup runs, the lane tree was no longer clean:

  ```
  $ git status --short
  ?? docs/runs/setup/
  $ find docs/runs/setup -type f
  docs/runs/setup/setup-github-20260820T084514Z.log
  docs/runs/setup/setup-github-20260820T084804Z.log
  ```

- The script writes a timestamped log of each run into `docs/runs/setup/`. That
  is good behaviour — it is exactly the self-recording the template promises.
  But nothing commits the file and nothing ignores it, so it is left untracked
  in the working tree.
- **Why that matters here:** the very next documented step is starting the
  driver, and `deliver-loop.sh` refuses to start on a dirty tree. The
  template's own setup step therefore leaves the repository in the one state
  its own driver step rejects. On this machine the previous run's driver
  refusal was recorded for the same class of reason
  (`run2-refused-dirty-tree`).
- **Expected:** one of three, any of which closes it — the script commits its
  own log, or `.gitignore` covers `docs/runs/setup/`, or the script prints what
  the operator must now do with the file before starting the driver. It does
  none of the three.
- **Checked:** neither log contains any identity-register value, so committing
  them is safe under rule 13. Verified by comparing every register value, and
  the home directory path, against both files.
- **Severity:** bug — a documented two-step sequence where step one blocks step
  two, with no message saying so.
- **Action taken:** committed the logs to the lane as run evidence, which is
  where the template plainly meant them to live.

### F11 — the budget gauge is reachable, and reads high before the run starts
- **Where:** Part 2 rule 8, `.claude/scripts/budget-probe.sh`
- **What happened:** the probe returns a real reading with **no** environment
  configuration at all — `BUDGET_PROBE_CMD` was unset in the driver's shell:

  ```
  $ .claude/scripts/budget-probe.sh
  session=41 week=78 week_model=88 reset=Aug 20, 11am (Europe/Amsterdam)
  rc=0
  ```

- **Against rule 8:** the gauge is reachable, so there is no blocker finding
  here, and no silent fallback to pull-request-per-hour limits. Positive
  observation: the probe finds the subscription reader on its own, which the
  earlier run needed an explicit `BUDGET_PROBE_CMD` export to do.
- **Recorded for the owner, not as a defect:** the weekly gauge is already at
  **78%** and the model-specific gauge at **88%** before the driver has spent
  anything, against a `--budget-points 20` allowance. If the allowance is read
  as a delta, the run can reach 98% weekly. The run may therefore stop on the
  allowance well before `--max-prs 30` or `--max-hours 12`. Flagged so an early
  budget stop is read as expected arithmetic rather than as a fault.
- **Severity:** none

### F12 — driver started; both rule-8 requirements met
- **Where:** Part 1 step 7 / driver start
- **Command:**

  ```
  nohup .claude/scripts/deliver-loop.sh --base run/local \
    --budget-points 20 --max-prs 30 --max-hours 12 \
    > /tmp/mobo-local-driver.log 2>&1 &
  ```

- **It announces this run's base branch**, in a banner, before anything else:

  ```
  THIS RUN'S BASE BRANCH: run/local
  Every pull request this run opens will merge into 'run/local',
  and this run waits only on pull requests targeting 'run/local'.
  Non-default base: every branch this run pushes is suffixed '--run-local'.
  ```

  The branch-suffix line is the v0.4.37 lane isolation stating itself, and is
  what keeps this lane's branches distinguishable from `run/web`'s.
- **It shows a real gauge reading**, not a fallback:

  ```
  deliver-loop: budget: weekly at 79% (model 90%), allowance 20 points, ...
  ```

  Rule 8 is satisfied: a live gauge, no silent fall back to pull-request-per-hour
  limits. Re-verified: the readiness check ran again inside the driver and
  returned every line `ready`, including all seven checks binding at
  `run/local`.
- **First dispatch:** `iteration 1: phase ORACLE`, worker
  `oracle-20260820085541`.
- **Severity:** none — positive confirmation.

### F13 — the budget line's reset value is truncated mid-word
- **Where:** driver start banner, `deliver-loop.sh`
- **What happened:** the line ends on a bare month name:

  ```
  deliver-loop: budget: weekly at 79% (model 90%), allowance 20 points, window resets Aug
  ```

  Confirmed against the raw log with `cat -A` — the line genuinely ends there;
  nothing was cut by a terminal or a pager.
- **What the probe actually returns:** the full value is present one layer down —
  `.claude/scripts/budget-probe.sh` prints
  `reset=Aug 20, 11am (Europe/Amsterdam)`. The reset field contains spaces and
  commas, and the driver's formatting takes only the first whitespace-separated
  token of it.
- **Expected:** the whole reset time. It is the one field that tells an operator
  reading a stopped run's log whether the window had already turned over, and
  it is exactly the field that gets dropped.
- **Severity:** friction — cosmetic in isolation, but it removes the only
  timestamp that makes a budget stop interpretable after the fact.

### F14 — the steward/oracle livelock reproduced here (confirms the anvil's ESC-66/67)
- **Where:** driver run `20260820T085531Z`, iterations 7 and 8, phase STEWARD
- **What happened:** the run advanced properly for six iterations —
  ORACLE -> WAIT -> STEWARD -> WAIT -> ORACLE -> WAIT — merging PRs #100 through
  #103. Then the steward on OD-6 did exactly what the planning rule tells it to:
  it hit a HIGH-risk question it may not rule on, filed it as `BL-16` in
  `docs/BACKLOG.md`, committed that alone, and stopped. Its own log says so:

  > That makes it HIGH-risk under the planning rule, which means I may not rule
  > on it. So I filed it as **BL-16** in `docs/BACKLOG.md`, with my proposed
  > default (no cross-cue joining), committed that alone, and stopped. **The
  > driver should now run the oracle on BL-16 and re-dispatch me.**

- **The driver did not run the oracle.** It read the steward's deliberate stop
  as a worker failure and re-dispatched the same steward:

  ```
  iteration 7: phase STEWARD
  dispatch steward worker (steward-od-6)
  steward worker failed — see .claude/orchestration-logs/steward-od-6.log
  iteration 8: phase STEWARD
  dispatch steward worker (steward-od-6)
  ```

  Three dispatches of the identical worker, no phase change, no oracle. Left
  alone it would have spent the whole allowance re-asking a question it had
  already filed.
- **Significance:** this is the livelock the anvil lane found (ESC-66/67),
  reproduced independently on a different repository with a genuinely different
  question. It is not anvil-specific and not bait-specific — a correct steward
  stop is indistinguishable, to this driver, from a crash.
- **Severity:** blocker — already fixed upstream in v0.4.39; recorded as
  independent confirmation from a second lane.

### F15 — worker tool grants use `Write(path)`, which binds nothing
- **Where:** `.claude/scripts/spawn-worker.sh` role grants, seen in
  `steward-od-6.log`
- **What happened:** every steward dispatch opened with the engine rejecting two
  of its own grants:

  ```
  Permission allow rule (--allowed-tools): Write(docs/plans/oracle/**) is not
  matched by file permission checks — only Edit(path) rules are.
  Use Edit(docs/plans/oracle/**) instead (Edit rules cover all file-editing tools).
  Permission allow rule (--allowed-tools): Write(docs/BACKLOG.md) is not
  matched by file permission checks — only Edit(path) rules are.
  ```

- **Expected:** the steward is granted write access to the two paths its role
  exists to write. `Write(path)` rules match nothing; only `Edit(path)` rules
  bind, and `Edit` rules already cover every file-editing tool.
- **Consequence:** the steward's two most important write targets — the oracle
  plan directory and the backlog it must file uncertainties into — are
  ungranted. It worked here only because the fallback path allowed it; the
  grant itself is inert.
- **Severity:** bug — needs checking against v0.4.39; if still present it is
  live.

### F16 — the template landed its own evidence, complete, with no failsafe (positive)
- **Where:** driver stop, `deliver-loop.sh` EXIT trap
- **What happened:** on SIGTERM the trap ran unprompted:

  ```
  deliver-loop: landing this run's evidence in docs/runs/20260820T085531Z ...
  collect-evidence: 3 worker log(s) into docs/runs/20260820T085531Z/workers.
  collect-evidence: 3 review(s) into docs/runs/20260820T085531Z/reviews (97 skipped).
  ```

  and pushed `docs/run-20260820T085531Z--run-local` — correctly lane-suffixed.
- **Contents, checked against rule 9:** `run.md` present, 2186 bytes, not empty.
  `reviews/` holds all three pull requests with full `meta/payload/reply/verdict`
  and an `index.md`. **Zero `MISSING.md` files** — ESC-43 observed fixed.
  `workers/` holds all three worker logs — ESC-42 observed fixed.
- **This is explicitly NOT a `TEMPLATE SELF-RECORDING FAILURE` row.** No failsafe
  was used, nothing was secured by hand, and nothing had to be recovered. The
  template's own promise held at the stop. Recorded because the failure mode
  this whole test exists to catch did not occur, which is only meaningful if the
  success is written down too.
- **Severity:** none — positive confirmation.

---

## RESTART — v0.4.39

The owner restarted the lane at template **v0.4.39**. Findings F1-F16 stand as
written; nothing above is revised. This section continues the same ledger.

v0.4.39 carries the fixes for three findings this lane filed, plus the oracle
livelock this lane independently reproduced. All four verified present in the
updated tree before the restart:

| finding | fix, verified in the v0.4.39 tree |
| --- | --- |
| F1 | `scripts/update-from-template.sh` now takes `--base <b>` (line 26 help, line 42 parse, line 222 `gh pr create`) |
| F10 | `scripts/setup-github.sh` `git add` + `git commit` its own transcript (lines 126-127), so setup no longer leaves the tree dirty |
| F13 | `deliver-loop.sh` reads the reset field to end-of-line — "reset= is the probe's LAST field by contract and its value contains spaces" (line 622) |
| F14 | oracle livelock, ESC-66/67 |

**F13's reach, per the owner:** the truncation was not cosmetic after all. It
was the root cause of a live window-rollover miss on the other test bed. Logged
here because this lane filed it as *friction* — the lowest severity it carries —
and the severity was wrong. A dropped timestamp is not a display defect when a
scheduler reads the same value.

### F17 — the v0.4.37 -> v0.4.39 update, and why the F1 fix could not be used for it
- **Where:** restart step 2 (THE UPDATE)
- The shipped updater is still the v0.4.37 one, so it refused the lane exactly
  as F1 recorded: `update-from-template: you are on 'run/local', not 'main'.`
  Its `--base` fix arrives *inside the pull request being opened*, so the first
  update after the fix must still be done by hand; every one after it can use
  the script. Not a new finding — the ordering is inherent, and worth one line
  so it is not re-filed next round.
- `copier update --vcs-ref=v0.4.39`: seven files, **no conflicts, no `.rej`**.
  Second clean update in a row on this project.
- **Severity:** none

### F18 — the update pull request is BLOCKED on CODEOWNERS, exactly as designed
- **Where:** restart, PR #105 into `run/local`
- **State:** all seven required checks green (`review` 1m32s, `template-sync`
  15s, `checks` 16s, `acceptance-criteria` 13s, `secrets` 11s, `test-the-tests`
  9s, `plan` 8s), `arm-auto-merge` **pass** 7s, auto-merge armed —
  and `mergeStateStatus: BLOCKED`, `reviewDecision: ""`.
- **Why:** the update touches four CODEOWNERS-owned gate paths —
  `.claude/scripts/`, `.github/scripts/`, `.github/workflows/`, `scripts/`. The
  owner's review is required and has not been given.
- **This is the machinery working**, and the update script's own closing message
  predicts it in advance: "You will have to approve it. A template update
  touches CODEOWNERS-owned paths… That is deliberate: a change to this
  project's gates is exactly what a person should look at."
- **It also sets up a Part 3 closing action.** The pull request is authored by
  `app/autogrims`, not the owner — which is the only reason the owner *can*
  approve it, since GitHub refuses an author's approval of their own pull
  request. ESC-35 predicted this works and nothing has ever observed it. The
  owner's approval here is that observation.
- **Severity:** none — expected, and blocking the restart until approved.

---

## RESTART — v0.4.41

Second restart, ordered by the owner. Findings F1-F18 stand as written.

### F19 — F1 and F3 confirmed fixed, observed in use (not just read)
- **Where:** restart step 2, `scripts/update-from-template.sh --base run/local --no-pr`
- The updater this lane could not use at all in F1 ran the whole update:

  ```
  update-from-template: refreshing run/local
  update-from-template: currently on template v0.4.39
  update-from-template: (copier may print 'Make sure Git >= 2.24 is installed' —
    that is copier's stock advisory, not a real prerequisite failure; any
    modern git satisfies it)
  update-from-template: v0.4.39 -> v0.4.41
  Switched to a new branch 'template/v0.4.41--run-local'
  ```

- **F1 closed.** It refreshed `run/local`, not `main`, and cut a **lane-suffixed**
  branch `template/v0.4.41--run-local`. Both are the behaviours F1 asked for.
- **F3 closed.** The copier advisory is now annotated inline, one line before
  copier prints it, saying in plain words that it is not a real failure.
- **Severity:** none — two closures, both observed rather than inferred.

### F20 — F10's fix verified in the tree, not observed live
- `scripts/setup-github.sh` now runs `git add` then `git commit -q -m "Record the
  setup-github transcript"` on its own log (lines 126-127), and its header says
  it "records its own transcript under docs/runs/setup/".
- **Honest limit:** no setup run was needed this restart (see F22), so the fix is
  read in the source, not watched working. Recorded as verified-by-reading.
- **Severity:** none

### F21 — F15 confirmed fixed, both halves
- **The inert grants (this lane's F15).** Every `Write(path)` in
  `spawn-worker.sh` now carries an `Edit(path)` twin, with the reason written
  beside it: "Every Write() carries an Edit() twin, and the twin is the half
  that … rejects Write(path) with a warning". The steward's two ungranted
  targets, `docs/plans/oracle/**` and `docs/BACKLOG.md`, both have twins.
  Note the template credits the anvil's F7 for this; the two lanes filed the
  same defect independently.
- **Lane-scoped `update-open-prs`.** The job now reports
  `update-open-prs: base $BASE_REF — updated N, M conflicted, K skipped`, so a
  merge in this lane no longer churns `run/web`'s pull requests.
- **Severity:** none — closure.

### F22 — ESC-72's new readiness line passes, and the rig duties were already met
- **The new line, green:**

  ```
  ready    no pull request is open against 'run/local' — the run starts on a clear base
  ```

  This is the check for the exact condition that stranded this lane at v0.4.37,
  where the run's first act would have been to wait on a pull request needing a
  human review no unattended actor can give.
- **Rig duties, checked rather than repeated.** `setup-github.sh` was NOT re-run,
  deliberately. Its three purposes were each verified already satisfied, by API
  read: App identity proves out (`app-token.sh` exit 0); the `grimsverk-gates`
  ruleset already includes `~DEFAULT_BRANCH`, `refs/heads/run/local` **and**
  `refs/heads/run/web`, active, with all seven checks; and readiness returns
  exit 0. Re-running it would have reset the ruleset to the default branch only
  before re-gating, opening a window in which both lanes were ungated, to reach
  a state already held. Recorded as a judgment, not an omission.
- **`run/web` needed no waiting** — it was already at `_commit: v0.4.41`, and its
  own `unattended-ready --runtime` returns exit 0 including the same clear-base
  line. The bounded 45-minute poll was not entered.
- **Severity:** none

### F23 — ESC-35 observed live, twice: the owner CAN approve an App-authored pull request
- **Where:** PRs #105 and #107, both `author: app/autogrims`
- GitHub refuses an author's approval of their own pull request, so this only
  works because the pipeline's pull requests are opened by the App and not by
  the owner. ESC-35 predicted it; nothing had ever observed it.

  | PR | approved by | approved at | merged at | gap |
  | --- | --- | --- | --- | --- |
  | #105 | `GrimsVerk` | 10:12:52Z | 10:12:54Z | 2s |
  | #107 | `GrimsVerk` | 10:24:33Z | 10:25:39Z | 66s |

- Both merged by `app/autogrims` under armed auto-merge, with every required
  check already green — the approval was the last gate in each case.
- This is Part 3's closing action 1, satisfied on the template-update pull
  requests rather than on an acceptance one.
- **Severity:** none — first live observation.

### F24 — the driver refused to start on leftover worktrees, correctly, and nothing said to clean them
- **Where:** restart, driver start
- **What happened:** the first start attempt refused outright:

  ```
  deliver-loop: leftover worktrees under .worktrees/ — a previous run did not
  finish assembling; inspect and remove them first
  ```

  Three worktrees survived the v0.4.37 run being killed:
  `oracle-20260820085541`, `oracle-20260820090923`, `steward-od-6`.
- **The refusal is right and the message is right** — it says what is wrong,
  where, and what to do. No finding against it. Recorded for two other reasons.
- **First: the readiness check does not know about it.**
  `RUN_BASE=run/local .github/scripts/unattended-ready.sh` returned **exit 0,
  every line ready**, minutes before the driver refused to start. Readiness is
  the step the plan puts immediately before "start your driver", and it passes a
  repository the driver will not run in. ESC-72 just added a clear-base check to
  exactly this script for exactly this class of problem — a precondition the
  driver enforces that readiness cannot see. Leftover worktrees belong in the
  same list.
  **Severity: bug** — a green readiness check that is not a green light.
- **Second: one worktree held unmerged work.** `worker/steward-od-6` carried a
  commit that is on no other branch —
  `35cceee Plan OD-6 and OD-15: caption-split aliases match within a cue,
  cross-cue splits are counted`. The steward wrote a real plan on its last
  dispatch before the run was killed; it never reached a pull request. The two
  oracle worktrees held nothing unmerged (0 commits each), and `BL-16` — the
  uncertainty the steward filed during the livelock — **did** land on the lane
  base, so that part was not lost.
- **Secured before cleanup**, per the stop rule: the commit is saved as
  `docs/runs/operator/salvage/steward-od-6-stranded-plan.patch` on this ledger
  branch, 562 lines, and can be replayed with `git am`. The branch was then
  deleted so the restarted run cannot collide with a `worker/steward-od-6` name
  it will create itself.
- **Not a `TEMPLATE SELF-RECORDING FAILURE`.** The template's evidence trap had
  already landed the run report, reviews and worker logs (F16); this commit is
  work-in-flight at the moment of the kill, which the trap does not claim to
  capture. Salvaged by hand because it was real work, not because a promise
  broke.

---

## RESTART — v0.4.42

Third restart. Findings F1-F24 stand. The v0.4.41 run
(`20260820T102917Z`) reached 8 iterations and merged PRs #109 through #117
before being stopped for this update; three of its findings are below.

### F25 — ESC-74 observed live: the window "reset" flapped five times in one run
- **Where:** v0.4.41 run, `deliver-loop.sh` budget re-baselining
- **What happened:** the driver announced a mid-run weekly reset **five times**,
  alternating between two renderings of the same instant:

  ```
  the weekly window reset mid-run (Aug 27, 11am -> Aug 27, 10:59am) — re-baselining the allowance
  the weekly window reset mid-run (Aug 27, 10:59am -> Aug 27, 11am) — re-baselining the allowance
  the weekly window reset mid-run (Aug 27, 11am -> Aug 27, 10:59am) — re-baselining the allowance
  the weekly window reset mid-run (Aug 27, 10:59am -> Aug 27, 11am) — re-baselining the allowance
  the weekly window reset mid-run (Aug 27, 11am -> Aug 27, 10:59am) — re-baselining the allowance
  ```

  (Timezone suffix `(Europe/Amsterdam)` trimmed from each line for width; it was
  identical on both sides of every arrow.)
- **The two values are the same moment**, rounded differently by the upstream
  gauge — 10:59am and 11am one minute apart, never a real weekly rollover, which
  can happen at most once and not at all inside a 40-minute run.
- **Why it matters:** each "reset" **re-baselines the allowance**, so the 20
  points were reset to zero-spent five times. A run that flaps like this can
  never reach its ceiling: the ceiling is moved every other iteration. The
  budget was the one limit the owner said they would actually rely on.
- **Independent confirmation of ESC-74**, which v0.4.42 fixes by comparing the
  reset as an instant rather than as a rendered string. Recorded because this
  lane watched it happen rather than reading about it.
- **Severity:** blocker — an allowance that re-zeroes is not an allowance.

### F26 — ESC-75 observed live: a killed run reports exit code 0 and no reason
- **Where:** v0.4.41 run stop, landed report
  `docs/runs/20260820T102917Z/run.md`
- **What happened:** the run was stopped with `SIGTERM`. The report records:

  ```
  Stopped 2026-08-20T11:08:20Z with exit code 0.
  ```

  Exit code 0 is "finished cleanly". No stop reason is given, and the driver's
  own log ends after the evidence lines with no stop line at all.
- **Expected (and what v0.4.42 now does):** a stop with no reason is exit code
  **7**, never 0, and kills are trapped and named.
- **Why it matters beyond tidiness:** the exit code is what a reader of the
  landed report has to judge the run by. A killed run and a completed run are
  currently indistinguishable in the one artefact that outlives the session.
- **Independent confirmation of ESC-75.**
- **Severity:** bug

### F27 — the landed run report leaks the operator's absolute machine paths
- **Where:** `docs/runs/20260820T102917Z/run.md`, merged to the lane in PR #117
- **What happened:** every `WORKER_RESULT` line records the worktree as an
  absolute path:

  ```
  WORKER_RESULT id=steward-od-6 branch=docs/oracle-plan-caption-split-aliases
    worktree=<repos_root>/find_best_mobo/.worktrees/steward-od-6 engine=claude exit=0 commits=1
  ```

  Four such lines, in a file that is committed, pushed, and merged.
- **The literal path expands the owner's `repos_root` register value**, together
  with the home directory it sits under. Under the test kit's rule 13 that is
  exactly the thing that must never appear in a pushed file — and the plan says
  a register value found in anything pushed is itself a finding.
- **The template wrote it, not the operator.** No hand-editing put it there;
  `deliver-loop.sh` composes the line. So no amount of operator discipline
  prevents it — the rule cannot be kept while this line is emitted as-is.
- **This repository is private, so the exposure here is small.** The finding is
  that the mechanism is unconditional: the same code renders the same absolute
  path into a public project's run evidence.
- **Suggested fix:** record the worktree relative to the repository root
  (`.worktrees/steward-od-6`), which is the only part that carries meaning to a
  later reader anyway.
- **Severity:** bug
- **Note:** the paths quoted in THIS ledger are masked to `<repos_root>` by hand.

### F28 — the evidence pull request opened and merged on its own (positive)
- `docs/run-20260820T102917Z--run-local` was pushed by the trap, opened as
  **#117**, and **merged** — `run.md`, 3 review payloads with **zero
  `MISSING.md`**, and **4** worker logs. ESC-40 and ESC-43 confirmed again, on a
  second run. Second consecutive clean self-recording; no failsafe used.
- **Severity:** none

### F29 — F24 closed: readiness now refuses on leftover worktrees, and says to read them first
- **Where:** restart step 3, `.github/scripts/unattended-ready.sh`
- **The gap F24 named is closed.** Readiness now carries the check, and both
  new lines report green on a clear lane:

  ```
  ready    no pull request is open against 'run/local' — the run starts on a clear base
  ready    no leftover worktrees — no dead run's debris in the way
  ```

- **The refusal path does more than refuse.** It names the worktrees it found
  and tells the reader to READ them before removing them, with the two commands
  to do it. The source comment gives the reason, and it is this lane's own
  incident: *"a leftover worktree can hold a worker's finished, unpushed
  commits — a real plan was salvaged from one as a 562-line patch — so read it
  before removing it."* That is F24's salvage, upstream.
- **Severity:** none — closure, and the strongest form of one: the fix carries
  the reasoning, not just the check.

### F30 — driver restarted at v0.4.42
- **Command:** unchanged — `--base run/local --budget-points 20 --max-prs 30
  --max-hours 12`.
- **Start state:** base `78a8ae3` (v0.4.42), tree clean, zero worktrees, zero
  open pull requests, readiness exit 0.
- **Banner:** `THIS RUN'S BASE BRANCH: run/local`.
- **Budget, with the full reset value (F13's fix holding):**

  ```
  budget: weekly at 10% (model 9%), allowance 20 points, window resets Aug 27, 11am (Europe/Amsterdam)
  budget: weekly at 10% (model 9%), spent 0 of 20 points on the per-model weekly limit
  ```

- **First dispatch:** `iteration 1: phase STEWARD`, worker `steward-od-8`.
- **Watching, per the owner's instruction:** the per-iteration budget line; the
  stop line against the landed report's exit code and reason (F26's fix); and
  any refusal readiness did NOT catch — that class is now the finding.
- **Severity:** none

### F31 — TEMPLATE SELF-RECORDING FAILURE: run evidence for 20260820T112543Z was collected but never pushed; the operator's manual push caught it
- **Where:** v0.4.42 run stop, `deliver-loop.sh` evidence trap
- **What the template failed to record:** the run's own evidence branch. The
  trap ran and said it had done the work:

  ```
  deliver-loop: landing this run's evidence in docs/runs/20260820T112543Z ...
  collect-evidence: 10 worker log(s) into docs/runs/20260820T112543Z/workers.
  collect-evidence: 10 review(s) into docs/runs/20260820T112543Z/reviews (78 skipped).
  ```

  The branch `docs/run-20260820T112543Z--run-local` existed **locally only**.
  `git ls-remote --heads origin` did not have it, and no evidence pull request
  was opened. Ten worker logs and ten review payloads — the whole record of a
  26-iteration run — sat on one machine with nothing pointing at them.
- **The likely cause is visible three lines earlier in the same log:**
  `deliver-loop: pull --ff-only failed; continuing on the local tree`. The
  driver noted the failure, carried on, and the later push inherited the broken
  state without a second complaint.
- **Which failsafe caught it:** none of the template's. The operator checked
  `git ls-remote` by hand at the stop, found the branch missing, and pushed it.
  Verified after: 52 files, **zero `MISSING.md`**, so the *contents* were
  complete — only the delivery failed.
- **Why this is the named row and not a summary line:** the template promises to
  land its own evidence at every stop. Here it announced success and delivered
  nothing, which is worse than failing loudly — a reader of the log would have
  believed the evidence was safe. This is the exact failure mode the anvil
  exists to catch.
- **Severity:** blocker

### F32 — F26 confirmed fixed: the stop now carries a real exit code and a reason
- The landed report reads:

  ```
  Stopped 2026-08-20T13:49:30Z with exit code 3: the same checks failed three
  times on docs/r26-fifteen-percent (plan review )
  ```

  Against F26's `exit code 0` and no reason for a killed run. A reader of the
  report can now tell what ended the run without the console log. Closure.
- **Severity:** none

### F33 — the driver spent three fix sessions on a pull request that could never go green
- **Where:** iterations 24-26, PR #133 (`docs/r26-fifteen-percent`)
- **What happened:** the operator opened a pull request editing `docs/DESIGN.md`
  — an owner ruling, changing R26's cap from 10% to 15%. The `plan` check failed
  with:

  > An agent's job here ends at a pushed branch. GrimsVerk opens the pull
  > request, reads the diff, and merges it — and that reading is the point.

  `docs/DESIGN.md` may only reach a pull request the **owner** opened. The
  operator opened it through the App, so it was App-authored and the check
  failed — correctly, and it would fail identically on every retry.
- **The driver could not tell.** It read a red required check, dispatched a fix
  session, watched it fail, and repeated until its three-strikes rule stopped
  the run. Three model-funded sessions against a check whose failure text says
  the fix is not a code change but a different human opening the pull request.
- **The run report says so itself**, unprompted: *"Nothing stopped a design edit
  from being composed onto a driver-opened branch in the first place, which
  guarantees a permanently red required check and stalls the lane until someone
  notices by hand. That's a ratchet candidate."* The worker diagnosed the class
  correctly and could not act on it.
- **Operator error contributed** and is recorded as such: the App token should
  not have been used to open a `docs/DESIGN.md` change. But the machinery has no
  guard — nothing refuses the push, warns at open time, or marks the failure
  unfixable-by-agent — so the same mistake costs three sessions every time.
- **Suggested fix:** classify owner-authored failures as terminal for a fix
  session, and stop after the first rather than the third.
- **Severity:** bug

### F34 — the steward has no delete or rename grant, and leaves scratch behind
- **Where:** worktree `steward-od-13`, uncommitted file
  `docs/plans/oracle/whole-transcript-sequential-bundles.md`
- The steward wrote its own explanation into the file it could not remove:

  > NOT A PLAN. Scratch left by the OD-13 steward session, never committed. …
  > The steward's tool grant carries no file deletion or rename, so the
  > replacement was done as an in-place rewrite of that file instead, and this
  > one could not be removed. It is deliberately left with no front matter: if
  > it were ever committed by accident, `plan-lint.sh` fails a plan with no
  > `slug:` field, which is a loud failure rather than a silent second plan
  > claiming the same routing.

- **Good judgment under a bad grant.** The worker could not clean up, so it made
  the leftover fail loudly if it ever landed, and documented the reason in the
  artefact itself. But it leaves the tree dirty, which is the state the driver
  refuses to start on — so a session that does this blocks the next run.
- **Severity:** friction — the grant should cover removing a file the role is
  already allowed to create.
- **Action:** nothing salvaged; the file says "Delete this file" and it was.

### F35 — the owner reversed the 15% ruling; R26 stays at 10%
- **Where:** closing the R26 thread opened at F33
- **What happened:** the owner changed their mind and kept the cap at **10%**.
  PR #133 was closed by them deliberately and stays closed. `docs/DESIGN.md` on
  the lane was never modified — the edit only ever existed on the closed
  branch — so nothing had to be reverted and R26 still reads 10%.
- **What this does to F33:** the three fix sessions the driver spent on that
  pull request were spent on a change that is no longer wanted. It does not
  change the finding — the driver could not tell an owner-authored failure from
  a fixable one, and would have burned the same three sessions on a change that
  *was* wanted. Recorded so a later reader does not treat 15% as pending.
- **One local-only commit was left behind and deliberately abandoned:**
  `d57e687 "Drop the docs/DESIGN.md edit: only the owner may open a pull request
  touching it"`, written by a fix session on `docs/r26-fifteen-percent`. Its
  effect would have been to keep the `DECISIONS.md` entry recording a 15%
  ruling while `DESIGN.md` still said 10% — a decision log disagreeing with the
  design it governs. It is on no remote and is being left to die with the
  branch, on the owner's instruction.
- **Worth noting as a near-miss:** that commit is what a fix session does when
  the red check is "the owner must open this". It removed the owner's change and
  kept the record of it, which is the wrong half to keep. Strengthens F33's
  suggested fix — treat owner-authored failures as terminal rather than
  something to edit around.
- **Severity:** none as a template finding; recorded to close the thread.

### F36 — the driver's own console log is not part of the evidence the template lands
- **Where:** evidence for run `20260820T112543Z`
- **What the landed evidence contains:** `run.md` (the report), 10 review
  payloads, and all 10 worker logs — verified byte-identical to the local copies.
- **What it does not contain:** the driver's own console output. That log is the
  only place carrying `deliver-loop: pull --ff-only failed; continuing on the
  local tree` — the line that explains F31, where the evidence branch was
  collected but never pushed. The report says the run stopped; only the console
  says why the evidence did not arrive.
- **It lived in `/tmp`**, so a reboot would have taken the one record of how the
  self-recording failed.
- **Preserved by hand** at
  `docs/runs/operator/driver-logs/run-20260820T112543Z-console.log`, 194 lines,
  with the operator's home directory replaced by `<repos_root_home>` and checked
  against every identity-register value before committing (rule 13).
- **Suggested fix:** land the driver's console log alongside `run.md`. The
  report is the driver's account of itself; the console is what actually
  happened, and the two differ exactly when something went wrong.
- **Severity:** bug — recorded as a gap in what the template preserves, distinct
  from F31 which is the push failing outright.

