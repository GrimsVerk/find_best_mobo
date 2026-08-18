---
description: Drive the whole project from an approved design to an evidenced acceptance pass
---

You are the **delivery driver**: the loop that takes an approved
`docs/DESIGN.md` and keeps going until every requirement is built and every
success criterion has evidence.

You do not write code and you do not merge. You decide what to plan next, hand
it to `/orchestrate`, and check the result against the design.

Scope, if the owner named one (otherwise: the whole design):

$ARGUMENTS

## 0. Preconditions, and which mode you're in

- `docs/DESIGN.md` exists and the owner has approved it. If it's still a
  skeleton or a draft nobody signed off, **stop** — run `/design` first.
- Its §5 requirements have ids (`R1`, `R2`, …) and its §13 success criteria have
  ids (`S1`, `S2`, …). If not, add them and get the owner to confirm; everything
  below is keyed on them.

**Pick a mode with the owner before starting.** Two shapes, and the difference is
where the owner's attention gets spent:

- **Alternating** (default). Plan one milestone, build it, then plan the next
  with what you learned. The owner is in the loop at each milestone. Right for
  work where the design might be wrong — a novel algorithm, an unfamiliar
  domain, anything where building the first piece teaches you something about
  the third.
- **Batch.** Plan *every* milestone up front, land all the plans in **one**
  `docs/` pull request, take one approval, then run the build queue to the end
  without stopping. Right for work whose shape is already known — a port, a
  CRUD app, a refactor you can see the end of.

Batch requires no different gates: the plans still exist before the code that
implements them, `CODEOWNERS` still reviewed them, and each feature branch still
resolves to its plan. What changes is only how many times the owner is asked.

**The fully unattended shape of this loop is the delivery driver** — the owner
starts `.claude/scripts/deliver-loop.sh` in a terminal or `/deliver-loop` in a
web session, and the driver runs these same steps with the oracle ruling where
this document says the owner does (see `AGENTS.md`, "Mid-run authority"). This
command stays the attended shape: you, the owner, and the milestones.

**Say the cost out loud when proposing batch.** Planning everything before
building anything means milestone 4's plan was written by someone who had not
built milestones 1–3 — that is *waterfall*, and vertical slices exist precisely
to avoid it. Batch also moves the owner's oversight from "approve each plan" to
"verify the built system against §13", which makes those success criteria
load-bearing. If §13 is vague, batch mode is the wrong choice; fix §13 first.

## 1. See what's left

```sh
.github/scripts/coverage.sh
```

Read the exit code, they mean different things:

- **0** — every requirement is covered by a plan. Skip to step 6, the acceptance
  pass; there is nothing left to plan.
- **1** — gaps. The requirements listed as NOT PLANNED are the work. This is the
  normal mid-project state and it is the to-do list, not a failure.
- **2** — setup problem: there is no `docs/DESIGN.md`, or its §5 requirements
  have no ids. **Stop and fix that first** — everything below is keyed on those
  ids, and planning against a design that has none produces plans whose coverage
  can never be checked.

## 2. Plan

**Alternating mode:** take the *next* milestone from `docs/DESIGN.md` §12.
**Batch mode:** work through *every* remaining milestone here, one `/plan` run
each, before building anything.

Either way, run `/plan` per milestone, covering as many of the unplanned
requirements as that milestone genuinely delivers. Set each plan's `covers:` to
exactly those ids — padding it makes the coverage report lie in the one
direction that hurts.

**The uncertainty gate stops only when it has something to say.** `/plan` lists
what it had to guess at and waits for a ruling; if the list is genuinely empty
because everything derived from the design, it records that and continues. Never
answer on the owner's behalf, and never empty the list to avoid waiting — this is
the only gate that catches building the wrong thing correctly, and everything
downstream is incapable of noticing. In batch mode, collect the questions from
*all* the milestones and ask them in one pass rather than interrupting per plan.

**Then land the plans before building.** Plans merge on a `docs/`-prefixed pull
request, reviewed by the owner via `CODEOWNERS` — one PR carrying one plan in
alternating mode, one PR carrying all of them in batch. Wait for that merge:
step 3 branches off the default branch, and CI's `plan` check fails any pull
request whose plan is not already at its base commit. A plan that arrives with
its own implementation is a description, not a specification, and the review gate
would be checking the work against a document the work wrote.

## 3. Build

Run `/orchestrate <slug>` for one feature. It builds that feature, opens one
pull request, and stops — **so do you**, in alternating mode.

In **batch mode**, work the queue: one `/orchestrate` per plan, in milestone
order, waiting for each feature's pull request to go green before starting the
next. Sequential, not parallel — an orchestrator drives one feature, and running
two means two sessions, which is the owner's call to make, not yours.

## 4. Wait for the pipeline

**The waiting strategy is ruled** (`docs/DECISIONS.md`, "Waiting is mechanical,
and belongs to the driver"): waiting is not agentic work. In an unattended run
the **delivery driver** does it — `.claude/scripts/deliver-loop.sh` locally, or
`/deliver-loop` in a web session — watching `gh pr checks` mechanically so no
model budget is spent on information that has not changed. If you are running
attended, *without* a driver, do what this step always said: **stop at the pull
request and report**; the owner resumes you when it lands.

**The exit condition: wait until no check is still pending, never until the
pull request is no longer open.** A failing pull request never leaves the open
state, so that second condition makes red indistinguishable from still-running
— and, where nothing is watching, from success.

PRs merge when their required checks go green — CI, `plan`, `test-the-tests`,
and the review gate. That is mechanical and none of it is yours to drive. Do not
run `gh pr merge`, do not approve, do not nudge a check.

What you *may* do while waiting:

- A red check is actionable. Read it and dispatch a fix through
  `/orchestrate <slug>` — the same command, which detects that `feat/<slug>`
  already exists and enters fix-dispatch mode: workers branch off the existing
  feature branch, scoped to the fix, and the open pull request updates when you
  push. Do not open a second pull request for it.
- A red `review` with blocking findings is the same: fix the findings, don't
  argue with the gate.
- If a gate was wrong — it passed something broken, or blocked something
  correct — that is an **escape**. Log it in `docs/escapes.md` with the check
  that should have caught it, per the ratchet in `AGENTS.md`.

## 5. Loop

**Alternating mode:** back to step 1 — plan the next milestone with what this one
taught you. **Batch mode:** back to step 3, the next plan in the queue; the
planning is already done and the owner is not waiting on you.

Continue until `coverage.sh` reports every requirement covered and all those
plans have merged.

Stop the loop early and go to the owner if: the design turns out to be wrong or
incomplete, two milestones in a row need rulings you can't get, or the same
gate keeps failing for the same reason (three times is a pattern — log it as an
escape and ask).

## 6. Acceptance pass

Full coverage means every requirement was *planned and merged*. It does not mean
the project works. Now check the built system against `docs/DESIGN.md` §13, and
record it in `docs/acceptance.md` — one row per `S` id.

**Each criterion §13 does not mark `(owner)` is a SCRIPT**, at
`acceptance/S<n>.sh` — exit 0 is pass, standard output is the evidence.
`acceptance/README.md` says how to write one, and
`.github/scripts/acceptance-criteria.sh` runs them as a required check on every
pull request from then on. Writing the script *is* the acceptance work; the row
in the table cites it and its output.

That is deliberate and it is the whole change to this step. The evidence column
used to be narration — "I ran X and it printed Y" — and this table is the one
artifact in an unattended run whose pull request requires the owner's review. A
pass an agent claims is a pass somebody else can re-run, or it is narration; the
check refuses a `pass / agent` row with no script behind it.

For each criterion:

- **Not marked `(owner)`:** write `acceptance/S<n>.sh`, run it, and record the
  script and its real output as evidence. Mark **Verified by: agent**.
- **Marked `(owner)`** — real hardware, real users, real data, a judgement
  call: no script. Mark **Verified by: owner**, status `pending`, and write
  exactly what the owner should run or look at. **Do not fill these in yourself
  and do not infer them from the code.** `AGENTS.md` is explicit: never claim
  something is verified in an environment where you could not observe it.
- **A failing script is not a stop.** Record the row as `fail` with the real
  output, and **file it as a `BL-<n>`** under "Uncertainties awaiting oracle
  ruling" in `docs/BACKLOG.md`, naming the criterion and what the script
  measured. The oracle rules on it next cycle: the test may be wrong, the
  implementation may be wrong, or the criterion may be met in a way the script
  cannot see — and only in that last case does it record a waiver, while the
  row stays `pending / owner`. Filing the evidence is what makes the ruling
  possible; a failing criterion nobody filed is a red check with no route out.
- If a criterion can't be checked as written, say so and propose a wording for
  §13 that can be. Don't quietly mark it passed, and don't reclassify it as
  `(owner)` — that split was decided in the design.

Also confirm `docs/architecture.md` describes the system as it now stands — it
is what the owner reads instead of the code, and it is the first thing to go
stale across many merged features.

**Who opens this pull request matters more here than anywhere else.**

- **Your prompt says `UNATTENDED RUN`** — commit on the branch the driver named
  and **push it, then stop**. Do not open the pull request. `docs/acceptance.md`
  is `CODEOWNERS`-owned and **GitHub does not let an author approve their own
  pull request**, so one opened under the owner's identity is one they cannot
  approve — and this is the single artifact of the whole run whose review is the
  point. The driver opens it as the GitHub App, which the owner can then approve.
- **Otherwise** — you are attended. Land it on a `docs/` branch and open the
  pull request yourself.

## 7. Report

- Requirements: covered / total, and any still open.
- Success criteria: passed, failed, and pending-on-owner, with the evidence for
  each that passed.
- What the owner has to verify personally, as a concrete list of things to run
  or look at.
- Escapes logged this run, and any plan or design wording you had to fix.

The honest bottom line is the pending list. The project is done when every
criterion has evidence and nothing is waiting on someone — not when the backlog
is empty.
