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
#                   [--role <role>] [--engine codex|claude] [--model <m>]
#                   [--effort <level>] [--base <branch>]
#                   [--bypass-sandbox] [--skip-preflight] [--print-command]
#
# --role selects the defaults for that kind of work: which model, how much
# reasoning effort, and which tools it may reach. See "ROLES" below. An explicit
# --model or --effort overrides the role's default; SPAWN_WORKER_ALLOWED_TOOLS
# overrides its tool grants.
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
EFFORT=""
ROLE=""
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
    --effort)          EFFORT="${2:-}"; shift 2 ;;
    --role)            ROLE="${2:-}"; shift 2 ;;
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
GIT_TOOLS=(
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(git status:*)"
  "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)"
  # A worker already starts on its own branch in its own worktree, so it does
  # not NEED these — but a denied `git switch` does not fail loudly, it makes
  # the agent abandon the commit it was about to make. Observed downstream: a
  # finished plan left uncommitted in the worktree because the branch step was
  # refused (ESC-38).
  "Bash(git switch:*)" "Bash(git branch:*)"
)
BUILD_TOOLS=(
  "Bash(uv run:*)" "Bash(uv sync:*)"
  "Bash(swiftformat:*)" "Bash(swiftlint:*)"
  "Bash(xcodegen:*)" "Bash(xcodebuild:*)"
)
ALLOWED_TOOLS=("${GIT_TOOLS[@]}" "${BUILD_TOOLS[@]}")
PERM_MODE="acceptEdits"

# ROLES — model, effort, and reach, per kind of work.
#
# Owner rulings, and the reasoning matters more than the table because the table
# will be edited and the reasoning is what should survive the edit.
#
#   oracle       fable-5 high   Its decisions are append-only, permanent, and
#                               written unattended. It runs once per run and
#                               writes little, so it is the cheapest place to
#                               spend more in absolute terms and the one where a
#                               mistake is least recoverable.
#   steward      opus-5 high    Turns a decision into a plan, and plan quality
#                               is the binding constraint on everything
#                               downstream: blind authorship faithfully builds a
#                               wrong contract, and the suite goes green on it.
#   test-writer  opus-5 high    Deliberately the same tier as the steward and
#                               ABOVE the coder. Blind authorship assumes two
#                               peers; making the test side cheaper quietly
#                               turns the contract into "whatever the coder
#                               thought".
#   reviewer     opus-5 high    Reads a diff against fixed documents — a
#                               narrower job than writing one.
#   coder        opus-5 medium  Lower ON PURPOSE, and this is the ruling worth
#                               keeping. The tests are written blind and in
#                               parallel, so a coder failure is recoverable by
#                               construction — it gets another attempt and
#                               nothing merges either way. That makes the
#                               failure diagnostic: if this model cannot write
#                               code that passes the tests, the likely fault is
#                               the TASK DEFINITION, not the coding. Running the
#                               coder at the steward's tier would mask that
#                               signal by letting a stronger coder paper over a
#                               weak contract.
#   explore      opus-5 low     Read-only search, the highest-volume spawn.
#
# The orchestrator is opus-5 high. It is not spawned by this script — it is the
# session you are sitting in — so it is recorded here and set by /config.
#
# `--effort` is passed to the `claude` engine only. codex spells reasoning
# effort differently and is UNVERIFIED here (no codex on the machine this was
# written on), so rather than guess a flag, a codex role gets its model and no
# effort setting, and says so.
#
# THE REACH COLUMN IS NOT THE REAL ENFORCEMENT. It is the first of two: the CI
# checks at merge time are what bind, because a tool grant constrains one agent
# in one worktree while a required check constrains every route to the default
# branch. Treat a narrow grant as a way to make the intended path the easy one,
# never as the thing standing between an agent and a document.
ORACLE_TOOLS=(
  "Read" "Grep" "Glob"
  "Write(docs/DESIGN.oracle.md)" "Edit(docs/DESIGN.oracle.md)"
  "Write(docs/oracle/**)"
  "${GIT_TOOLS[@]}"
)
STEWARD_TOOLS=(
  "Read" "Grep" "Glob"
  "Write(docs/plans/oracle/**)" "Edit(docs/plans/oracle/**)"
  # The backlog is in the steward's reach for two documented duties: an
  # objection to a decision goes to docs/BACKLOG.md (steward.md), and the
  # unattended planner — which runs under this role — files uncertainties
  # there as BL-<n> items for the oracle to rule on (plan.md, the gate).
  "Write(docs/BACKLOG.md)" "Edit(docs/BACKLOG.md)"
  # The gate scripts this role's own prompts tell it to run. Without them the
  # instruction is unfollowable: plan.md and steward.md point at
  # oracle-decisions.sh, and a planner that cannot parse or lint its own plan
  # finds out at CI instead (ESC-38).
  "Bash(.github/scripts/oracle-decisions.sh:*)"
  "Bash(.github/scripts/plan-parse.sh:*)"
  "Bash(.github/scripts/plan-lint.sh:*)"
  "${GIT_TOOLS[@]}"
)
READ_ONLY_TOOLS=("Read" "Grep" "Glob")

if [[ -n "$ROLE" ]]; then
  # Every role names a Claude model, and codex spells reasoning effort
  # differently. Silently applying a claude model id to codex would fail deep
  # inside the run as an unrecognised model, which reads as anything but a
  # mismatched engine — the same shape of misdiagnosis --full-auto produced.
  [[ "$ENGINE" == "claude" ]] || die "--role is defined for the 'claude' engine \
(every role names a Claude model, and codex spells effort differently). Pass \
--engine claude, or drop --role and set --model yourself."
  case "$ROLE" in
    coder)
      ROLE_MODEL="claude-opus-5"; ROLE_EFFORT="medium" ;;
    test-writer)
      ROLE_MODEL="claude-opus-5"; ROLE_EFFORT="high" ;;
    oracle)
      ROLE_MODEL="claude-fable-5"; ROLE_EFFORT="high"
      ALLOWED_TOOLS=("${ORACLE_TOOLS[@]}"); PERM_MODE="default" ;;
    steward)
      ROLE_MODEL="claude-opus-5"; ROLE_EFFORT="high"
      ALLOWED_TOOLS=("${STEWARD_TOOLS[@]}"); PERM_MODE="default" ;;
    reviewer)
      ROLE_MODEL="claude-opus-5"; ROLE_EFFORT="high"
      ALLOWED_TOOLS=("${READ_ONLY_TOOLS[@]}"); PERM_MODE="default" ;;
    explore)
      ROLE_MODEL="claude-opus-5"; ROLE_EFFORT="low"
      ALLOWED_TOOLS=("${READ_ONLY_TOOLS[@]}"); PERM_MODE="default" ;;
    architect)
      # The architect is the only role that may write docs/DESIGN.md and
      # docs/VISION.md, and it is deliberately NOT spawnable. It exists in the
      # owner's own interactive session, during /design, and nowhere else.
      #
      # This refusal is the point of naming it. Spawning is how an agent starts
      # another agent, so a spawnable architect would be a door any role could
      # walk through to reach the two documents it is otherwise denied —
      # including the orchestrator, mid-run, unattended. Closing the door here
      # means the architect's authority cannot be delegated, borrowed, or
      # reached by accident: it is available exactly when a human is typing.
      #
      # The rule this enforces has been wrong twice in this template's history.
      # ESC-24: "no agent may edit it" made docs/VISION.md impossible to fill
      # in, because /design is an agent writing down what the owner said.
      # ESC-25: the correction went too far and let any agent LAND the design,
      # which dissolves the asymmetry docs/DESIGN.oracle.md exists for. The
      # boundary neither wording found is this one — an agent may transcribe,
      # in a session the owner is driving, and the owner opens the pull request.
      die "the 'architect' role is not spawnable, and that is deliberate.

It is the only role that may write docs/DESIGN.md and docs/VISION.md, so it
runs only where a human is present: the owner's own session, via /design. An
agent that wants those documents changed does not spawn one — it files evidence
(docs/BACKLOG.md or docs/escapes.md) and the oracle rules on it, or it says so
in its report and the owner decides.

If you are the owner and you want the design or the vision written, run
/design in an interactive session." ;;
    *)
      die "unknown --role '$ROLE'.
Known roles: coder, test-writer, oracle, steward, reviewer, explore.
The 'architect' role exists but is not spawnable — see /design.
A typo would otherwise land silently on the engine's own defaults — a wide tool
grant and whatever model happened to be configured — which is the opposite of
what naming a role was for." ;;
  esac
  # An explicit flag always wins over the role's default. The role is where the
  # default lives, not a lock.
  MODEL="${MODEL:-$ROLE_MODEL}"
  EFFORT="${EFFORT:-$ROLE_EFFORT}"
fi

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
  # `--` before the prompt, ALWAYS. Every command file opens with YAML
  # frontmatter, so a prompt built from one begins with `---` — and without the
  # terminator the CLI reads that as a flag and dies with "unknown option"
  # before any model is reached. That is how the first unattended run failed at
  # its first dispatch, eight times in thirty seconds (ESC-37).
  CMD+=(-- "$PROMPT")
else
  CMD=(claude -p)
  if [[ "$BYPASS" -eq 1 ]]; then
    CMD+=(--dangerously-skip-permissions)
  else
    CMD+=(--allowed-tools "${ALLOWED_TOOLS[@]}" --permission-mode "$PERM_MODE")
  fi
  [[ -n "$MODEL" ]] && CMD+=(--model "$MODEL")
  [[ -n "$EFFORT" ]] && CMD+=(--effort "$EFFORT")
  # Same terminator as the codex branch, same reason (ESC-37). Verified:
  # `claude -p -- "…"` accepts a `---`-leading prompt.
  CMD+=(-- "$PROMPT")
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
