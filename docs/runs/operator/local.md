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

