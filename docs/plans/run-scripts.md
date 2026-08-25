---
slug: run-scripts
status: draft
created: 2026-08-15
design: none — operator tooling, not a DESIGN.md milestone
covers: []
---

# Two commands: install, and run — Plan

## Summary

Today the pipeline is five subcommands with an undocumented ordering. `README.md`
covers `uv sync` and `uv run pytest` and says nothing about running the thing.
The owner wants **two commands**: one that makes the machine ready, once, and one
that runs everything.

- **`scripts/install.sh`** — installs `uv` if it is missing and **checks it is up
  to date if it is present** (owner ruling, below), then `uv sync --locked`, then
  verifies the package imports. Idempotent; every step reports what it did.
- **`scripts/run.sh`** — `index → fetch → select → estimate → extract`, in
  order, stopping on first failure, and skipping at every step what is already
  done: cached transcripts are not refetched, and batches already in the claim
  store are not re-extracted.

**`run.sh` spends money, and slice 2 is where that starts.** Slice 1 shipped a
wrapper that provably could not, because no command could. Stage B built one.
The owner's decision, landed in `docs/DESIGN.md` R7 and §3's non-goals in the
same change as this slice: a run is always STARTED deliberately — by the owner,
or by an agent the owner told to start it — and how many batches it does is an
argument. `--batches 1` while the numbers are unfamiliar, `--batches all` once
they are not. R26's ceiling stops it earlier whatever the number was. Nothing
runs on a schedule and nothing starts itself.

Decisions the owner could refuse:

- **The pipeline is four stages, not five.** `aliases` reports the alias table's
  recall and produces nothing downstream; `select` loads the table itself. It is
  reachable as `./scripts/run.sh aliases` and is labelled a diagnostic.
- **`aliases` is invoked through Python, not the CLI**, because it requires
  `--check` and the dispatcher cannot pass per-subcommand flags. That is `BL-5`,
  unresolved. The workaround is commented in place and names BL-5, so it is
  visible rather than buried, and it reverts to a plain CLI call once BL-5 is
  ruled on. **A visible workaround for a known defect, not a fix for it.**
- **`install.sh` runs the official `astral.sh` installer** when `uv` is absent —
  a `curl | sh` from a third-party host. Not reached when `uv` is present, which
  on the owner's machine it already is — that case runs `uv self update` instead,
  and a failure there (a package-manager-owned `uv`, a rate-limited check) is
  reported and stepped over rather than failing an otherwise working machine.
- **No caching work is needed and none is done.** `fetch_all` already skips any
  video in `data/transcripts/` and reports "N already cached"; that is `R2`.
- **These scripts add no product behaviour and cover no requirement**, so
  `covers:` is empty and `coverage.sh` credits nothing. They are operator
  tooling.

Costs: one new directory of shell, and a `curl | sh` path the owner may not want.

Open questions for the owner: none remaining. Both were ruled on 2026-08-15 and
the rulings are recorded under **Uncertainties** below.

## Uncertainties

- **Q:** Should `install.sh` install `uv` itself, or only detect it and tell the
  owner what to run? — **proposed:** install it, since "two commands" is the
  stated goal and a script that stops to give instructions is not that.
  **Ruling:** 2026-08-15 — install it, **and check it is up to date when it is
  already present**: "see if uv is installed, if it is (and up to date), then
  proceed, if not, install uv". So the present-and-current case is not a bare
  skip; the script asks uv to update itself, which is both halves of the check in
  one call. A uv owned by a package manager cannot self-update, and that is
  reported and stepped over rather than failing a working machine.
- **Q:** Should the BL-5 Python workaround ship, or should `aliases` be omitted
  until BL-5 is ruled on? — **proposed:** ship it, commented and naming BL-5,
  because the recall report is the one thing that tells the owner whether the
  alias table is any good before a full run.
  **Ruling:** 2026-08-15 — ship it, on the owner's stated trust in the
  recommendation rather than on an independent judgement of the trade. Worth
  recording as such: the workaround stays visible and reverts to a plain CLI call
  when BL-5 is ruled on.

## The slices

One slice. This is operator tooling with no behaviour to test blind: there is no
contract between a coder and a test author, because there is no product surface
— the deliverable is that two commands work on the owner's machine, which is
observed by running them.

## Slice 1 — the pipeline runs from two commands

- **Delivers:** `./scripts/install.sh` makes a clean machine ready and is safe to
  re-run; `./scripts/run.sh` runs the whole pipeline in order and stops at the
  cost projection. `./scripts/run.sh --help` names the stages and their order.
- **Files:** `scripts/install.sh`, `scripts/run.sh`
- **Estimate:** ~165 lines

### Signatures

No Python surface. The interface is the two command lines and their exit codes:

    ./scripts/install.sh                  0 ready, 1 uv installed but not on PATH
    ./scripts/run.sh                      all four stages in order
    ./scripts/run.sh <stage> [stage ...]  only those, in the order given
    ./scripts/run.sh aliases              the recall diagnostic
    ./scripts/run.sh --help               0, usage
    ./scripts/run.sh <unknown>            2, names the unknown stage

Stage order is fixed and is the contract: `index → fetch → select → estimate`.

## Out of scope

- **No shell tests.** Nothing in this repository tests shell today, and adding a
  bash test harness to cover 165 lines of glue is a bigger change than the glue.
  The scripts are verified by running them; that is recorded in the pull request
  rather than automated.
- **Fixing BL-5.** The dispatcher's inability to pass per-subcommand flags is a
  plan question about `cli.py` and stays the owner's.
- **Any change to the pipeline itself.** No stage's behaviour moves; the scripts
  only sequence what already exists.
- **Anything that invokes a model.** True when slice 1 was written and false
  now: Stage B exists. Slice 2 below is where that changes, and it changes
  because `docs/DESIGN.md` changed in the same commit — not because these
  scripts route around it.


## Slice 2 — `run.sh` runs the whole pipeline, including extraction

Slice 1 said the run "stops at the cost projection because there is no code that
continues", and put anything invoking a model out of scope. Both were statements
of FACT, not policy: no command could spend, so the wrapper could not. Stage B's
slices 1-3 built one, and both sentences became false without anyone deciding
they should.

The owner's own words for what `run.sh` is: **the thing to run when you want to
run the software.** A wrapper that omits a third of the pipeline is not that; it
is a list of the parts that existed when it was written. This plan's Summary has
said so since slice 1 — "one that makes the machine ready, once, and one that
runs everything".

`docs/DESIGN.md` changes in the same commit as this slice, which is deliberate
and is the one place this plan departs from the usual ordering: a plan derives
from the landed design, and this slice's design basis did not exist until now.
The owner directed both to travel together and to merge them past the gate. The
design half is theirs; this half is not, and it implements exactly what the
design half now says.

- **Delivers:** `./scripts/run.sh` runs `index → fetch → select → estimate →
  extract` in order, skipping what is already done at every step — cached
  transcripts are not refetched, and batches already in the claim store are not
  re-extracted. Extraction does ONE batch by default and as many as
  `--batches N` or `--batches all` asks for, then stops, reports what it spent
  and what remains, and waits. R26's ceiling stops it earlier whatever the number
  was. `./scripts/run.sh extract --batch 1` still runs exactly one named batch.
- **Files:** `scripts/run.sh`, `src/find_best_mobo/commands/extract.py`, `tests/test_run_script.py`, `tests/test_extract_batches.py`, `docs/architecture.md`
- **Estimate:** ~300 lines

### Signatures

No new module. `commands/extract.py` keeps `parse_args` and `run`; `--batches`
is added beside the existing `--batch`, and two helpers with it.

```python
# find_best_mobo/commands/extract.py


def pending_batches(config: Config) -> tuple[int, ...]: ...
def batches_to_run(requested: str | None, config: Config) -> tuple[int, ...]: ...
```

### Behaviour the signatures cannot carry

- **`--batches N` and `--batches all` say HOW MANY, and one is the default.**
  One, because that is the state the owner starts in: the numbers are unfamiliar
  until the calibration batch reports. `all` is the state after. Defaulting to
  `all` would make the first run the largest one, which is the opposite of what
  the calibration batch exists for.
- **`--batch N` and `--batches N` are different arguments and both stay.**
  `--batch 3` names ONE batch and refuses if it is already stored; `--batches 3`
  says how many PENDING ones to work through. Naming a stored batch is a mistake
  worth reporting; skipping it while working through the pending ones is not.
  Giving both is an error rather than a precedence rule — a precedence rule is a
  thing readers guess at.
- **The loop belongs in Python, not in the shell.** `run.sh` cannot read the
  claim store, and a wrapper guessing batch numbers would drift from it the
  moment either changed. `pending_batches` reads `claimstore.batches_stored`
  against the batches `data/bundles/` actually holds.
- **The ceiling stops the loop, not just the batch.** A run halted by R26 does
  not try the next batch. It reports which batches landed, which are still
  pending, and what the meter read, and exits non-zero.
- **A run that completes its count exits 0 and says what remains.** Stopping
  because you asked for one batch is not a failure, and it must not read as one
  — the next run is a normal continuation, not a recovery.
- **`run.sh` forwards arguments after a stage name.** Today it treats every
  argument as a stage name, so `./scripts/run.sh extract --batches all` would
  fail validation on `--batches`. Everything after the first non-stage token is
  forwarded to that stage.
- **The header stops promising what it cannot.** `run.sh` currently states that
  "Nothing in this script spends money." It will spend money. The replacement
  says what is true: the projection is printed before anything is spent, a run
  does the number of batches it was given, and R26's ceiling bounds what it can
  cost.
- **Nothing about the guard, the retry policy or the store changes.** This slice
  adds a loop and an argument. Every protection Stage B built is untouched,
  which is the point of putting the loop where the store can be read.
