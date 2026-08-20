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
