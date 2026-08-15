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

- **`scripts/install.sh`** — checks for `uv` and installs it **only if missing**,
  then `uv sync --locked`, then verifies the package imports. Idempotent; every
  step reports whether it acted or skipped.
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
  a `curl | sh` from a third-party host. Skipped entirely when `uv` is present,
  which on the owner's machine it already is.
- **No caching work is needed and none is done.** `fetch_all` already skips any
  video in `data/transcripts/` and reports "N already cached"; that is `R2`.
- **These scripts add no product behaviour and cover no requirement**, so
  `covers:` is empty and `coverage.sh` credits nothing. They are operator
  tooling.

Costs: one new directory of shell, and a `curl | sh` path the owner may not want.

Open questions for the owner: whether the `curl | sh` install path is acceptable,
and whether the BL-5 workaround should exist at all rather than the diagnostic
simply being unavailable until BL-5 is ruled on.

## Uncertainties

- **Q:** Should `install.sh` install `uv` itself, or only detect it and tell the
  owner what to run? — **proposed:** install it, since "two commands" is the
  stated goal and a script that stops to give instructions is not that.
  **Ruling:** _pending_
- **Q:** Should the BL-5 Python workaround ship, or should `aliases` be omitted
  until BL-5 is ruled on? — **proposed:** ship it, commented and naming BL-5,
  because the recall report is the one thing that tells the owner whether the
  alias table is any good before a full run.
  **Ruling:** _pending_

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
- **Anything that invokes a model.** The run stops at the projection because
  there is no code path past it (`R20`), and these scripts add none.
