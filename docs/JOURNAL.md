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

## 2026-08-14 — template v0.4.4, and the template URL

The v0.4.4 update (#4) introduces `template-sync`: it replays `copier update`
from the base commit and passes only if the result matches the branch exactly.
That check is what earns a `template/` branch its exemption from planning — a
stronger claim than a plan, because it verifies the diff rather than recording
an intention.

It could not run. `_src_path` named `github.com-grimsverk`, an SSH host alias
defined in the owner's `~/.ssh/config` and resolvable nowhere else, so the clone
failed before copier started. `TEMPLATE_TOKEN` does not reach this: the workflow
rewrites `https://github.com/` and `git@github.com:`, and an `ssh://` alias URL
matches neither. This pull request points `_src_path` at the plain `https://`
URL, which the runner can resolve and the token can authenticate.

Two consequences worth carrying forward. First, #4 was merged by owner override:
it also carried unresolved conflict markers in `src/find_best_mobo/__init__.py`,
and fixing them by hand is itself a manual edit, so `template-sync` would reject
that branch even once it could run. Second, `project_name` is now the slug and
`project_slug` is gone — deliberate, matching the new template, not drift.

## 2026-08-14 — the design doc, written and nearly lost

`docs/DESIGN.md` is filled in, replacing the skeleton that has been gating all
planned work since the bootstrap session. It carries 25 requirements and 11
success criteria. Every owner ruling behind it is recorded in `docs/DECISIONS.md`
(created this session) rather than left in chat.

The shape that came out of elicitation: the pipeline splits at the model
boundary, because no API key exists and all inference runs on the owner's
subscription. Python owns the deterministic corpus work and writes bundles to
disk; agents read bundles and write claims back. Between them sits a hard
checkpoint that prints a cost projection and stops, then a small calibration
batch that turns the projection into a measurement, then three larger batches
with a stop after them. Reports are generable at any batch boundary with a
coverage stamp, so stopping early is a real option rather than an abandonment.

Two owner revisions during drafting, both superseding positions taken earlier in
the same session and both recorded in `DECISIONS.md`: transcript failures are
logged and tolerated with two halt triggers rather than failing hard, and the
excerpt window starts wide (2 min before a mention, 5 after) to be narrowed
later on evidence rather than starting tight.

**Nearly lost.** The owner reset their local checkout to `origin/main` partway
through, and the design doc — tracked, but never committed — went back to the
skeleton. It was reconstructed from the session's context in full. Nothing else
was affected; `GLOSSARY.project.md` survived as an untracked file. The lesson is
the ordinary one: git protects what has been committed, and a large document
living only in the working tree is one command from gone.

**Found while reviewing before the pull request:** two requirement ids added
during drafting, `R2a` and `S1a`, do not match what the coverage gate parses
(`**R<digits>**`, validated as `^R[0-9]+$`). They would have been silently
uncounted. Renumbered to `R24` and `S10`. The gate ignores unrecognised ids
rather than failing on them — it fails open on a malformed id — which is a
ratchet candidate for the owner, since gate scripts are human-owned.

**Open, and blocking the merge of this pull request.** The design doc cannot
pass the `plan` check. The `docs/` exemption is size-capped at 50 added lines and
the doc adds around 600; no plan can cover it either, since plans implement the
design doc's requirements and would have to predate it. This is the same
bootstrap shape as #2 and #4 — a document the pipeline requires but has no path
for — and it needs an owner decision: bypass and log, or add an uncapped
exemption for the design doc in `plan-resolve.sh`, which is a gate path and
therefore the owner's to change.

Next session: with the design doc landed, write the plan for the MVP milestone —
corpus and the cost checkpoint, no inference at all — as `docs/plans/<slug>.md`
on its own `docs/` pull request, before any code.
