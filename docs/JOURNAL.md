# Journal — Finding Best Mobo by Buildzoid

One dated entry per working session: what was done, what was decided elsewhere
and only referenced here, and what the next session should pick up. Newest at
the bottom. This is the hand-off file — chat is not storage.

## 2026-08-14 — pipeline bootstrap

The `copier update to v0.4.0` pull request (#2) landed the enforcement pipeline:
CI, the `plan` gate, `test-the-tests`, the LLM review gate, and auto-merge.

Two failures were fixed on the branch before it merged:

- `uv.lock` still recorded a `ruff` version outside the range `pyproject.toml`
  pins, so `uv sync --locked` refused to install and CI stopped before running
  anything. Relocked.
- The `secrets` job crashed with a 403 on every pull request — the default token
  cannot list a pull request's commits, so gitleaks aborted instead of scanning.
  The job now requests `pull-requests: read`. Logged in `docs/escapes.md`.

The `plan` and `review` gates could not pass and were not made to: this is the
pull request that introduces the planning system, so no plan for it can exist on
the default branch, and the review gate blocks a large unplanned rewrite of the
gates themselves by design. The owner merged it with bypass rights. That is the
bootstrap path, not a precedent — from here every change has a pipeline to pass.

Next session: `docs/DESIGN.md` is still the unfilled template, so §5 has no
requirements for a plan to cover and §13 no success criteria for the acceptance
pass to evidence. Filling it in is the gate on all planned work.
