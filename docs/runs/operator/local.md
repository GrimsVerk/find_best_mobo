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

