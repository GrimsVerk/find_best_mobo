# Postmortem — the first unattended run, 2026-08-18/19

Written 2026-08-19 from the run's own committed evidence: the run reports on
`docs/run-*` branches, the raw logs and retro on `docs/run-analysis-20260819`
(PR #87), the CI runs and review comments on GitHub, and the template sources
at v0.4.23. This document adds what the in-run analysis could not see —
two root causes confirmed after the fact — and records the fixes now sitting
upstream, plus the decisions that remain the owner's.

Audience: technical. The one-line version: **the driver had never been run end
to end by anyone, and the first run paid for that all at once. Every defect is
a template defect, all seven are now fixed upstream with demonstrated checks,
and the run still delivered its oracle pass and three plans.**

## Outcome

- Three driver invocations across the evening. The first died instantly (8
  failed dispatches in ~30 s), the second delivered the oracle ruling pass
  (PR #81, merged) and two plans (#82, #83, both merged after one review-fix
  session each), the third delivered one plan PR (#85, still open and red) and
  then stalled 90 minutes on a check that never reported.
- Budget spent: ~3 percentage points of the weekly limit of the 33 allowed.
  The oracle pass — the expensive part — is done and merged.
- Left behind: 4 open PRs (#85, #86, #87, #88), 6 leftover remote branches,
  and zero collected review artifacts.

## Timeline (UTC)

| When | What |
| --- | --- |
| 21:07–22:19 | Pre-run queue clearing: template v0.4.21 then v0.4.23 land (#69, #76); ESC-22 (flaky path assertion) and ESC-23 (dead auto-merge workflow) logged and fixed; #75's local gate fix correctly blocked by review — fixed upstream instead. |
| 22:26:21 | Run 1 starts. First oracle dispatch dies: `error: unknown option '---` (TB-1). Seven identical retries in 20 s. Aborted. |
| 22:40–22:51 | TB-1 worked around in-repo (#78, owner-approved `.claude/` change); template-bugs collection point created (#79); TB-2 recorded (#80). |
| 22:51:24 | Run 2 starts. Oracle succeeds → #81 merged 23:09. Steward OD-4 → #82 red on review (self-ruled HIGH uncertainties, TB-3), fix session repairs, merged 23:26. Steward OD-5 → #83, same failure, same repair, merged 23:48. Run-evidence PR #84 cannot merge (TB-2), closed. |
| 00:11:05 | Run 3 starts. Steward OD-6 fails twice (TB-4: ungranted gate scripts; a denied `git switch` cost a finished plan), succeeds third → #85. |
| 00:24–00:26 | #85: `review` goes red at 00:26:48 (TB-3, third of three). `test-the-tests` never reports. |
| 00:26–01:23 | Driver sits in its checks-watch: red verdict known, watch waiting for the check that never arrives (TB-6). Stopped by hand ~58 min in; evidence lands as #86, which cannot merge (TB-2). |
| 01:25 | Analysis pushed: #87 (run data, TB-1…TB-7, retro), #88 (TB-4 fix, blocked — `.claude/` is a gate path here, correctly). |

## The seven defects, with root causes

All seven live in **grimsverk-template**, not in this repository's own code.
TB numbers refer to `docs/template-bugs.md` (the TB-1…TB-7 version on PR #87);
ESC-37…ESC-43 are the template repository's ledger rows for the same defects.

1. **TB-1 / template ESC-37 — no worker could ever start.** Prompts are built
   by `cat`-ing a command file; every command file opens with `---` YAML
   frontmatter; `spawn-worker.sh` appended the prompt with no `--` terminator,
   so the CLI parsed it as a flag and refused before any model was reached.
   Both engine branches had the bug. This is the proof the driver had never
   run end to end anywhere: the first dispatch of the first role fails.
2. **TB-4 / ESC-38 — the steward's grants contradicted its prompt.** Its
   command files name three gate scripts to run; none were granted. And a
   denied `git switch` made a worker abandon a finished, uncommitted plan —
   intermittent, because only sessions that happened to reach for the command
   failed. Two OD-6 sessions were lost to this.
3. **TB-6 / ESC-39 — a check that never reports hangs the driver.** The watch
   exits when *no check is still pending*; on #85 `review` failed in 2 minutes
   while `test-the-tests` never reported at all (its check-run is still frozen
   mid-state on GitHub), so the driver held a decided PR for the full timeout.
4. **TB-3 / ESC-41 — every unattended plan self-ruled its uncertainties, and
   the compliant path was impossible.** Two layers, and the second was only
   established in this postmortem:
   - `steward.md` told the role "you cannot stop for a ruling … continue on
     your best reading", while `AGENTS.md` — the document the review gate
     judges against — says a HIGH uncertainty is filed as a `BL-<n>` and
     planning stops. The prompt manufactured the violation; the gate caught it
     three out of three times, at one fix session each.
   - The rule-following diff could not merge anyway: the moment
     `docs/BACKLOG.md` joins a plan's diff, the branch falls out of
     `plan-resolve.sh`'s size-cap carve-out and the whole plan fails the
     `plan` check. #82's fix session discovered this and said so, in
     `docs/runs/20260818T225124Z/run.md`.
5. **TB-2 / ESC-40 — the run's own evidence cannot merge.** `docs/runs/` was
   missing from the same carve-out, so any real run report fails the 50-line
   exempt cap. Hence #84 closed unmerged and #86 open-unmergeable.
6. **TB-5 / ESC-43 — zero review artifacts, and the cause is a default.**
   Confirmed here from the CI logs, which the in-run analysis left open: the
   gate writes its evidence to `.review-out/`, and `actions/upload-artifact@v4`
   **excludes hidden files by default** (since v4.4). The upload step logged
   `No files were found with the provided path: …/.review-out` and uploaded
   nothing, while the comment step right after it read the same directory
   happily — which is why the verdicts posted and nobody noticed. Five runs,
   five `MISSING.md` markers, zero artifacts (verified: the API reports
   `total_count: 0` artifacts on those runs).
7. **TB-7 / ESC-42 — worker logs die with the machine.** `.claude/
   orchestration-logs/` is gitignored and nothing copied it into the run's
   committed evidence. Every diagnosis above came from those files; on a
   reclaimed web container they would all have been lost. They survived only
   because the owner asked for everything to be pushed (PR #87).

**The systemic cause, once, plainly:** five of the seven could only be found
by running the driver, and nothing — in the template's CI, in its tests, in
any generated project — had ever dispatched one worker through one real
command file, landed one run report, or downloaded one review artifact. The
template's checks gate everything except the machinery that runs the checks.

## What worked, for the record

- The **review gate** caught three genuine process violations unattended,
  each correctly reasoned (self-ruled HIGH uncertainties on #82/#83/#85).
  It also correctly blocked two attempts to hand-edit gate paths in this
  repository (#75, #88) — the fix belongs upstream, and now is.
- `acceptance/S9.sh` caught a latent flaky test on its first CI run (ESC-22).
- The driver's refusals all fired correctly: dirty tree, wrong branch,
  leftover worktrees, unattended-readiness.
- The evidence design mostly held: run reports were written and committed at
  every stop, and `collect-evidence.sh`'s MISSING markers are exactly what
  made the artifact gap findable.

## Fixes shipped

All seven defects are fixed on the template branch
**`claude/find-best-mobo-postmortem-18nhu7`** (grimsverk-template), one commit
per defect group, each with a check that was observed **red against the old
code and green against the fix**:

| Template commit | Fixes | Check |
| --- | --- | --- |
| Record ESC-37…ESC-43 | ledger rows + verbatim mirror of this repo's `template-bugs.md` | — (records) |
| Plan: fix what the first unattended run found | `docs/plans/first-run-defects.md` | plan-lint |
| Spawn: terminator-protect the prompt… | TB-1a, TB-4 | test-spawn-worker (6 new, red→green) |
| Driver: strip frontmatter…, leave the watch on first failure | TB-1b, TB-6 (`--fail-fast`) | test-deliver-loop (2 new, red→green) |
| Gates: run evidence and BL filings can merge | TB-2, TB-3-mechanical (`docs/runs/`, `docs/BACKLOG.md` join the carve-out) | test-gates (3 new, red→green; smuggling negatives still capped) |
| Review gate: … include-hidden-files | TB-5 | test-lint-workflows sweep (1 new, red→green) |
| Evidence: collect the worker logs | TB-7 | test-collect-evidence (2 new, red→green) |
| Steward: derive what is delegated, file what is not | TB-3-prompt (`steward.md`, `plan.md`) | the review gate remains the check |

Full suite: 320 assertions green, shellcheck clean, all template-ci governance
checks (escape-refs, append-only, render, plan-lint, vision, acceptance) run
locally against the merge base and green.

**Nothing is changed in this repository's `.claude/` or `.github/`** — the
gate that blocks that is right, and these fixes arrive here as the next
`template/vX.Y.Z` sync once the branch merges upstream and a release is cut.

## Cleanup this repository still needs (owner actions)

1. **Merge the template branch upstream and cut a release**, then run
   `copier update` here on a `template/` branch. This supersedes #88
   (`chore/steward-tool-grants` — same diff, now upstream) — close it after
   the sync lands.
2. **PR #87** (run analysis) — merge. It is `docs/`-only evidence; note its
   `docs/template-bugs.md` will conflict trivially with `main`'s shorter copy
   (keep the branch's TB-1…TB-7 version).
3. **PR #86** (run evidence) — merges only after the template sync brings the
   `docs/runs/` carve-out. Leave open until then, or close and let the data
   live in #87's copy (it carries the same run's driver-state).
4. **PR #85** (OD-6 plan) — red for self-ruling a HIGH uncertainty (cross-cue
   splits). After the template sync, the compliant path exists: file the
   question as the next `BL-<n>` on the branch, land the ruling through the
   oracle, then re-cut the plan's Uncertainties section. Or close it and let
   the next unattended run's steward redo OD-6 under the fixed prompt.
5. **Stale branches** — `docs/run-20260818T222639Z` and
   `docs/run-20260818T225124Z` belong to closed PRs (#77, #84); delete after
   confirming #87 carries what you want kept. `docs/oracle-plan-od-6` and
   `chore/steward-tool-grants` follow their PRs' fate.

## The decision that is still open, and it is the owner's

**A generated project cannot unblock its own driver.** Both blocking defects
lived under `.claude/`; the review gate refuses any change there from this
repository (correct, and it fired correctly); the driver refuses a dirty tree
and a non-default branch, so it cannot even be hot-patched for one run. Every
route required the owner awake. The run-analysis retro laid out three options
(accept it / a narrow `driver-fix/` carve-out treated like a template sync /
driver fully immutable). **Recommendation: option 1 — accept it — now.** The
argument for a carve-out was "an unattended run that is one `git switch` grant
away from working stops until morning"; with the seven fixes and their tests
upstream, driver bugs of that class now have a check pinning them, and the
remaining gap is better closed by the retro's other recommendation: an
end-to-end dispatch smoke test in the template (one real role, one real
command file, asserting a commit lands — on-demand, since it costs
subscription budget). That test does not exist yet; it is the one item from
the retro deliberately not built in this pass, because its budget policy is an
owner call.

## What would have caught this earlier

The ratchet question, answered once for the whole incident: a single
end-to-end exercise of the driver — dispatch one worker from a real command
file, land one run report, download one review artifact — run before release,
would have caught TB-1, TB-2, TB-3, TB-4 and TB-5 before any generated
project existed. The per-defect checks now exist; the end-to-end exercise is
the open recommendation above.
