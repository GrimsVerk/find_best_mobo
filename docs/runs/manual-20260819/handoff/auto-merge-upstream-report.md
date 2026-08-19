# Bug report — grimsverk-template: the auto-merge workflow is dead on arrival

Every project generated from **v0.4.21** ships a workflow that fails validation.
No job in it has ever run.

## The defect

`template/.github/workflows/{% if auto_merge %}auto-merge.yml{% endif %}`, line 94:

```yaml
      - name: Mint the App token
        # Skipped in repositories where the App is not configured; the arming
        # step's token fallback chain handles both outcomes. Step-level `if` is
        # used because the secrets context is not available in job-level `if`.
        id: app-token
        if: ${{ secrets.APP_ID != '' }}
```

The `secrets` context is **not available in an `if:` at all** — not job level, not
step level. The comment beside the line states the wrong reason, which is what
makes the bug look deliberate.

A workflow referencing `secrets` there does not skip a step. It **fails
validation**: the run is created, dies immediately, and produces **zero jobs**.
Every job in the file dies with it:

- `arm-auto-merge` — nothing arms auto-merge, so nothing ever merges itself
- `delete-merged-branch` — merged branches accumulate
- `sweep-merged-branches` — the nightly cleanup never runs

## How it was found

In `find_best_mobo`, every `auto-merge.yml` run since v0.4.21 landed:

```
32189400097  docs/plans-summary-and-covers          -> failure
32189395666  chore/flaky-path-in-report-assertions  -> failure
32189380636  main                                   -> failure
```

`gh run view` reports only "This run likely failed because of a workflow file
issue", with no jobs listed.

**Why no gate caught it.** `arm-auto-merge` is a check reported *by* the broken
workflow, so its disappearance read as "not applicable" rather than "the file is
dead" — and a required-checks list cannot notice a check that never reports.

**The self-host cannot catch it either.** The template repo's own
`.github/workflows/` holds `template-ci.yml`, `release-tag.yml` and
`reviewer-fixtures.yml` — no `auto-merge.yml`. This is the one shipped workflow
the template never runs on itself, so "the template is governed by the template"
has a hole exactly here.

## The workaround, until the fix ships

The workflow's only job is to **arm** GitHub's native auto-merge; GitHub does the
merging. So the breakage does not stop merges — it stops *arming*. A pull request
armed before the breakage still merges itself, which is why the failure looked
intermittent rather than total.

Arming by hand does work, and was confirmed live: a green pull request armed with
`gh pr merge <n> --auto --merge` merged within seconds.

```sh
gh pr merge <n> --auto --merge   # arm; merges on green (and on approval)
gh pr update-branch <n>          # after any OTHER pull request merges
```

The second line is not optional. Observed directly: when one pull request merged,
every other open one flipped to `mergeStateStatus: BEHIND` **while armed**, and
GitHub did not bring any of them up to date. That is the evidence for step 3
below — armed is not sufficient under a strict required-checks policy.

## The work

### 1. Fix the validation error

Hoist the id into a job-level `env:` (secrets *are* allowed there) and test `env`
in the step `if:` (where it *is* available). Same behaviour, valid file.

```yaml
  arm-auto-merge:
    ...
    env:
      APP_ID: ${{ secrets.APP_ID }}
    steps:
      - name: Mint the App token
        id: app-token
        if: env.APP_ID != ''
```

**Correct the comment too.** Leaving it preserves the false claim that step-level
`if:` can read secrets — which is how this survives a review.

### 2. Add the gate that would have caught it: actionlint

There is no `actionlint` anywhere in the repo (`grep -rn actionlint` returns
nothing). It flags an unavailable context in an `if:` by name.

Natural home: beside the existing `shellcheck` job in
`.github/workflows/template-ci.yml` (line 23). One wrinkle — the shipped filename
is Jinja, so lint the **rendered** output; `tests/test-render.sh` already renders
a project.

### 3. Consider: update open pull requests on merge

Separate problem, same file. Generated projects set
`strict_required_status_checks_policy: true`, so **the moment any PR merges,
every other open one becomes unmergeable** however green it is. GitHub reports
`mergeStateStatus: BEHIND`, which never appears in the checks list — seven green
ticks on a PR that cannot merge.

That is `ESC-17`, whose recorded answer was to forbid queues. Right for
unattended runs (`deliver-phase.sh` returns `WAIT` on any open PR). Wrong for
attended work, where the cost lands on the owner by hand, once per merge, per
branch.

A working implementation exists downstream on `fix/auto-merge-secrets-in-if`: an
`update-open-prs` job on `pull_request: closed` when merged, calling
`gh pr update-branch` on each remaining open PR. Two deliberate properties — **it
never fails** (a genuine conflict is reported and left for a human, not turned
into a red check on an innocent PR), and **it uses the App token**, because a
branch updated by `GITHUB_TOKEN` pushes without creating workflow runs and would
come up to date without ever re-running its checks.

### 4. Log it

Append to `docs/escapes.md`. The template's ledger is at `ESC-17`, so the next id
is **ESC-18**. Gate column: nothing could have caught it, because this is the one
shipped workflow the self-host never executes. Check-added column: `actionlint`.

Numbering is per-repository — the same defect is `ESC-23` in `find_best_mobo`'s
ledger. Do not reuse that number here.

## After the fix

Merging to `main` tags and releases automatically. Then each generated project
runs `scripts/update-from-template.sh`.

**Coordinate one thing.** `find_best_mobo` currently carries a hand fix of this
same file, to get unblocked tonight. A `template/` branch must be byte-for-byte
`copier update` output, so `template-sync` will fail while that local edit is in
the tree. Order it: land the template fix, then in the project revert the local
change to `.github/workflows/auto-merge.yml` and take the template's version
through `copier update`. The local `docs/DECISIONS.md` entry can stay — it is
project prose, not template output.

## Verifying it actually works

The failure mode is silence, so check for presence, not the absence of red.

- [ ] Open a PR in a generated project — `arm-auto-merge` **appears** in
      `gh pr checks` and passes. Before the fix it is simply absent.
- [ ] `gh run list --workflow=auto-merge.yml` shows `success`, and
      `gh run view <id> --json jobs` lists jobs rather than an empty array.
- [ ] A green PR merges without anyone pressing the button.
- [ ] With two PRs open, merge one — the other's branch updates on its own and
      its checks re-run.
- [ ] `actionlint` fails the build if the `secrets`-in-`if` line is put back.
      Test it by putting it back.

---

Reported from `find_best_mobo` · template v0.4.21 · 18 August 2026.
Downstream ledger entry: `ESC-23`. Downstream fix branch:
`fix/auto-merge-secrets-in-if`.
