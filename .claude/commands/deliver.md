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

> **⚠ OPEN QUESTION — RAISE THIS WITH THE OWNER BEFORE A LONG UNATTENDED RUN.**
>
> This step says "wait" without saying *how*, and nobody has decided yet. Each
> feature costs minutes of CI plus an LLM review, and in batch mode that repeats
> per plan, so an unattended run is mostly waiting. The options have real
> tradeoffs and the owner wants to pick:
>
> - **idle** — end the turn and let the owner resume. Costs nothing, but the run
>   is not actually unattended.
> - **poll** — re-check every N seconds. Unattended, but spends budget on
>   information that usually has not changed, and that budget is shared with the
>   review gate you are waiting for.
> - **something else** — a scheduled wake-up, a webhook, or a stop-and-report at
>   each PR boundary.
>
> Until this is decided: **stop at the pull request and report**, rather than
> guessing. Say plainly that you are stopping because the waiting strategy is
> undecided, and offer the options above. Delete this block once the owner rules,
> and record the ruling in `docs/DECISIONS.md`.

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

For each criterion:

- If you can check it by running something, **run it** and record the command
  and its real output as evidence. Mark **Verified by: agent**.
- If it needs real hardware, real users, real data, or a judgement call, mark it
  **Verified by: owner**, status `pending`, and write exactly what the owner
  should run or look at. **Do not fill these in yourself and do not infer them
  from the code.** `AGENTS.md` is explicit: never claim something is verified in
  an environment where you could not observe it.
- If a criterion can't be checked as written, say so and propose a wording for
  §13 that can be. Don't quietly mark it passed.

Also confirm `docs/architecture.md` describes the system as it now stands — it
is what the owner reads instead of the code, and it is the first thing to go
stale across many merged features.

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
