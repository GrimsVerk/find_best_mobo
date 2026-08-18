# Template bugs found downstream

Defects in **grimsverk-template**, found while running this project, recorded
here so they can be collected and taken upstream after the run. A fix applied
here is drift: `copier update` owns these files and will replace them, so each
entry says what to change in the template, not just what was changed here.

Nothing reads this file. It is a collection point, not a gate.

## TB-1 — no worker role could ever start: the prompt begins with `---`

**Found:** 2026-08-19, first unattended run, at the first dispatch.
**Template version:** v0.4.23.
**Files:** `template/.claude/scripts/spawn-worker.sh`,
`template/.claude/scripts/deliver-loop.sh`, and every
`template/.claude/commands/*.md`.

`deliver-loop.sh` builds a worker prompt with `cat .claude/commands/<role>.md`,
and every one of those files opens with YAML frontmatter. The prompt therefore
begins with `---`. `spawn-worker.sh` appends it as the final argument with no
option terminator, so the CLI reads it as a flag and refuses:

    error: unknown option '---

The worker dies before the model is reached. The driver reports only
"oracle worker failed" and retries, so it spins: seven iterations in twenty
seconds, every one identical. **This means the unattended driver has never
worked end to end** — the first dispatch of the first role fails.

**Two independent defects, both worth fixing upstream:**

1. `spawn-worker.sh` must pass the prompt positionally — `CMD+=(-- "$PROMPT")`.
   Verified: `claude -p -- "…"` accepts a `---`-leading prompt.
2. `deliver-loop.sh` must strip frontmatter before using a command file as a
   prompt. It is loader metadata, and sending it tells the model to read its own
   catalogue entry as an instruction.

Fix 2 alone unblocks it; fix 1 alone also unblocks it. Do both — one removes the
noise, the other stops any future `---`-leading prompt breaking the same way.
The `codex` branch of `spawn-worker.sh` has the same missing terminator and was
not exercised here.

**Why nothing caught it:** the template's own CI never dispatches a worker, and
the smoke test in `tests/smoke-worker.sh` passes its prompt inline rather than
through a command file, so the one input shape that breaks is the one never
tested. A test that builds a prompt from a real `commands/*.md` file would have
caught it on day one.

**Fixed here on:** `chore/worker-prompt-frontmatter` (PR #78).

## TB-2 — the driver's own run evidence cannot merge

**Found:** 2026-08-19, clearing the queue before the first real run.
**Template version:** v0.4.23.
**Files:** `template/.github/scripts/plan-resolve.sh`,
`template/.claude/scripts/deliver-loop.sh`.

`deliver-loop.sh` lands its run report at `docs/runs/<timestamp>/run.md` on a
`docs/`-prefixed branch, at every stop. `plan-resolve.sh` caps an exempt-prefix
branch at 50 added lines, and exempts only `docs/plans/`, `docs/DESIGN.md`,
`docs/VISION.md`, `docs/DESIGN.oracle.md`, `docs/oracle/`, `docs/acceptance.md`
and `docs/architecture.md`. `docs/runs/` is not among them.

So any run report longer than 50 added lines fails `plan` and cannot merge — and
a real run's report is always longer than that. The evidence the design calls
"committed, on its own pull request, at every stop" is the one thing that cannot
land.

Observed on the aborted first run: the report was 8 failed iterations and
already over the cap.

**Not a stall, and that matters.** The report lands from an `EXIT` trap, so it
only appears when the run stops. A run is not blocked by its own evidence
mid-flight; it finishes, and then leaves an unmergeable pull request behind.

**Fix upstream:** add `docs/runs/` to the exempt path list in
`plan-resolve.sh`, beside the other documents no plan can cover. A run report is
by construction not plannable work — it is a record of what happened.

**Why nothing caught it:** the gate is exercised against hand-written branches in
`tests/`, never against a branch the driver itself produced. No test lands a run
report and asks whether it could merge.

**Not fixed here.** `plan-resolve.sh` is a gate path: the review gate blocks any
change to `.github/` from a generated project, correctly. This one has to come
from the template.
