# Finding Best Mobo by Buildzoid

Searching Buildzoid videos on YT to extract his top pick for an AMD mobo.

Generated from [grimsverk-template](https://github.com/GrimsVerk/grimsverk-template);
pull in template updates with `copier update --trust`.

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

## Repository setup (manual, once)

These are GitHub settings the template can't set from inside the repo. Enable
them on the default branch (`main`):

1. **Branch protection** on `main`: require a pull request before merging, and
   require these **status checks** to pass:
   - `checks` (CI hard gate)
   - `secrets` (mechanical: gitleaks over the full history)
   - `plan` (mechanical: the PR resolves to exactly one plan, already at base)
   - `test-the-tests` (mechanical: the new tests fail without the new code)
   - `review` (LLM soft gate)
2. **Require review from Code Owners** (branch protection), so changes to the
   gate paths in `CODEOWNERS` need @GrimsVerk's approval even under
   auto-merge.
3. **Review engine credential** (a *subscription*, not a metered API key): the
   review runs on your Claude Code subscription. Generate a token once with
   `claude setup-token` and add it as the `CLAUDE_CODE_OAUTH_TOKEN` secret under
   *Settings → Secrets and variables → Actions*. (A metered `ANTHROPIC_API_KEY`
   also works, as a fallback, if you happen to have one.) Without a credential
   the review job fails closed and nothing merges. *Codex engine: running the
   gate on a ChatGPT/Codex subscription needs that CLI's login injected into CI
   — not wired yet; see the comment in `review.yml`.*
4. **Allow auto-merge** for the repo (*Settings → General → Pull Requests →
   Allow auto-merge*), and keep **Allow merge commits** enabled (the default) —
   the PR lands as a merge commit. Without auto-merge enabled, `auto-merge.yml`
   can't arm PRs.

Coding agents work on a branch and open a PR into this pipeline; branch
protection plus the required checks are what prevent self-merging.

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

