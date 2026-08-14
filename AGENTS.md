# Finding Best Mobo by Buildzoid — agent guidelines

Canonical working instructions for any coding agent in this repository.
Tool-specific entry points (e.g. `CLAUDE.md`) only point here; rules are
never duplicated elsewhere.

## Workflow

**Branches.** Never commit to the default branch directly; work on a branch
and let the owner merge. Never force-push or rewrite history on a branch
that has been pushed.

**Commits.** One conceptually contained commit per unit of work, pushed
when complete, with an imperative one-line message. The test suite must
pass before every commit. Documentation is updated in the same commit as
the code it describes — docs never lag the code.

**Tests.** New behaviour comes with tests in the same commit. The suite
runs offline and deterministically; a test that needs an unavailable
optional resource skips with a clear reason rather than failing.

**Dependencies.** No new dependencies without the owner's approval — ask
first, in chat.

**Licensing.** This project is intentionally unlicensed: there is no
`LICENSE` file and no `license` field in package metadata, and their absence
is a decision, not an omission. Licensing is assessed per project by the
owner, at the point it actually matters — publication, distribution, or
accepting outside contributions — because a default chosen up front silently
attaches terms to a project that never revisits them. So: do not add a
license file, do not populate a `license` field, and do not ask which license
to use. If a task genuinely cannot proceed without one, say so in chat and
let the owner decide.

**Decisions.** Design choices and owner rulings are recorded in
`docs/DECISIONS.md` (ADR-lite: one dated entry per decision, newest at the
bottom; create the file on the first decision). A recorded ruling is never
silently reversed — to change one, argue the case in chat, wait for the
owner, then add a superseding entry. History is never rewritten.

**Work queue.** When working unattended, implement only items the owner
has approved in `docs/BACKLOG.md` ("Approved" section, top to bottom), and
keep going until the list is done or you are truly blocked. New ideas are
written into "Proposed" as text — never coded unprompted. If an attempt is
stuck after 3–5 tries, log what was tried and why it failed, then move on;
if the blocker gates everything, build the simplest clearly-marked
stand-in and leave the real fix for the owner.

**Memory.** Chat is not storage. Anything a future session (or a different
agent) would need is written into the repository in the same unit of work:
decisions → `docs/DECISIONS.md`, work items and ideas → `docs/BACKLOG.md`,
session notes and hand-offs → `docs/JOURNAL.md` (one dated entry per
working session), user-facing behaviour → `README.md`.

**Honesty about verification.** Never claim something is verified in an
environment where you could not observe it. Record what was verified where;
"CI added" is not "CI verified" until a run has actually passed. When only
the owner can verify something, say exactly what to run and ask for the
output.

**Ambiguity.** Prefer stating what you need in chat and continuing on best
judgment over blocking; the owner reads chat. Stop and ask only when truly
blocked on something only the owner can provide.

## Enforcement

Pre-commit hooks (`.pre-commit-config.yaml`) and CI
(`.github/workflows/ci.yml`) enforce formatting, linting, typing, and the
test suite on every commit and push, regardless of which tool or agent
wrote the code. A failing gate is fixed, never bypassed: no `--no-verify`,
no skipping or weakening checks to get green.

**The merge pipeline.** Merges are mechanical: a pull request merges when
its required checks go green — the **hard gate** (CI: format/lint/type/tests,
which is authoritative) plus a **soft gate** (`.github/workflows/review.yml`,
an independent read-only LLM review of the diff against this file and
`docs/DESIGN.md`, run with fresh context — a different model than the author
is a nice-to-have, not required). The soft gate is an added check, never a
replacement for CI. No agent merges on its own judgment: opening the PR into this pipeline
is where an agent's job ends, and the merge is triggered by check status,
not by any agent — including a passing local review — deciding to merge.

**Gate paths are off-limits.** Never modify the things that check the code:
CI workflows (`.github/workflows/`), the review check or its prompt
(`.github/review-prompt.md`, `.github/scripts/review.sh`), the pre-commit
config, or `CODEOWNERS`. These are human-owned and enforced by `CODEOWNERS`;
a change to any of them requires human review even under auto-merge. Do not
weaken, skip, or route around a gate to get green.

## Language-specific

Tool configuration in `pyproject.toml` is the source of truth for lint,
format, and typing rules — follow it, don't restate or override it. The
test suite's offline rule is enforced by the autouse fixture in
`tests/conftest.py`. Run the full gate locally with:

    uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
