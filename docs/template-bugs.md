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

## TB-3 — every oracle plan self-rules its uncertainties and is blocked

Observed three times in a row (PRs #82, #83, #85), template v0.4.23.

The steward writes a `## Uncertainties` section that DECIDES the questions
rather than filing them. The review gate blocks it — "four HIGH-risk
uncertainties were self-ruled instead of routed through the oracle" — and the
driver spends an extra fix session rewriting the section as derivations, which
then passes.

Cost: one extra session per plan. With a dozen decisions to plan that is a dozen
avoidable sessions of the owner's budget, every run.

The repair is not obviously wrong: a choice the design layer explicitly hands to
the plan IS the plan's to make, and the rewrites cite real requirement ids. The
defect is that `template/.claude/commands/plan.md` never draws that line, so the
role writes the section the gate rejects, by default, every time.

**Fix upstream:** state in `plan.md` what belongs in `## Uncertainties` (genuine
gaps in the design layer, filed as `BL-<n>`) versus what belongs in the plan's
own reasoning (a choice the design delegated), with the HIGH-risk test spelled
out. The gate already knows the difference; the prompt does not say it.

**Watch for:** the rewrite becoming a habit of reclassifying real uncertainties
as derivations. That would erode the mid-run authority rule and nothing
downstream would notice.

## TB-4 — the steward is told to run gate scripts it is not allowed to run

Two failed sessions in a row planning OD-6 before the loop was stopped.

`spawn-worker.sh`'s `STEWARD_TOOLS` grants Read/Grep/Glob, writes to
`docs/plans/oracle/**` and `docs/BACKLOG.md`, and `GIT_TOOLS` — which is
`git add|commit|status|diff|log|show` and nothing else.

1. **No gate script is grantable.** `plan.md` tells this role to run
   `.github/scripts/oracle-decisions.sh`; the grant list has neither it nor
   `plan-parse.sh` nor `plan-lint.sh`. The instruction is unfollowable as
   shipped.
2. **`git switch` is denied, and that silently costs the commit.** The worker
   already starts on its own branch, so it does not need it — but the agent
   reached for `git switch -c`, was refused, and ABANDONED the commit. Its own
   words: *"The plan is written. I could not complete the last step… So the plan
   sits in the worktree, uncommitted."* A finished plan thrown away by a denied
   branch command.

Intermittent by nature: the OD-4 and OD-5 plans succeeded because those sessions
happened not to reach for `git switch`. Same role, same grants, different luck.

**Fix upstream:** add the three plan gate scripts to `STEWARD_TOOLS`, and
`git switch`/`git branch` to `GIT_TOOLS`. Neither widens what can reach the
default branch — the required checks are the real fence, as the file says.

**Why nothing caught it:** no test dispatches a role and asks whether the
commands its prompt names are in its grant list. A static test diffing "scripts
mentioned in `commands/*.md`" against "Bash grants for that role" would have.

**Fix branch here:** `chore/steward-tool-grants` (pushed, unmerged — `.claude/`
is a gate path and the review gate correctly refuses local edits).

## TB-5 — no review artifact is ever collected

Every review in the first run — five of five, all `conclusion: success` —
produced a `MISSING.md`:

    # No artifact for review run 32195782165
    The run happened; its artifact could not be downloaded (expired,
    never uploaded, or the job died before the upload step).

Five for five points at "never uploaded" rather than expiry. `docs/VISION.md`
states the intent directly: the review gate should keep what it was shown and
what it said, because it is the only load-bearing gate with no fixtures and the
only one leaving no trace to build fixtures from. It is keeping nothing.

`collect-evidence.sh` is blameless — it writes the placeholder so the gap is
visible rather than indistinguishable from a review that never ran.

**To confirm before filing upstream:** read `template/.github/workflows/review.yml`
for an upload step and compare the artifact name with the one
`collect-evidence.sh` looks for.

## TB-6 — a check that never reports hangs the driver for 90 minutes

Observed on PR #85. `review` went **red**, and the driver did not react for 58
minutes — because `test-the-tests` sat `pending` and never reported at all.

`wait_on_pr` watches until NO check is pending, then branches on the result. A
check that never reports is therefore indistinguishable from one still running,
and the wait runs to `WAIT_TIMEOUT` (5400s) before re-detecting. The information
needed to act — a required check already failed — was available the whole time.

The design note in `deliver-loop.sh` explains why the exit condition is "no check
still pending" rather than "the pull request is no longer open", and that
reasoning is sound. The gap is the third case: a check that never arrives.

**Fix upstream:** react to a red required check immediately, without waiting for
the remaining pending ones to settle. A failed check is terminal for that pull
request; nothing a still-pending check can report will change it.

## TB-7 — worker logs are gitignored, so the per-session evidence dies

`.gitignore` line 3 ignores `.claude/orchestration-logs/`. Those logs are the
only record of what each worker actually did — the frontmatter failure, the
abandoned commit, the refused permissions were all diagnosed from them, and all
of it would have been lost on a fresh machine or a reclaimed web container.

This is the same defect `docs/VISION.md` records as already fixed for the run
report ("The run log used to be gitignored, and in a web session it lived in a
container that is reclaimed, so the evidence that would tell the next run what
went wrong was destroyed by default"). The fix was applied to `docs/runs/` and
not to the worker logs feeding it.

`collect-evidence.sh` copies review artifacts into the run directory but not the
orchestration logs.

**Fix upstream:** copy each dispatched worker's log into
`docs/runs/<timestamp>/workers/` alongside the reviews, for the same reason.
