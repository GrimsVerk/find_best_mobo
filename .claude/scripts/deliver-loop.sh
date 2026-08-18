#!/usr/bin/env bash
#
# deliver-loop.sh — the local delivery driver: run the pipeline until the
# design is built, with nobody watching.
#
#     .claude/scripts/deliver-loop.sh [options]
#
# This is a SCHEDULER, NOT AN AGENT — deterministic bash the owner starts, in
# the position orchestration.md already blesses ("you know what is running,
# because you started both"). It holds no model and makes no judgment beyond
# branching on exit codes: each iteration it asks `deliver-phase.sh` what the
# world needs next, dispatches ONE headless session (or waits on one open pull
# request), and comes back. All waiting is mechanical — `gh pr checks --watch`
# — so no model budget is spent watching CI (docs/DECISIONS.md, the waiting
# ruling). The one-layer rule survives intact: this driver opens sessions;
# only an orchestrator session spawns workers.
#
# The web-session variant of this driver is `/deliver-loop`
# (.claude/commands/deliver-loop.md); both consume the same phase detector,
# which is what keeps the two modes from drifting. Choose a mode by choosing
# which entry point you start.
#
# STATE IS RECOMPUTED, NOT TRUSTED. Every iteration re-reads the tree and the
# open pull requests. The only persistence is `.claude/deliver-loop/`
# (gitignored): failure signatures, evidence ids the oracle dismissed, the
# design/vision SHAs at run start, and the run log as it is being written
# (`run.md`).
#
# THE RUN LEAVES EVIDENCE BEHIND, AND THAT IS NEW. The run log used to end its
# life gitignored — and in web mode, inside a container that is reclaimed — so
# the loop the owner described (run, learn, fix the template, run again) had
# nothing to learn from. At EVERY stop, whatever the reason, the driver copies
# the run report to `docs/runs/<timestamp>/run.md`, collects the review gate's
# payloads and replies beside it, and opens one pull request carrying both.
#
# It is written to the gitignored path DURING the run and copied at the stop,
# rather than written straight into docs/runs/. An untracked file sitting in the
# tree while an orchestrator session runs `git add -A` is a file that ends up
# inside somebody's feature commit, and the report would then be spread across
# the branches it was reporting on.
#
# STOPS, and their exit codes — every stop says why, none degrades silently:
#   0  done: the acceptance pass ran (or was already recorded);
#      docs/runs/<timestamp>/run.md has the report and the pending-on-owner list
#   2  setup: refused before dispatching anything — readiness check failed,
#      no design ids, dirty tree, wrong branch
#   3  the same failure signature three times — a pattern, not a blip
#      (deliver.md step 5's rule, mechanised)
#   4  blocked on the owner: a green pull request only the owner can merge
#      (gate paths are CODEOWNERS-owned), reported rather than waited out
#   5  iteration limit, or the livelock guard
#   6  allowance spent: the weekly percentage-point allowance, or a limit the
#      owner set (--max-prs, --max-hours)
#
# THE CEILING IS ASKED FOR, EVERY RUN. Nothing below has a default, because a
# limit the owner did not choose is a limit they will not recognise when it
# fires at 3am — and the numbers that used to be here (25 points, 10 pull
# requests, 8 hours) were picked by the session that wrote the script. The rate
# limit is the only stop that applies by default; the rest exist for a run
# deliberately cut short ("give it twenty minutes; longer means something is
# wrong"). With no limit at all the run refuses to start.
#
# Which question gets asked is decided by PROBING the usage gauge, not by
# guessing the environment: a reading means a terminal, no reading means a web
# session, and that is a fact rather than an inference.
#
# Options (all unset by default):
#   --budget-points <n>    percentage points of the WEEKLY limit this run may
#                          spend. The window is weekly on the owner's ruling,
#                          and because the 5-hour window resets mid-run and
#                          makes the delta go negative. Both weekly limits are
#                          watched — the all-models one and the per-model one,
#                          which has its own smaller cap and can bind first.
#   --max-prs <n>          stop after this many pull requests
#   --max-hours <n>        stop after this much wall clock
#   --max-iterations <n>   stop after this many iterations
#   --wait-for-owner       on a green owner-owned pull request, keep polling
#                          instead of exiting 4
#   --dry-run              detect and print the phase, dispatch nothing
#   --print-command <phase>  print the session command a phase would run, run
#                          nothing (CI pins the flags this way; needs no engine)
#
# Env:
#   DELIVER_ENGINE        engine for oracle/steward/plan workers (default
#                         claude; codex has no --role support in spawn-worker)
#   DELIVER_ORCH_TOOLS    --allowed-tools for orchestrate/acceptance sessions,
#                         comma-separated; command-line grants because a fresh
#                         workspace ignores settings.json (the ESC-5 lesson)
#   SESSION_TIMEOUT       seconds per headless session (default 3600)
#   WAIT_TIMEOUT          seconds per checks-watch before re-detecting (5400)
#   GH                    the GitHub CLI (tests substitute a stub)
#   DELIVER_SKIP_READY=1  skip the unattended-ready refusal (tests)
#   DELIVER_SKIP_PULL=1   skip the per-iteration pull (tests, offline)
#   DELIVER_APP_TOKEN_CMD the command that mints the App installation token
#                         (default .claude/scripts/app-token.sh; tests
#                         substitute a stub). Deliberately an INJECTION POINT
#                         and not a skip flag: there is no way to run the
#                         driver without a non-owner identity, because a run
#                         under the owner's login makes owner-authored.sh a
#                         formality (docs/synthesis.md, D15).

set -uo pipefail

# Every ceiling starts at zero — meaning "not set" — because the owner's ruling
# is that no limit applies unless they chose it, and the run asks for one before
# it starts. The previous defaults (25 points, 10 PRs, 8 hours) were invented by
# the session that wrote this script; the owner chose none of them, and a stop
# whose number nobody recognises is a stop nobody can act on at 3am.
MAX_ITER=0; BUDGET_POINTS=0; MAX_PRS=0; MAX_HOURS=0
# Not a budget: a livelock guard. Set far above any real run, it exists only so
# a loop that makes no progress cannot spin forever. It is deliberately not
# something the owner is asked about, because reaching it is a bug report rather
# than a spent allowance — and the driver says so when it fires.
HARD_MAX_ITER="${DELIVER_HARD_MAX_ITER:-200}"
BUDGET_POINTS_SET=""; MAX_ITER_SET=""
WAIT_FOR_OWNER=0; DRY_RUN=0; PRINT_PHASE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations) MAX_ITER="${2:-}"; MAX_ITER_SET=1; shift 2 ;;
    --budget-points)  BUDGET_POINTS="${2:-}"; BUDGET_POINTS_SET=1; shift 2 ;;
    --max-prs)        MAX_PRS="${2:-}"; shift 2 ;;
    --max-hours)      MAX_HOURS="${2:-}"; shift 2 ;;
    --wait-for-owner) WAIT_FOR_OWNER=1; shift ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --print-command)  PRINT_PHASE="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,/^[^#]/p' "$0" | sed -n 's/^# \{0,1\}//p'; exit 0 ;;
    *) echo "deliver-loop: unknown argument: $1" >&2; exit 2 ;;
  esac
done

GH="${GH:-gh}"
APP_TOKEN_CMD="${DELIVER_APP_TOKEN_CMD:-.claude/scripts/app-token.sh}"
ENGINE="${DELIVER_ENGINE:-claude}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-3600}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-5400}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "deliver-loop: not inside a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2
SPAWN=".claude/scripts/spawn-worker.sh"
PHASE_SH=".claude/scripts/deliver-phase.sh"
STATE_DIR=".claude/deliver-loop"
DEFAULT_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
[[ -n "$DEFAULT_BRANCH" ]] || DEFAULT_BRANCH="$(git branch --show-current)"

# The orchestrator session's reach. Explicit and on the command line: the
# whitelist below is everything /orchestrate documents itself doing — spawn
# workers, assemble branches, open one pull request — and nothing else, so
# `git reset --hard`, `--no-verify` and `gh pr merge` are unreachable rather
# than forbidden.
#
# ON THE BARE `Write,Edit`. It is not an oversight and it is not a blank
# cheque. Assembly genuinely writes across the tree — resolving a conflict
# between two workers' branches, correcting docs/architecture.md — and any list
# narrow enough to be a real fence would either be wrong for some project's
# layout or would have to enumerate the plan's own Files: entries, which the
# pipeline writes. So the two documents that must never be reached this way are
# denied instead of un-allowed, in three places, because an allowlist cannot
# express "everything except":
#
#   1. .claude/settings.json denies Write/Edit on docs/DESIGN.md and
#      docs/VISION.md for every session in the project. Deny beats allow, and
#      that file is CODEOWNERS-owned so a session cannot widen it.
#   2. `Bash(claude:*)` is absent here, and settings.json no longer allows
#      `claude -p` either, so this session cannot start another session to do
#      the writing on its behalf. Its one door to a new agent is
#      spawn-worker.sh, which refuses --role architect.
#   3. .github/scripts/owner-authored.sh fails any pull request touching those
#      documents that the owner did not OPEN — and since this driver now opens
#      pull requests as the GitHub App rather than as the owner, that check
#      finally binds. It is the layer that actually stops the merge; the two
#      above just make the wrong thing hard to do by accident.
#
# AND `gh pr create` IS ABSENT, WHICH IS THE POINT OF THIS LIST'S NEWEST EDIT.
# ESC-26 gave the driver an App identity so no unattended pull request is
# authored by the owner, and fixed the two places the DRIVER opens one. This
# grant was the two places a SESSION opened one: run_session() passes no
# credential, so an orchestrate or acceptance session inherited the owner's
# local `gh` auth and every feature and acceptance pull request in an unattended
# run was authored by them.
#
# That is worse than a provenance problem. docs/acceptance.md is
# CODEOWNERS-owned and GitHub does not let an author approve their own pull
# request — so the one artifact whose review is the entire point of the run
# could not be approved by the only person entitled to approve it.
#
# The button moved rather than the token: an installation token lasts an hour
# and SESSION_TIMEOUT is an hour, so handing one to a session would fail late,
# rarely, and looking like a GitHub outage. The driver opens both pull requests
# after the session returns, exactly as it already does for every worker.
ORCH_TOOLS="${DELIVER_ORCH_TOOLS:-Read,Grep,Glob,Write,Edit,\
Bash(.claude/scripts/spawn-worker.sh:*),\
Bash(git add:*),Bash(git commit:*),Bash(git status:*),Bash(git diff:*),\
Bash(git log:*),Bash(git show:*),Bash(git switch:*),Bash(git checkout:*),\
Bash(git branch:*),Bash(git merge:*),Bash(git push:*),Bash(git worktree:*),\
Bash(gh pr list:*),Bash(gh pr checks:*),Bash(gh pr view:*)}"

# ------------------------------------------------------- command assembly
# One place builds every session command, so --print-command and the real
# dispatch cannot disagree — the same trick spawn-worker.sh uses for CI.
orch_cmd() { # orch_cmd <prompt>
  printf '%s\n' claude -p "$1" \
    --model claude-opus-5 --effort high \
    --permission-mode acceptEdits \
    --allowed-tools "$ORCH_TOOLS"
}

print_command() {
  case "$1" in
    oracle)  "$SPAWN" --print-command --id oracle-N --role oracle \
               --engine claude --base "$DEFAULT_BRANCH" --prompt "<oracle.md + scope>" ;;
    steward) "$SPAWN" --print-command --id steward-ODN --role steward \
               --engine claude --base "$DEFAULT_BRANCH" --prompt "<steward.md + OD id>" ;;
    plan)    "$SPAWN" --print-command --id plan-N --role steward \
               --engine claude --base "$DEFAULT_BRANCH" --prompt "<plan.md + UNATTENDED + milestone>" ;;
    orchestrate) orch_cmd "/orchestrate <slug>" ;;
    acceptance)  orch_cmd "/deliver — acceptance pass only (step 6)" ;;
    *) echo "deliver-loop: unknown phase '$1' (oracle|steward|plan|orchestrate|acceptance)" >&2
       exit 2 ;;
  esac
}
if [[ -n "$PRINT_PHASE" ]]; then print_command "$PRINT_PHASE"; exit 0; fi

log() { echo "deliver-loop: $*"; echo "- $(date -u +%H:%M:%SZ) $*" >> "$STATE_DIR/run.md"; }
die() { echo "deliver-loop: $*" >&2; exit 2; }

# ---------------------------------------------------------------- preflight
[[ -x "$SPAWN" && -x "$PHASE_SH" ]] || die "missing $SPAWN or $PHASE_SH"
command -v "$GH" >/dev/null 2>&1 || die "'$GH' is not on PATH"
"$GH" auth status >/dev/null 2>&1 || die "gh is not authenticated — run: gh auth login"
command -v claude >/dev/null 2>&1 || die "the claude CLI is not on PATH"

[[ -z "$(git status --porcelain)" ]] \
  || die "the working tree is dirty — a run recomputes state from the tree, and uncommitted changes make that state a lie"
CURRENT_BRANCH="$(git branch --show-current)"
[[ "$CURRENT_BRANCH" == "$DEFAULT_BRANCH" ]] \
  || die "on branch '$CURRENT_BRANCH', not '$DEFAULT_BRANCH' — the driver dispatches from the default branch only"
if [[ -d .worktrees ]] && [[ -n "$(ls -A .worktrees 2>/dev/null)" ]]; then
  die "leftover worktrees under .worktrees/ — a previous run did not finish assembling; inspect and remove them first"
fi

# ------------------------------------------------- readiness, said out loud
# The owner's ruling: "if the script says the repo is not ready to run
# unattended, then block and fail very loudly. i really need to know before i
# go." So the preflight announces itself before it runs, and both outcomes are
# unmissable — the whole point is that the owner is about to walk away.
banner() { printf '\n%s\n' "════════════════════════════════════════════════════════════════════"; }

if [[ "${DELIVER_SKIP_READY:-0}" != "1" ]]; then
  echo "deliver-loop: checking whether this repository can run unattended…"
  # The refusal, not a warning (docs/DECISIONS.md): a run that cannot succeed
  # is refused at dispatch time, while someone can still act on it.
  if ! .github/scripts/unattended-ready.sh; then
    banner
    echo "  STOP — this repository is NOT ready to run unattended."
    echo "  Nothing has been dispatched. Fix the items listed above and re-run."
    banner
    exit 2
  fi
fi

# ------------------------------------------------------------ the identity
# owner-authored.sh compares the pull request's author login to the CODEOWNERS
# owner. Opening driver pull requests under the owner's own `gh` credentials
# makes that comparison pass for every pull request the driver has ever
# opened — including one carrying an agent's edit to docs/DESIGN.md. Minting
# here rather than at first use means the failure lands NOW, while the owner is
# still watching, instead of three phases in.
APP_TOKEN=""
if ! APP_TOKEN="$("$APP_TOKEN_CMD" 2>&1)"; then
  banner
  echo "  STOP — no usable GitHub App identity, so this run cannot be safe."
  echo
  printf '%s\n' "$APP_TOKEN" | sed 's/^/  /'
  echo
  echo "  Why this blocks the run rather than warning about it:"
  echo "  the driver would otherwise open pull requests as YOU, and"
  echo "  .github/scripts/owner-authored.sh would then report that"
  echo "  docs/DESIGN.md was 'landed by its owner' no matter which agent"
  echo "  wrote it. The guarantee would be printed and absent."
  echo
  echo "  Attended mode needs no App: run /deliver for a single pass and"
  echo "  merge by hand."
  banner
  exit 2
fi
[[ -n "$APP_TOKEN" ]] || die "the App token command printed nothing"
unset APP_TOKEN  # minted fresh per pull request; installation tokens last 1h

mkdir -p "$STATE_DIR"
# One identifier for this run, used for the evidence directory, its branch and
# its pull request, so all three can be found from any one of them.
#
# Disambiguated if a second run starts inside the same second — two runs sharing
# an id would append into one report and one branch, which is a record of
# neither. Rare in life, routine in the test suite, and the failure is silent.
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_N=1
while [[ -d "docs/runs/$RUN_ID" ]] \
   || git rev-parse -q --verify "refs/heads/docs/run-$RUN_ID" >/dev/null 2>&1; do
  RUN_N=$((RUN_N + 1))
  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$RUN_N"
done
RUN_DIR="docs/runs/$RUN_ID"
RUN_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PROCESSED_FILE="$STATE_DIR/processed-evidence"
touch "$PROCESSED_FILE"
SIG_FILE="$STATE_DIR/failure-signatures"
: > "$SIG_FILE"
# Per-RUN state, and it was not being cleared: a marker left by a previous run
# made the next one short-circuit to "the run is complete" on its first
# ACCEPTANCE iteration, having dispatched nothing. deliver-phase.sh promises
# that "recomputed state cannot go stale"; the driver's own persisted file was
# the exception, and it decided the most consequential thing in the run.
rm -f "$STATE_DIR/acceptance-dispatched"
{ echo "# Delivery run $RUN_ID"; echo; echo "Started $RUN_STARTED_AT."; echo; } >> "$STATE_DIR/run.md"

# ------------------------------------------------- the evidence, at every stop
#
# An EXIT trap rather than a call at each `exit`, because this script has eight
# of them and the one that would get forgotten is the one that fires at 3am. A
# stop that leaves no evidence is the failure this whole slice exists to fix, so
# it must not be possible to add a ninth exit and lose it.
#
# Everything here is best-effort and nothing here changes the run's exit code. A
# recorder that fails a run because it could not record has inverted its job.
LANDED=0
land_evidence() {
  local rc=$?
  [[ "$LANDED" -eq 1 ]] && return "$rc"
  LANDED=1
  # A dry run dispatches nothing, so it has nothing to report — and landing a
  # branch and a pull request for it would make the "show me what you would do"
  # flag do something.
  [[ "$DRY_RUN" -eq 1 ]] && return "$rc"
  [[ -f "$STATE_DIR/run.md" ]] || return "$rc"

  echo "deliver-loop: landing this run's evidence in $RUN_DIR ..."
  mkdir -p "$RUN_DIR"
  {
    cat "$STATE_DIR/run.md"
    echo
    echo "Stopped $(date -u +%Y-%m-%dT%H:%M:%SZ) with exit code $rc."
    echo
    echo "See .claude/scripts/deliver-loop.sh's header for what each exit code"
    echo "means. Every stop says why; none degrades silently."
  } > "$RUN_DIR/run.md"

  .claude/scripts/collect-evidence.sh --run-dir "$RUN_DIR" \
    --since "$RUN_STARTED_AT" 2>&1 | sed 's/^/deliver-loop: /' || true

  # On a branch and a pull request, never straight onto the default branch:
  # the same branch discipline every other change in this repository obeys, and
  # a `docs/` prefix so the plan check exempts it.
  # On a branch and a pull request, never straight onto the default branch: the
  # same branch discipline every other change here obeys, and a `docs/` prefix
  # so the plan check exempts it.
  #
  # ONE exit path, and it switches back. A stop that left the checkout sitting
  # on docs/run-<id> would make the next run refuse ("not on the default
  # branch") — the recorder breaking the thing it records.
  local ref="docs/run-$RUN_ID" token
  git switch -q "$DEFAULT_BRANCH" 2>/dev/null || true
  if git switch -qc "$ref" 2>/dev/null || git switch -q "$ref" 2>/dev/null; then
    git add "$RUN_DIR" 2>/dev/null || true
    if git diff --cached --quiet 2>/dev/null; then
      echo "deliver-loop: nothing to land."
    elif ! git commit -q -m "Run evidence for $RUN_ID" 2>/dev/null; then
      echo "deliver-loop: could not commit the run evidence."
    elif ! git push -q origin "$ref" 2>/dev/null; then
      echo "deliver-loop: could not push $ref — the evidence is committed locally."
    elif token="$("$APP_TOKEN_CMD" 2>/dev/null)" && [[ -n "$token" ]]; then
      GH_TOKEN="$token" "$GH" pr create --head "$ref" \
        --title "Run evidence for $RUN_ID" \
        --body "The run report and the review gate's payloads and replies, collected by .claude/scripts/collect-evidence.sh. Opened mechanically at the run's stop." \
        >/dev/null 2>&1 || echo "deliver-loop: could not open the pull request for $ref"
    else
      echo "deliver-loop: no App token — $ref is pushed but has no pull request."
    fi
  else
    echo "deliver-loop: could not create $ref — the report is at $RUN_DIR/run.md."
  fi
  git switch -q "$DEFAULT_BRANCH" 2>/dev/null || true
  return "$rc"
}
trap land_evidence EXIT

design_sha() { git rev-parse -q --verify "HEAD:docs/DESIGN.md" 2>/dev/null || echo none; }
vision_sha() { git rev-parse -q --verify "HEAD:docs/VISION.md" 2>/dev/null || echo none; }
STEER_DESIGN="$(design_sha)"; STEER_VISION="$(vision_sha)"

START_EPOCH="$(date +%s)"
PR_COUNT=0

# ----------------------------------------------------------------- the ceiling
# The owner's rulings, and they change the shape of this from what it was:
#
#   - the rate limit is the ONLY default stop. Pull requests, iterations and
#     wall clock stay available, opt-in, for a run where an early answer is all
#     that is wanted ("run 20 minutes; if it takes longer something is wrong").
#   - ask EVERY run. No silent default: a number the owner did not choose is a
#     number they will not recognise at 3am. The previous default of 25 points
#     was invented by the session that wrote the script.
#   - the window is WEEKLY. The 5-hour window resets mid-run and makes the delta
#     go negative; the 7-day one rarely does.
#
# WHICH ENVIRONMENT — decided by PROBING the gauge, not by guessing. If a
# reading comes back this is a terminal with a usage source; if it does not,
# this is a web session or a machine with nothing configured. That is a fact
# rather than an inference, so it cannot be wrong about a case nobody foresaw.
BUDGET_START=""; BUDGET_START_MODEL=""; BUDGET_RESET=""
if BUDGET_LINE="$(.claude/scripts/budget-probe.sh 2>/dev/null)"; then
  read_field() { sed -n "s/.*\\b$1=\\([^ ]*\\).*/\\1/p" <<<"$BUDGET_LINE" | head -1; }
  BUDGET_START="$(read_field week)"
  BUDGET_START_MODEL="$(read_field week_model)"
  BUDGET_RESET="$(read_field reset)"
fi

ask() { # ask <prompt> — one line from the owner, or empty when not a terminal
  local reply=""
  [[ -t 0 ]] || return 1
  read -r -p "$1" reply || return 1
  printf '%s' "$reply"
}

if [[ -n "$BUDGET_START" ]]; then
  if [[ -z "${BUDGET_POINTS_SET:-}" ]]; then
    banner
    echo "  Usage gauge found. Current weekly use: ${BUDGET_START}%"
    [[ "$BUDGET_START_MODEL" != "$BUDGET_START" ]] && \
      echo "  Per-model weekly use: ${BUDGET_START_MODEL}% (its own cap — either can stop the run)"
    echo "  Weekly window resets: ${BUDGET_RESET:-unknown}"
    banner
    reply="$(ask "  How many percentage points of your WEEKLY limit may this run spend? ")" || reply=""
    if [[ "$reply" =~ ^[0-9]+$ ]] && [[ "$reply" -gt 0 ]]; then
      BUDGET_POINTS="$reply"
    else
      die "no weekly allowance given, so this run has no ceiling.

The rate limit is the only stop that applies by default, and it needs a number
from you. Answer the prompt, or pass --budget-points <n>. If you want a run
bounded some other way instead — for a short test, say — pass --max-hours,
--max-prs or --max-iterations and those become the ceiling."
    fi
  fi
  log "budget: weekly at ${BUDGET_START}% (model ${BUDGET_START_MODEL}%), allowance ${BUDGET_POINTS} points, window resets ${BUDGET_RESET:-unknown}"
else
  # No gauge. Do not invent one — ask for the limits that CAN be counted here.
  if [[ "$MAX_PRS" -eq 0 && "$MAX_HOURS" -eq 0 && -z "${MAX_ITER_SET:-}" ]]; then
    banner
    echo "  No usage gauge is reachable here (a web session, or no reader configured)."
    echo "  So the percentage ceiling cannot apply, and this run needs a limit"
    echo "  it CAN count. Give at least one; blank means no limit of that kind."
    banner
    p="$(ask "  Max pull requests   (blank = none): ")" || p=""
    h="$(ask "  Max wall-clock hours (blank = none): ")" || h=""
    i="$(ask "  Max iterations       (blank = none): ")" || i=""
    [[ "$p" =~ ^[0-9]+$ ]] && MAX_PRS="$p"
    [[ "$h" =~ ^[0-9]+$ ]] && MAX_HOURS="$h"
    [[ "$i" =~ ^[0-9]+$ ]] && MAX_ITER="$i"
    if [[ "$MAX_PRS" -eq 0 && "$MAX_HOURS" -eq 0 && "$MAX_ITER" -eq 0 ]]; then
      die "no gauge and no limit, so nothing would ever stop this run.

In a web session the subscription percentage cannot be read, so a ceiling has
to be something countable here: pull requests, wall-clock hours, or iterations.
Give at least one — at the prompt, or as --max-prs / --max-hours /
--max-iterations."
    fi
  fi
  log "budget: no usage gauge — ceiling is $( \
    { [[ "$MAX_PRS"   -gt 0 ]] && printf '%s PRs, ' "$MAX_PRS"; \
      [[ "$MAX_HOURS" -gt 0 ]] && printf '%sh, ' "$MAX_HOURS"; \
      [[ "$MAX_ITER"  -gt 0 ]] && printf '%s iterations, ' "$MAX_ITER"; } | sed 's/, $//')"
fi

# ------------------------------------------------------------- dispatchers
mechanical_pr() { # mechanical_pr <source-branch> <head-ref> <title>
  # The commissioner's half of C5: a worker/<id> branch is neither docs/-
  # exempt nor slug-resolvable, so its head is pushed under a docs/-prefixed
  # name and the pull request opened from that. Mechanical — no judgment.
  #
  # The two refs may also be the SAME, which is how the feature and acceptance
  # pull requests use it: a feature branch must keep its `feat/<slug>` name or
  # plan-resolve.sh cannot match the slug against a plan.
  #
  # IDEMPOTENT. If a pull request already exists for the head ref, say so and
  # succeed. An attended session that opened its own, or an iteration retried
  # after a timeout, is a harmless race — and a driver that hard-failed on it
  # would turn that race into a stopped run. What covers the case where a
  # session opens one it should not is the tool grant above, which no longer
  # contains `gh pr create`, and the fixture that asserts so.
  git push -q origin "$1:$2" || { log "push $2 failed"; return 1; }
  if [[ -n "$("$GH" pr list --head "$2" --state open --limit 1 \
                --json number --jq '.[].number' 2>/dev/null)" ]]; then
    log "a pull request is already open for $2 — not opening a second one"
    PR_COUNT=$((PR_COUNT + 1))
    return 0
  fi
  # Opened as the App, never as the owner. This is the line that makes
  # owner-authored.sh a real boundary instead of a formality: `app[bot]` is not
  # the CODEOWNERS owner, so a driver-opened pull request touching
  # docs/DESIGN.md or docs/VISION.md fails that check — which is the intended
  # behaviour, because the driver has no business landing either document.
  # Minted per pull request because installation tokens expire in an hour and a
  # long run outlives one. The value is passed in the environment of a single
  # command, so it never reaches argv, the run log, or `ps`.
  local token
  if ! token="$("$APP_TOKEN_CMD" 2>/dev/null)" || [[ -z "$token" ]]; then
    log "could not mint an App token for $2 — refusing to open this pull request as the owner"
    return 1
  fi
  GH_TOKEN="$token" "$GH" pr create --head "${2}" \
    --title "$3" \
    --body "Opened mechanically by deliver-loop.sh, as the GitHub App. The content is the branch; the gates are the review." \
    >/dev/null || { log "gh pr create for $2 failed"; return 1; }
  PR_COUNT=$((PR_COUNT + 1))
}

run_worker() { # run_worker <id> <role> <prompt> <docs-ref> <pr-title>
  local id="$1" role="$2" prompt="$3" ref="$4" title="$5"
  log "dispatch $role worker ($id)"
  if ! timeout "$SESSION_TIMEOUT" "$SPAWN" --id "$id" --role "$role" \
       --engine "$ENGINE" --base "$DEFAULT_BRANCH" --prompt "$prompt" \
       >> "$STATE_DIR/run.md" 2>&1; then
    log "$role worker failed — see .claude/orchestration-logs/$id.log"
    return 1
  fi
  mechanical_pr "worker/$id" "$ref" "$title"
}

run_session() { # run_session <label> <prompt>
  log "dispatch $1 session"
  local -a cmd
  mapfile -t cmd < <(orch_cmd "$2")
  if ! timeout "$SESSION_TIMEOUT" "${cmd[@]}" >> "$STATE_DIR/run.md" 2>&1; then
    log "$1 session failed or timed out"
    return 1
  fi
}

record_dismissed_evidence() {
  # The newest handoff's "do not act" list, plus everything the run just made
  # citable — recorded so the loop cannot thrash re-running the oracle over
  # evidence it already ruled on or dismissed. Coarse: any id the newest
  # handoff mentions is one the oracle has READ, which is all "processed"
  # claims.
  local newest
  newest="$(find docs/oracle -name 'handoff-*.md' 2>/dev/null | sort | tail -1)"
  [[ -n "$newest" ]] || return 0
  grep -oE '(ESC|BL)-[0-9]+' "$newest" | sort -u >> "$PROCESSED_FILE"
  sort -u "$PROCESSED_FILE" -o "$PROCESSED_FILE"
}

wait_on_pr() { # wait_on_pr <number> <headref>
  local pr="$1" headref="$2" rc=0
  log "waiting on PR #$pr ($headref) — mechanical watch, no model budget"
  timeout "$WAIT_TIMEOUT" "$GH" pr checks "$pr" --watch --interval 30 \
    >/dev/null 2>&1 || rc=$?
  if [[ "$rc" -eq 124 ]]; then
    log "checks still pending after ${WAIT_TIMEOUT}s — re-detecting"
    return 0
  fi
  if [[ "$rc" -eq 0 ]]; then
    # Green. The exit condition was "no check still pending", and that has
    # been met; now the merge is auto-merge's job. Give it a grace period.
    local waited=0
    while [[ "$waited" -lt 600 ]]; do
      state="$("$GH" pr view "$pr" --json state --jq .state 2>/dev/null)"
      [[ "$state" == "MERGED" ]] && { log "PR #$pr merged"; return 0; }
      [[ "$state" == "CLOSED" ]] && { log "PR #$pr closed unmerged — investigate"; return 0; }
      sleep 30; waited=$((waited + 30))
    done
    # Green and open: an owner-owned path (CODEOWNERS) is the designed cause.
    if [[ "$WAIT_FOR_OWNER" -eq 1 ]]; then
      log "PR #$pr is green and waiting on the owner — polling (--wait-for-owner)"
      sleep 600; return 0
    fi
    log "PR #$pr is green and only the owner can merge it — stopping to report"
    exit 4
  fi
  # Red. Same signature three times is a pattern, not a blip.
  local failing sig count
  failing="$("$GH" pr checks "$pr" 2>/dev/null | awk -F'\t' '$2=="fail"{print $1}' | sort | tr '\n' ' ')"
  sig="$(printf '%s|%s' "$headref" "$failing" | sha1sum | awk '{print $1}')"
  count="$(grep -cxF "$sig" "$SIG_FILE" || true)"
  echo "$sig" >> "$SIG_FILE"
  if [[ "$count" -ge 2 ]]; then
    log "the same checks failed three times on $headref (${failing:-unknown}) — stopping (deliver.md step 5)"
    exit 3
  fi
  log "PR #$pr red (${failing:-unknown}) — dispatching a fix"
  run_session "fix" "PR #$pr on branch $headref has failing required checks: ${failing:-see gh pr checks $pr}. Diagnose from the check output, fix ON THE EXISTING BRANCH ($headref), and push — the open pull request updates; never open a second one. Reproduce the failure locally before pushing. Never weaken a test or a gate to get green." \
    || true
}

# ------------------------------------------------------------- the loop
ITER=0
while :; do
  ITER=$((ITER + 1))
  if [[ "$MAX_ITER" -gt 0 && "$ITER" -gt "$MAX_ITER" ]]; then
    log "iteration limit ($MAX_ITER) reached"
    exit 5
  fi
  if [[ "$ITER" -gt "$HARD_MAX_ITER" ]]; then
    # Not an allowance. Reaching this means the loop kept choosing a phase and
    # never finished one — a livelock, not a run that ran out of room — so it
    # is reported as the bug it is rather than as a spent budget.
    log "STOPPED after $HARD_MAX_ITER iterations without finishing. This is not a"
    log "budget stop: the loop kept picking work and never converged. Read the"
    log "phase lines above — the same phase repeating is the diagnosis."
    exit 5
  fi

  if [[ "${DELIVER_SKIP_PULL:-0}" != "1" ]] && git remote get-url origin >/dev/null 2>&1; then
    git pull -q --ff-only origin "$DEFAULT_BRANCH" 2>/dev/null \
      || log "pull --ff-only failed; continuing on the local tree"
  fi

  # The steering lever working is not an error: the owner edited the design
  # layer, so everything derived from it is re-derived and failure counters
  # reset — a "pattern" spanning an owner edit is two different runs.
  if [[ "$(design_sha)" != "$STEER_DESIGN" || "$(vision_sha)" != "$STEER_VISION" ]]; then
    log "owner edited the design layer — re-deriving everything, resetting failure counters"
    STEER_DESIGN="$(design_sha)"; STEER_VISION="$(vision_sha)"
    : > "$SIG_FILE"
  fi

  # Ceilings. Each applies only if the owner set it — zero means "not a limit",
  # per the ruling that the rate limit is the only stop by default.
  ELAPSED_H=$(( ($(date +%s) - START_EPOCH) / 3600 ))
  if [[ "$MAX_HOURS" -gt 0 && "$ELAPSED_H" -ge "$MAX_HOURS" ]]; then
    log "wall-clock limit (${MAX_HOURS}h) reached"; exit 6
  fi
  if [[ "$MAX_PRS" -gt 0 && "$PR_COUNT" -ge "$MAX_PRS" ]]; then
    log "pull-request limit (${MAX_PRS}) reached"; exit 6
  fi
  if [[ -n "$BUDGET_START" ]] && out="$(.claude/scripts/budget-probe.sh 2>/dev/null)"; then
    f() { sed -n "s/.*\\b$1=\\([^ ]*\\).*/\\1/p" <<<"$out" | head -1; }
    now_reset="$(f reset)"
    if [[ -n "$BUDGET_RESET" && "$BUDGET_RESET" != "unknown" && "$now_reset" != "$BUDGET_RESET" ]]; then
      # The weekly window rolled over mid-run. Every delta against the old
      # baseline is now meaningless — and negative — so re-baseline rather than
      # measure nonsense, and say so, because the allowance silently restarting
      # is a thing the owner should know happened.
      log "the weekly window reset mid-run (${BUDGET_RESET} -> ${now_reset}) — re-baselining the allowance"
      BUDGET_START="$(f week)"; BUDGET_START_MODEL="$(f week_model)"; BUDGET_RESET="$now_reset"
    else
      # Both weekly limits count. The per-model cap is separate and smaller, so
      # a run can exhaust it while the all-models number still looks healthy —
      # and the oracle runs on its own model tier, which is exactly the case.
      # Whichever has moved furthest is the one that binds.
      spent_all="$(awk -v a="$(f week)" -v b="$BUDGET_START" 'BEGIN{print (a-b)}')"
      spent_mod="$(awk -v a="$(f week_model)" -v b="${BUDGET_START_MODEL:-$BUDGET_START}" 'BEGIN{print (a-b)}')"
      spent="$(awk -v x="$spent_all" -v y="$spent_mod" 'BEGIN{print (x>y?x:y)}')"
      which="$(awk -v x="$spent_all" -v y="$spent_mod" 'BEGIN{print (x>y?"weekly":"per-model weekly")}')"
      if awk -v s="$spent" -v cap="$BUDGET_POINTS" 'BEGIN{exit !(s >= cap)}'; then
        log "allowance spent: ${spent} of ${BUDGET_POINTS} points on the ${which} limit"
        exit 6
      fi
    fi
  fi

  # What next? Recomputed from the world, never remembered.
  PHASE=""; PR=""; HEADREF=""; UNRULED=""; UNCITED=""; ODS=""; REQS=""; SLUG=""; REASON=""
  CRITERIA=""
  while IFS='=' read -r k v; do
    case "$k" in
      PHASE) PHASE="$v" ;; PR) PR="$v" ;; HEADREF) HEADREF="$v" ;;
      UNRULED) UNRULED="$v" ;; UNCITED) UNCITED="$v" ;; ODS) ODS="$v" ;;
      REQS) REQS="$v" ;; SLUG) SLUG="$v" ;; REASON) REASON="$v" ;;
      CRITERIA) CRITERIA="$v" ;;
    esac
  done < <(GH="$GH" PROCESSED_FILE="$PROCESSED_FILE" "$PHASE_SH")
  [[ -n "$PHASE" ]] || die "phase detection failed"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "PHASE=$PHASE"
    for kv in "PR=$PR" "HEADREF=$HEADREF" "UNRULED=$UNRULED" "UNCITED=$UNCITED" \
              "ODS=$ODS" "REQS=$REQS" "SLUG=$SLUG" "REASON=$REASON" \
              "CRITERIA=$CRITERIA"; do
      [[ -n "${kv#*=}" ]] && echo "$kv"
    done
    exit 0
  fi

  log "iteration $ITER: phase $PHASE"
  case "$PHASE" in
    SETUP)
      log "setup problem: $REASON — /design is interactive and owner-landed; the loop cannot do it"
      exit 2 ;;
    WAIT)
      wait_on_pr "$PR" "$HEADREF" ;;
    ORACLE)
      scope="Scope for this run: ${UNRULED:+rule on the filed uncertainties: $UNRULED.} ${UNCITED:+work the logged evidence: $UNCITED.}"
      run_worker "oracle-$(date -u +%Y%m%d%H%M%S)" oracle \
        "$(cat .claude/commands/oracle.md)

UNATTENDED RUN. The delivery driver commissioned this session. $scope" \
        "docs/oracle-$(date -u +%Y%m%d%H%M%S)" \
        "Oracle: rulings and handoff" || true
      record_dismissed_evidence ;;
    STEWARD)
      od="${ODS%% *}"
      run_worker "steward-${od,,}" steward \
        "$(cat .claude/commands/steward.md)

UNATTENDED RUN. The decision to plan: $od" \
        "docs/oracle-plan-${od,,}" \
        "Plan for $od" || true ;;
    PLAN)
      run_worker "plan-$(date -u +%Y%m%d%H%M%S)" steward \
        "$(cat .claude/commands/plan.md)

UNATTENDED. The delivery driver commissioned this session; follow the
unattended branches of the gate above. Requirements still unplanned: $REQS.
Plan the next milestone of docs/DESIGN.md that delivers them (or file the
uncertainties that block it)." \
        "docs/plan-$(date -u +%Y%m%d%H%M%S)" \
        "Plan: next milestone ($REQS)" || true ;;
    ORCHESTRATE)
      # UNATTENDED RUN is the marker the worker prompts have always carried and
      # this dispatch did not — which is exactly how it kept opening its own
      # pull request as the owner through the whole of ESC-26's remediation. A
      # command file that cannot tell which mode it is in has to write prose
      # that is right for both, and "open the pull request" was right for one.
      if run_session "orchestrate" "/orchestrate $SLUG

UNATTENDED RUN. The delivery driver commissioned this session. Build the
feature, commit it, and PUSH feat/$SLUG — then stop. Do NOT open the pull
request: you have no grant to, and the driver opens it as the GitHub App so it
is not authored by the owner."; then
        if git rev-parse -q --verify "refs/heads/feat/$SLUG" >/dev/null 2>&1; then
          mechanical_pr "feat/$SLUG" "feat/$SLUG" "Build: $SLUG" || true
        else
          log "orchestrate session finished but feat/$SLUG does not exist — nothing to open"
        fi
      fi ;;
    ACCEPTANCE)
      # The marker used to be written BEFORE the session ran, and the dispatch
      # is `|| true`, and run start never cleared it. So an acceptance session
      # that timed out, failed, or exited 0 having written nothing produced
      # "the run is complete" and exit 0 — whose documented meaning is "the
      # acceptance pass ran" — with docs/acceptance.md left as the shipped
      # skeleton. Worse, the marker outlived the run, so every later invocation
      # in the same clone short-circuited to exit 0 on its first ACCEPTANCE
      # iteration, having dispatched nothing at all.
      #
      # That mattered more than its size suggests: docs/acceptance.md is the
      # ONE artifact in an unattended run whose pull request requires the
      # owner's review, so it is the single guaranteed connection between the
      # run and a human — and this severed it while reporting success.
      #
      # Now the marker means what its name says: an acceptance session ran and
      # produced something. It is written after the session returns, only if
      # the session succeeded, and only if docs/acceptance.md actually changed.
      if [[ -f "$STATE_DIR/acceptance-dispatched" ]]; then
        log "acceptance recorded and nothing is open — the run is complete"
        log "report: $RUN_DIR/run.md (landed at the stop); the honest bottom line is the pending-on-owner list in docs/acceptance.md"
        exit 0
      fi
      ACC_BEFORE="$(git rev-parse -q --verify "HEAD:docs/acceptance.md" 2>/dev/null || echo none)"
      ACC_REF="docs/acceptance-$RUN_ID"
      if run_session "acceptance" "UNATTENDED RUN. The delivery driver commissioned this session. /deliver — run ONLY step 6, the acceptance pass: check the built system against docs/DESIGN.md §13, record evidence per criterion in docs/acceptance.md, mark owner-only criteria pending with exactly what the owner should run. Every criterion §13 does NOT mark (owner) is a script at acceptance/S<n>.sh — write it, run it, and cite its real output; the required check .github/scripts/acceptance-criteria.sh runs them on every pull request from then on.${CRITERIA:+ Scripts failing right now: $CRITERIA.} A failing criterion is recorded as fail AND filed as a BL-<n> under 'Uncertainties awaiting oracle ruling' in docs/BACKLOG.md, so the oracle can rule on it — never reclassified as (owner) and never quietly passed. Commit it on the branch $ACC_REF and PUSH it — then stop. Do NOT open the pull request: you have no grant to, and the driver opens it as the GitHub App. That is not bookkeeping — docs/acceptance.md is CODEOWNERS-owned, and GitHub does not let an author approve their own pull request, so a pull request opened under the owner's identity is one THEY cannot approve. It is the single artifact of this run whose review is the point."; then
        ACC_AFTER="$(git rev-parse -q --verify "HEAD:docs/acceptance.md" 2>/dev/null || echo none)"
        if [[ "$ACC_AFTER" != "$ACC_BEFORE" ]] || [[ -n "$(git status --porcelain -- docs/acceptance.md)" ]]; then
          if git rev-parse -q --verify "refs/heads/$ACC_REF" >/dev/null 2>&1; then
            mechanical_pr "$ACC_REF" "$ACC_REF" "Acceptance: the built system against docs/DESIGN.md §13" || true
          else
            log "acceptance session changed docs/acceptance.md but left no $ACC_REF branch to open"
          fi
          touch "$STATE_DIR/acceptance-dispatched"
        else
          # Exit 0 having written nothing is the exact failure spawn-worker.sh's
          # empty-branch check exists to catch for workers; this dispatch path
          # does not use it, so the emptiness is checked here instead.
          log "acceptance session exited cleanly but docs/acceptance.md is unchanged — NOT recording it as done"
          ACCEPT_EMPTY=$((${ACCEPT_EMPTY:-0} + 1))
          if [[ "${ACCEPT_EMPTY}" -ge 2 ]]; then
            log "the acceptance pass produced nothing twice — stopping rather than reporting a complete run"
            exit 3
          fi
        fi
      else
        log "acceptance session failed or timed out — NOT recording it as done; the next iteration will try again"
        ACCEPT_FAILS=$((${ACCEPT_FAILS:-0} + 1))
        if [[ "${ACCEPT_FAILS}" -ge 2 ]]; then
          log "the acceptance pass failed twice — stopping rather than reporting a complete run"
          exit 3
        fi
      fi
      PR_COUNT=$((PR_COUNT + 1)) ;;
    *)
      die "unknown phase '$PHASE'" ;;
  esac
done
