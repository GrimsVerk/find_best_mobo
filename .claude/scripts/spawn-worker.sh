#!/usr/bin/env bash
#
# spawn-worker.sh — the orchestration worker primitive.
#
# Runs ONE headless worker agent in an isolated git worktree on its own
# branch, so it never touches the main working tree. The orchestrator (the
# main Claude Code session) calls this once per subtask, in parallel, then
# collects the printed WORKER_RESULT lines to merge or discard each branch.
#
# This is a single-layer tool: a worker does only its assigned task. It must
# NOT call this script or spawn further agents (see .claude/orchestration.md).
#
# Usage:
#   spawn-worker.sh --id <name> (--prompt <string> | --prompt-file <path>)
#                   [--engine codex|claude] [--model <m>] [--base <branch>]
#                   [--bypass-sandbox]
#
# --base defaults to the CURRENT HEAD. That is fine for a single feature and
# silently wrong for more than one: pass --base feat/<slug> explicitly so a
# worker branches off its own feature, not off whatever is checked out. See
# .claude/orchestration.md.
#
# On success it leaves the worktree and branch in place and prints:
#   WORKER_RESULT id=<id> branch=<branch> worktree=<path> engine=<engine> exit=<code>
#
# Logs (stdout+stderr of the worker) go to .claude/orchestration-logs/<id>.log
# (gitignored). On a setup failure it cleans up its own worktree and branch.

set -euo pipefail

usage() {
  # Print the leading comment block, stopping at the first non-comment line.
  # Self-terminating rather than a fixed line range, so editing the header
  # above can't make --help spill shell code into its own output.
  sed -n '2,/^[^#]/p' "$0" | sed -n 's/^# \{0,1\}//p'
}

ID=""
PROMPT=""
PROMPT_FILE=""
ENGINE="codex"
MODEL=""
BASE=""
BYPASS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --id)             ID="${2:-}"; shift 2 ;;
    --prompt)         PROMPT="${2:-}"; shift 2 ;;
    --prompt-file)    PROMPT_FILE="${2:-}"; shift 2 ;;
    --engine)         ENGINE="${2:-}"; shift 2 ;;
    --model)          MODEL="${2:-}"; shift 2 ;;
    --base)           BASE="${2:-}"; shift 2 ;;
    --bypass-sandbox) BYPASS=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "spawn-worker: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "spawn-worker: $*" >&2; exit 2; }

[[ -n "$ID" ]] || die "missing --id"
[[ "$ENGINE" == "codex" || "$ENGINE" == "claude" ]] \
  || die "--engine must be 'codex' or 'claude' (got '$ENGINE')"

# Resolve the prompt (string wins if both are given).
if [[ -z "$PROMPT" ]]; then
  [[ -n "$PROMPT_FILE" ]] || die "provide --prompt or --prompt-file"
  [[ -f "$PROMPT_FILE" ]] || die "prompt file not found: $PROMPT_FILE"
  PROMPT="$(cat "$PROMPT_FILE")"
fi
[[ -n "$PROMPT" ]] || die "prompt is empty"

command -v "$ENGINE" >/dev/null 2>&1 || die "engine '$ENGINE' not on PATH"
command -v git >/dev/null 2>&1 || die "git not on PATH"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || die "not inside a git repository"

# Branch/worktree names derived from the worker id; keep them filesystem- and
# ref-safe (letters, digits, dash, underscore, dot).
SAFE_ID="$(printf '%s' "$ID" | tr -c 'A-Za-z0-9._-' '-')"
BRANCH="worker/${SAFE_ID}"
WORKTREE="${REPO_ROOT}/.claude/worktrees/${SAFE_ID}"
LOG_DIR="${REPO_ROOT}/.claude/orchestration-logs"
LOG_FILE="${LOG_DIR}/${SAFE_ID}.log"
BASE="${BASE:-$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)}"

SETUP_OK=0
# shellcheck disable=SC2317  # invoked indirectly via the EXIT trap
on_exit() {
  local ec=$?
  # Only clean up when we failed DURING setup — once the worker has run, the
  # orchestrator owns the worktree/branch and decides whether to keep them.
  if [[ "$SETUP_OK" -eq 0 && "$ec" -ne 0 ]]; then
    echo "spawn-worker[$ID]: setup failed (exit $ec) — cleaning up" >&2
    if [[ -e "$WORKTREE" ]]; then
      git -C "$REPO_ROOT" worktree remove --force "$WORKTREE" 2>/dev/null || true
    fi
    if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
      git -C "$REPO_ROOT" branch -D "$BRANCH" 2>/dev/null || true
    fi
  fi
}
trap on_exit EXIT

if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  die "branch '$BRANCH' already exists — pick a fresh --id or clean it up"
fi
[[ -e "$WORKTREE" ]] && die "worktree path already exists: $WORKTREE"

mkdir -p "$LOG_DIR"
git -C "$REPO_ROOT" worktree add -b "$BRANCH" "$WORKTREE" "$BASE" \
  >>"$LOG_FILE" 2>&1 || die "git worktree add failed (see $LOG_FILE)"

# Worktree is live; from here failures belong to the worker, not to setup.
SETUP_OK=1

# Assemble the headless command per engine. Default sandbox stays at
# workspace level; --bypass-sandbox is the only way to drop it.
if [[ "$ENGINE" == "codex" ]]; then
  # --ephemeral: parallel runs must not share session state.
  if [[ "$BYPASS" -eq 1 ]]; then
    CMD=(codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral)
  else
    CMD=(codex exec --full-auto --ephemeral)
  fi
  [[ -n "$MODEL" ]] && CMD+=(--model "$MODEL")
  CMD+=("$PROMPT")
else
  CMD=(claude -p)
  [[ "$BYPASS" -eq 1 ]] && CMD+=(--dangerously-skip-permissions)
  [[ -n "$MODEL" ]] && CMD+=(--model "$MODEL")
  CMD+=("$PROMPT")
fi

{
  echo "=== spawn-worker[$ID] engine=$ENGINE branch=$BRANCH base=$BASE bypass=$BYPASS ==="
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} >>"$LOG_FILE"

set +e
( cd "$WORKTREE" && "${CMD[@]}" ) >>"$LOG_FILE" 2>&1
RC=$?
set -e

echo "WORKER_RESULT id=${ID} branch=${BRANCH} worktree=${WORKTREE} engine=${ENGINE} exit=${RC}"
exit "$RC"
