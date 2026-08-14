# Finding Best Mobo by Buildzoid — agent guidelines

Canonical working instructions for any coding agent in this repository.
Tool-specific entry points (e.g. `CLAUDE.md`) only point here; rules are
never duplicated elsewhere.

## Workflow

**Branches.** Never commit to the default branch directly; work on a branch and
open a pull request. **The pipeline merges, not you and not the owner** — a PR
lands when its required checks go green (see "The merge pipeline" below), so
your job ends at opening it. Never force-push or rewrite history on a branch
that has been pushed. **Any branch you open a pull request from must contain its
plan's `slug`** — CI resolves the plan by matching slugs against the branch name,
and a PR whose plan can't be resolved fails the `plan` check. Name intermediate
branches with the slug too, so they stay traceable to the work they belong to.

**Planning.** Non-trivial work gets a plan before it gets code — copy
`docs/plans/_TEMPLATE.md` to `docs/plans/<slug>.md` and fill it in. A plan is
3-5 **vertical** slices: each delivers something observable end-to-end, never a
horizontal layer (all the storage, then all the CLI), because horizontal work
leaves nothing testable until the end, when steering is most expensive. Each
slice declares the files it touches, its type and method signatures, and a line
estimate. Before writing any slices, list the decisions you had to guess at
rather than derive, and stop for the owner's ruling — then record the rulings in
the plan.

**The stop is conditional on there being something to stop for.** If every
decision was derived from `docs/DESIGN.md` rather than guessed, write "no
uncertainties — every decision derived from the design" in that section and keep
going. A gate that fires when it has nothing to report trains people to click
through it, which is how it stops working on the day it matters. The plan is
still reviewed by the owner before it merges, so a falsely empty list is visible
where it counts. The estimate is a **tripwire, not a target**: never compress code,
drop error handling, or thin tests to come in under it. An overrun does not fail
the build; CI reports the delta and the reviewer asks whether it was justified.

**A plan lands before the code it plans.** Commit it on its own `docs/` branch,
let it merge, and only then branch off the default branch to build it. This is
enforced, not advisory: the `plan` check fails a pull request whose plan does not
already exist at its base commit. A plan written alongside its implementation
specifies nothing — the estimates, the file list, and the slice boundaries all
end up as whatever the change turned out to need, and the reviewer is left
checking a diff against a document from that same diff. `CODEOWNERS` puts
`docs/plans/` behind the owner's review, so merging the plan is the ruling on it.

A genuinely trivial change — a typo, a doc tweak — may skip planning by using a
`chore/` or `docs/` branch prefix, which the `plan` check exempts. That escape
hatch exists so small fixes aren't ceremony; reaching for it to avoid planning
real work is a rule violation, and it is visible in the branch name precisely so
that it can't be done quietly. It is also **size-capped** — an exempt branch
adding more than ~50 lines fails the `plan` check — and the reviewer is told to
scrutinise exempt branches harder rather than to relax, because an unplanned
change is less checked than a planned one, not more trusted.

**Commits.** One conceptually contained commit per unit of work, pushed
when complete, with an imperative one-line message. The test suite must
pass before every commit. Documentation is updated in the same commit as
the code it describes — docs never lag the code.

**Tests.** New behaviour comes with tests in the same commit. The suite
runs offline and deterministically; a test that needs an unavailable
optional resource skips with a clear reason rather than failing.

**Who writes the tests.** A slice's code and its tests are written by
**different agents, in parallel, neither able to see the other's work**. The
test author works from the slice's declared behaviour and signatures — never
from the implementation, which is why it is written at the same time rather than
afterwards. An agent that writes both describes what its code happens to do,
bugs included, and calls that a test suite. The separation is structural, not a
promise to be careful: each agent works in its own worktree off the same base,
so the other's output is not there to read. The two meet at assembly, and tests
disagreeing with the code is the signal that something needs a human decision —
not a nuisance to smooth over by editing whichever side is easier.

This is checked, not just asked for. Tests written blind are committed with a
`Blind-Tests: <slug>-<n>` trailer, before the implementation is merged, and
`.github/scripts/blind-tests.sh` reports to the reviewer any of those test files
that a later commit in the same pull request modified. Editing a test after it
was written blind is allowed — it may have asserted something the slice never
promised — but it is visible, and the commit that does it must say why. Weakening
a test so the existing implementation passes is a blocking finding.

**Architecture doc.** At the end of every slice, update `docs/architecture.md`
so it describes what now exists and how it flows. Keep it at the level of
**logic, not code**: what the components are, what data moves between them, what
happens on the main paths. It is not overhead paid for someone else's benefit —
it is the file a future agent reads to get its bearings from the repository
alone, and a human reading the same file is what keeps it honest. A slice isn't
finished until it's accurate.

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

**Done.** "Everything merged" is a statement about the queue, not about the
product. A slice is done when its tests pass against it; a plan is done when it
has merged; the **project** is done when every `docs/DESIGN.md` §5 requirement
is covered by a merged plan *and* every §13 success criterion has recorded
evidence in `docs/acceptance.md`. Coverage is mechanical
(`.github/scripts/coverage.sh`); acceptance is not, which is exactly why it is
written down rather than inferred from the code. Never report the project as
done while criteria are pending on the owner — report it as pending on the
owner, and say precisely what they need to run or look at.

**Memory.** Chat is not storage. Anything a future session (or a different
agent) would need is written into the repository in the same unit of work:
decisions → `docs/DECISIONS.md`, work items and ideas → `docs/BACKLOG.md`,
the plan for a change being built → `docs/plans/<slug>.md`, what the system is
and how it flows → `docs/architecture.md`, anything that escaped to the owner →
`docs/escapes.md`, evidence that a success criterion holds →
`docs/acceptance.md`, session notes and hand-offs → `docs/JOURNAL.md` (one dated
entry per working session), a term the owner had to ask about →
`GLOSSARY.project.md` (create it on the first word; never edit `GLOSSARY.md`,
which the template owns), user-facing behaviour → `README.md`. `BACKLOG.md` is the standing queue of what
*might* be built; a plan covers the one change being built now.

**Honesty about verification.** Never claim something is verified in an
environment where you could not observe it. Record what was verified where;
"CI added" is not "CI verified" until a run has actually passed. When only
the owner can verify something, say exactly what to run and ask for the
output.

**Ambiguity.** Prefer stating what you need in chat and continuing on best
judgment over blocking; the owner reads chat. Stop and ask only when truly
blocked on something only the owner can provide.

**Talking to the owner.** Read `GLOSSARY.md` and `GLOSSARY.project.md` (the
second may not exist yet) before your first substantial reply. They carry the
owner's communication rules and two word lists: vocabulary being learned, which
you explain, and vocabulary already learned, which you must not re-explain. A
word in neither list counts as unknown — gloss it in passing and ask which list
it belongs in. Working commentary can be as technical as it likes; **final
summaries are high level**, and any detail worth keeping is explained only far
enough to land. This applies to conversation with the owner, not to commit
messages, pull request bodies, code comments, or the CI review agent, all of
which are written for a technical reader.

## Enforcement

Pre-commit hooks (`.pre-commit-config.yaml`) and CI
(`.github/workflows/ci.yml`) enforce formatting, linting, typing, and the
test suite on every commit and push, regardless of which tool or agent
wrote the code. A failing gate is fixed, never bypassed: no `--no-verify`,
no skipping or weakening checks to get green.

**The merge pipeline.** Merges are mechanical: a pull request merges when its
required checks go green. Four of them, three mechanical and one judgment:

- **CI** — format/lint/type/tests. The authoritative hard gate.
- **`plan`** — the PR resolves to exactly one plan under `docs/plans/`, matched
  by that plan's slug appearing in the branch name. Fails hard, because a plan
  the reviewer never receives is a gate that quietly stopped working. Branches
  prefixed `chore/` or `docs/` are exempt.
- **`test-the-tests`** — reverts this PR's implementation, keeps its new tests,
  and fails if the suite still passes.
- **review** (`.github/workflows/review.yml`) — an independent read-only LLM
  reviewing the diff against this file, `docs/DESIGN.md`, the plan, and the
  mechanical facts CI computed, with fresh context. A different model than the
  author is a nice-to-have, not required. It is an added check, never a
  replacement for CI.

No agent merges on its own judgment: opening the PR into this pipeline is where
an agent's job ends, and the merge is triggered by check status, not by any
agent — including a passing local review — deciding to merge.

**The ratchet.** Nothing that escapes to the owner gets fixed without also
producing a permanent check that would have caught it. "Why did this bug exist"
and "which gate should have caught this" are the same question, and the second
one is the one worth answering — a fix without a check buys one bug, a fix with
a check buys every future instance of it. This applies equally to bugs found in
use and to CI failures that only surfaced late.

Record each one in `docs/escapes.md`: what escaped, which gate should have caught
it, what check was added. One line, appended, never rewritten. The log exists
because the next check worth building is the one the log keeps pointing at — do
not add speculative checks in advance of it.

**Gate paths are off-limits.** Never modify the things that check the code:
CI workflows (`.github/workflows/`), the review check or its prompt
(`.github/review-prompt.md`, `.github/scripts/review.sh`), the pre-commit
config, or `CODEOWNERS`. These are human-owned and enforced by `CODEOWNERS`;
a change to any of them requires human review even under auto-merge. Do not
weaken, skip, or route around a gate to get green.

The same applies to the things that check the code's **intent** — this file,
`docs/DESIGN.md`, and everything under `docs/plans/` — plus the append-only
ledgers `docs/escapes.md` and `docs/acceptance.md`. They are what the review
gate measures a change against, so a change may not carry its own revision of
them: the review scripts read all of them at the pull request's base commit, and
`CODEOWNERS` requires the owner's review to change any of them. Revise them on
their own pull request, before the work they govern, never alongside it.

## Language-specific

Tool configuration in `pyproject.toml` is the source of truth for lint,
format, and typing rules — follow it, don't restate or override it. The
test suite's offline rule is enforced by the autouse fixture in
`tests/conftest.py`. Run the full gate locally with:

    uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
