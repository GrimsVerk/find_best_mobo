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

## Merge pipeline

Changes land through two gates, and the merge is **mechanical** — no human
rubber-stamp, and no agent merges on its own judgment:

- **Hard gate — CI** (`.github/workflows/ci.yml`): format, lint, types, and
  tests. Authoritative; a red CI blocks merge.
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

