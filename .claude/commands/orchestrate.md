---
description: Build one planned feature in parallel worker agents and open a pull request for it
---

You are the **orchestrator**. Drive the single-layer orchestration described in
`.claude/orchestration.md` (read it first if you have not).

**One feature per orchestrator.** You build the single feature named below,
start to finish. If more than one slug is given, take the first, build it, and
say plainly that the others need their own session — the owner runs a second
`/orchestrate` in a second window for those. Do not try to juggle two features
here: the reason is in `.claude/orchestration.md`, and it is about keeping your
own context clean for assembly, which is the step that degrades silently.

The feature to build — one plan slug:

$ARGUMENTS

Follow these steps.

## 0. If the oracle left a handoff

Look for the newest `docs/oracle/handoff-<date>-<n>.md`. If there is one you
have not acted on, deal with it before anything else — it names design decisions
that have landed in `docs/DESIGN.oracle.md` and have no plan yet, and building a
feature against a design those decisions have already corrected is wasted work.

**You spawn the stewards; the oracle does not.** That split is deliberate: an
agent that both rules on the design and hires the labour to act on its own
ruling is the one arrangement this repository consistently refuses, the same way
it keeps code apart from tests and reviewing apart from merging. It also makes
the handoff an artifact rather than a private prompt — something later readable,
which a prompt never is.

One steward per decision, in parallel, each given exactly one `OD-<n>`:

```sh
.claude/scripts/spawn-worker.sh --id steward-<od> --role steward \
  --engine claude --base main --prompt "<steward prompt>" &
```

The steward prompt is `.claude/commands/steward.md` plus the decision id. Read
which decisions the handoff says NOT to act on yet, and do not act on them.
Stewards branch off the **run's base branch** (the default branch, unless the
commissioning driver named another) — their plans depend on the landed ledger,
not on any feature's code.

Their plans land on their own pull requests, before any code, exactly like every
other plan. The steward's branch is `worker/steward-<od>`, which neither the
`docs/` carve-out nor slug resolution recognises — so push its head under a
`docs/`-prefixed name and open the pull request from that:

```sh
git push origin worker/steward-<od>:docs/oracle-plan-<slug>
gh pr create --head docs/oracle-plan-<slug> --fill   # attended only — see below
```

**Unattended, the push is all you do.** The `gh pr create` line above is for a
human running this command; under `UNATTENDED RUN` you have no grant for it and
the driver opens the pull request as the App. The driver also dispatches
stewards itself, so unattended you will rarely reach this at all.

A diff confined to planning documents is exempt from the plan gate's size cap at
any size, which these pull requests satisfy by construction. Only then does a feature branch off to build one. If the handoff
names a decision that makes an *existing* plan partly wrong, say so in your
report — reworking that plan is the owner's call, not yours.

If there is no handoff, or you have already acted on the newest one, continue.

## 1. Load the plan

The feature must already have a plan at `docs/plans/<slug>.md`, and that plan
must already be merged — CI's `plan` check fails any PR whose plan is not at its
base commit. If there is no plan, **stop and write it first** (`/plan`); if there
is one but it hasn't landed yet, stop and land it.

Read the plan. Its **slices are the subtasks** — do not invent a second
decomposition.

If the plan's slices are not scoped to disjoint files, fix the plan rather than
working around it here.

## 2. Check the budget before spawning

Two limits from `.claude/orchestration.md`, and they are not the same limit:

- **12 concurrent workers** — machine and subscription. Workers share the rate
  limit with the PR review gate, and that gate fails closed, so over-spawning
  can leave you unable to merge what you just built.
- **6 slices assembled in one session** — your context. Assembly reads every
  diff and reconciles every code/test pair, and it degrades quietly rather than
  failing.

A 3–5 slice plan sits inside both. If this plan has more than 6 slices, say so:
that is the plan telling you it is really two features, and the fix is to split
the plan, not to push through.

## 3. Create the branch, then spawn the workers

Get onto the feature's branch. Create it off the run's base branch the
first time; switch to it if it already exists, because **dispatching a fix into
an open pull request runs this same command** (`/deliver` step 4) and must not
fail on a branch that is already there:

```sh
git switch feat/<slug> 2>/dev/null || git switch -c feat/<slug> main
```

The base branch is `main` unless a commissioning driver's dispatch names
another — an unattended dispatch states its base branch and the exact
feature-branch name (a non-default base adds a `--<base>` suffix, e.g.
`feat/<slug>--run-web`). When it does, use BOTH exactly as given: the branch
name is how the driver and the plan check find the work, and the base is what
keeps two runs on two base branches out of each other's pull requests.

If the branch already existed you are in **fix-dispatch mode**: the feature's
pull request is open, its checks have said something, and you are adding commits
to it. Everything below is unchanged — workers still branch off `feat/<slug>`,
still get disjoint files, still commit — but scope the slices to the fix, do not
re-run slices that already landed, and do not open a second pull request. The
existing one updates itself when you push.

Then, for each slice, spawn **two workers in parallel**: one writing the code,
one writing the tests. They never see each other's work — both branch off
`feat/<slug>` at the same commit, so neither has the other's output in its
worktree. That blindness is the point: an agent writing both the code and its
tests writes tests that describe what its code happens to do, bugs included.

Split the slice's declared files between them: paths under `tests/` or `Tests/`
belong to the **test-writer**, everything else to the **coder**. They must not
write into each other's files.

### Write the shared contract block first

Before either prompt exists, write **one** block stating everything both agents
need to agree on for this slice: the signatures exactly as the plan declares
them, and every behaviour either side can observe — ordering, error cases, edge
cases, what round-trips and what does not. Then **quote that block verbatim into
both prompts**. Not paraphrased, not summarised per role: the same text, twice.

This is not tidiness. The two agents cannot see each other's work, so the only
thing keeping them in agreement is what they were both told. A rule that reaches
one prompt and not the other is a contract only one of them is building to, and
the disagreement surfaces at assembly as a test failure about a behaviour the
plan never stated — which reads exactly like a bug and is not one. That happened:
a coder's brief said records are sorted canonically, the test author's said only
that they round-trip, so the tests asserted input order and the suite failed at
assembly. The retry used a shared block and the disagreements vanished.

**And anything both sides can observe belongs in the plan, not in a prompt.** If
you find yourself adding a behaviour to the shared block that the plan does not
state, you have found a gap in the plan. Fix the plan and say so in your report.
A prompt is not a specification: nothing reads it afterwards, the reviewer never
sees it, and the next agent to touch this slice will not know the rule exists.

Each prompt is then the shared block, plus only what is genuinely role-specific:
which files that agent owns, and what it must not do.

**Coder prompt** — the shared contract block, the slice (`Slice N` of
`docs/plans/<slug>.md`), its
non-test files, its signatures, the acceptance bar (follows `AGENTS.md`,
`docs/architecture.md` updated), plus:

> You are a worker. Do only this assigned slice, in the files listed. Implement
> the signatures declared in the slice EXACTLY — another agent is writing tests
> against them right now, from the same declaration, and cannot see your code.
> Do not write tests; they are being written in parallel. You are NOT an
> orchestrator: do not spawn, invoke, or delegate to any further agents, and do
> not use any orchestration scripts. Never modify the merge gates — CI workflows
> (`.github/workflows/`), the review check or its prompt
> (`.github/review-prompt.md`, `.github/scripts/review.sh`), branch protection,
> `CODEOWNERS`, or the pre-commit config. Before you finish, update
> `docs/architecture.md` to describe what now exists — logic, not code. Then
> **commit your work on this branch** with an imperative one-line message, per
> `AGENTS.md`. Work left uncommitted does not exist: the orchestrator collects
> your branch by its commits and an empty branch is discarded. Then stop.

**Test-writer prompt** — the same shared contract block, quoted verbatim, then
the slice, its test files, and the role defined in
`.claude/agents/test-writer.md` (read it into the prompt, or delegate to that
subagent). Its tests are expected to **fail** in isolation, because the
implementation is not in its tree; that is correct and it must not write the
implementation to go green. Its prompt ends with:

> **Commit your tests on this branch** before you stop, with an imperative
> one-line message and this trailer as the last line of the message:
>
>     Blind-Tests: <slug>-<n>
>
> The trailer records that these tests were written without the implementation
> present. CI reads it (`.github/scripts/blind-tests.sh`) and reports any of
> these test files that a later commit modifies, so that a test quietly weakened
> to match the code is visible to the reviewer instead of invisible. Your tests
> failing right now is expected and is not a reason to delay committing.

Never hand a worker `spawn-worker.sh` or any orchestration tooling.

Spawn every worker **in parallel**, each via the primitive:

```sh
.claude/scripts/spawn-worker.sh --id <slug>-<n>       --role coder \
  --base feat/<slug> --prompt "<coder prompt>" &
.claude/scripts/spawn-worker.sh --id <slug>-<n>-tests --role test-writer \
  --base feat/<slug> --prompt "<test prompt>" &
```

`--role` carries the model and effort defaults for that kind of work, and the
tools it may reach — pass it rather than `--model`, so the defaults live in one
place. The test-writer's default is deliberately a tier ABOVE the coder's: blind
authorship assumes two peers, and a cheaper test side quietly turns the shared
contract into whatever the coder happened to think. The coder is a tier lower on
purpose too — with the tests written blind, a coder failure is recoverable and
therefore *diagnostic*: when it cannot pass tests written from the same
contract, suspect the contract before the coding.

Pairing **doubles the worker count** — a 5-slice feature is 10 processes, close
to the 12 cap. You may skip the pair and let the coder write its own tests for a
slice that delivers no real logic (pure scaffolding, config, a rename); say so
when you do. Never skip it for a slice with behaviour worth asserting on.

- `--id <slug>-<n>` becomes the branch `worker/<slug>-<n>`, keeping every branch
  traceable to its plan.
- `--base feat/<slug>` is **required**, not optional. It defaults to the current
  HEAD, which is whatever you happen to have checked out — pass it explicitly so
  a worker cannot branch off the wrong commit and carry unrelated code into
  this PR.

Run them with background `&` + `wait` (or `xargs -P`), not one at a time.
Defaults: engine `codex`, workspace-level sandbox. Keep the sandbox on — do NOT
pass `--bypass-sandbox` unless the task genuinely requires it and you have said
why. Collect each printed `WORKER_RESULT` line (id, branch, worktree, engine
exit code, and `commits=<n>`).

A spawn that exits **3** means the engine finished cleanly and committed
nothing; a spawn that exits **2** failed before the worktree existed, and if it
says *installed but not usable* the engine cannot authenticate — switch engines
or sign in, and do not re-dispatch until it can.

## 4. Review, then assemble

After the workers finish, for each one:

- **Check it actually committed.** `spawn-worker.sh` now does this for you — it
  exits 3 and prints `commits=0` when the engine returned cleanly having
  committed nothing — but read the branch yourself as well, because "committed
  something" is not "committed the slice":

  ```sh
  git -C <worktree> log --oneline feat/<slug>..HEAD   # empty => failure
  git -C <worktree> status --porcelain                # uncommitted leftovers
  ```

  A branch with no commits beyond its base is a **failed worker**, not a worker
  with nothing to say — most likely it edited files and stopped without
  committing, or was refused every write and could not be told so. Treat it as
  errored: re-dispatch it once (with the commit instruction made explicit) or
  discard it, and say so in your report. Never let an empty branch pass as a
  success.
- Read its branch diff (`git -C <worktree> diff feat/<slug>...`) and its log
  under `.claude/orchestration-logs/<id>.log`.
- Review the changes against `AGENTS.md` **and against the slice it was given** —
  did it build what the plan said, in the files the plan named? If a `reviewer`
  subagent exists, delegate to it; otherwise review directly. This is a local
  **pre-check to catch obvious junk before it costs a CI run — it is NOT merge
  authorization.** The authoritative review is the pipeline's soft gate, which
  runs independently on the PR.
- **Assemble** the branches that pass into `feat/<slug>` (merge the worker
  branches into it), taking each slice's coder and test-writer together. For the
  ones that failed or errored, either re-dispatch a corrected worker prompt
  (once) or discard the branch — don't assemble broken work.

  **Merge the test-writer's branch first, then the coder's**, for each slice:

  ```sh
  git merge --no-ff worker/<slug>-<n>-tests    # blind tests, with the trailer
  git merge --no-ff worker/<slug>-<n>          # then the implementation
  ```

  This ordering is load-bearing, not cosmetic. It puts the blind tests into the
  pull request's history *before* the code, so `.github/scripts/blind-tests.sh`
  can report any test file that a later commit modified. Merge them the other
  way round and every test looks like it was written after the implementation —
  the reviewer loses the one signal that distinguishes a test that was always
  correct from one that was quietly relaxed to match the code.

- **Reconcile the pair.** Once a slice's code and tests are both merged, run the
  suite. This is the first moment they meet, and a failure here is *information*,
  not a nuisance: the two agents disagreed about what the slice meant. Work out
  which side is wrong before touching either.
  - Tests assert behaviour the slice promised and the code doesn't deliver →
    **the code is wrong.** Fix the code.
  - Tests assert something the slice never promised → **the tests are wrong.**
    Fix the tests.
  - Both are defensible readings → **the plan was ambiguous.** Fix the plan, say
    so in your report, and note it as an escape in `docs/escapes.md` — an
    ambiguous slice is exactly the kind of gap the plan is supposed to close.

  Never resolve a disagreement by weakening the test to match the code. That
  converts a caught defect into a passing suite, which is the failure mode this
  whole split exists to prevent. This is no longer only a rule you follow: any
  test file you touch after its blind-authoring commit is reported to the
  reviewer by `.github/scripts/blind-tests.sh`, naming the commit that touched
  it. So when a test genuinely was wrong, fix it in a commit whose message says
  which slice promise it got wrong and why — the reviewer will be reading it.
- Check `docs/architecture.md` actually got updated and reads as one coherent
  description rather than several workers' fragments stitched together. Fix it
  yourself if not; it is the file the owner reads.

## 5. Open the PR, then stop

**Before opening it, review your own diff the way the gate will** (ESC-16:
three of four recent escapes were found by use, after merge, because nothing
looked before the pull request existed). If a review credential is reachable —
`CLAUDE_CODE_OAUTH_TOKEN` in the environment, or you can run the gate's script
locally — run `.github/scripts/review.sh` against your assembled diff and act
on blocking findings now, before a CI run is spent on them. If no credential
is reachable, do the written pre-flight instead: name each rule in `AGENTS.md`
the diff touches, state in one line how the diff complies, and stop on any
line you cannot write honestly — fix it rather than arguing with the gate
later. This pre-check is never authorization to merge; it exists to make the
gate's red runs rare, not to replace them.

**Who opens the pull request depends on who commissioned you, and this is not a
style choice.**

- **Your prompt says `UNATTENDED RUN`** — the delivery driver commissioned you.
  **Push `feat/<slug>` and stop there.** Do not open the pull request; you have
  no `gh pr create` grant, and the driver opens it as the GitHub App so it is
  not authored by the owner. That is what makes
  `.github/scripts/owner-authored.sh` a real boundary rather than a formality:
  a pull request opened under the owner's own credentials is one GitHub reports
  as theirs, whatever wrote it.
- **Otherwise** — a human is running you. Push `feat/<slug>` and open **one**
  pull request for it yourself. A human running a command and a pull request
  appearing under their name is an accurate record.

Either way: **do not merge it.**
The merge is the pipeline's, triggered by the required checks going green — CI,
`plan`, `test-the-tests`, and the review soft gate (and, where enabled, GitHub
auto-merge completes it mechanically). A passing local pre-check is never your
authorization to merge, and you never run `gh pr merge` on your own judgment.

**Opening the pull request is not the finish line — it starts a wait.** If you
wait, the condition to wait on is **"no check is still pending"**. Never "the
pull request is no longer open".

That second condition is the one to get right, because it looks correct and is
not: a *failing* pull request never leaves the open state. Waiting on it makes
red indistinguishable from still-running until the timeout, and where nothing is
watching at all, indistinguishable from success. Downstream, an orchestrator
reported its slice built and stopped watching; its checks went red and it sat
there until the owner noticed and said so.

```sh
gh pr checks <n> --watch    # returns when nothing is pending; non-zero if red
```

Report **which** checks failed, not merely that the wait ended. A red check is
actionable: fix it through this same command in fix-dispatch mode. How long to
wait — or whether to hand back to the owner instead of waiting — is `/deliver`
step 4's question; the exit condition is this one either way.

Clean up the worktrees you're done with:

```sh
git worktree remove --force .worktrees/<id>
git branch -D worker/<id>   # for discarded branches
```

## 6. Report

What each worker was asked to build, which branches you assembled, which you
discarded and why, and the PR link. Then: any slice whose code and tests
disagreed and how you resolved it, and any plan wording you had to fix. If other
slugs were passed and you deferred them, name them and say they need their own
session.
