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
decision was derived from the design — `docs/DESIGN.md` and
`docs/DESIGN.oracle.md`, which are read together — rather than guessed, write
"no uncertainties — every decision derived from the design" in that section and
keep going. A gate that fires when it has nothing to report trains people to click
through it, which is how it stops working on the day it matters. The plan is
still reviewed by the owner before it merges, so a falsely empty list is visible
where it counts. The estimate is a **tripwire, not a target**: never compress code,
drop error handling, or thin tests to come in under it. An overrun does not fail
the build; CI reports the delta and the reviewer asks whether it was justified.

**`docs/VISION.md` must be finished before a plan lands, and not before that.**
The vision does not have to be written before the design — writing it after is
often the better order, because by then the owner knows what the thing is, where
a vision written first is a guess about their own priorities. What must not
happen is implementation starting while it is empty, and implementation starts
at the plan. This is checked, not asked for: a pull request that adds or edits a
plan fails while any `##` section of `docs/VISION.md` is still empty
(`.github/scripts/vision-complete.sh`). Design-doc pull requests pass freely,
which is what makes deferring the vision safe rather than merely tolerated. A
section the project does not want is DELETED rather than left blank — an absent
section reads as a decision, an empty one as an omission — and deleting the
whole file is how a project opts out of the oracle.

**A plan opens with a decision-complete summary.** One document, not two: a
short plan the owner approves and a long one an agent builds from will drift,
and then the approval covered something that was not built. So the plan starts
with a `## Summary` the owner can approve from alone.

- **Decision-complete** — every choice the owner could say no to appears there.
  Nothing they would refuse may live only in the body.
- **One screen**, ~40 lines, a hard ceiling. Not fitting is itself a signal that
  the plan is doing too much.
- **It carries** what is being built and the requirement or evidence it serves;
  each decision expensive to reverse; each thing deliberately *not* done; and
  anything that costs the owner something — a gate change, a new required check,
  money, a manual step.
- **It leaves out** file lists, signatures, test matrices, sequencing, and prose
  defending choices nobody would contest. Those belong in the body, which is
  written for the agent that builds it and may be as long as that needs.
- **It ends with the open questions** — an explicit "what I need you to rule on"
  list. Scattered through the body, those are the reason reading a plan end to
  end is the only safe way to approve one.
- **Promotion rule.** The body may elaborate a summary decision; it may never
  introduce one. If a detail turns out to be a decision, move it up.

**A plan lands before the code it plans.** Commit it on its own `docs/` branch,
let it merge, and only then branch off the default branch to build it. This is
enforced, not advisory: the `plan` check fails a pull request whose plan does not
already exist at its base commit. A plan written alongside its implementation
specifies nothing — the estimates, the file list, and the slice boundaries all
end up as whatever the change turned out to need, and the reviewer is left
checking a diff against a document from that same diff. `CODEOWNERS` puts
`docs/plans/` behind the owner's review, so merging the plan is the ruling on it.

**Template updates are the third kind of change.** Pulling template improvements
in with `copier update` is neither planned work nor a trivial chore: it was
specified and reviewed in the *template* repository, at the merge that produced
the version being pulled in, so no plan here could ever describe it. Put it on a
`template/` branch, which the `plan` check exempts and the **`test-the-tests`**
check ignores. What earns that exemption is `template-sync`, which replays
`copier update` from the base commit and fails unless the result is byte-for-byte
this pull request — a stronger guarantee than a plan, because it proves nothing
hand-written rode along. A `template/` branch may therefore carry the template's
output and **nothing else**; a hand change on top belongs in its own later pull
request, with a plan.

A genuinely trivial change — a typo, a doc tweak — may skip planning by using a
`chore/` or `docs/` branch prefix, which the `plan` check exempts. That escape
hatch exists so small fixes aren't ceremony; reaching for it to avoid planning
real work is a rule violation, and it is visible in the branch name precisely so
that it can't be done quietly. It is also **size-capped** — an exempt branch
adding more than ~50 lines fails the `plan` check — and the reviewer is told to
scrutinise exempt branches harder rather than to relax, because an unplanned
change is less checked than a planned one, not more trusted.

**The planning documents themselves are exempt from that cap**, and only they: a
branch whose entire diff sits inside `docs/plans/`, `docs/DESIGN.md`,
`docs/DESIGN.oracle.md` or `docs/oracle/` passes at any size. A completed design doc runs to hundreds of lines and the plan template
is over a hundred before anything is filled in, so the cap made the two
documents this process demands the two documents it could not accept — and no
plan can cover them anyway, since a plan branch cannot resolve to a plan that
does not exist yet. Writing a plan is not skipping planning; it is the planning,
and `CODEOWNERS` still puts it behind the owner's review. Touch one file outside
those paths and the cap is back: split the branch rather than widening the
exemption.

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

**The design is two documents.** `docs/DESIGN.md` is the owner's and is
`CODEOWNERS`-owned: changing it waits for them. `docs/DESIGN.oracle.md` is the
evidence-driven ledger an agent may append to unattended, and is deliberately
**not** owned — ownership there would stop overnight work, which is the point of
having it. Read them together; a requirement is a requirement whichever document
declares it, and `coverage.sh` unions both.

What keeps the second one safe is mechanical, not a promise
(`.github/scripts/oracle-decisions.sh`): every decision cites evidence that
already landed — an `ESC-<n>` or a `BL-<n>` — so a design change can only ever
*metabolise something logged*, never be invented; decisions are append-only and
superseded rather than revised; ids start at **R1000** because requirement ids
share one integer space; and each decision names the `docs/VISION.md` statement
it relied on, so the owner steers by editing that statement rather than by
arguing with each decision. `docs/VISION.md` is owned and **no agent edits it**.

Writing there is the **oracle's** job and nobody else's. If you are not the
oracle and you believe the design is wrong, that belongs in `docs/BACKLOG.md`
where every other objection goes.

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
has merged; the **project** is done when every requirement of the design — both
`docs/DESIGN.md` §5 and anything `docs/DESIGN.oracle.md` added — is covered by a
merged plan *and* every §13 success criterion has recorded
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
`GLOSSARY.project.md`, user-facing behaviour → `README.md`. `BACKLOG.md` is the standing queue of what
*might* be built; a plan covers the one change being built now.

**The project glossary is a staging buffer, not a record.**
`GLOSSARY.project.md` exists only because a session may not have the template
repository attached, so it is the one place a word can be added mid-project.
Create it on the first word; never edit `GLOSSARY.md`, which the template owns
and replaces wholesale on every update. Its words are periodically merged into
the template's glossary and this file is then **wiped back to empty** — they
return here, and reach every other project, on the next template update. There
are deliberately no lasting project-specific glossaries, so do not treat this
file as somewhere vocabulary lives permanently.

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

## Working with the owner

**The owner replies as they read, not after.** A response to an early paragraph
may be overtaken by a later one in the same message, and an instruction may be
retracted a sentence after it was given, once they reach the part that answers
it. Two consequences, and they are standing rules rather than courtesies:

- **Read the whole message before acting on any part of it.** The last word on a
  point wins. Starting work off the first paragraph is how you end up building
  something the fourth paragraph cancelled.
- **Say so when an instruction contradicts something already established.** The
  owner has explicitly asked to be called out rather than quietly obeyed. Being
  argued out of a position is a normal outcome here, in both directions — the
  point is that the disagreement happens before the work, not in a pull request
  body after it.

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
  reviewing the diff against this file, both design documents, the plan, and the
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

**A recorded check is demonstrated, or it is labelled as a proposal.** The "check
added" column takes either a check that has actually been run — **red against the
defect, green against the fix**, both observed — or a candidate written as
*unverified: <what it would be>*. Never a suggestion phrased as though it were
verified. The column is read as a record of what now protects this project, so an
untested idea in it carries exactly the same authority as a demonstrated check
and sends the next reader down a dead end. That has happened here: a proposed
check would have been red on the day it was added, because it parsed a file whose
placeholders the parser rejects by design, and it was caught by chance rather
than by anything in the process. If you cannot run the check, say so and say what
would have to be true to run it.

**Gate paths are off-limits.** Never modify the things that check the code:
CI workflows (`.github/workflows/`), the review check or its prompt
(`.github/review-prompt.md`, `.github/scripts/review.sh`), the pre-commit
config, or `CODEOWNERS`. These are human-owned and enforced by `CODEOWNERS`;
a change to any of them requires human review even under auto-merge. Do not
weaken, skip, or route around a gate to get green.

The same applies to the things that check the code's **intent** — this file,
`docs/DESIGN.md`, `docs/VISION.md`, and everything under `docs/plans/` — plus
the append-only ledgers `docs/escapes.md` and `docs/acceptance.md`. They are what the review
gate measures a change against, so a change may not carry its own revision of
them: the review scripts read all of them at the pull request's base commit, and
`CODEOWNERS` requires the owner's review to change any of them. Revise them on
their own pull request, before the work they govern, never alongside it.

**When one of these documents cites another, land them in this order: the ratchet
entry first, then the document that cites it, then the work.** The review gate
reads `docs/escapes.md` **at the pull request's base commit**, so a plan or a
rule claiming "logged in `docs/escapes.md`" while that entry sits unmerged in
another pull request is making a claim that is false at the only moment anything
checks it. The reviewer is right to block, and it will block again on the second
attempt for the same reason, because nothing about the ordering has changed.
Downstream this blocked the same pull request twice. Write the ledger entry, land
it, then reference it.

**Citations are by id, and they point backward only.** Every `docs/escapes.md`
entry carries an id — `ESC-<n>`, the next unused integer — and a gated document
cites an entry by that id alone, only once the entry exists on the default
branch. This is checked, not asked for: CI resolves every `ESC-` citation in
this file, both design documents, and `docs/plans/` against `docs/escapes.md` at the
pull request's base commit (`.github/scripts/escape-refs.sh`) and fails when one
dangles, so a claim about the ledger can never be false at the moment it is
checked. And the entry-first ordering is cheap to obey, because an entry may
land before its check exists — as a **stub**: id, date, the one-clause
description, the gate column, and a check column explicitly marked *unverified —
pending*. A stub is one line, blocks on nothing, and is exactly the
explicitly-marked proposal the ratchet rule above already allows; once the fix
and its check have merged, append the completing correction row — same id, the
demonstrated check, citing the merged work. Entries are records, never
authorization: no gate passes a change because of anything in the escapes log,
so neither a stub nor a completed row is worth forging.

**This ordering is the cost, and it is not going to be traded away.** It was put
to us that one pull request might reasonably carry an `docs/escapes.md` entry
together with the fix it describes, when the two share a root cause — the
argument being that an append-only incident log is not really "the standard the
change is judged against", and that one root cause fanning into four serialized
pull requests is a chain that can block on itself. **Rejected, deliberately, so
it is not relitigated.** Two reasons. The log is not merely a record: the review
gate reads it as evidence, and a change that appends its own exculpatory entry is
supplying the evidence it is judged by — the fact that appending is the only
permitted edit does not make the claim in the appended row true. And an agent
logging its own escape is exactly where a self-serving entry would come from, in
the direction hardest to notice, since a plausible line about what "should have
caught it" reads no differently from an accurate one. The serialization is real
and it is the price. Order the chain correctly and it does not deadlock — and
the stub lifecycle above is what keeps the price small: the entry that must land
first is one line and waits on nothing.

## Language-specific

Tool configuration in `pyproject.toml` is the source of truth for lint,
format, and typing rules — follow it, don't restate or override it. The
test suite's offline rule is enforced by the autouse fixture in
`tests/conftest.py`. Run the full gate locally with:

    uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
