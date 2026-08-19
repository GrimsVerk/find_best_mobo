# First unattended run — what happened, and what to improve

2026-08-18 evening into 2026-08-19. Template v0.4.21 → v0.4.23. Written for
analysis, not as a gate artifact. Raw logs are in `logs/`.

## Outcome in one line

The driver ran for the first time ever, delivered the oracle's full ruling pass
and three plans, and exposed seven template defects — five of which had never
been reachable because **the driver had never been run end to end by anyone**.

## What landed

| PR | What |
|----|------|
| #78 | worker prompts may start with frontmatter (TB-1 fix) + owner's run ruling |
| #79 | `docs/template-bugs.md`, the upstream collection point |
| #80 | TB-2 recorded |
| #81 | oracle: `OD-1` … `OD-12`, clearing all 18 uncited evidence items |
| #82 | plan for OD-4 |
| #83 | plan for OD-5 |
| #85 | plan for OD-6 — open, red on review when the run was stopped |
| #86 | run evidence (cannot merge — TB-2) |

Budget: weekly 38% → 41%, Fable 25% → 27%. **About 3 points of the 33 allowed.**
The oracle pass was the expensive part and it is done.

## The seven defects

All detailed in `docs/template-bugs.md`. Ordered by how much they cost:

1. **TB-1** — no worker role could start; every prompt begins with `---`.
   The driver had never worked end to end in any generated project.
2. **TB-4** — the steward is told to run gate scripts it is not granted, and a
   denied `git switch` made it throw away a finished plan.
3. **TB-6** — a check that never reports hangs the driver for 90 minutes, even
   when a required check has already gone red.
4. **TB-3** — every oracle plan self-rules its uncertainties, is blocked, and
   costs an extra fix session. Three for three.
5. **TB-5** — no review artifact is ever collected; five of five `MISSING.md`.
6. **TB-7** — worker logs are gitignored, so per-session evidence dies.
7. **TB-2** — the driver's own run evidence exceeds the exempt-branch cap and
   can never merge.

**The pattern worth acting on:** five of the seven are things no gate could
catch, because the template's CI never dispatches a worker and never lands a run
report. The self-host argument — "the template is governed by the template" — has
a hole exactly where the driver lives. A single end-to-end test that dispatches
one real role through a real command file would have caught TB-1, TB-3 and TB-4
before release.

## How the assistant worked, and where that went wrong

Recorded because it cost the owner real time.

**Using CI as a test loop.** Repeatedly pushed, read the gate's verdict, pushed
again. That turned one piece of work into six pull requests and is exactly what
`ESC-19` already logs: run the gates against your own diff *before* opening
anything. The escape existed, was read, and was repeated anyway. Reciting a rule
is not a mechanism — which is `ESC-18`'s point, twice over.

**Stacking pull requests.** At one point six were open at once. The repo's own
`ESC-20` says land one before opening the next; the `strict` branch policy then
made every merge knock the rest out of sync, and the dead auto-merge workflow
meant nothing recovered on its own. Owner intervention was needed repeatedly.

**Arguing with a gate instead of listening to it.** The review gate blocked a
local fix to `.github/workflows/auto-merge.yml`. That block was correct: gate
machinery must arrive as a verified template sync, never as a hand edit in a
generated project. The right response was to close the pull request and fix
upstream — which is what eventually happened, after the owner said so.

**What worked.** Verifying locally before pushing (the v0.4.23 sync passed
byte-for-byte first time), reproducing a flake deterministically before fixing
it, and refusing to paper over a conflict.

## What the gates got right

Worth recording, because the failures are easier to notice than the saves:

- The review gate caught **three** genuine process violations unattended: a
  document revised in the same pull request as its own evidence, a fix landing
  without its ledger row, and a plan self-ruling HIGH-risk uncertainties.
- `acceptance/S9.sh` caught a **latent flaky test on its first CI run** — one
  that depended on pytest's temp-directory counter, invisible to any single run.
- The driver refuses a dirty tree, a non-default branch, and leftover worktrees.
  All three fired during this run and all three were right.

## The structural tension worth deciding on

Both blocking defects — TB-1 and TB-4 — live in `.claude/`. The review gate
refuses **any** change to `.claude/` or `.github/` from a generated project, on
the grounds that gate machinery must arrive as a verified template sync rather
than a hand edit. That rule is right, and it fired correctly three times tonight.

But it has a consequence nobody has ruled on: **a generated project that hits a
driver bug cannot unblock itself.** The fix is refused by the gate, and the
driver additionally refuses a dirty tree, a non-default branch, and leftover
worktrees — so it cannot even be hot-patched for one run. Every route requires
the owner, awake, at whatever hour the bug appears. An unattended run that is
one `git switch` grant away from working stops until morning.

Three ways out, and the choice is the owner's:

1. **Accept it.** Driver bugs are rare once the template is exercised, and the
   owner approving a `.claude/` fix is a reasonable price for gate integrity.
   This becomes much more defensible once an end-to-end dispatch test exists.
2. **Carve out a narrow exception** — a `driver-fix/` branch prefix the review
   gate treats like a template sync, on the argument that the driver is not a
   gate: it dispatches work, and every gate still runs on everything it produces.
   The risk is obvious and the prefix makes it visible, which is the same
   argument `chore/` already rests on.
3. **Ship the driver as something the project cannot edit at all** and make
   template updates the only route, accepting that a driver bug halts every
   project until a release goes out.

Tonight ran on (1) by default, and it cost the night twice.

## Next steps

1. Take TB-1 … TB-7 upstream. TB-1 and TB-4 block every unattended run.
2. Land `chore/steward-tool-grants` (TB-4 fix, pushed here, needs owner review
   because `.claude/` is a gate path).
3. Add an end-to-end dispatch test to the template — one real role, one real
   command file, asserting a commit lands.
4. Decide on TB-3: where the line sits between a plan's own reasoning and a
   genuine uncertainty. That is an owner ruling, not an agent's.
