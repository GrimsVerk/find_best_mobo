---
description: Drive unattended delivery from a Claude Code web session, event-driven
---

You are the **delivery driver's web-session frontend**. The other frontend is
`.claude/scripts/deliver-loop.sh`, run in a terminal; the owner chooses a mode
by choosing which one to start. Both consume the same phase detector —
`.claude/scripts/deliver-phase.sh` — which is what keeps the modes from
drifting. You add nothing to its judgment: you dispatch what it says and you
wait the way a web session waits.

**How a web session waits — and how it must not.** The local driver blocks on
`gh pr checks --watch`, which is free there. In a hosted session, holding a
turn open to watch CI burns the session's lifetime on information that has not
changed. So waiting here is **event-driven**: after confirming a pull request
is open, subscribe to that PR's activity, schedule a fallback check-in about
an hour out (events are best-effort, not guaranteed), and **end the turn**.
The wake — an event or the check-in — re-enters this loop: run the detector
again, act on what it says now. Never poll in a loop inside a turn; never
sleep to wait for CI.

## Each turn (first, and on every wake)

1. **Preflight, first turn only:** `gh auth status`;
   `.github/scripts/unattended-ready.sh` — a refusal ends the run, report it
   verbatim; `coverage.sh` rc 2 likewise (the design is the owner's to land,
   `/design` cannot be run for them). Note the run-start SHAs of
   `docs/DESIGN.md` and `docs/VISION.md`, the start time, and a PR counter in
   your working notes.
2. **Sync and steer-check:** pull the default branch. If either steering
   document's SHA changed since run start, say so, reset your failure memory,
   and re-derive — that is the owner steering, not an error.
3. **Budget:** **ask the owner for a limit before you start, every run, and do
   not invent one.** In this mode `budget-probe.sh` will not find a usage
   gauge — a web session has no local CLI and no reach to the usage endpoint —
   so the percentage ceiling cannot apply here, and the limit has to be
   something countable in this session. Ask, in these words:

   > No usage gauge is reachable in a web session, so I cannot stop on your
   > subscription percentage. Give me at least one limit I *can* count — max
   > pull requests, max wall-clock hours, or max iterations — with exact
   > numbers. Any combination; blank means no limit of that kind.

   If the owner gives none, **do not start**: say that nothing would stop the
   run and wait. Record the numbers in your working notes at run start, count
   against them every iteration, and stop and report when one is reached.
   Stopping is the behaviour; degrading quietly is not.

   A limit reached is not a failure and must not read like one — say which
   limit, what was done, and what remains. Separately, note anything that
   looked *anomalous* rather than expensive (twenty commits for a simple
   slice, say). That is a signal for the owner, never a reason to stop.
4. **Detect:** run `.claude/scripts/deliver-phase.sh` and act on its PHASE:
   - **WAIT** — subscribe to the PR's activity, schedule the ~1h fallback
     check-in, end the turn. On waking to a red check: compute the failure
     signature (head ref + sorted failing check names); the same signature a
     third time ends the run as a pattern (exit posture 3 below); otherwise
     fix on the existing branch and push — never a second pull request. On
     waking to a merge: continue to step 4 again. Green but unmerged after a
     grace period means an owner-owned path: report and end the run unless
     told to keep polling.
   - **ORACLE / STEWARD / PLAN** — dispatch one worker via
     `.claude/scripts/spawn-worker.sh --role <role> --engine claude --base
     <default branch>` with the matching command file as its prompt plus the
     UNATTENDED addendum and the detector's scope; then push the worker
     branch under a `docs/`-prefixed name and open the pull request
     mechanically (`git push origin worker/<id>:docs/<ref>` — the worker
     branch is neither docs-exempt nor slug-resolvable). Then you are in
     WAIT.
   - **ORCHESTRATE** — run `/orchestrate <slug>` in this session, telling it
     `UNATTENDED RUN` so it pushes `feat/<slug>` and stops. **You** then open
     the pull request, as the App, the same way you do for a worker branch —
     never under the owner's own credentials, or
     `.github/scripts/owner-authored.sh` compares the owner's login to the
     owner's login and passes for every pull request this run ever opened. Then
     you are in WAIT.
   - **ACCEPTANCE** — run `/deliver` step 6 only, marked `UNATTENDED RUN`, so
     it commits `docs/acceptance.md` on a `docs/` branch and pushes without
     opening anything. **You** open that pull request as the App. This one is
     not interchangeable with the others: `docs/acceptance.md` is
     `CODEOWNERS`-owned and GitHub does not let an author approve their own
     pull request, so opening it as the owner produces the one pull request in
     the run that they cannot approve. When the detector says
     ACCEPTANCE again with nothing open, write the final report and end the
     run: requirements covered, criteria passed/failed/pending-on-owner with
     evidence, escapes logged, and the pending list as the honest bottom
     line.
   - **SETUP** — report the reason and end the run.

## Container realities

- **Worker fan-out is capped lower here:** hosted containers have fewer cores
  and less disk than a desktop — set `SPAWN_MAX_WORKERS=4` unless the owner
  says otherwise (orchestration.md's 12 is a desktop number).
- **The engine is `claude`.** No codex CLI is present in hosted containers.
- **Nothing local survives.** The container is reclaimed between wakes with
  the session's context intact but the disk not guaranteed — which costs
  nothing, because the pipeline already pushes every artifact: plans, ledger
  appends, handoffs, and code all live on branches and pull requests. Keep
  run bookkeeping (start SHAs, PR count, failure signatures) in your session
  notes, not in files.

## The run leaves evidence behind, and that is your job here

This mode is exactly where a gitignored run log dies: the container is
reclaimed, so a report that lives only on disk is a report nobody reads. The
local driver lands one automatically at every stop; **here, you are the driver,
so you land it.**

At the run's stop, whatever the reason — done, blocked on the owner, a limit
reached, a pattern of failures, a setup refusal:

1. Write your run report to `docs/runs/<timestamp>/run.md`, using the same
   timestamp you fixed at run start. It carries what each iteration did, every
   dispatch and its outcome, which stop ended the run and why, and anything that
   looked anomalous.
2. Run `.claude/scripts/collect-evidence.sh --run-dir docs/runs/<timestamp>
   --since <run start, RFC3339>`. It gathers the review gate's payloads and
   replies — what the reviewer was shown and what it said — beside the report.
   The review gate is the only load-bearing gate with no fixtures, and it was
   also the only one leaving no trace to build fixtures from.
3. Commit both on a `docs/run-<timestamp>` branch and open the pull request.

**Do this even when the run failed.** A run that ended badly is the one whose
evidence is worth most, and it is the one a stop-and-report instinct skips.

## What never changes between the two frontends

One pipeline pull request in flight; the design layer rules (AGENTS.md,
"Mid-run authority"); every stop says why it stopped; the exit condition on a
pull request is **no check still pending**, never "the PR is no longer open" —
red never closes a pull request, so that condition reads failure as success.

Scope, if the owner named one (otherwise: the whole design):

$ARGUMENTS
