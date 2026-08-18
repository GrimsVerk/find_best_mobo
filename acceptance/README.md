# Acceptance criteria, as scripts

One script per success criterion in `docs/DESIGN.md` §13:

    acceptance/S1.sh
    acceptance/S2.sh

**Exit 0 is pass. Any other exit is fail. Standard output is the evidence.**
Nothing else is a contract. A criterion is checked by running its script, so a
criterion that cannot be written as a script is one nobody can check by running
anything — say so and fix the wording in §13, which is where the criterion
lives.

## Why these exist at all

`docs/acceptance.md` is the one artifact in an unattended run whose pull request
requires the owner's review — the single guaranteed connection between a run and
a human. Until these scripts existed, the evidence in that table was an agent's
narration: *"I ran X and it printed Y."* Everywhere else this project separates
computed facts from judged verdicts. That table was the one place narration was
admitted as evidence, and it is the last thing the owner reads.

A script closes it. The command is in the repository, anyone can run it, and the
output it produces is the output the table cites.

## Which criteria get a script

Every criterion §13 does **not** mark `(owner)`. That mark is the owner's and it
is durable: `docs/DESIGN.md` is `CODEOWNERS`-owned, so the split between "an
agent verifies this by running something" and "only the owner can judge this"
is decided in the design and not at the end of a run by the party that saves
work by deciding it.

An `(owner)` criterion gets no script. Writing one for it would be an agent
deciding it could verify something the design says it cannot.

## When they run

`.github/scripts/acceptance-criteria.sh` runs them on **every pull request**, as
a required check — not once at the acceptance pass.

That is the whole point. A criterion verified once and trusted thereafter is
exactly the "verified once, trusted forever" shape this project distrusts
everywhere else: one that passed at acceptance and regressed three merges later
is caught by nothing until the next acceptance pass, which may be the last one.

## What the check does with a failure

A failing criterion is not a stop. It is information the delivery loop acts on:
the acceptance pass files it as a `BL-<n>` in `docs/BACKLOG.md` and the oracle
rules on it (see `.claude/commands/oracle.md`). The oracle may rule the test
wrong, the implementation wrong, or the criterion met by other means — and in
that last case it records a **waiver** in `docs/DESIGN.oracle.md`, which is what
lets the pipeline keep moving while the row in `docs/acceptance.md` stays
`pending / owner`.

**The oracle may not mark a criterion passed.** The owner's own definition of
done is adjudicated by the owner.

## Writing one

- Keep it deterministic and offline, like the rest of the suite. A criterion
  that needs the network is a criterion whose result depends on the network.
- Print what you measured, not just a verdict — the stdout **is** the evidence
  cell in `docs/acceptance.md`.
- Fail loudly. `set -euo pipefail`, and say which number missed which bound.
- No fixtures, no mocks of the thing under test. This script asks whether the
  built system satisfies the criterion, so it exercises the built system.

A worked shape:

```sh
#!/usr/bin/env bash
# S3 — cold start completes in under 2 seconds on the target device.
set -euo pipefail
elapsed="$( ... )"
echo "cold start: ${elapsed}s (bound: 2.0s)"
awk -v e="$elapsed" 'BEGIN { exit !(e < 2.0) }'
```
