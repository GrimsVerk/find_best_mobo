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
- **`scripts/run.sh`** — `index → fetch → select → estimate`, in order, stopping
  on first failure, and stopping at the cost projection because there is no code
  that continues.

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
  because `docs/DESIGN.md` R7 changed, not because these scripts route around
  it.


## Slice 2 — `run.sh` runs the whole pipeline, including extraction

Slice 1 said the run "stops at the cost projection because there is no code that
continues". That was a statement of fact, not a policy: no command could spend,
so the wrapper could not. Stage B's slices 1-3 built one, and the sentence became
false without anyone deciding it should.

The owner's own words for what `run.sh` is: **the thing to run when you want to
run the software.** A wrapper that omits a third of the pipeline is not that; it
is a list of the parts that existed when it was written.

**This slice depends on the R7 amendment landing first.** R7 required a human
between the projection and the first model call. It now requires the projection
on every run and puts the bound on R26's ceiling instead — read from the real
subscription meter before a batch, part-way through a long one, and after it.
Built before that lands, this slice contradicts the design at its own base
commit and the review gate should block it.

- **Delivers:** `./scripts/run.sh` runs `index → fetch → select → estimate →
  extract` in order, skipping what is already done at every step — cached
  transcripts are not refetched, and batches already in the claim store are not
  re-extracted. It ends when the corpus is extracted or when R26's ceiling stops
  it, and says which. `./scripts/run.sh extract --batch 1` still runs exactly one
  named batch.
- **Files:** `scripts/run.sh`, `src/find_best_mobo/commands/extract.py`, `tests/test_run_script.py`, `tests/test_extract_all_batches.py`, `docs/architecture.md`
- **Estimate:** ~260 lines

### Signatures

No new module. `commands/extract.py` keeps `parse_args` and `run`; `--batch`
becomes optional and `pending_batches` is added beside them.

```python
# find_best_mobo/commands/extract.py


def pending_batches(config: Config) -> tuple[int, ...]: ...
```

### Behaviour the signatures cannot carry

- **`--batch` becomes optional, and omitting it means every pending batch in
  order.** The loop belongs in Python, not in the shell: `run.sh` cannot read the
  claim store, and a wrapper that guessed batch numbers would drift from the
  store the moment either changed.
- **A batch already in the claim store is skipped, not refused.** Slice 1 of
  `stage-b-extraction` makes re-ingesting a stored batch an error, and that
  refusal stays exactly as it is for an explicit `--batch N`. What changes is
  that the no-argument form never asks: it extracts the batches that are
  pending, which is what makes a second `./scripts/run.sh` cheap rather than
  fatal. That distinction is the whole of R2's restartability applied to a stage
  that spends.
- **The ceiling stops the loop, not just the batch.** A run halted by R26 does
  not try the next batch. It reports which batches landed, which are still
  pending, and what the meter read, and exits non-zero.
- **`run.sh` forwards arguments after a stage name.** Today it treats every
  argument as a stage name, so `./scripts/run.sh extract --batch 1` would fail
  validation on `--batch`. Everything after the first non-stage token is
  forwarded to that stage.
- **The header stops promising what it cannot.** `run.sh` currently states that
  "Nothing in this script spends money." It will spend money. The replacement
  says what is actually true: the projection is printed before anything is spent,
  and R26's ceiling bounds what a run can cost.
- **Nothing about the guard, the retry policy or the store changes.** This slice
  adds a loop and an argument. Every protection Stage B built is untouched, which
  is the point of putting the loop where the store can be read.
