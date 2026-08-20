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
| 2026-08-20T08:26Z | Ledger branch `chore/test-report-web` created off `origin/main` in a separate worktree, so ledger commits never disturb the lane checkout. |

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

