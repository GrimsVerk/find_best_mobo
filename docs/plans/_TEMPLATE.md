---
slug: <kebab-case-id>      # MUST appear in every branch name working this plan
status: draft              # draft | in-flight | merged  (see below)
created: <YYYY-MM-DD>
design: <the docs/DESIGN.md milestone this implements>
covers: [R1, R2]           # the DESIGN.md §5 requirement ids this plan delivers
---

# <Feature name> — Plan

<!-- Copy this file to `docs/plans/<slug>.md` and fill it in. Guidance comments
(like this) explain what each part is for; delete them or leave them, they don't
render. The filename, the `slug` field, and the branch name must agree — CI finds
this plan by looking for a plan whose slug appears in the PR's branch name, and
without a match the reviewer runs with no estimates to check the diff against.

`covers:` lists the `docs/DESIGN.md` §5 requirement ids this plan delivers. It is
what `.github/scripts/coverage.sh` reads to answer "is every requirement actually
planned?" — a requirement no plan covers is work nobody has scheduled, and
without this field that gap is invisible until the end. List only what this plan
genuinely delivers; padding it hides the same gap more convincingly. -->

<!-- `status: merged` means THE WORK LANDED, not that this document merged. The
delivery driver reads it: `.claude/scripts/deliver-phase.sh` otherwise calls a
plan built only when a branch named `feat/<slug>` has merged, so a plan whose
work shipped some other way — a retrospective record, or work that landed on a
differently-named branch — would be asked for forever. Set it when the work is
done, not when the plan is approved. -->

## Uncertainties

<!-- Filled in BEFORE the slices, and left here afterwards as the record of
every decision taken without a design basis — who ruled, or what default was
proceeded on. This is the only gate that catches a correct implementation of
the wrong thing: no downstream review can recover from a misunderstood goal,
and a wrong guess is cheap to fix here and expensive to fix once code exists.

Classify each question first — HIGH if the candidate answers change slice
boundaries, a Signatures block, an external format or schema, or anything
expensive to reverse (unsure means HIGH); LOW otherwise. Who rules depends on
who is awake:

  - attended: the owner rules on everything before slices are written;
  - unattended: HIGH stops for an oracle ruling (filed as a BL-<n> in
    docs/BACKLOG.md, ruled as an OD-<n> in docs/DESIGN.oracle.md — record
    both ids here); LOW proceeds on the recorded default, reviewed by the
    oracle next cycle.

If there is genuinely nothing to ask — every decision followed from
docs/DESIGN.md — write "None: every decision derived from the design" and carry
straight on. A stop with nothing behind it teaches everyone to skip the stop.

One line per question, with the risk class, your proposed default, then the
ruling once given (or the default proceeded on, marked as such). -->

- **Q:** <the decision you're unsure about> — **risk:** <HIGH or LOW, and why>
  — **proposed:** <your default>
  **Ruling:** <what the owner or oracle decided, with the OD-<n> id if the
  oracle ruled — or "proceeded on the default (LOW)," left for review>

## The slices

<!-- This banner deliberately does NOT begin with the word "Slice" followed by a
space. `.github/scripts/plan-parse.sh` finds slices by that pattern, and a
banner reading `## Slices` matched it — parsing as a slice that declares no
files and no estimate, which failed the plan for every plan copied from here.
The parser is now stricter too; both halves of that fix are worth keeping.

The plan is a list of VERTICAL slices. Each one delivers something
observable end-to-end — a thing that works, however narrowly.

Do NOT slice horizontally (all the storage, then all the logic, then all the
CLI, then all the tests). Horizontal slicing leaves nothing testable until the
very end, which is exactly when it's most expensive to discover the design was
wrong. Vertical slices create checkpoints where re-steering is still cheap, and
they give someone who doesn't read code something observable at each stage.

Aim for 3-5 slices. Each becomes one unit of work. -->

## Slice 1 — <the behaviour this delivers>

- **Delivers:** <what a person can observe once this slice lands, end to end>
- **Files:** `<path>`, `<path>`
  <!-- Every file this slice creates or touches, tests included. Naming them
  forces the program design — where code lives, what depends on what — while it
  is still cheap to change. Two slices should not list the same file if they are
  to run in parallel.

  Under orchestration this list is split between two agents: paths under
  `tests/` or `Tests/` go to the test-writer, everything else to the coder. So
  list the test files too — a slice with no test path declared gives the test
  author nowhere to write. -->
- **Estimate:** ~<N> lines
  <!-- A TRIPWIRE, NOT A TARGET.

  You must not optimise toward this number. Do not compress code, drop error
  handling, skip edge cases, or thin out tests to come in under it. Coming in
  over it is not a failure and does not block the merge — CI reports the delta
  and the reviewer asks whether the overrun is justified. That is the whole
  purpose of the number.

  It earns its keep before CI ever reads it: a slice you estimate at ~1400 lines
  is the plan telling you this is really three slices. Re-slice instead. -->

### Signatures

<!-- Type definitions and method signatures only — NO implementation bodies.

This is the interface contract for the slice. Writing it here is what turns
"build the thing" into a program design decision made in a document, where it
costs a line edit to change, instead of in code, where it costs a refactor.

It is also load-bearing for how the slice gets built: the code and the tests are
written by two agents at the same time, neither able to see the other's work, and
this block is the only thing they share. Vague or missing signatures mean they
agree on the intent and disagree on every identifier. Be exact — names,
arguments, and types are the agreement. -->

<!-- Keep this block formatter-clean: `ruff format` formats Python code blocks
inside Markdown, so a snippet with the wrong blank-line spacing fails the
generated project's own `ruff format --check .` on its very first run. -->

```python
@dataclass
class Draft:
    id: DraftId
    body: str


def save_draft(draft: Draft) -> DraftId: ...
def load_draft(draft_id: DraftId) -> Draft | None: ...
```

## Slice 2 — <the behaviour this delivers>

- **Delivers:**
- **Files:**
- **Estimate:** ~<N> lines

### Signatures

<!-- as above -->

## Out of scope

<!-- What this plan deliberately does NOT do, so a reviewer can tell a gap from
an omission, and so scope creep is visible as a diff against this list. -->

-
