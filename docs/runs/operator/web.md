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
