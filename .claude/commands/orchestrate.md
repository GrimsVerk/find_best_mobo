---
description: Fan a task out to a few headless worker agents, then merge their results
---

You are the **orchestrator**. Drive the single-layer orchestration described
in `.claude/orchestration.md` (read it first if you have not). The task:

$ARGUMENTS

Follow these steps.

## 1. Decompose

Break the task into a small number of **independent** subtasks — target 3–5,
never more. Each subtask must be scoped to **disjoint files or directories**
so no two workers can touch the same path and collide. If the task can't be
split cleanly into independent pieces, say so and do it yourself instead of
forcing a bad split.

## 2. Write worker prompts and spawn

For each subtask, write a **self-contained** prompt: what to change, which
files/dirs it owns, the acceptance bar (tests pass, follows `AGENTS.md`), and
this explicit instruction —

> You are a worker. Do only this assigned task, in the files listed. You are
> NOT an orchestrator: do not spawn, invoke, or delegate to any further
> agents, and do not use any orchestration scripts. Never modify the merge
> gates — CI workflows (`.github/workflows/`), the review check or its prompt
> (`.github/review-prompt.md`, `.github/scripts/review.sh`), branch
> protection, `CODEOWNERS`, or the pre-commit config. When done, ensure the
> project's checks pass, then stop.

Never hand a worker `spawn-worker.sh` or any orchestration tooling.

Spawn workers **in parallel**, each via the primitive:

```sh
.claude/scripts/spawn-worker.sh --id <short-id> --prompt "<prompt>" &
```

Run them with background `&` + `wait` (or `xargs -P`), not one at a time.
Defaults: engine `codex`, workspace-level sandbox. Keep the sandbox on — do
NOT pass `--bypass-sandbox` unless the task genuinely requires it and you have
said why. Collect each printed `WORKER_RESULT` line (id, branch, worktree,
exit code).

## 3. Review, then assemble

After all workers finish, for each one:

- Read its branch diff (`git -C <worktree> diff <base>...`) and its log
  under `.claude/orchestration-logs/<id>.log`.
- Review the changes against `AGENTS.md`. If a `reviewer` subagent exists,
  delegate the review to it; otherwise review directly. This is a local
  **pre-check to catch obvious junk before it costs a CI run — it is NOT
  merge authorization.** The authoritative review is the pipeline's soft
  gate (`.github/workflows/review.yml`), which runs independently on the PR.
- **Assemble** the branches that pass your pre-check into a single feature
  branch (merge the worker branches into it). For the ones that failed or
  errored, either re-dispatch a corrected worker prompt (once) or discard the
  branch — don't assemble broken work.

## 4. Open a PR into the pipeline, then stop

Push the assembled feature branch and open **one** pull request. **Do not
merge it.** Your job ends here: the merge is the pipeline's, triggered by the
required checks going green — the CI hard gate plus the review soft gate (and,
where enabled, GitHub auto-merge completes it mechanically). A passing local
pre-check is never your authorization to merge, and you never run `gh pr merge`
on your own judgment.

Clean up the worktrees you're done with:

```sh
git worktree remove --force .claude/worktrees/<id>
git branch -D worker/<id>   # for discarded branches
```

Then report a summary: what each worker was asked to do, which branches you
assembled into the PR, which you discarded and why, and the PR link.
