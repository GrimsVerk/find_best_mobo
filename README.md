# Finding Best Mobo by Buildzoid

Searching Buildzoid videos on YT to extract his top pick for an AMD mobo.

Generated from [grimsverk-template](https://github.com/GrimsVerk/grimsverk-template);
pull in template updates with `scripts/update-from-template.sh`.

## Development

```sh
uv sync                # install dependencies (creates .venv)
uv run pytest          # run tests
pre-commit install     # enable git-level checks (ruff, mypy, gitleaks)
```

## Talking to agents here

`GLOSSARY.md` holds the owner's communication rules and two word lists:
vocabulary being learned, which agents explain in passing, and vocabulary
already settled, which they use plainly. A word in neither list counts as
unknown — the agent glosses it and asks where it belongs.

`GLOSSARY.md` comes from the template and is replaced by `copier update`, so it
is never edited here. Words met during this project go in
`GLOSSARY.project.md`, which is created on first use and belongs to this
repository alone.

## Merge pipeline

Changes land through two gates, and the merge is **mechanical** — no human
rubber-stamp, and no agent merges on its own judgment:

- **Hard gate — CI** (`.github/workflows/ci.yml`): format, lint, types, and
  tests. Authoritative; a red CI blocks merge.
- **Hard gate — secrets** (the `secrets` job): gitleaks over the full history.
  It runs in CI and not only in pre-commit, because pre-commit needs
  `pre-commit install` on every clone — a fresh worktree, or anyone who skipped
  that step, would otherwise bypass it, and a committed credential is exactly
  the thing that must not depend on someone having run a setup command.
- **Hard gate — plan** (the `plan` job): every PR must resolve to exactly one
  plan under `docs/plans/`, matched by the plan's `slug` appearing in the branch
  name, **and that plan must already exist at the PR's base commit**. It fails
  hard rather than warning, because a plan the reviewer never receives is a gate
  that quietly stopped working — and a plan arriving with its own implementation
  is one the implementation wrote. Plans land first, on their own `docs/` PR.
  Branches prefixed `chore/` or `docs/` are exempt, for changes too small to
  plan; the exemption is capped at ~50 added lines so it can't be used to route
  real work around the gate.
- **Hard gate — template-sync** (the `template-sync` job): a `template/` branch
  is exempt from `plan`, because a template update is specified in the *template*
  repository and no plan here can describe it. This is what earns that: it
  replays `copier update` from the base commit and fails unless the result is
  byte-for-byte this PR. Stronger than a plan — a plan says someone intended the
  change; this proves nothing hand-written rode along with it. Passes trivially
  on every other branch.
- **Hard gate — test-the-tests** (the `test-the-tests` job): reverts this PR's
  implementation, keeps its new tests, and fails if the suite still passes.
  Tests that stay green without the code they cover are testing nothing, which
  matters most when nobody reads them. Runs only when a PR changes both
  implementation and tests.

  Know what this does and does not prove. It proves the suite **depends on** the
  new code — nothing more. A compile error or a failed import satisfies it, so a
  test that imports a new module and then asserts very little still passes the
  check. It is not mutation testing and it does not measure how good the
  assertions are. What it catches is the specific, common failure of a suite
  wired to nothing: tests asserting on mocks, on fixtures, or on the absence of
  an exception. The assertion quality question is the reviewer's, informed by
  the blind-authorship facts.
- **Hard gate — acceptance-criteria** (the `acceptance-criteria` job): runs
  every success criterion `docs/DESIGN.md` §13 does **not** mark **(owner)**,
  as a script at `acceptance/S<n>.sh`. Exit 0 is pass, standard output is the
  evidence, and `acceptance/README.md` says how to write one.

  On **every** pull request, not once at the acceptance pass. That is the point:
  a criterion verified once and trusted thereafter is exactly the "verified
  once, trusted forever" shape this template distrusts everywhere else, and one
  that passed at acceptance and regressed three merges later would be caught by
  nothing until the next acceptance pass — which may be the last one.

  It exists because `docs/acceptance.md` is the one artifact in an unattended
  run whose PR requires your review, and its evidence used to be an agent's
  narration: *"I ran X and it printed Y."* A pass an agent claims is now a pass
  you can re-run, or the check refuses the row.

  A criterion nobody has scripted yet is **reported, not failed** — one for work
  that is not built is failing correctly, and failing the pipeline for it would
  stop the build that would make it pass. A criterion that fails routes to the
  oracle, which may rule it met in a way the script cannot see and record a
  waiver; the row then stays `pending / owner`, because the oracle may not mark
  a criterion passed.
- **Soft gate — review** (`.github/workflows/review.yml`): an independent,
  read-only LLM reviews the PR diff against `AGENTS.md` and `docs/DESIGN.md`
  (design conformance, scope creep, soundness, security smells) and blocks on
  any blocking finding. It is an *added* check on top of CI, never a
  replacement. Its independence comes from **fresh context** (a one-shot
  headless run, not the author's session) and being **read-only** — running a
  *different* model than the author is a nice-to-have, not required.

When both gates are green, the PR merges automatically via GitHub native
auto-merge (armed by `.github/workflows/auto-merge.yml`, completed by GitHub
when checks pass — as a merge commit, preserving history).

## Unattended delivery

Once `docs/DESIGN.md` and `docs/VISION.md` have landed, the whole loop — plan,
build, merge, next — can run with nobody watching. Two frontends, one phase
detector (`.claude/scripts/deliver-phase.sh`), chosen by which you start:

```sh
.claude/scripts/deliver-loop.sh          # local: waits on `gh pr checks --watch`
```

or `/deliver-loop` in a Claude Code web session, which waits on PR events and
scheduled check-ins instead of holding a turn open. Before dispatching
anything, the driver runs `.github/scripts/unattended-ready.sh`, which reads
the *repository's* configuration back and **refuses** a run that cannot
succeed, naming each missing setting.

Your three jobs, and the loop never adds a fourth: land the design and vision;
optionally steer mid-run by editing those two documents (they are the steering
lever — every oracle ruling quotes `docs/VISION.md`, so editing a sentence
moves everything downstream); review at the end. Mid-run questions go to the
oracle, not to you: HIGH-risk uncertainties block planning until a ruling
lands, LOW-risk ones proceed on a recorded default (`docs/DECISIONS.md` ships
the rulings behind this). Every stop states its reason — the same failure
three times, the allowance spent, or a green pull request only you can merge —
and the morning read is `.claude/deliver-loop/run.md` plus
`docs/acceptance.md`'s pending-on-owner list.

**The run asks you for its ceiling before it starts, every time, and refuses to
start without one.** No number is defaulted, because a limit you did not choose
is one you will not recognise when it fires while you are asleep. Which question
you get is decided by probing the usage gauge rather than by guessing where you
are running:

- **In a terminal, with a usage reader** — *how many percentage points of your
  **weekly** limit may this run spend?* That percentage is the only stop that
  applies by default. Both weekly limits are watched: the all-models one and
  the per-model one, which has its own smaller cap and can bind first.
- **In a web session, or with no reader** — the subscription percentage cannot
  be read at all, so you are asked for at least one limit that *can* be counted
  here: pull requests, wall-clock hours, or iterations.

`--budget-points`, `--max-prs`, `--max-hours` and `--max-iterations` answer the
question up front, which is what you want for a deliberately short run ("give it
twenty minutes; if it needs longer, something is wrong").

On a machine with a free usage reader, point `BUDGET_PROBE_CMD` at it — the
built-in fallback is `claude -p "/usage"`, which works but starts a small
session every time it is asked, and the driver asks once per iteration. On
Omarchy:

```sh
export BUDGET_PROBE_CMD='omarchy-agent-usage-claude --limits-only --force'
```

`--force` matters: the reading is cached for 15 seconds, so without it two
probes in a row return the same number and a short iteration reads as zero spend.

## Repository setup (manual, once)

These are GitHub settings the template can't set from inside the repo. Enable
them on the default branch (`main`):

1. **Branch protection** on `main`: require a pull request before merging, and
   require these **status checks** to pass:
   - `checks` (CI hard gate)
   - `secrets` (mechanical: gitleaks over the full history)
   - `plan` (mechanical: the PR resolves to exactly one plan, already at base)
   - `template-sync` (mechanical: a `template/` PR is pure `copier update` output)
   - `test-the-tests` (mechanical: the new tests fail without the new code)
   - `acceptance-criteria` (mechanical: every scripted success criterion still holds)
   - `review` (LLM soft gate)
2. **Require review from Code Owners** (branch protection), so changes to the
   gate paths in `CODEOWNERS` need @GrimsVerk's approval even under
   auto-merge.
3. **Template read token** (`TEMPLATE_TOKEN`): a fine-grained PAT with
   **Contents: Read-only** on the template repository, added under *Settings →
   Secrets and variables → Actions*. This repository's built-in CI token is
   scoped to this repository and cannot read another one, so `template-sync`
   cannot fetch the template without it — and it fails closed, meaning no
   template update can merge. Fine-grained tokens expire (a year at most); when
   this one does, the check starts failing here and in every other project at
   once, so renew it deliberately rather than discovering it.
4. **Review engine credential** (a *subscription*, not a metered API key): the
   review runs on your Claude Code subscription. Generate a token once with
   `claude setup-token` and add it as the `CLAUDE_CODE_OAUTH_TOKEN` secret under
   *Settings → Secrets and variables → Actions*. (A metered `ANTHROPIC_API_KEY`
   also works, as a fallback, if you happen to have one.) Without a credential
   the review job fails closed and nothing merges. *Codex engine: running the
   gate on a ChatGPT/Codex subscription needs that CLI's login injected into CI
   — not wired yet; see the comment in `review.yml`.*
5. **Allow auto-merge** for the repo (*Settings → General → Pull Requests →
   Allow auto-merge*), and keep **Allow merge commits** enabled (the default) —
   the PR lands as a merge commit. Without auto-merge enabled, `auto-merge.yml`
   can't arm PRs.

Coding agents work on a branch and open a PR into this pipeline; branch
protection plus the required checks are what prevent self-merging.

## Updating from the template

Template improvements arrive through `copier update`, and that is a third kind
of change: not planned work, not a trivial chore. It was specified and reviewed
in the template repository, so no plan here could describe it.

```sh
scripts/update-from-template.sh
```

That is the whole thing: it updates, works out which template version you landed
on, branches as `template/<version>`, commits, pushes, and opens the pull
request. `--no-pr` stops before the pull request; `--ref HEAD` pulls in a
template change that has merged but is not tagged yet.

> If `copier update` prompts for a password, your machine is missing the local
> git routing rule — see the template repository's README. Nothing in this
> project needs changing; `_src_path` is an `https://` URL on purpose, because CI
> is the one consumer that cannot choose its own transport.

It stops and hands back to you in exactly one case: a **conflict**, where the
template changed a file this project also changed. Copier leaves both versions
in the file with conflict markers around them, and no script can know which side
you meant. Nothing is committed at that point, so `git checkout -- .` backs the
whole update out if you would rather deal with it later.

The `template/` prefix exempts it from the `plan` check and hands verification
to `template-sync`, which replays the update from the base commit and fails
unless this PR is exactly its output. So the branch may carry the template's
changes and **nothing else** — if a hand fix is needed on top, it goes in its own
pull request afterwards, with a plan.

**If the template tightened a dependency pin, the lockfile lags.** `uv.lock`
still records the old resolution and `uv sync --locked` refuses to install, so CI
goes red on a change the template made. The template ships no lockfile, so there
is nothing to fix upstream — run `uv lock` and land it as a **separate `chore/`
pull request** after the template one merges. It cannot ride along: a `template/`
branch must be pure `copier update` output, and a regenerated lockfile is not,
so `template-sync` would reject it.

Expect to approve it yourself. A template update usually touches `.github/` and
`AGENTS.md`, which `CODEOWNERS` owns, and GitHub will not accept your approval on
your own PR — see the deadlock note in the root template's README. That is
working as intended: a change to your own gates is exactly what a human should
look at. `template-sync` being green is what makes that a quick read of the
template's release notes rather than a line-by-line audit of 40 files.

> **This repository needs a `TEMPLATE_TOKEN` secret**, because the template is
> private. A project's built-in CI token is scoped to the project and cannot read
> another repository, so without it `template-sync` fails closed and no template
> update can merge. Add a fine-grained PAT with **Contents: Read-only** on the
> template repo under *Settings → Secrets and variables → Actions*. It expires —
> a year at most — and when it does, this check starts failing here and in every
> other project at the same time.

## The ratchet

Nothing that escapes to you gets fixed without also adding a permanent check
that would have caught it — "why did this bug exist" and "which gate should have
caught this" are the same question. Each escape is one line in
`docs/escapes.md`: what escaped, which gate should have caught it, what check
was added.

Only one check is seeded (`test-the-tests`). That is deliberate: the log is what
tells you which check to add next, and a check added on speculation is machinery
you now maintain for a failure that never happens. Let the log ask first.

## Is it done?

Two different questions, deliberately kept apart:

```sh
.github/scripts/coverage.sh    # is every DESIGN.md §5 requirement PLANNED?
```

Coverage is mechanical: it matches requirement ids against the `covers:` field
of each plan. A full pass means the work was **scheduled and merged** — not that
it works.

Whether it works is the **acceptance pass**, recorded in `docs/acceptance.md`:
one row per §13 success criterion, with evidence, and an honest split between
what an agent observed by running something and what only you can verify. The
project is done when every criterion has evidence and nothing is pending on you.
An empty backlog is not the same claim.

`/deliver` drives the whole loop — plan, build, wait for the pipeline, repeat,
then run the acceptance pass.

## Reverting a bad merge

Because no human reads every change before it lands, fast rollback is the real
safety net. PRs land as merge commits, so reverting a whole bad PR is one line:

```sh
git revert -m 1 <merge-sha> && git push   # <merge-sha> = the bad PR's merge commit
```

`main` stays buildable/deployable at every commit (CI gates every push), so a
revert restores a known-good state immediately.

> **Auto-merge tradeoff.** This project auto-merges on green. That trades a
> human pre-merge checkpoint for speed, relying on CI + the review gate up
> front and `git revert` after. For anything real people download, or that
> touches payments, secrets, or user data, regenerate (or set) `auto_merge`
> to `false` to keep a human merge step; the review gate still runs.

