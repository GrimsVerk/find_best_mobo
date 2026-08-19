# What is in this directory

Everything the first unattended run produced, collected here because most of it
is gitignored by default (TB-7) and would otherwise exist only on one machine.
Pushed for analysis. Nothing reads it.

## `driver-state/`

- **`run.md`** — the driver's own cumulative report across all three launch
  attempts, with a timestamped line per iteration. **This is the single most
  useful file here**: every dispatch, every worker exit code, every phase
  decision, in order.
- `failure-signatures`, `processed-evidence` — both empty. The driver never got
  far enough to record a repeated failure signature or dismiss evidence.
- `budget-baseline.txt` — usage before and after: weekly 38% → 41%,
  Fable 25% → 27%. About 3 points of the 33 allowed.

## `worker-logs/`

Every dispatched session, copied out of `.claude/orchestration-logs/`, which
`.gitignore` excludes (TB-7). The ones that matter:

- `oracle-2026081822264*.log` … `…2706.log` — **eight identical failures in
  twenty seconds**, the frontmatter bug (TB-1). All eight are kept deliberately:
  the identical repetition is the evidence that the driver retries a permanent
  failure without recognising it as permanent.
- `oracle-20260818225129.log` — the successful oracle pass that produced
  `OD-1`…`OD-12`.
- `steward-od-4.log`, `steward-od-5.log` — plans that succeeded.
- `steward-od-6.log` — **the interesting one.** 33KB, and it ends with the agent
  explaining that it wrote the plan but could not commit it because
  `git switch`, `git branch` and the gate scripts were all refused (TB-4).
- `corpus-and-checkpoint-*.log`, `dft-*.log`, `cac-1-zerodur-tests.log` — earlier
  attended sessions, kept because they are the only surviving record of them.

## `driver-logs/`

The three launch attempts, named for how each ended:

- `run1-aborted-frontmatter.log` — spun on TB-1, stopped by hand.
- `run2-refused-dirty-tree.log` — the driver refused to start with an
  uncommitted fix in the tree. Correct behaviour, and the reason a `.claude/`
  fix cannot be hot-patched: it also refuses a non-default branch.
- `run3-stalled-on-pending-check.log` — ran, delivered the OD-6 plan, then sat
  for 58 minutes because a required check never reported (TB-6).

## `handoff/`

- `auto-merge-upstream-report.md` — the report written for the agent who fixed
  the auto-merge workflow upstream. Kept as the worked example of the
  downstream-to-upstream handoff shape the owner asked for.
