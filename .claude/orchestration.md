# Orchestration

A single layer of parallelism for Claude Code: the main session (the
**orchestrator**) fans a task out to a few **worker** agents, each running
headless in its own git worktree, then assembles their branches into a single
pull request. It does **not** merge — see "Handoff to the merge pipeline".

This whole setup lives under `.claude/` — the deletable, Claude-Code-specific
layer. Removing `.claude/` removes orchestration and leaves a fully functional
project (docs, CI, and pre-commit are untouched).

- **Command:** `/orchestrate <task>` (see `.claude/commands/orchestrate.md`).
- **Primitive:** `.claude/scripts/spawn-worker.sh` (one worker per call).

## The one-layer rule

There is **exactly one** level of spawning: the orchestrator spawns workers;
**workers spawn nothing**. Each worker prompt states this explicitly, and the
orchestrator never hands a worker `spawn-worker.sh` or any other orchestration
tooling. This keeps the process tree flat and predictable — no recursive
fan-out, no worker pools, no cross-machine work. One layer, on this machine,
in the terminal.

## Worker isolation

Each worker gets its own `git worktree` on a fresh `worker/<id>` branch under
`.claude/worktrees/<id>`, so workers never touch the main working tree or each
other. The orchestrator scopes subtasks to **disjoint files/directories** so
two branches can't conflict. Worker stdout+stderr is captured to
`.claude/orchestration-logs/<id>.log`. Both directories are gitignored.

## Sandbox default and the opt-in bypass

Workers run at **workspace-level sandbox** by default:

- `codex` (default engine): `codex exec --full-auto --ephemeral` — sandboxed
  writes limited to the workspace; `--ephemeral` so parallel runs don't share
  session state.
- `claude`: `claude -p` under the project's normal permission rules.

The sandbox is dropped **only** when you pass `--bypass-sandbox` to
`spawn-worker.sh` (which switches to `codex --dangerously-bypass-approvals-and-sandbox`
or `claude --dangerously-skip-permissions`). It is off by default and should
stay off unless a task genuinely needs it — say why when you use it.

## The 3–5 worker sweet spot

Aim for **3–5** workers, never more. Fewer than 3 rarely beats doing the work
inline; more than 5 means the subtasks probably aren't cleanly independent, the
review/merge step dominates, and the odds of overlapping edits climb. If a task
won't split into ~3–5 disjoint pieces, that's a signal to do it directly rather
than to spawn a crowd.

## Hard single-layer enforcement (available, off by default)

The one-layer rule is enforced by **convention** — the worker prompt tells the
worker not to spawn. If you need a hard guarantee, launch workers with a
restricted `PATH` that omits `codex`/`claude` so those CLIs simply aren't
reachable from inside a worker. This is deliberately **not** the default: it
adds friction for the common, well-behaved case. Turn it on only when running
untrusted or experimental worker prompts.

## Handoff to the merge pipeline

The orchestrator's job ends at **opening a PR**. Merging belongs to the
pipeline, not to any agent: a PR merges when its required checks go green — the
CI **hard gate** plus an independent **soft gate** (`.github/workflows/review.yml`,
a read-only LLM review of the diff). The orchestrator's own local review is a
pre-check to avoid wasting a CI run on obvious junk; it is never authorization
to merge, and no agent runs `gh pr merge` on its own judgment. The reviewer
that gates the PR is separate from whoever wrote or assembled the change — no
single agent both reviews and merges. Workers must never touch the gate paths
(CI, the review check, `CODEOWNERS`, pre-commit); those are human-owned.

## Safety

Workers **execute unreviewed code** the model wrote. Keep the sandbox on. Do
not export API keys or other secrets into worker environments unless a specific
worker actually needs them — a broadly-scoped key handed to several parallel,
unattended agents is a large blast radius for little benefit. Review each
worker's diff against `AGENTS.md` before merging; discard anything you can't
vouch for.
