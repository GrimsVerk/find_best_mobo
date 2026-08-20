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

