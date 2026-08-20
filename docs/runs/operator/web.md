# WEB lane — operator ledger

Lane base branch: `run/web`. Repository: `find_best_mobo` (real project, not a
throwaway). Mechanics follow the public anvil test plan
(`test-kit/TESTPLAN.md` on GrimsVerk/grimsverk-anvil, Parts 1 and 2) with the
operator's overrides for this project:

- The project already exists at template **v0.4.27**; there is no `copier copy`
  render and no canned input install. Part 1 step 2/3 is replaced by a template
  **update** to the latest release.
- The ledger lives at `docs/runs/operator/web.md` on `chore/test-report-web`
  (pushed, never a pull request), not at `test-kit/reports/web.md`.
- Conflict rule for the update: template machinery takes the **template** side,
  project content keeps the **project** side, and every conflict is logged here.

Anvil Part 2 rules bind this lane, including rule 13 (no value from the owner's
identity register appears in anything pushed) and rule 11 (a failsafe that
preserves evidence the template should have preserved itself is filed as its own
`TEMPLATE SELF-RECORDING FAILURE` finding).

Times are UTC.

---

## Timeline

| Time | Event |
| --- | --- |
| 2026-08-20T08:24:10Z | Session start. Lane stated: `run/web`. Tooling probe: `uv`, `copier` 9.17.2, `gh` 2.97.0, `python3`, `jq`, `curl` present; standalone `pre-commit` absent (expected — it is used via `uv run`). `/tmp/anvil-env-setup.log` present and shows a clean environment setup at 08:22:03Z. |
| 2026-08-20T08:25Z | Latest `grimsverk-template` tag resolved as **v0.4.37** by `git ls-remote --tags`. Project is on **v0.4.27**, so the update is a ten-release jump. |
| 2026-08-20T08:26Z | `git ls-remote --heads origin` shows only `main`. `run/local` does not exist yet, so the local agent has not started. Created `run/web` off `origin/main`. |
| 2026-08-20T08:26Z | Ledger branch `chore/test-report-web` created off `origin/main` in a separate worktree, so ledger commits never disturb the lane checkout. || 2026-08-20T08:26Z | `scripts/update-from-template.sh` refused: "you are on 'run/web', not 'main'." See F2. |
| 2026-08-20T08:26Z | `copier update --defaults --trust` succeeded: "Updating to template version 0.4.37". `_commit` moved v0.4.27 -> v0.4.37. **Zero conflict markers.** 21 files modified, 1 added (`.github/workflows/open-pr.yml`); every one of them template machinery, no project content touched. See F3. |
| 2026-08-20T08:27Z | `uv sync` OK (adds `pre-commit==4.6.2` as a dev dependency, ESC-55). `uv run pre-commit install` OK. Full gate green: `ruff check`, `ruff format --check`, `mypy` (33 files), `pytest` **474 passed**. |
| 2026-08-20T08:27Z | Committed the update on `run/web` and pushed. Push **accepted on the first attempt** — no ruleset yet names this lane, so the bounded retry of TESTPLAN step 6 was not exercised. |
| 2026-08-20T08:28:10Z | `RUN_BASE=run/web .github/scripts/unattended-ready.sh --runtime` REFUSED, 1 missing item: "no rules bind the run's base branch 'run/web'". Everything else green or correctly deferred to the owner's full check. The `--runtime` identity note names ESC-50 explicitly and says the ambient login drives while pull requests open via the `open-pr` workflow — correct for this session. |
| 2026-08-20T08:28:10Z | Bounded wait armed: 15 attempts, 3 minutes apart, 45 minutes total, logging each attempt. |
| 2026-08-20T08:28:37Z | Attempt 1/15: still ungated. Remote heads now `chore/test-report-local chore/test-report-web main run/web` — the LOCAL lane's ledger branch exists, so the local agent is alive; `run/local` has not appeared yet. |
| 2026-08-20T08:29Z | Phase detector (read-only, before any dispatch): `PHASE=ORACLE BASE=run/web REASON=evidence UNCITED=BL-14`. The detector reports this run's base back correctly. |
| 2026-08-20T08:31:40Z | Attempt 2/15: `run/local` appears on the remote. Both lanes now exist. Still ungated. |
| 2026-08-20T08:34-08:46Z | Attempts 3-7/15: unchanged, still `MISSING no rules bind the run's base branch 'run/web'`. |
| 2026-08-20T08:48:47Z | Direct REST read of `repos/.../rules/branches/run%2Fweb` shows the gate HAS landed: `deletion`, `non_fast_forward`, `pull_request` (code-owner review required, 0 approvals) and `required_status_checks` with all seven contexts — `checks`, `secrets`, `plan`, `template-sync`, `test-the-tests`, `acceptance-criteria`, `review`. `strict_required_status_checks_policy: true`. |
| 2026-08-20T08:49:09Z | `RUN_BASE=run/web .github/scripts/unattended-ready.sh --runtime` **PASSES**: "this repository can run unattended." Every one of the seven required checks reported as binding on `run/web`. Total wait from lane push to gate: ~22 minutes, 7 polls, well inside the 45-minute bound. |

---

## Findings

### F1 — the template API is unreadable from this session, only the git remote is
- Where: setup, TESTPLAN Part 1 step 2 (confirm the template release)
- What happened: the step's own command is `gh release view -R
  GrimsVerk/grimsverk-template --json tagName --jq .tagName`. The session's
  GitHub API surface is scoped to `find_best_mobo` alone, and the equivalent
  REST call returned:
  `Access denied: repository "grimsverk/grimsverk-template" is not configured
  for this session. Allowed repositories: grimsverk/find_best_mobo`.
  The release was resolved instead with
  `git ls-remote --tags --refs https://github.com/GrimsVerk/grimsverk-template.git`,
  which works because that is the same anonymous git-read channel copier uses.
- Expected: TESTPLAN Part 0 says the template is attached "only so copier can
  read it", and step 2 then asks the agent to read it through the GitHub **API**.
  Those two statements are not compatible: an attachment that only serves git
  reads cannot answer an API call. The step needs a git-only fallback in its own
  text.
- Severity: docs


### F2 — the template's own update script cannot update a lane branch
- Where: setup, template update step; `scripts/update-from-template.sh`
- What happened:
  ```
  $ git rev-parse --abbrev-ref HEAD
  run/web
  $ scripts/update-from-template.sh
  update-from-template: you are on 'run/web', not 'main'.

  A template update branches off the default branch, so that the pull request
  contains the update and nothing else.
  ```
  Exit 1, nothing done. The update had to be driven with a bare
  `copier update --defaults --trust` instead, which then leaves the branching,
  committing, pushing and pull-request opening to be done by hand.
- Expected: the same template release that introduces **per-base-branch**
  running — `deliver-loop.sh --base`, lane branch suffixes,
  `setup-github.sh --gate-branch` — still has an update script that hard-codes
  the default branch as the only place an update may happen. Once a project can
  have more than one base branch, "the default branch" is no longer a synonym
  for "the base branch of this run", and the script has no way to be told which
  one it is. It needs the same `--base` the driver got.
- Severity: bug

### F3 — the ten-release update itself was clean; recorded because it is the ESC-14 live test
- Where: template update, v0.4.27 -> v0.4.37
- What happened: `copier update --defaults --trust` produced **no conflict
  markers at all** across ten releases. 21 files modified, 1 added. Every
  changed path is template machinery (`.claude/`, `.github/`, `AGENTS.md`,
  `README.md`, `.pre-commit-config.yaml`, `pyproject.toml`,
  `scripts/setup-github.sh`) plus a template-owned append to
  `docs/DECISIONS.md` above its "append project decisions below" marker. No
  file under `src/`, `tests/`, `data/`, `acceptance/`, `docs/DESIGN*.md`,
  `docs/BACKLOG.md`, `docs/plans/` or `docs/runs/` was touched, so the standing
  conflict rule (template machinery takes the template side, project content
  keeps the project side) never had to be applied — there was nothing to
  arbitrate.
- Expected: the anvil plan lists `copier update` / `template-sync` on a real
  update, "including the conflict path (template ESC-14)", as **out of scope**
  for the anvil round and explicitly arms it for "whichever lane survives
  better". This project is that live test, and the update half of it passed
  cleanly. The `template-sync` half is not proven yet: it is only proven when
  the check runs green on a pull request, and this lane's update rides on the
  lane base branch rather than on a `template/<version>` branch, so
  `template-sync` may never judge it. Flagged here so the gap is not read as a
  pass.
- Severity: docs (recorded observation; the update itself produced no defect)

### F4 — the update script would open its pull request with `gh pr create`
- Where: `scripts/update-from-template.sh`, final step
- What happened: had the script run, it would have finished with a plain
  `gh pr create`. In a web session that pull request is authored by the
  session's injected owner credential, which is exactly what the pipeline
  forbids and what `.github/workflows/open-pr.yml` — added by this very update —
  exists to prevent. The script and the workflow arrived in the same release
  and disagree about who opens a pull request.
- Expected: a release that ships a server-side, push-fired opener because
  drivers cannot hold App identity should not also ship a maintenance script
  that opens pull requests as whoever happens to be logged in. The script needs
  the `.pr-request.json` path, or a flag that selects it.
- Severity: bug
### F5 — the deliver-loop command file tells the driver both to use and never to use `gh auth status`
- Where: `.claude/commands/deliver-loop.md`, credential paragraph vs. step 2
- What happened: the credential paragraph says, emphatically, "Probe with
  `gh api user`, **NEVER** `gh auth status` — auth status inspects local
  configuration and reports failure on exactly this platform, while real
  requests succeed at the proxy (ESC-52)." Eleven lines later, step 2 opens:
  "**Preflight, first turn only:** `gh auth status` (on the credential
  established above)". A driver that follows step 2 literally runs the one
  command the file just forbade, on the one platform where it lies.
- Expected: one instruction. Step 2's preflight should say `gh api user`, the
  same probe the rule above it mandates. Followed the rule, not step 2; the
  probe returned `GrimsVerk (type: User)`.
- Severity: bug

### F6 — a web session cannot read CI job logs, and green checks carry no output, so ESC-45's duty cannot be discharged from inside the driver
- Where: driver WAIT phase, PR #100; GitHub Actions job logs over REST
- What happened: `gh api repos/.../actions/jobs/<id>/logs` redirects to Azure
  blob storage, and the session's egress proxy refuses it:
  ```
  Get "https://productionresultssa5.blob.core.windows.net/actions-results/.../job-logs.txt?...": Forbidden
  ```
  Both zero-second-step checks failed the same way. The obvious fallback is
  empty too: every `check_runs[].output.title` and `.output.summary` on this
  pull request is `(none)`, so the checks publish no summary a REST reader can
  see.
- Expected: the driver's whole WAIT contract is "on waking to a red check,
  compute the failure signature and fix on the existing branch". That needs the
  log. And the anvil observation checklist requires recording, per check, that a
  fast green one is not ESC-45's silent skip — which also needs the log. In a
  web session neither is reachable. The only route left was to read
  `.github/workflows/ci.yml` and `.github/scripts/*.sh` in the checkout and
  reason about what the steps would have done, which is inference from source,
  not observation of the run.
- Consequence, stated plainly: a **red** check in this lane will be diagnosable
  only if its failure is reproducible locally. A check that fails for an
  environment reason visible only in its log would strand the driver with no way
  to compute a failure signature beyond the check's name.
- Suggested ratchet: have each check publish its one-line verdict into the
  check-run's `output.summary` — the skip lines already exist as text
  (`test-the-tests: SKIP — this PR changes no files under src/`), they are just
  written somewhere a hosted driver cannot read.
- Severity: bug

---

## Driver run

Run timestamp: `20260820T085011Z`. Run start: 2026-08-20T08:50:11Z.
Limits, given by the owner in advance: **30 pull requests, 12 wall-clock hours,
60 iterations**. Wall-clock deadline 2026-08-20T20:50:11Z.
Steering SHAs at run start: `docs/DESIGN.md` 00a8a21f, `docs/VISION.md` 89ef09ec.

| Time | Iteration | PHASE | Detail |
| --- | --- | --- | --- |
| 08:50:11Z | preflight | - | Credential: App mint **failed** (rc 3, "the App identity is not set up yet", no `.claude/app-identity`); `gh api user` **succeeds** and returns `GrimsVerk (type: User)`. This is exactly the ESC-50 shape the command file predicts, so the ambient owner credential drives and every pull request must go through `.pr-request.json` + `open-pr.yml`. |
| 08:50:11Z | preflight | - | `coverage.sh` rc **1** (not the run-ending rc 2): 18/36 requirements covered, 18 unplanned (R8-R16, R19, R26, R27, R1002-R1007). Adequacy note: R25 and R28 are claimed by a plan but named by none of its slices. |
| 08:50:11Z | preflight | - | `budget-probe.sh` rc 3: "no usage source is reachable here... The driver will ask you for explicit limits instead of inventing one — that is the design, not a degradation." **Correct behaviour** per anvil rule 8; recorded positively, not as a finding. |
| 08:52Z | 1 | ORACLE | `PHASE=ORACLE BASE=run/web REASON=evidence UNCITED=BL-14`. Dispatched one oracle worker via `spawn-worker.sh --role oracle --engine claude --base run/web`. |
| 08:56Z | 1 | ORACLE | Worker returned: `WORKER_RESULT id=oracle-20260820085103 branch=worker/oracle-20260820085103 engine=claude exit=0 commits=1`. Diff: `docs/DESIGN.oracle.md` +37, `docs/oracle/handoff-2026-08-20-1.md` +67. Ruling **OD-13** — supersedes OD-5/R1001 on the owner's 2026-08-19 entry, adds R1008 to keep the per-path projection measurable, hands the re-cut to the steward. Cites BL-14 as its evidence and names the vision statement it relied on, as the append-only check requires. |
| 08:56Z | 1 | ORACLE | **Contamination probe (anvil rule 10): clean.** The worker's diff references neither the operator ledger, nor the anvil kit, nor `run/local`. It stayed inside the design layer. |
| 08:56:55Z | 1 | ORACLE | Marker `.pr-request.json` committed as the branch's last commit (base `run/web`), pushed as `worker/oracle-20260820085103:docs/oracle-20260820085103--run-web` — `docs/` prefix so the branch is plan-exempt, `--run-web` lane suffix so the two lanes cannot collide. Push accepted first attempt. |
| 08:57:08Z | 1 | WAIT | **PR #100 opened by `autogrims[bot]` (type `Bot`)**, base `run/web`, head `docs/oracle-20260820085103--run-web`. The push-fired `open-pr` workflow did it server-side, ~13 seconds after the push. Checklist item (ESC-26/ESC-35): **pipeline pull request authored by the App, not the owner — confirmed positively.** |
| 08:58Z | 1 | WAIT | Checklist item (ESC-36): **`arm-auto-merge` appears in the check list and succeeded (6s).** Merge completion still to be observed. |
| 08:58Z | 1 | WAIT | Detector confirms `PHASE=WAIT BASE=run/web PR=100 HEADREF=docs/oracle-20260820085103--run-web`. `mergeable_state: blocked` while `review` runs. Subscribed to the pull request's activity and scheduled the ~1 hour fallback check-in, per the command file's event-driven rule. No polling inside the turn. |

### Check durations on PR #100 (checklist item, ESC-45)

Every required check, measured from the REST `check-runs` timestamps:

| Check | Result | Duration | Honest? |
| --- | --- | --- | --- |
| `checks` | success | 15s | **Yes.** Step-level timings prove the work ran: `uv sync --locked` 1s, `ruff check` 0s, `ruff format --check` 0s, `mypy` 3s, `pytest` 2s. 474 tests that take 1.6s locally. |
| `secrets` | success | 6s | Yes — gitleaks action 2s. |
| `plan` | success | 6s | Yes — eleven sub-steps, each a small shell script, all reporting. |
| `acceptance-criteria` | success | 10s | Yes — "Every scripted success criterion still holds" 4s. |
| `template-sync` | success | 7s | **Yes, but by exiting early.** `SYNC_PREFIX` defaults to `template/`, and this is a `docs/` branch, so the script has nothing to do. Documented, not a silent skip. |
| `test-the-tests` | success | 7s | **Yes, but by skipping.** The script prints `test-the-tests: SKIP — this PR changes no files under src/`. Correct for a docs-only pull request. |
| `arm-auto-merge` | success | 6s | Yes. |
| `open-pr` | success | 7s | Yes — this is the job that opened the pull request. |
| `review` | pending | - | Still running at the time of writing. |

No check finished in ~1 second while claiming to have done real work, so ESC-45's
failure shape did not occur here. Getting to that answer, however, took a
workaround — see F6.
| 08:59:00Z | 1 | WAIT | **PR #100 MERGED**, by `autogrims[bot]`, ~112 seconds after it opened. No human touched it. Checklist item (ESC-36): **auto-merge completes without a human — confirmed live.** |
| 08:59:11Z | 1 | WAIT | **The head branch vanished.** Checklist item (ESC-21) — the one nothing had ever observed — answered completely, see the block below. |
| 09:25:08Z | - | RESTART | Owner instruction: restart the lane at template **v0.4.39**. Not a blocker; the local lane is restarting and re-gating `run/web`. |

### ESC-21 answered: a merged branch vanishing, observed live for the first time

Four wrong theories were on record. The measured answer, from the REST job
timings on this lane's own pull request:

| Moment | Time | Evidence |
| --- | --- | --- |
| Pull request opened by the App | 08:57:08Z | `open-pr` workflow, push-fired |
| `arm-auto-merge` armed it | 08:57:13-19Z | Auto-merge run, `pull_request` opened event |
| Merged by `autogrims[bot]` | 08:59:00Z | `merged_by.login = autogrims[bot]` |
| **`delete-merged-branch` ran** | **08:59:06-11Z** | second Auto-merge run, `pull_request` closed event |
| Branch absent from the remote | confirmed at 09:25Z | `git ls-remote --heads origin 'docs/oracle-*'` returns nothing |

**By which path: the `delete-merged-branch` job of the Auto-merge workflow,
fired by the pull-request-closed event — 11 seconds after the merge.** NOT the
nightly sweep: `sweep-merged-branches` was `skipped` in the very same run. The
whole open-to-vanished lifecycle took 123 seconds.

`update-open-prs` (ESC-17) also **ran and succeeded** in that same post-merge
run, 08:59:06-13Z. That is the job firing, observed live; what it is meant to
do — auto-update a *different* open pull request into the same base — was not
exercised, because this lane had no second pull request open. Recorded as a
partial observation, not a full one.

---

## RESTART — round 2, template v0.4.39

The owner restarted both lanes at template **v0.4.39**. The web lane was not
blocked by a bug: round 1 ended mid-WAIT while the local lane restarted and
re-gated `run/web`. Every finding above stands and is carried forward; numbering
continues from F7.

| Time | Event |
| --- | --- |
| 2026-08-20T09:25:08Z | Restart instruction received. Latest template tag now **v0.4.39** (round 1 ran v0.4.37). |
| 09:25Z | Round-1 evidence captured before touching anything — PR #100 merged and its branch vanished; see the ESC-21 block above. |
| 09:29Z | Cleaned the round-1 worker worktree and branch. `git checkout -B run/web origin/main` — lane reset to the kit's common ancestor, `_commit` back to v0.4.27. |
| 09:30Z | `copier update --defaults --trust` -> **v0.4.39**. **Zero conflict markers** again. 22 files modified, 1 added (`open-pr.yml`). Verified mechanically that every changed path is template machinery: nothing outside `.claude/`, `.github/`, `scripts/`, `AGENTS.md`, `README.md`, `pyproject.toml`, `.pre-commit-config.yaml`, `.copier-answers.yml` and the template-owned append to `docs/DECISIONS.md`. Project and canned inputs untouched. |
| 09:30Z | `uv sync`, `uv run pre-commit install`, full gate: ruff, ruff format, mypy (33 files), **474 tests pass**. |
| 09:31:15Z | Committed on `run/web` and force-pushed. Push accepted — **and reported bypassing all seven required checks. See F9.** |

### F7 — RESOLVED UPSTREAM: v0.4.39 fixes this lane's F2 and F4, citing this lane by name

- Where: `scripts/update-from-template.sh` at v0.4.39
- What happened: both round-1 findings against the update script are fixed in
  the release the restart pulled in.
  - F2 (cannot update a lane branch): the script now takes `--base <branch>`,
    "the same flag deliver-loop.sh and setup-github.sh take". Its own comment
    names the source of the report: *"Without this, every step assumed the
    default branch and a lane could be driven but never updated (anvil mobo
    F1)."* The update branch also carries the lane suffix so twin lanes cannot
    collide on `template/<version>`.
  - F4 (opens its pull request as the ambient login): replaced by the driver's
    credential rule in script form, logged as ESC-63 — mint the App token and
    open directly, or write `.pr-request.json` as the branch's last commit and
    let `open-pr.yml` open it server-side, or push and say exactly what remains.
    The comment states the reason this lane hit: an owner-authored update
    "was unapprovable by construction".
- Expected: this is the ratchet working end to end — a lane reports friction, the
  template repository fixes it and cites the report. Recorded as a positive
  observation, and as evidence that the finding channel is live.
- Severity: docs (resolved; no action)

### F8 — the ten-release update was clean a second time, at a different target
- Where: template update, v0.4.27 -> v0.4.39
- What happened: a second independent `copier update` across the full gap, to a
  different target release, again produced **no conflict markers** and touched
  no project content. The standing conflict rule (template machinery takes the
  template side, project content keeps the project side) has now had two
  opportunities to be exercised and has needed neither.
- Expected: the anvil plan lists the ESC-14 conflict path as never yet tested.
  It is still untested, but not for want of trying — this project's divergence
  from the template simply does not overlap the template's own files. Recorded
  so the gap is not mistaken for a pass.
- Severity: docs (recorded observation)

### F9 — TOP SEVERITY: the web session's credential bypassed all seven required checks, the pull-request requirement, and the force-push ban
- Where: `git push --force-with-lease -u origin run/web`, 2026-08-20T09:31:15Z
- What happened: the push was accepted, and GitHub said exactly what it had
  waived:
  ```
  remote: Bypassed rule violations for refs/heads/run/web:
  remote:
  remote: - Cannot force-push to this branch
  remote:
  remote: - Changes must be made through a pull request.
  remote:
  remote: - 7 of 7 required status checks are expected.
  remote:
  To https://github.com/GrimsVerk/find_best_mobo
   + 586338f...a9513dd run/web -> run/web (forced update)
  ```
  Three separate protections — non-fast-forward, pull-request-required, and
  every one of the seven required status checks — were bypassed in a single
  push by the session's injected credential.
- Expected: this reproduces anvil **F16** (round 2.1) exactly, on a different
  repository and a newer template. The ruleset holds against this session as
  **policy only** — an instruction the agent obeys — never as mechanism. Nothing
  but the agent's discipline stands between this credential and `main`, and a
  push rejection can never teach a web agent that a gate is missing, because it
  will not be rejected.
- Scope note, stated plainly so it is not mistaken for a violation: this
  particular force-push was **explicitly instructed by the owner** as part of the
  restart (`git checkout -B run/web origin/main ... push`), and it targeted this
  lane's own base branch, never `main` and never `run/local`. The finding is not
  that the push happened; it is that GitHub permitted it and reported the
  bypass, which is the mechanism failing in a way only a log line reveals.
- Consequence for the round: TESTPLAN Part 3 closing action 3 asks the owner to
  verify the ruleset held. For `run/web` the honest answer is that it did not
  hold as mechanism, and this ledger entry is the disclosure. Pipeline integrity
  in this lane rests entirely on the merge path — auto-merge on green required
  checks — which the bypass does not touch, and which round 1 observed working
  correctly on PR #100.
- Severity: blocker

### Driver run, round 2

Run timestamp `20260820T093300Z`. Run start 2026-08-20T09:33:36Z.
Limits unchanged: **30 pull requests, 12 wall-clock hours** (deadline
2026-08-20T21:33Z), **60 iterations**.
Steering SHAs at run start: `docs/DESIGN.md` 00a8a21f, `docs/VISION.md` 89ef09ec
— identical to round 1, so the owner has not steered between rounds.

| Time | Iteration | PHASE | Detail |
| --- | --- | --- | --- |
| 09:32:54Z | wait | - | `unattended-ready.sh --runtime` **PASSES immediately** — the round-1 gate on `run/web` survived the restart, all seven checks still binding. No bounded wait was needed this round. Re-verified rather than assumed, because the local lane's setup step can reset the ruleset; `run/local` is at `v0.4.37` and 13 commits ahead of `main`, and a `template/v0.4.39--run-local` branch exists, so that lane is taking the update through the pipeline rather than resetting. |
| 09:33:36Z | preflight | - | Credential unchanged: App mint fails rc 3, `gh api user` returns `GrimsVerk (User)` — ESC-50 again. `coverage.sh` rc 1, 18 requirements unplanned. `main` still at `88400b8`, untouched by either lane (TESTPLAN Part 3 closing action 3, first half: clean). |
| 09:33:36Z | 1 | ORACLE | `PHASE=ORACLE BASE=run/web REASON=evidence UNCITED=BL-14`. Same starting phase as round 1, as expected from an identical base. Oracle worker dispatched. |
| 09:38:04Z | 1 | ORACLE | Worker returned `exit=0 commits=1`. Ruling **OD-13** again, reached independently on a fresh worker from the same base: supersedes OD-5/R1001, adds R1008, hands the re-cut to the steward. Cites BL-14 and BL-13. Diff `docs/DESIGN.oracle.md` +33, `docs/oracle/handoff-2026-08-20-1.md` +45 — a little shorter than round 1's +37/+67, same conclusion. **Contamination probe: clean.** Marker committed, branch pushed as `docs/oracle-20260820093352--run-web`. |
| 09:38:26Z | 1 | WAIT | **PR #106 opened by `autogrims[bot]`**, base `run/web` — 22 seconds after the push. App-authored again. |
| 09:41Z | 1 | WAIT | **Per-base lane isolation confirmed live.** Two pull requests are open on the repository at once: `#106 base=run/web` (mine) and `#105 base=run/local head=template/v0.4.39--run-local` (the other lane's own v0.4.39 update, taken through the pipeline via the new `--base` path). The detector reports **only** `PR=106`. The other lane's pull request never appeared as mine to wait on or fix — which TESTPLAN Part 2 rule 1 calls a top-severity finding if it ever does. It did not. |
| 09:41Z | 1 | WAIT | Subscribed to PR #106's activity; ~1 hour fallback check-in armed for 10:42Z; turn ended. No polling inside the turn, per the command file's event-driven rule. |
| 09:39:56Z | 1 | WAIT | **PR #106 MERGED** by `autogrims[bot]`, 90 seconds after opening. Second App-merge with no human. |
| 09:39:57Z | 1 | WAIT | **Head branch deleted 1 second after the merge**, actor `autogrims[bot]`, recorded in the pull request's own timeline as `head_ref_deleted`. Round 1 measured 11 seconds via the job timings; the timeline puts the deletion event itself at +1s. **ESC-21 confirmed a second time, on an independent cycle.** Full lifecycle: opened 09:38:26 -> auto-merge armed 09:38:30 -> merged 09:39:56 -> branch gone 09:39:57 = **91 seconds**. |
| 10:12:54Z | - | - | The other lane merged its own PR #105 (base `run/local`) — but **after** mine had already merged, so the two were never open at the same time. **ESC-17 remains unexercised**: my pull request's commit list was never rewritten by a cross-lane merge, because there was no overlap to test. Recorded as still-unobserved, not as a pass. |
| 10:24:09Z | - | RESTART | Owner restarts both lanes at template **v0.4.41**. Round 2 ended cleanly with its pull request merged; it was not blocked. |

### F12 — the merged `.pr-request.json` marker persists on the base branch, so the next branch inherits a stale pull-request request
- Where: `.github/workflows/open-pr.yml` + the marker's deliberate ride-along in the pull request diff
- What happened: the marker is committed as the branch's last commit and merges
  with it, by design ("deleting it would take another App push and another round
  of CI for no gain"). After PR #108 merged, `run/web` carries:
  ```
  $ git show origin/run/web:.pr-request.json
  {"base": "run/web", "title": "Oracle: OD-13 supersedes OD-5/R1001 (BL-14)", "body": "..."}
  ```
  Every branch cut from `run/web` now starts life carrying a complete, valid
  request for the **previous** pull request. `open-pr.yml`'s only guard is
  idempotence on the same head->base pair:
  ```
  existing="$(gh api "repos/$REPO/pulls?state=open&base=$BASE&per_page=100" \
    --jq ".[] | select(.head.ref == \"$HEAD\") | .number" ...)"
  ```
  It never asks whether the marker is fresh, whether this push changed it, or
  whether anyone asked for a pull request at all. A new `docs/**` branch is a new
  head, so the guard does not fire.
- Consequence: any push of a `docs/**` or `feat/**` branch that does not
  deliberately overwrite the marker opens a pull request titled and described as
  the previous one. The content would be this branch's; the description would
  describe something else entirely — and a reviewer reads the description.
- Why it did not bite this lane: the driver's rule is to write the marker as the
  final commit before every push, so it is always overwritten. The exposure is any
  other push to a matching branch prefix — an evidence branch, a fix branch pushed
  before its marker is written, a re-push.
- Suggested ratchet: have `open-pr.yml` open a pull request only when the pushed
  commit actually **modifies** `.pr-request.json`, which is precisely the signal
  "somebody asked, on this push".
- Severity: bug

---

## RESTART — round 3, template v0.4.41

| Time | Event |
| --- | --- |
| 2026-08-20T10:24Z | Restart at **v0.4.41**. Round 2 was not blocked — its pull request merged cleanly. |
| 10:25Z | Lane reset to `origin/main`; `copier update` v0.4.27 -> **v0.4.41**. **Zero conflicts, third time running.** 22 files modified, `open-pr.yml` added, and mechanically verified that no path outside template machinery changed. |
| 10:26Z | `uv sync`, `uv run pre-commit install`, full gate green — ruff, format, mypy (33 files), **474 tests**. |
| 10:26Z | Force-pushed `run/web`. **F9 reproduced verbatim**: the push again reported `Bypassed rule violations ... Changes must be made through a pull request ... 7 of 7 required status checks are expected.` Third round, same waiver. |
| 10:26:23Z | `unattended-ready.sh --runtime` **passes immediately** — the gate on `run/web` survived this restart too, all seven checks binding. No bounded wait needed for the third round running. |

### F10 — the web frontend never spells out the ESC-69 unattended contract it tells the driver to send
- Where: `.claude/commands/deliver-loop.md` step 5 vs. `.claude/scripts/deliver-loop.sh`
- What happened: v0.4.41 adds ESC-69 — "every unattended dispatch carries a
  written contract". The contract exists, as `UNATTENDED_ADDENDUM` in
  `.claude/scripts/deliver-loop.sh`: four clauses telling a headless worker
  that nobody is watching, never to address a human or offer a menu, never to
  push, and to finish with `WORK_ON_BRANCH <branch>`. The **local** frontend
  appends it to every worker prompt automatically. The **web** frontend — the
  file a web driver actually follows — only says to send "the matching command
  file as its prompt plus the UNATTENDED addendum", and never defines what the
  addendum is or where to find it.
- Consequence, observed on this lane: rounds 1 and 2 dispatched their oracle
  workers with the one-line marker the web file's own examples imply
  (`UNATTENDED RUN. The delivery driver commissioned this session. <scope>`) and
  **not** the four-clause contract, because the web file gave nothing else to
  send. Those workers happened to behave, so nothing broke — which is precisely
  how this stays invisible. A fix that lands in only one of two frontends
  protects only one of them.
- Expected: the addendum belongs in the web command file verbatim, or in a file
  both frontends read. Round 3 sends the full contract, lifted out of
  `deliver-loop.sh` by hand.
- Severity: bug

### F11 — F5 is still open at v0.4.41
- Where: `.claude/commands/deliver-loop.md` lines 32 and 104
- What happened: the credential rule still says "Probe with `gh api user`,
  **NEVER** `gh auth status`", and step 2 still opens "**Preflight, first turn
  only:** `gh auth status`". Unchanged across v0.4.37, v0.4.39 and v0.4.41.
- Expected: F2 and F4 were fixed within one release of being reported (F7), so
  the channel works. This one has simply not been picked up yet. Re-raised here
  so it is not lost between rounds.
- Severity: bug (duplicate of F5, still open)

### Driver run, round 3

Run timestamp `20260820T102700Z`. Run start 2026-08-20T10:27:06Z. Template v0.4.41.
Limits unchanged: **30 pull requests, 12 wall-clock hours** (deadline 2026-08-20T22:27Z),
**60 iterations**. Steering SHAs unchanged from rounds 1 and 2 — the owner has not steered.

| Time | Iteration | PHASE | Detail |
| --- | --- | --- | --- |
| 10:27:06Z | preflight | - | Credential: mint fails rc 3, `gh api user` returns `GrimsVerk` — ESC-50 unchanged. `coverage.sh` rc 1. **ESC-72 precondition checked explicitly**: no open pull request targets `run/web`, so nothing holds the run. |
| 10:27:18Z | 1 | ORACLE | Dispatched with the **full four-clause ESC-69 contract**, lifted by hand out of `.claude/scripts/deliver-loop.sh` because the web command file does not carry it (F10). |
| 10:31Z | 1 | ORACLE | Worker returned `exit=0 commits=1`. **ESC-69 compliance confirmed positively**: the worker's log ends with the literal line `WORK_ON_BRANCH worker/oracle-20260820102718`. It did not address a human, offer a menu, or try to push. **ESC-68 reported no relocation** — the work is on the worker branch the driver expected, so no empty ref was pushed. |
| 10:31:24Z | 1 | ORACLE | Branch pushed as `docs/oracle-20260820102718--run-web`. Contamination probe: clean. |
| 10:32Z | 1 | WAIT | **PR #108 opened by `autogrims[bot]` (Bot)**, base `run/web`. Third App-authored pipeline pull request in three rounds. Detector reports `PHASE=WAIT PR=108`. |

### Three independent oracle runs on identical input — a reproducibility note

The same evidence (`BL-14`) was ruled on by three separate headless workers from
three byte-identical bases, at v0.4.37, v0.4.39 and v0.4.41. All three:

- reached the **same decision id and substance** — OD-13, supersede `R1001`,
  re-cut the merged capped plan rather than discard it, keep `OD-4`/`R1000`
  untouched and sequenced first;
- cited `BL-14` as evidence and named the vision statement relied on, as the
  append-only check requires;
- stayed inside the design layer — every contamination probe clean.

They differed on **one** point: rounds 1 and 2 added a new requirement `R1008` to
carry the measurement the reversal creates; round 3 added no requirement and made
the measurement the re-cut plan's stated obligation instead, explicitly
considering and rejecting the new-id alternative on the grounds that the owner's
own amended `R5`/`R28` already carry the behaviour and a duplicate id would split
one behaviour across two.

Recorded as an observation, **not** a finding: all three satisfy AGENTS.md's rule
that a change nothing measures must bring its measurement. The variation is in
where the measurement is booked, not whether it exists. Worth the owner's eye
nonetheless, because nothing mechanical would have caught it had one of the three
simply dropped the measurement — the rule is prose, and the check that enforces it
is a reader.
| 10:31:44Z | 1 | WAIT | `auto_merge_enabled` by `autogrims[bot]`. |
| 10:33:05Z | 1 | WAIT | **Review gate returned `PASS`** on `0e03605b`, with a substantive verdict — it verified the evidence chain (BL-14 present at the base commit with a proposed default OD-13 follows), the schema fields, both vision quotes matching `docs/VISION.md` verbatim, the exemption-path claim, gate-tampering (none), and checked the base tree directly to confirm the capped plan exists as described. It also noted `test-the-tests` correctly did not run. **87 seconds** — a real review, not a skip. |
| 10:33:09Z | 1 | WAIT | **PR #108 MERGED** by `autogrims[bot]`. |
| 10:33:10Z | 1 | WAIT | **Head branch deleted 1 second after the merge**, actor `autogrims[bot]`. **ESC-21 confirmed a third time.** Full lifecycle: opened 10:32 -> armed 10:31:44 -> merged 10:33:09 -> branch gone 10:33:10. |
| 10:34Z | 2 | STEWARD | Base pulled. Detector: `PHASE=STEWARD BASE=run/web ODS=OD-6 OD-7 OD-8 OD-9 OD-10 OD-11`. **The pipeline advanced a phase** — first time this lane has moved past ORACLE in any round. Dispatched a steward worker for **OD-6**, again with the full ESC-69 contract. |

### Check durations on PR #108 (checklist item, ESC-45)

| Check | Duration | Honest? |
| --- | --- | --- |
| `review` | **87s** | Yes — a real LLM review with a detailed, verifiable verdict. |
| `checks` | 12-18s | Yes. |
| `acceptance-criteria` | 15s | Yes. |
| `template-sync` | 13s | Yes (early exit on a non-`template/` branch). |
| `secrets` | 6-10s | Yes. |
| `plan` | 6s | Yes. |
| `test-the-tests` | 6s | Yes (documented skip: no `src/` change). |
| `arm-auto-merge` | 8s | Yes. |
| `open-pr` | 8s | Yes. |
| `delete-merged-branch` | 2s | Yes — this is the job that removed the head branch. |
| `update-open-prs` | 3s | Ran; nothing to update (no second open pull request on this base). |

Nothing green-in-one-second while claiming work. ESC-45's failure shape has not
appeared on this lane in three rounds.
| 10:39Z | 2 | STEWARD | Worker returned, and **ESC-68 fired live** — see the block below. Work landed on `docs/od-6-cross-cue-splits`, a branch the worker made for itself. |
| 10:39Z | 2 | STEWARD | **The steward wrote no plan — it filed `BL-15` and stopped.** OD-6/R1002 does not say whether caption-split matching must recover a split straddling two cues, so it filed a HIGH uncertainty with a proposed default (no cross-cue joining) and named why it is HIGH (the other answer changes `find_mentions`'s shape, the Signatures block, and a slice boundary). It cited the precedent: the first OD-6 plan, PR #85, was **blocked by the review gate for ruling on this same question itself**. This is the bait-map behaviour working exactly as the plan predicts — planner files HIGH and stops rather than self-ruling. Contamination probe: clean. |
| 10:40:03Z | 2 | STEWARD | Marker rewritten (see F12) and branch pushed as `docs/oracle-plan-od-6--run-web`. |

### ESC-68 observed live — a worker that relocates its own work

```
spawn-worker[steward-od-6]: the worker moved its work to 'docs/od-6-cross-cue-splits'
  (this script created 'worker/steward-od-6'); reporting the branch that carries the commits
WORKER_RESULT id=steward-od-6 branch=docs/od-6-cross-cue-splits ... exit=0 commits=1
```

The worker committed to a branch of its own choosing rather than the one
`spawn-worker.sh` created for it. v0.4.41's ESC-68 fix is exactly this: report the
branch that actually carries the commits, instead of handing the driver the empty
`worker/steward-od-6` ref it made. Before the fix the driver would have pushed an
empty ref and the App would have opened a **contentless pull request**. Recorded
as a **positive observation of a fix working on its first live opportunity** —
the driver pushed the right branch because the script told it the truth.
| 10:41Z | 2 | WAIT | **PR #110 opened by `autogrims[bot]` (Bot)** — title `File BL-15: OD-6 does not say whether cross-cue caption splits must match`, i.e. the marker I wrote, not the stale one inherited from `run/web`. Fourth App-authored pipeline pull request. Detector: `PHASE=WAIT PR=110`. Subscribed; turn ended. |
| 10:41:34Z | 2 | WAIT | **PR #110 MERGED** by `autogrims[bot]`, 80 seconds after opening. Head branch deleted at 10:41:35Z — **1 second after the merge, ESC-21 confirmed a fourth time.** |
| 10:42Z | 2 | WAIT | Merge speed checked rather than assumed, because 80 seconds is fast enough to look like a bypass. It is not: all seven required checks ran with real durations — `review` **71s**, `checks` 12-16s, `acceptance-criteria` 13s, `template-sync` 10s, `test-the-tests` 9s, `secrets` 5-8s, `plan` 7s. The checks run in parallel and the project is small. No check reported success in ~1 second while claiming work. |
| 10:43Z | 3 | ORACLE | Base pulled. Detector: `PHASE=ORACLE BASE=run/web REASON=evidence UNCITED=BL-15`. **The feedback loop closed end to end**: the steward hit a HIGH uncertainty, filed `BL-15` instead of self-ruling, that filing merged, and the detector routed it straight back to the oracle to rule on. Uncertainty -> filing -> merge -> ruling is the exact path AGENTS.md specifies for unattended work, observed running unassisted. Oracle worker dispatched for BL-15 with the full ESC-69 contract. |
| | | | Pull request count this round: **2 of 30** (#108, #110), both merged. Iterations: 3 of 60. Wall clock used: ~16 minutes of 12 hours. |

**Measurement caveat, noted in passing:** some `skipped` check-runs report a
`completed_at` EARLIER than their `started_at`, giving negative durations
(`arm-auto-merge -1s`, `delete-merged-branch -5s`, `plan -7s`). This is a
GitHub artifact on skipped jobs, not a template defect — recorded only so the
duration figures above are not read as sloppy arithmetic.
| 10:47:17Z | 3 | ORACLE | Worker returned `exit=0 commits=1`; ESC-69 compliance confirmed (`WORK_ON_BRANCH worker/oracle-bl15-104223` present in the log). Ruling **OD-14**: `R1002`'s caption-split matching is **per-cue**; a split straddling two cues stays out of scope — the proposed default BL-15 was filed with. No requirement added, none superseded. Contamination probe: clean. |
| 10:47:17Z | 3 | ORACLE | Two things in this ruling are worth the owner's eye, both marks of an honest decision rather than a confident one: it records **"(no vision statement decided this)"** rather than reaching for support it does not have, and it argues *against* `V1` — the tenet that pushes toward recovering every mention — instead of ignoring it. It also states the limit of its own evidence: BL-8's three failures were **measured**, whereas no cue-spanning miss has ever been observed, so the population it rules out of scope is **hypothesized**. |
| 10:48Z | 3 | WAIT | **PR #112 opened by `autogrims[bot]`**, base `run/web`. Fifth App-authored pipeline pull request. Detector: `PHASE=WAIT PR=112`. Subscribed; turn ended. Counters: **3 of 30 pull requests, 4 of 60 iterations**, ~21 minutes of 12 hours. |
| 10:49:05Z | 3 | WAIT | **Review gate `PASS`** on `924fe14c`. The most thorough verdict of the run: it checked the exemption-path claim, confirmed `BL-15` existed at the base commit by finding its merge in the git log, verified OD-14's schema fields, checked that the `V1` quotation is the **complete first sentence and matches `docs/VISION.md` word for word** rather than a truncated fragment, confirmed the ledger is append-only with monotonically increasing ids, confirmed the handoff file is new rather than modified, and ran an injection check on the pull-request body. |
| 10:49:08Z | 3 | WAIT | **PR #112 MERGED** by `autogrims[bot]`. Head branch deleted 10:49:09Z — **1 second after. ESC-21 confirmed a fifth time.** |
| 10:49Z | 4 | STEWARD | Detector: `PHASE=STEWARD ODS=OD-6 ...`. OD-6 comes back around, now unblocked by OD-14. Steward dispatched again with the full ESC-69 contract. Counters: **3 of 30 pull requests** (all merged), **5 of 60 iterations**, ~22 minutes of 12 hours. |

### The review gate is doing real work, and this is the evidence for it

Three review verdicts have landed on this lane, at 87s, 71s and ~50s. None is a
rubber stamp. Across them the reviewer has independently:

- read the **base tree** to confirm a plan file exists as the pull request claims;
- confirmed a cited `BL-<n>` was filed **and merged before** the document citing
  it, by finding the merge commit in the log — the entry-before-citation ordering
  AGENTS.md makes a hard rule;
- checked a quoted vision tenet **word for word** against `docs/VISION.md`, and
  specifically that it was quoted in full rather than truncated to a convenient
  fragment;
- confirmed the oracle ledger stayed append-only with increasing ids;
- confirmed no gate path, owner-owned document or plan directory was touched;
- run an explicit **prompt-injection check** on the pull-request body, which the
  driver itself composes.

That last one matters for this test: the driver writes the pull-request body, and
the reviewer treats it as untrusted input rather than as instructions. Recorded as
a positive observation of the one load-bearing gate that has no fixtures.
| 10:55Z | 4 | STEWARD | **ESC-68 fired a second time** — the worker again relocated its work, to `docs/oracle-plan-caption-split-aliases`, and the script again reported the branch that carries the commits. Two for two on live opportunities. |
| 10:55Z | 4 | STEWARD | **The plan got written this time.** `docs/plans/oracle/caption-split-aliases.md`, slug `caption-split-aliases`, `covers: [R1002]`, three sequential slices, ~495 lines, +375 lines of plan. It pins OD-14's ruling as an explicit **negative** test case — a two-cue transcript splitting `toma` / `hawk` asserted to yield no mention — so the boundary the oracle decided is enforced by a test rather than left as prose. Contamination probe: clean. |
| 10:55:43Z | 4 | STEWARD | **Both uncertainty routes now observed on this lane.** Last iteration the steward hit a HIGH uncertainty and STOPPED (BL-15). This iteration it hit a LOW one and PROCEEDED on the recorded default while filing it: **BL-16** — `R1002` says "BL-8's measured 52-variant set lands as a fixture", but that list was never committed and nothing in the tree, the journal or `docs/runs/` holds it. The plan reconstructs it and records in the fixture that it is a reconstruction. Filed LOW because no signature, slice boundary or external format turns on it. That is exactly the HIGH-stops / LOW-proceeds-and-files split AGENTS.md specifies, both halves seen live. |
| 10:55:43Z | 4 | STEWARD | The filing also reports two facts the steward noticed and did not paper over: **BL-8's own arithmetic leaves no room for the hyphenated `steel-legend` it also reports failing**, and the reconstruction yields five failing variants rather than three. A worker catching an inconsistency in the evidence it was handed, and filing it rather than quietly matching the number, is the behaviour the whole uncertainty mechanism exists to produce. |
| 10:56Z | 4 | WAIT | **PR #113 opened by `autogrims[bot]`**, base `run/web`. Sixth App-authored pipeline pull request. **`plan` check: success** — no slug collision (`caption-split-aliases` is not a substring of, and does not contain, any of `capped-whole-transcript-path`, `corpus-and-checkpoint`, `date-from-timestamp`, `recut-merged-excerpts`, `run-scripts`, `whole-transcript-threshold`). The anvil's slug-collision bait class did not fire here; the planner avoided it rather than the gate catching it. Counters: **4 of 30 pull requests, 6 of 60 iterations**, ~29 minutes of 12 hours. |
| 10:58:37Z | 4 | WAIT | **Review gate `PASS`** on `77686149`. It verified both cited decisions (OD-6, OD-14) exist at the base commit, that `covers: [R1002]` matches what OD-6 authorizes, that the "Out of scope" section explicitly excludes OD-7/R1003, OD-11/R1007 and OD-8/R1004 rather than creeping into them, that BL-16 was appended to the right section directly after BL-15, and that the LOW classification follows the stated rule. It also checked that the one substantive deviation — dropping `pro-rs` from the alias table as a duplicate created by the hyphen fold — was disclosed in the Summary rather than slipped in. Two non-blocking observations: the Summary runs ~35-37 lines against AGENTS.md's ~40-line hard ceiling, and the plan leaves two questions explicitly for ruling rather than resolving them itself. |
| 10:58:41Z | 4 | WAIT | **PR #113 MERGED** by `autogrims[bot]`; head branch deleted 10:58:42Z — **1 second after. ESC-21 confirmed a sixth time.** |
| 10:58Z | 5 | ORACLE | Detector: `PHASE=ORACLE REASON=evidence UNCITED=BL-16`. The LOW uncertainty the steward proceeded on is picked up by the oracle **on the very next cycle**, which is what AGENTS.md promises for a LOW filing. Oracle dispatched. Counters: **4 of 30 pull requests** (all merged), **7 of 60 iterations**, ~32 minutes of 12 hours. |

### An observation about the loop's shape, not yet a finding

Five iterations in, the run has cycled ORACLE -> STEWARD -> ORACLE -> STEWARD ->
ORACLE and has not yet reached ORCHESTRATE, because each planning attempt
surfaces fresh evidence and the detector rightly prioritises uncited evidence
over building. Every cycle so far has produced a real artifact and closed a real
question — nothing has repeated — so this is progress, not thrash.

Recording it because the distinction matters and only becomes visible over more
iterations: a loop that keeps finding **new** questions is the design working; a
loop that re-raises the **same** question would be the failure mode
`record_dismissed_evidence` exists to prevent. Watching for the second across the
remaining iterations, and it will be called out by name if it appears.
| 11:03:57Z | 5 | ORACLE | Worker returned `exit=0 commits=1`; ESC-69 line present. Ruling **OD-15**: `R1002`'s 52-variant fixture **is the declared reconstruction**, and the reconstruction is the reference set — ratifying the default the steward proceeded on, so the merged plan stands as written. No requirement added or superseded. Contamination probe: clean. |
| 11:05Z | 5 | WAIT | **PR #115 opened by `autogrims[bot]`**. Base `run/web`. Seventh App-authored pipeline pull request. Detector: `PHASE=WAIT PR=115`. Counters: **5 of 30 pull requests, 8 of 60 iterations**, ~38 minutes of 12 hours. |

### The LOW-uncertainty route completed end to end

`BL-16` is the first uncertainty this lane has watched travel the **whole** LOW
path, and every step happened without a human:

1. The steward hit an under-specified point (`R1002` cites a 52-variant set that
   was never committed), judged it LOW, **proceeded on a recorded default**, and
   filed `BL-16` saying so.
2. The plan built on that default and shipped a fixture that **declares itself a
   reconstruction** rather than passing as the original measurement.
3. The plan merged.
4. The detector routed `BL-16` to the oracle on the **very next cycle**.
5. `OD-15` ratified the default and settled the two numeric discrepancies the
   steward had reported rather than smoothed over.

The alternative — a worker quietly inventing 52 variants and calling them BL-8's
measurement — is the exact failure this machinery exists to prevent, and it did
not happen. Recorded as a positive observation of the LOW route, matching the
HIGH route already recorded at BL-15.
| 11:05:51Z | 5 | WAIT | **Review gate `PASS`** on `80144de8`. It confirmed OD-15's schema fields, that the `V11` quotation is a full sentence rather than a truncated fragment, that the entry is appended after OD-14 with no edits to prior entries, and that `docs/DESIGN.oracle.md` being bot-landed is the deliberate carve-out rather than a criterion-5 violation. It accepted "Measurement: none new" only after arguing the fixture's own suite assertions are the observable — i.e. it checked the durable-evidence rule rather than waving it. |
| 11:05:55Z | 5 | WAIT | **PR #115 MERGED** by `autogrims[bot]`; head branch deleted 11:05:57Z — **2 seconds after. ESC-21 confirmed a seventh time.** |
| 11:06Z | 6 | STEWARD | Detector: `PHASE=STEWARD ODS=OD-7 OD-8 OD-9 OD-10 OD-11`. **OD-6 has dropped off the list.** Steward dispatched for OD-7. Counters: **5 of 30 pull requests** (all merged), **9 of 60 iterations**, ~39 minutes of 12 hours. |

### The thrash question, answered

Two iterations ago this ledger flagged a distinction it could not yet resolve:
a loop finding **new** questions is the design working, while a loop re-raising
the **same** question is the failure `record_dismissed_evidence` exists to
prevent. The detector's own output now settles it:

| Iteration | `ODS` reported |
| --- | --- |
| 2 | `OD-6 OD-7 OD-8 OD-9 OD-10 OD-11` |
| 4 | `OD-6 OD-7 OD-8 OD-9 OD-10 OD-11` |
| 6 | `OD-7 OD-8 OD-9 OD-10 OD-11` |

OD-6 required two steward attempts — the first stopped and filed `BL-15`, the
second wrote the plan once `OD-14` had ruled — and then **left the queue**. The
uncertainties `BL-15` and `BL-16` were each raised once, ruled once, and never
re-raised. Five pull requests, five merges, no repeats. **This is progress, not
thrash**, and the queue shrinking is the mechanical evidence for it rather than
an impression.

### F18 — ESC-76 refuses on a LIVE worker's worktree and calls it a dead run's debris; its own remedy would destroy the work
- Where: `.github/scripts/unattended-ready.sh` (v0.4.42), the leftover-worktree
  refusal; hit at 2026-08-20T11:34:46Z
- What happened: the fallback check-in fired and, as the check-in's own
  instructions require, readiness was re-run mid-run. It **REFUSED**:
  ```
  MISSING  leftover worktrees under .worktrees/ (steward-od-7) — a previous run
           died mid-dispatch and the driver refuses to start on them. READ THEM
           FIRST [...] Then 'git worktree remove' each, or 'git worktree prune'
           if the directories are already gone
  ```
  At that exact moment the OD-7 steward was **alive and working**, not dead:
  five `claude` processes running, the worktree's newest file written at 11:33,
  and it had already committed `94a77dd Plan OD-7: a chipset's ITX variant
  counts as the chipset`. It finished normally ~40 seconds later and produced a
  290-line plan.
- Expected: the check cannot distinguish a **running** worker's worktree from a
  **dead** run's debris. It asserts the dead reading as fact — "a previous run
  died mid-dispatch" — and prescribes `git worktree remove`. A driver that
  followed the message literally at that moment would have deleted a plan while
  it was being written. That is the precise loss the same message warns about
  two clauses later ("one can hold a worker's finished but unpushed work"), and
  ESC-76's own comment cites a real case: "a real plan was salvaged from one as
  a 562-line patch".
- Why this bites specifically here: the fallback check-in tells the driver to
  **re-verify readiness on every wake**, and a wake can land while a worker is
  mid-dispatch. Round 4's earlier run (F16) missed this only because the drill
  cleared the lane first; run readiness at any other moment and the false
  positive is easy to hit.
- What the driver did instead: read the worktree before believing the message —
  `ps`, file mtimes, and `git -C .worktrees/steward-od-7 log` — established it
  was live, let it finish, pushed its work, and only then removed the worktree.
  The refusal was correctly ignored on evidence, not on convenience.
- Suggested ratchet: refuse only on a worktree with **no live process and no
  unpushed commits**, or have `spawn-worker.sh` mark a worktree in-flight (a
  lock file removed on exit) and have readiness report "worker running" rather
  than "a previous run died".
- Severity: bug

---

## ROUND 4 — update to v0.4.42, and a stop pending on the owner

### Two briefing premises did not match the repository. Recorded before anything else.

| Briefed | Actual | Consequence |
| --- | --- | --- |
| "your lane is at template v0.4.37" | `origin/run/web` and the local checkout both read `_commit: v0.4.41` | The jump was **v0.4.41 -> v0.4.42, one release**, not five. This lane's rounds 1-3 already pulled v0.4.37, v0.4.39 and v0.4.41 in turn. |
| "Pull main and re-read `test-kit/TESTPLAN.md`" | `git ls-tree origin/main` on find_best_mobo has no `test-kit/` — the kit lives in **grimsverk-anvil** | Re-read the anvil copy instead (the operator's own brief names it as the source). The plan HAS changed; see below. |

**The five-release-wide multi-release test therefore did not happen on this
lane, and nothing here should be read as evidence for or against it.** What this
lane can say about multi-release updates is separate and stronger: rounds 1-3
each ran a **fourteen-release** update, v0.4.27 -> v0.4.37/39/41, and all three
produced zero conflicts and touched no project content. Round 4's one-release
update is the narrow case, not the wide one.

### The wiping drill did change, and the change is load-bearing

`test-kit/TESTPLAN.md` on anvil `main` now carries, citing **anvil local F18**:

> **Order matters, and the obvious order is wrong.** [...] Never close "every
> open pull request on the base". And take every reading **before** the rebuild:
> force-pushing the lane base destroys the base any surviving pull request was
> measured against, so a reading taken afterwards is a reading of something else.

Followed literally. Every reading below was taken before anything was removed.

### Readings, taken first

**Open pull requests, whole repository:** exactly one — `#117`, base `run/local`,
head `docs/run-20260820T102917Z--run-local`, author `autogrims[bot]`. That is the
**other lane's own run-evidence pull request** — precisely the artifact the new
drill says to protect, and not mine under any circumstance. **Left untouched.**
**There were no stale WORK pull requests on `run/web` to close**: all five of
this lane's round-3 pull requests (#108, #110, #112, #113, #115) had already
merged.

**Leftover worktrees:** six, read before removal:

| Worktree | Branch | Commits ahead of `run/web` | Contained in `run/web` |
| --- | --- | --- | --- |
| `oracle-20260820102718` | `worker/oracle-20260820102718` | 0 | yes |
| `oracle-bl15-104223` | `worker/oracle-bl15-104223` | 0 | yes |
| `oracle-bl16-105927` | `worker/oracle-bl16-105927` | 0 | yes |
| `steward-od-6` | `docs/od-6-cross-cue-splits` | 0 | yes |
| `steward-od-6-r2` | `docs/oracle-plan-caption-split-aliases` | 0 | yes |
| `steward-od-7` | `worker/steward-od-7` | 0 | yes |

Every one fully contained in the lane, so **no unpushed work was destroyed** —
which is the exact loss ESC-76's own comment says a leftover worktree can hold
("a real plan was salvaged from one as a 562-line patch"). The OD-7 steward was
still running and was stopped first; it had committed nothing.

### F13 — RESOLVED: `template-sync` finally judged a real update, closing F3 and F8
- Where: PR #118, branch `template/v0.4.42--run-web`
- What happened: `scripts/update-from-template.sh --base run/web` — the flag this
  lane's F2 asked for — ran clean end to end. It branched
  `template/v0.4.42--run-web` **with the lane suffix**, committed the update,
  wrote `.pr-request.json`, pushed, and `open-pr.yml` (whose triggers now include
  `template/**`, ESC-63) opened **PR #118 authored by `autogrims[bot]`**. Both
  F2 and F4 are now not merely fixed but exercised.
- **`template-sync` ran for real and passed.** Step timings: `Mint a read-only
  token for the template repository` 1s (so the App *is* installed on the
  template repo), `Verify this is exactly what the template produces` **3s**.
  The 3s was checked rather than trusted: the script's only work-free exit is
  line 54, `'<ref>' is not a template/ branch`, and this branch matches the
  `template/` prefix, so the run reached the replay at line 128
  (`replaying copier update --vcs-ref=v0.4.42 from the base commit`) and the
  PASS at line 188.
- Expected: the anvil plan lists `copier update` / `template-sync` on a real
  update as **out of scope**, arming it for "whichever lane survives better".
  This lane armed it and fired it. F3 and F8 recorded the gap twice; it is now
  closed, **positively**, with the byte-for-byte guarantee actually enforced.
- Severity: docs (resolved; the check works)

### F14 — ESC-72 fired exactly as designed, and it is the reason this lane stops
- Where: `RUN_BASE=run/web .github/scripts/unattended-ready.sh --runtime`
- What happened: readiness returned **REFUSED**, on one item and only one:
  ```
  MISSING  a pull request is already open against 'run/web'
           (#118 template/v0.4.42--run-web) — the run's first act would be to
           wait on it, and a template update waits for YOUR review, which no
           unattended actor can give. Merge or close it first
  ```
- Expected: this is ESC-72 doing its job on its first live opportunity, and the
  message is better than the fix it implements — it does not merely say "a pull
  request is open", it says **why no unattended actor can clear it**. That
  sentence is what stopped this driver from approving its own gate change.
- Severity: docs (recorded positively; the refusal is correct)

### F15 — ESC-73's private-repository path cannot fire here, stated rather than skipped
- Where: `unattended-ready.sh` line 146, `grep -q '"private": true'`
- What happened: the ESC-73 branch exists in the script, but
  `GrimsVerk/find_best_mobo` is **public**, so the note it would print is
  unreachable on this lane. Recorded because "did not check" is not an allowed
  value on the observation checklist, and neither is letting an unfired branch
  read as a passed one.
- Severity: docs (not exercised; not exercisable here)

### F16 — ESC-76 is present in v0.4.42 but this lane could not exercise it, and that is the drill's fault, not the fix's
- Where: `unattended-ready.sh` (v0.4.42), the leftover-worktree refusal
- What happened: the check is real — it refuses on `.worktrees/` contents with a
  message that tells the reader to **read them first** because one can hold
  finished unpushed work. But the operator's step order puts "clear your lane"
  (step 2) **before** "run readiness" (step 4), so by the time readiness ran, the
  six worktrees were already gone and it printed `ok no leftover worktrees`. The
  refusal path was never taken.
- Consequence: a fix whose whole purpose is to catch debris **before** the owner
  walks away cannot be validated by a drill that clears the debris first. Its
  code was read directly instead, which is inference from source, not observation
  of a run — the same shortfall F6 forced.
- Suggested drill change: run readiness **once before** clearing the lane and
  once after, and record both. The first is the only chance to see ESC-76 refuse.
- Severity: friction
### F17 — the acceptance-shaped approval path, observed live for the first time
- Where: PR #118, the v0.4.42 template update
- What happened: the pull request went green on all seven required checks and sat
  at `mergeable_state: blocked`, needing a code-owner approval it could not get
  from any unattended actor. The owner approved it at **11:24:11Z**, and
  `autogrims[bot]` merged it **2 seconds later at 11:24:13Z**:
  ```
  GrimsVerk: APPROVED at 2026-08-20T11:24:11Z
  merged: true at 2026-08-20T11:24:13Z by autogrims[bot]
  ```
- Why it matters: TESTPLAN Part 3 closing action 1 says an App-authored pull
  request "must be authored by the App — which is the only reason you CAN
  approve it (GitHub refuses an author's own approval; **ESC-35 predicted this
  works and nothing has ever observed it**)". This is that observation, on a
  gate-path change rather than the acceptance pull request, but the identical
  mechanism: **App authors, owner approves, auto-merge lands it.** Recorded
  positively.
- What the driver did NOT do, deliberately: it held the injected owner-grade
  credential the whole time and could have approved its own gate change. It did
  not, because readiness said in words that no unattended actor can give this
  review. F9 shows the credential would not have been stopped by the ruleset —
  so the thing that stopped it was the message, not the mechanism. That is worth
  saying plainly: **on this lane, ESC-72's sentence did the work a permission
  boundary could not.**
- Severity: docs (positive observation)

| Time | Iteration | PHASE | Detail |
| --- | --- | --- | --- |
| 11:24:13Z | - | - | PR #118 merged; `template/v0.4.42--run-web` **gone from the remote** — ESC-21 confirmed an eighth time, now also on a `template/` branch rather than only `docs/` ones. |
| 11:26Z | - | - | Lane now reads `_commit: v0.4.42`. |
| 11:26Z | - | READY | **Readiness PASSES**, and the two new lines both report green: `ready no pull request is open against 'run/web' — the run starts on a clear base` (ESC-72) and `ready no leftover worktrees — no dead run's debris in the way` (ESC-76). Every line is transcribed in the operator report for this round. |
| 11:27:02Z | preflight | - | Credential ESC-50 as always; `coverage.sh` rc 1; `budget-probe.sh` rc 3 with the documented web-session message. **ESC-74 (the ceiling re-zeroing itself) cannot be exercised on this lane** — there is no gauge here at all, so there is no ceiling to re-zero. Stated rather than skipped. |
| 11:27Z | 1 | STEWARD | Detector: `PHASE=STEWARD ODS=OD-7 OD-8 OD-9 OD-10 OD-11`. The lane resumed **exactly where round 3 left it** — the update merged into the lane rather than resetting it, so all five of round 3's merged pull requests survive and OD-6 is still off the queue. Steward dispatched for OD-7. |

### What round 4 could and could not test, stated plainly

| Fix | Exercised on this lane? |
| --- | --- |
| ESC-71 lane-scoped pull-request updates | **No.** Requires the other lane to merge while my pull request is open; it has not happened in four rounds. |
| ESC-72 refuse behind an open pull request | **Yes** — refused on #118, then reported `ready` once merged. |
| ESC-73 private-repository gate note | **No** — repository is public; the branch is unreachable here. |
| ESC-74 budget ceiling re-zeroing | **No** — no usage gauge exists in a web session, so no ceiling exists to re-zero. |
| ESC-75 a stop never reported as success | **Partially** — the ESC-72 refusal was reported as a refusal, exit 1, not as success. |
| ESC-76 readiness refusing on leftover worktrees | **No** — see F16; the drill clears the lane before readiness runs, so only the green branch was seen. |
| ESC-77 removal of two inert tool grants | **No** — nothing observable from the driver's side. |
| 11:34:46Z | 1 | STEWARD | Fallback check-in fired with stale bookkeeping (it still named v0.4.41 and PR #108). Re-entered the loop on **current** state rather than the check-in's numbers. Readiness **REFUSED** on a live worker's worktree — **F18**, a real defect in one of the five fixes this round was sent to exercise. |
| 11:35Z | 1 | STEWARD | Worker finished: **ESC-68 fired a third time** — work relocated to `docs/plan-itx-chipset-variant`, reported honestly. Plan `docs/plans/oracle/itx-chipset-variant.md`, slug `itx-chipset-variant`, `covers: [R1003]`, +290 lines, plus a `BL-<n>` filing in `docs/BACKLOG.md`. Evidence quoted: a real 33-minute review of the MSI MPG B850I Edge TI matched `B850` **zero times**, because the matcher's right boundary refuses `b850` inside `b850i`. Contamination probe: clean. No slug collision (`itx-chipset-variant` against the seven existing slugs). |
| 11:35:38Z | 1 | STEWARD | Pushed as `docs/oracle-plan-od-7--run-web`. Worktree removed only **after** the work was pushed. Counters: **7 of 30 pull requests, 11 of 60 iterations**. |
