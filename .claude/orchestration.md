# Orchestration

A single layer of parallelism for Claude Code: the main session (the
**orchestrator**) drives **one feature** — its plan, its branch, its group of
**worker** agents, and its pull request. Workers run headless in isolated git
worktrees. The orchestrator assembles their branches and opens the PR. It does
**not** merge — see "Handoff to the merge pipeline".

This whole setup lives under `.claude/` — the deletable, Claude-Code-specific
layer. Removing `.claude/` removes orchestration and leaves a fully functional
project (docs, CI, and pre-commit are untouched).

- **Command:** `/orchestrate <feature slug>` (see `.claude/commands/orchestrate.md`).
- **Primitive:** `.claude/scripts/spawn-worker.sh` (one worker per call).

Two further roles exist for unattended runs: the **oracle** (`/oracle`), which
corrects `docs/DESIGN.oracle.md` from logged evidence and rules on filed
uncertainties, leaving a handoff; and the **steward** (`/steward`), which turns
one of its decisions into a plan. Their commissioner is the orchestrator in an
attended session, or the delivery driver (`deliver-loop.sh`) in an unattended
run — either way the oracle spawns nothing, see "Deciding and commissioning are
separate" below.

## The shape

```
orchestrator (this session)
└── feature: draft-saving      plan docs/plans/draft-saving.md → branch feat/draft-saving → PR
    ├── worker/draft-saving-1        slice 1, code
    ├── worker/draft-saving-1-tests  slice 1, tests (written blind, in parallel)
    ├── worker/draft-saving-2        slice 2, code
    └── worker/draft-saving-2-tests  slice 2, tests
```

Everything a worker needs comes from its slice in the plan. Everything the
reviewer needs comes from the plan the PR's branch resolves to. That is why
plans are per-feature and branch names carry the slug — it is the only link
between a PR and the document it is judged against.

## One feature per orchestrator

An orchestrator drives exactly one feature, start to finish. **To work on two
features at once, open a second session** and run `/orchestrate` there.

This is a deliberate reversal of an earlier design that let one session juggle
several features. Two sessions is strictly better: each keeps a clean context for
the part that actually degrades — assembly, where the orchestrator must read
every worker's diff and reconcile every code/test pair — and neither has to
police whether two features' file lists collide, because they cannot see each
other. The cost of that isolation is nil, since the features were required to be
disjoint anyway.

It does not violate the one-layer rule below. That rule stops an *agent* from
spawning an orchestrator, which is what makes a process tree unpredictable and
leaves nothing that knows what is running. You opening a second window is not
that: you know what is running, because you started both.

## Deciding and commissioning are separate

The oracle rules on the design. The orchestrator reads its handoff and decides
what to act on, and spawns the stewards. The oracle spawns nothing.

An agent that both ruled on the design and hired the labour to act on its own
ruling would be the one arrangement this repository consistently refuses — the
same separation as code from tests, and as reviewing from merging. It also makes
the handoff an artifact rather than a private prompt: a prompt is read once by
one agent and then gone, where a file under `docs/oracle/` is still there when
someone asks why a plan exists.

It costs nothing structurally. The orchestrator was already the single place
that knows what is running, and this keeps it that way. In an unattended run
the commissioner is the delivery driver — deterministic tooling rather than an
agent — which separates deciding from commissioning even further, not less.

## Mid-run authority: the design layer rules

Plans derive only from the design layer, and new work enters through one chain,
never sideways:

```
evidence (ESC-<n>, BL-<n>)  →  oracle amends docs/DESIGN.oracle.md   (own PR)
                            →  plan                                  (own PR)
                            →  code                                  (own PR)
```

Nothing an agent thinks of mid-run becomes work directly. It is logged as
evidence, the oracle decides what the design should say, a plan implements the
decision, and only then does code exist. Uncertainties travel the same road: a
plan that had to guess files the question as a `BL-<n>`, and the oracle rules
it — by risk class, see `AGENTS.md`'s Planning rule — so the answer is a
recorded decision quoting the vision (or explicitly declaring the vision
silent), never a private judgment inside one plan.

Each arrow is enforced, not promised: the oracle's ledger takes only
evidence-backed appends (`oracle-decisions.sh`), unattended plans must cite a
landed decision or cover landed requirements (same check), and code resolves to
a landed plan (the `plan` check). The owner steers the whole chain from the
top, by editing `docs/VISION.md` and `docs/DESIGN.md` — which stay owner-landed
— and reviews the built system at the end. Nothing mid-run waits on them.

## Roles: model, effort, and reach

`spawn-worker.sh --role <role>` carries the defaults for a kind of work. The
table and the reasoning behind each entry are in the script's header, which is
the source of truth; the shape is: **oracle** on Fable at high effort because
its output is permanent and unreviewed overnight, **steward**, **test-writer**
and **reviewer** on Opus at high, **coder** on Opus at *medium*, and **explore**
at low. The orchestrator is Opus at high and is not spawned by this script — it
is the session you are in.

Two of those are worth understanding rather than just obeying. The coder is
deliberately a tier below the test-writer: the tests are written blind and in
parallel, so a coder failure is recoverable by construction, which makes it
**diagnostic** — a model that cannot pass tests written from the same contract is
usually telling you the contract is wrong, and a stronger coder would paper over
that signal instead of raising it. And the test-writer is deliberately not
cheaper than the coder, because blind authorship assumes two peers; making one
side cheaper quietly turns the shared contract into whatever the other side
thought it said.

Role tool grants are the FIRST of two enforcements and not the binding one. A
grant constrains one agent in one worktree; the required checks constrain every
route to the default branch. Treat a narrow grant as a way to make the intended
path the easy one, never as the thing standing between an agent and a document.

## The unattended loop

The **delivery driver** is what runs the pipeline while nobody is awake. It is
a scheduler, not an agent: deterministic tooling the owner starts, holding no
model and making no judgment beyond branching on exit codes. That places it
exactly where "You opening a second window" sits above — the owner knows what
is running, because the owner started it — so the one-layer rule survives
untouched: the driver opens sessions, and only an orchestrator session spawns
workers.

Two frontends, one brain. The phase logic lives once, in
`.claude/scripts/deliver-phase.sh` (read-only: it recomputes the project's
state from the tree and the open pull requests every time, because recomputed
state cannot go stale). `.claude/scripts/deliver-loop.sh` drives it from a
local terminal, waiting mechanically on `gh pr checks --watch`;
`/deliver-loop` drives it from a Claude Code web session, waiting on events —
a PR subscription plus a scheduled check-in — because a hosted session holding
a turn open to watch CI spends its lifetime on nothing. The owner chooses a
mode by choosing which entry point to start.

The phase order encodes the authority chain: an open pull request targeting
the run's base branch holds everything (one PR in flight per base branch — a
pull request into a different base belongs to a different run and holds
nothing here); unruled HIGH uncertainties, then unmetabolised
evidence, wake the **oracle**; landed decisions without plans get
**stewards**; uncovered owner requirements get a **plan**; merged plans
without merged features get an **orchestrator**; and a fully built design
gets the acceptance pass. Every stop states its reason — repeated failure
signature, budget spent, blocked on the owner — and the run's record is
`.claude/deliver-loop/run.md`.

## The one-layer rule

There is **exactly one** level of spawning: the orchestrator spawns workers;
**workers spawn nothing**. In particular, an orchestrator never spawns another
orchestrator — that is a second layer wearing a different hat, and it brings back
everything the rule exists to prevent: recursive fan-out, an unpredictable
process tree, and no single place that knows what is running.

Each worker prompt states this explicitly, and the orchestrator never hands a
worker `spawn-worker.sh` or any other orchestration tooling.

## Worker isolation

Each worker gets its own `git worktree` on a fresh `worker/<slug>-<n>` branch
under `.worktrees/<slug>-<n>`, so workers never touch the main working tree or
each other. Worker stdout+stderr is captured to
`.claude/orchestration-logs/<slug>-<n>.log`. Both directories are gitignored.

**The worktrees are not under `.claude/`, and that is load-bearing.** Claude Code
treats `.claude/` as a protected directory: a headless worker whose tree sat
there was refused every write — `Write` and `Edit` denied, `touch` refused as
outside the allowed working directory, `git hash-object -w` left unapproved —
and headless mode has nobody to prompt, so every denial passed in silence. The
worker produced an empty branch and exited 0. Do not "fix" a write refusal by
reaching for `--bypass-sandbox`; that drops the sandbox for unreviewed
model-written code to work around a directory name. The dot prefix is also
deliberate: pytest and ruff both skip dot-directories by default, so a live
worktree cannot be swept up by the outer project's own test or lint run.

**A worker that commits nothing fails.** `spawn-worker.sh` compares the branch
against the commit it started from and exits 3 when nothing landed, printing
`commits=<n>` on its `WORKER_RESULT` line. Before that check existed, an agent
that was refused every write reported success, and the only thing between that
and an empty pull request was the orchestrator remembering to diff each branch.

**The engine is preflighted before any worktree is created.** Being on `PATH`
says nothing about whether an engine can authenticate, and the default engine is
`codex` — on an account with no codex subscription the default path cannot work
at all. `spawn-worker.sh` probes the engine first and fails with "engine X is
installed but not usable", rather than letting the worker die deep inside a
headless run where the error mentions anything but authentication.

Workers for a feature are based on **that feature's branch**, not on whatever
the orchestrator happens to have checked out. Pass `--base feat/<slug>`
explicitly on every spawn. `spawn-worker.sh` defaults `--base` to the current
HEAD, which is silently wrong the moment a second feature is in flight: workers
would branch off another feature's code and carry it into their PR.

## How much to run at once

Two limits, because two different things break, and they break for different
reasons. One number cannot express both.

**Concurrent workers: 12.** This is a *machine and budget* limit. Each worker is
a process with its own worktree — a full checkout — and often its own test run.
Twelve is comfortable on a desktop and worth lowering on a laptop; treat it as
hardware-dependent rather than sacred. The budget half matters more than it
looks: workers and the PR review gate draw on the same subscription, so a wide
fan-out can saturate the rate limit and leave the gate — a required check that
fails closed — with no capacity. Starve it and you have spent your budget
building something you now cannot merge.

**Slices assembled per session: 6.** This is an *attention* limit, and it is the
one to respect. After the workers finish, one session reads every branch diff,
checks each against its slice, and reconciles each code/test pair — all in a
single context window. It does not fail loudly when that gets too big. It fails
by giving slice 6 a worse review than slice 1, which looks exactly like a clean
review from the outside.

The two align at the ceiling: 6 slices × 2 workers = 12 concurrent. They come
apart when a slice skips its test-writer pair, which is allowed for slices with
no real logic — then 6 slices might be 9 workers.

A plan is 3–5 slices by design, so a normal feature sits inside both limits with
room to spare. If a plan needs more than 6, that is the plan telling you it is
really two features.

## Code and tests are written blind, in parallel

Each slice gets two workers: one writing the code, one writing the tests. Both
branch off `feat/<slug>` at the same commit, so **neither has the other's output
in its worktree** — the test author cannot read the implementation because it
is not there.

That structure is the mechanism. An agent asked to write code and its tests
writes tests that describe what its code happens to do, bugs included, and the
suite then certifies the bug. Splitting the roles only helps if the test author
genuinely cannot see the implementation; a promise to ignore it is not the same
thing, and writing tests *afterwards* fails for the same reason even with a
different agent — the code is there to read.

What makes blind parallel authorship work at all is the slice's **Signatures**
block. It is the contract both sides code against: same names, same arguments,
same types. Without it the two would agree on intent and disagree on every
identifier, and reconciliation would cost more than the separation saves. This
is the reason the plan schema demands signatures with no bodies.

The two meet at assembly, and disagreement there is the payoff, not a problem —
it means the slice was built and checked by two independent readings of the
spec, and they differed. `/orchestrate` step 4 says how to resolve it; the one
forbidden resolution is weakening the test to match the code.

CI's `test-the-tests` check backs this up from the other side: it reverts the
implementation and fails if the tests still pass, catching a test author that
asserted on nothing.

## If you run a second orchestrator, keep the features disjoint

Two features touching the same file will conflict when the second PR merges, and
neither PR's checks will have seen the combination. Since neither session can see
the other, **that check is yours to make** before you start the second one:

```sh
grep -h '^- \*\*Files:\*\*' docs/plans/<slug-a>.md docs/plans/<slug-b>.md
```

If the file lists overlap, run the features one after another instead. Do not try
to coordinate two live branches over the same file — you would be doing by hand,
across two contexts, exactly the merge reconciliation the pipeline exists to
avoid. This is a habit rather than a script on purpose; if it turns out to be the
thing that keeps escaping, `docs/escapes.md` will say so and *then* it earns
automation.

## Sandbox default and the opt-in bypass

Workers run at **workspace-level sandbox** by default:

- `codex` (default engine): `codex exec --approve-for-me --ephemeral` —
  sandboxed writes limited to the workspace; `--ephemeral` so parallel runs
  don't share session state. (`--approve-for-me` replaced `--full-auto`, which
  codex-cli removed; 0.147.0 rejects the old spelling outright.)
- `claude`: `claude -p --allowed-tools <worker grants> --permission-mode
  acceptEdits` — file writes auto-accepted inside the worktree, and a short
  whitelist of commands: git add/commit/status/diff/log/show, and the
  language's test and format runners. Nothing else is reachable, so `git push`,
  `git reset --hard` and `--no-verify` need no deny rule; they are simply not on
  the list. Override the list with `SPAWN_WORKER_ALLOWED_TOOLS` (comma-separated).

**Why the `claude` grants are passed on the command line rather than left to
`.claude/settings.json`.** A fresh worktree is a workspace nobody has trusted
interactively, so Claude Code ignores the project's own allow list there
("this workspace has not been trusted") and falls back to asking — which a
headless run has nobody to answer. The worker replies "I need your permission to
write that file" and exits 0 having written nothing. Command-line grants are not
subject to workspace trust, so that is where they have to live.

`spawn-worker.sh --print-command` prints the assembled command line without
running anything, which is how the template's own CI pins these flags.

The sandbox is dropped **only** when you pass `--bypass-sandbox` to
`spawn-worker.sh` (which switches to `codex --dangerously-bypass-approvals-and-sandbox`
or `claude --dangerously-skip-permissions`). It is off by default and should
stay off unless a task genuinely needs it — say why when you use it.

## Hard single-layer enforcement (available, off by default)

The one-layer rule is enforced by **convention** — the worker prompt tells the
worker not to spawn. If you need a hard guarantee, launch workers with a
restricted `PATH` that omits `codex`/`claude` so those CLIs simply aren't
reachable from inside a worker. This is deliberately **not** the default: it
adds friction for the common, well-behaved case. Turn it on only when running
untrusted or experimental worker prompts.

## Handoff to the merge pipeline

The orchestrator's job ends at **opening a PR per feature**. Merging belongs to
the pipeline, not to any agent: a PR merges when its required checks go green —
the CI **hard gate**, the `plan` check (the PR resolves to exactly one plan),
`test-the-tests`, and the independent **soft gate**
(`.github/workflows/review.yml`). The orchestrator's own local review is a
pre-check to avoid wasting a CI run on obvious junk; it is never authorization
to merge, and no agent runs `gh pr merge` on its own judgment. The reviewer that
gates the PR is separate from whoever wrote or assembled the change — no single
agent both reviews and merges. Workers must never touch the gate paths (CI, the
review check, `CODEOWNERS`, pre-commit); those are human-owned.

## Safety

Workers **execute unreviewed code** the model wrote. Keep the sandbox on. Do
not export API keys or other secrets into worker environments unless a specific
worker actually needs them — a broadly-scoped key handed to several parallel,
unattended agents is a large blast radius for little benefit. Review each
worker's diff against `AGENTS.md` before assembling; discard anything you can't
vouch for.
