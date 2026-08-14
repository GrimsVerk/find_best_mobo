# Acceptance — Finding Best Mobo by Buildzoid

Does the built system actually satisfy `docs/DESIGN.md` §13? One row per success
criterion id, filled in during the acceptance pass.

This exists because **"every plan merged" is not "the project works."** Merged
plans tell you each slice passed its own tests. They say nothing about whether
the pieces compose, or whether the thing you set out to build is what got built.
Coverage (`.github/scripts/coverage.sh`) answers the narrower question — is every
requirement *planned* — and even a full pass there only means the work was
scheduled, not that it works.

## How to fill this in

For each criterion, record what was actually observed, not what should follow
from the code. `AGENTS.md` applies in full here: never claim something is
verified in an environment where it could not be observed.

The **Verified by** column is the one that matters. Split it honestly:

- `agent` — checked by running something and reading real output. Cite the
  command and what it printed.
- `owner` — needs real hardware, real users, real data, or a judgement call. An
  agent **must not** fill these in. Write exactly what the owner should run or
  look at, then leave the status `pending` until they report back.

A criterion nobody can check as written is not a criterion. If you hit one, say
so and fix the wording in `DESIGN.md` §13 rather than quietly marking it passed.

| Criterion | Status | Verified by | Evidence |
| --- | --- | --- | --- |
| _S1_ | _pass / fail / pending_ | _agent / owner_ | _what was run, and what it printed_ |

<!-- Replace the row above with one per success criterion. Keep the id column
matching docs/DESIGN.md §13 exactly — that pairing is the whole point. -->

## Outstanding

<!-- Anything failing or pending, and what it needs. This is the honest answer
to "is it done?" — an empty section here, with every criterion passed and
attributed, is the only version of done worth the word. -->

-
