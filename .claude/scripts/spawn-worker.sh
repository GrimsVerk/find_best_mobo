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
#                   [--bypass-sandbox] [--skip-preflight] [--print-command]
#
# Env:
#   SPAWN_PREFLIGHT_CODEX / SPAWN_PREFLIGHT_CLAUDE   override the engine probe
#   SPAWN_WORKER_ALLOWED_TOOLS                       comma-separated tool grants
#                                                    for the `claude` engine
#
# --base defaults to the CURRENT HEAD. That is fine for a single feature and
# silently wrong for more than one: pass --base feat/<slug> explicitly so a
# worker branches off its own feature, not off whatever is checked out. See
# .claude/orchestration.md.
#
# --print-command assembles the engine command line, prints it one argument per
# line, and exits without creating a worktree or running anything. It needs no
# engine installed, which is what lets CI pin the flags this script passes.
#
# WORKTREES LIVE UNDER .worktrees/, NOT UNDER .claude/.
#
# Claude Code treats .claude/ as a protected directory. A headless worker whose
# tree sat under .claude/worktrees/ was refused every write — Write and Edit
# denied, `touch` refused as outside the allowed working directory, `git
# hash-object -w` left unapproved — and headless mode cannot prompt, so every
# denial was silent. The worker produced nothing and exited 0. Moving the trees
# out is the fix; --bypass-sandbox is NOT, because it drops the sandbox for
# unreviewed model-written code to work around a path choice.
#
# The directory is dot-prefixed deliberately: pytest's default norecursedirs and
# ruff's default excludes both skip dot-directories, so a live worktree cannot
# be collected by the outer project's own test or lint run. It is gitignored.
#
# THE ENGINE IS PREFLIGHTED, NOT JUST LOCATED.
#
# `command -v codex` says the binary exists. It says nothing about whether that
# binary can authenticate, and an engine with no subscription behind it fails
# deep inside a headless run, where the error reads as anything but "you are not
# logged in". So each engine gets a probe before any worktree is created, and a
# failing probe says "engine X is installed but not usable". --skip-preflight
# opts out; SPAWN_PREFLIGHT_CODEX / SPAWN_PREFLIGHT_CLAUDE override the probe.
#
# A WORKER THAT COMMITS NOTHING IS A FAILURE, AND THIS SCRIPT SAYS SO.
#
# A headless agent that is refused every write still exits 0. Reporting that as
# success put the entire burden of noticing on the caller remembering to diff
# each branch against its base. So after the engine returns, this compares the
# branch against its base commit and exits 3 when there are no commits — an
# empty branch fails loudly at the primitive instead of quietly at the top.
#
# On success it leaves the worktree and branch in place and prints:
#   WORKER_RESULT id=<id> branch=<branch> worktree=<path> engine=<engine>
#                 exit=<engine exit code> commits=<n>
#
# Exit codes:
#   0  the engine succeeded and the branch carries at least one commit
#   2  a setup fault (bad arguments, unusable engine, worktree collision)
#   3  the engine exited 0 but committed nothing — see above
#   *  otherwise, the engine's own exit code
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
SKIP_PREFLIGHT=0
PRINT_COMMAND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --id)              ID="${2:-}"; shift 2 ;;
    --prompt)          PROMPT="${2:-}"; shift 2 ;;
    --prompt-file)     PROMPT_FILE="${2:-}"; shift 2 ;;
    --engine)          ENGINE="${2:-}"; shift 2 ;;
    --model)           MODEL="${2:-}"; shift 2 ;;
    --base)            BASE="${2:-}"; shift 2 ;;
    --bypass-sandbox)  BYPASS=1; shift ;;
    --skip-preflight)  SKIP_PREFLIGHT=1; shift ;;
    --print-command)   PRINT_COMMAND=1; shift ;;
    -h|--help)         usage; exit 0 ;;
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

# What a worker is allowed to run, when the engine is `claude`.
#
# A whitelist, and short on purpose: write files, run the suite, commit. Nothing
# else is reachable, so `git push`, `git reset --hard` and `--no-verify` are not
# denied by a rule that a worker could argue with — they are simply not on the
# list. Both languages' runners are listed because this script ships to both and
# granting `xcodebuild` inside a Python project grants nothing.
#
# Override with SPAWN_WORKER_ALLOWED_TOOLS as a COMMA-separated list; the
# patterns contain spaces, so commas are the only safe separator here.
ALLOWED_TOOLS=(
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(git status:*)"
  "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)"
  "Bash(uv run:*)" "Bash(uv sync:*)"
  "Bash(swiftformat:*)" "Bash(swiftlint:*)"
  "Bash(xcodegen:*)" "Bash(xcodebuild:*)"
)
if [[ -n "${SPAWN_WORKER_ALLOWED_TOOLS:-}" ]]; then
  IFS=',' read -r -a ALLOWED_TOOLS <<< "$SPAWN_WORKER_ALLOWED_TOOLS"
fi

# Assemble the headless command per engine. Default sandbox stays at workspace
# level; --bypass-sandbox is the only way to drop it.
#
# codex: --approve-for-me is the current spelling of "run the whole task without
# stopping to ask". The old --full-auto was REMOVED from codex-cli (0.147.0
# rejects it outright), and because it died as an argument error every worker
# looked like a prompt problem rather than a flag problem.
#
# claude: a bare `claude -p` CANNOT WRITE ANYTHING. A fresh worktree is a
# workspace nobody has trusted interactively, so the project's own
# .claude/settings.json allow list is ignored there ("this workspace has not
# been trusted"), and the default permission mode asks for approval that a
# headless run has nobody to give. The worker replies "I need your permission to
# write that file" and exits 0 having done nothing. The grants therefore have to
# arrive on the command line, where workspace trust does not apply:
# --permission-mode acceptEdits for the files, --allowed-tools for the commands.
#
# --allowed-tools is VARIADIC: it swallows every following argument until the
# next flag. It is placed first, and --permission-mode terminates it, so the
# prompt cannot be parsed as a tool name.
if [[ "$ENGINE" == "codex" ]]; then
  # --ephemeral: parallel runs must not share session state.
  if [[ "$BYPASS" -eq 1 ]]; then
    CMD=(codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral)
  else
    CMD=(codex exec --approve-for-me --ephemeral)
  fi
  [[ -n "$MODEL" ]] && CMD+=(--model "$MODEL")
  CMD+=("$PROMPT")
else
  CMD=(claude -p)
  if [[ "$BYPASS" -eq 1 ]]; then
    CMD+=(--dangerously-skip-permissions)
  else
    CMD+=(--allowed-tools "${ALLOWED_TOOLS[@]}" --permission-mode acceptEdits)
  fi
  [[ -n "$MODEL" ]] && CMD+=(--model "$MODEL")
  CMD+=("$PROMPT")
fi

if [[ "$PRINT_COMMAND" -eq 1 ]]; then
  printf '%s\n' "${CMD[@]}"
  exit 0
fi

command -v git >/dev/null 2>&1 || die "git not on PATH"
command -v "$ENGINE" >/dev/null 2>&1 || die "engine '$ENGINE' not on PATH"

# The probe for each engine. Overridable so a machine with a different auth
# story — or a test running a stub engine — can substitute its own.
preflight_command() {
  case "$1" in
    codex)  printf '%s' "${SPAWN_PREFLIGHT_CODEX:-codex login status}" ;;
    claude) printf '%s' "${SPAWN_PREFLIGHT_CLAUDE:-claude auth status}" ;;
  esac
}

# preflight_ok <engine> <rc> <output>
#
# The exit status alone is not enough. Both CLIs report a signed-out account on
# stdout, and neither's status code is guaranteed to follow, so the output is
# read as well — a probe that "succeeds" while saying "Not logged in" is exactly
# the false green this check exists to prevent.
preflight_ok() {
  local engine="$1" rc="$2" out="$3"
  [[ "$rc" -eq 0 ]] || return 1
  case "$engine" in
    claude) [[ "$out" != *'"loggedIn": false'* && "$out" != *'"loggedIn":false'* ]] ;;
    codex)  [[ "$out" != *"Not logged in"* && "$out" != *"not logged in"* ]] ;;
  esac
}

if [[ "$SKIP_PREFLIGHT" -eq 0 ]]; then
  PROBE="$(preflight_command "$ENGINE")"
  set +e
  PROBE_OUT="$(bash -c "$PROBE" 2>&1)"
  PROBE_RC=$?
  set -e
  if ! preflight_ok "$ENGINE" "$PROBE_RC" "$PROBE_OUT"; then
    die "engine '$ENGINE' is installed but not usable.

  probe: $PROBE
  exit:  $PROBE_RC
  said:  ${PROBE_OUT:-(no output)}

The binary is on PATH, so this is not a missing install — it is an engine that
cannot authenticate, most often an account with no subscription for it or a
session that has expired. Sign in (or pass --engine <the other one>) rather than
letting the worker fail deep inside a headless run, where the error will not
mention authentication at all.

Pass --skip-preflight to run anyway."
  fi
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || die "not inside a git repository"

# Branch/worktree names derived from the worker id; keep them filesystem- and
# ref-safe (letters, digits, dash, underscore, dot).
SAFE_ID="$(printf '%s' "$ID" | tr -c 'A-Za-z0-9._-' '-')"
BRANCH="worker/${SAFE_ID}"
WORKTREE="${REPO_ROOT}/.worktrees/${SAFE_ID}"
LOG_DIR="${REPO_ROOT}/.claude/orchestration-logs"
LOG_FILE="${LOG_DIR}/${SAFE_ID}.log"
BASE="${BASE:-$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)}"

# Pin the base to a commit now. The branch it names can move while the worker
# runs, and the emptiness check below must compare against where this worker
# actually started, not against wherever that ref ended up.
BASE_SHA="$(git -C "$REPO_ROOT" rev-parse --verify "${BASE}^{commit}" 2>/dev/null)" \
  || die "base '$BASE' does not resolve to a commit"

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
git -C "$REPO_ROOT" worktree add -b "$BRANCH" "$WORKTREE" "$BASE_SHA" \
  >>"$LOG_FILE" 2>&1 || die "git worktree add failed (see $LOG_FILE)"

# Worktree is live; from here failures belong to the worker, not to setup.
SETUP_OK=1

{
  echo "=== spawn-worker[$ID] engine=$ENGINE branch=$BRANCH base=$BASE ($BASE_SHA) bypass=$BYPASS ==="
  echo "=== $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} >>"$LOG_FILE"

set +e
( cd "$WORKTREE" && "${CMD[@]}" ) >>"$LOG_FILE" 2>&1
RC=$?
set -e

# Did the worker actually produce anything? An agent refused every write, or one
# that edited files and stopped without committing, exits 0 all the same.
COMMITS="$(git -C "$WORKTREE" rev-list --count "${BASE_SHA}..HEAD" 2>/dev/null || echo 0)"
DIRTY="$(git -C "$WORKTREE" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"

echo "WORKER_RESULT id=${ID} branch=${BRANCH} worktree=${WORKTREE} engine=${ENGINE} exit=${RC} commits=${COMMITS}"

if [[ "$RC" -ne 0 ]]; then
  echo "spawn-worker[$ID]: engine exited $RC (see $LOG_FILE)" >&2
  exit "$RC"
fi

if [[ "$COMMITS" -eq 0 ]]; then
  {
    echo "spawn-worker[$ID]: the engine exited 0 but committed nothing."
    echo
    echo "  branch:   $BRANCH (no commits since ${BASE_SHA:0:12})"
    echo "  worktree: $WORKTREE"
    echo "  log:      $LOG_FILE"
    if [[ "$DIRTY" -gt 0 ]]; then
      echo
      echo "There are $DIRTY uncommitted path(s) in the worktree, so the worker did"
      echo "work and never committed it. Read the log before re-dispatching; the"
      echo "worktree is left in place precisely so that work is still recoverable."
    else
      echo
      echo "The worktree is clean, so the worker wrote nothing at all. The usual"
      echo "cause is silently denied writes: a headless agent cannot be prompted"
      echo "for permission, so every denial passes without a word and the run ends"
      echo "successfully having done nothing."
    fi
  } >&2
  exit 3
fi

exit 0
