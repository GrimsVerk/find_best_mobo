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
#   --base <branch>        the base branch this run merges into (default: the
#                          repository's default branch). SAID OUT LOUD at run
#                          start, so with several drivers running you always
#                          know which branch belongs to which. The checkout
#                          must BE on this branch. Every pull-request query is
#                          scoped to it (one pipeline PR in flight PER BASE —
#                          two runs on two bases never wait on or fix each
#                          other's pull requests), every worker branches off
#                          it, and every pull request is opened --base onto it.
#                          On a non-default base, every branch this run pushes
#                          gets a `--<base>` suffix so twin runs building the
#                          same slugs cannot collide on branch names. The base
#                          branch must be covered by the gates ruleset —
#                          unattended-ready.sh refuses when it is not; add it
#                          with scripts/setup-github.sh --gate-branch <branch>.
#   --land-evidence        land a PREVIOUS run's leftover report buffer and its
#                          collected evidence NOW, dispatching nothing, then
#                          exit. For a run killed too hard for its EXIT landing
#                          to fire (SIGKILL, a crashed machine, a pulled plug):
#                          its report survives in the gitignored buffer, where
#                          normally the NEXT run sets it aside and lands it —
#                          but a one-shot run, a finished test lane, or a
#                          machine being retired has no next run, and evidence
#                          waiting on one is evidence dying by default. Pass
#                          the same --base the dead run used, so the evidence
#                          lands in that run's own lane. Skips the readiness,
#                          identity, worktree and budget preflights on purpose:
#                          a recovery that refuses because the repository is no
#                          longer fit to RUN would be refusing to record that
#                          very fact. Degrades without an App identity — the
#                          branch still pushes; only the pull request is
#                          skipped, and it says so.
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
WAIT_FOR_OWNER=0; DRY_RUN=0; PRINT_PHASE=""; BASE_FLAG=""; LAND_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)           BASE_FLAG="${2:-}"; shift 2 ;;
    --land-evidence)  LAND_ONLY=1; shift ;;
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
# Overridable so the fixtures can substitute a worker without editing a
# tracked file (which the dirty-tree preflight would then refuse).
SPAWN="${DELIVER_SPAWN:-.claude/scripts/spawn-worker.sh}"
PHASE_SH=".claude/scripts/deliver-phase.sh"
STATE_DIR=".claude/deliver-loop"
DEFAULT_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
[[ -n "$DEFAULT_BRANCH" ]] || DEFAULT_BRANCH="$(git branch --show-current)"

# THE RUN'S BASE BRANCH — established here, once, and announced before anything
# is dispatched. Everything this run does is scoped to it: the phase detector
# only sees pull requests targeting it (one pipeline PR in flight PER BASE),
# workers branch off it, and every mechanical pull request is opened onto it.
# That scoping is what lets two drivers share one repository on two separate
# base branches without waiting on — or worse, pushing fixes into — each
# other's pull requests. Two runs on ONE base is still illegal, and the
# detector's WAIT phase is what enforces it.
RUN_BASE="${BASE_FLAG:-$DEFAULT_BRANCH}"

# On a non-default base, every branch this run pushes carries a `--<base>`
# suffix. Twin runs building the same design produce the same plan slugs, so
# without the suffix both would push `feat/<slug>` and `docs/oracle-plan-od-1`
# and collide. The suffix keeps the `feat/`/`docs/` prefixes (which the plan
# check reads) and keeps the slug a substring of the branch name (which
# plan-resolve.sh matches); the default-base run stays unsuffixed, so a
# single-run repository behaves exactly as before.
LANE=""
if [[ "$RUN_BASE" != "$DEFAULT_BRANCH" ]]; then
  LANE="--$(printf '%s' "$RUN_BASE" | tr -c 'A-Za-z0-9._-' '-')"
fi

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
               --engine claude --base "$RUN_BASE" --prompt "<oracle.md + scope>" ;;
    steward) "$SPAWN" --print-command --id steward-ODN --role steward \
               --engine claude --base "$RUN_BASE" --prompt "<steward.md + OD id>" ;;
    plan)    "$SPAWN" --print-command --id plan-N --role steward \
               --engine claude --base "$RUN_BASE" --prompt "<plan.md + UNATTENDED + milestone>" ;;
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

# The dirty-tree refusal guards a RUN, whose state is recomputed from the
# tree. It must NOT guard --land-evidence (ESC-60, anvil F13): the exact
# failure that mode exists for — an evidence commit that died half way —
# ALWAYS leaves the tree dirty with the very files to be landed, so refusing
# a dirty tree made the documented rescue unrunnable after every failure it
# was built to rescue, and cleaning by hand destroys the evidence. Landing
# tolerates dirt confined to the evidence paths (docs/runs/ and the driver's
# own state dir) and still refuses anything else: dirt in project space is
# not evidence and not this mode's to sweep up.
if [[ "$LAND_ONLY" -eq 1 ]]; then
  DIRT="$(git status --porcelain | awk '{print $2}' \
    | grep -vE '^docs/runs/|^\.claude/deliver-loop/' || true)"
  [[ -z "$DIRT" ]] \
    || die "the working tree carries changes OUTSIDE the evidence paths (docs/runs/, .claude/deliver-loop/) — landing only sweeps up a dead run's evidence, not project work: $(head -3 <<<"$DIRT" | tr '\n' ' ')"
else
  [[ -z "$(git status --porcelain)" ]] \
    || die "the working tree is dirty — a run recomputes state from the tree, and uncommitted changes make that state a lie"
fi
CURRENT_BRANCH="$(git branch --show-current)"
[[ "$CURRENT_BRANCH" == "$RUN_BASE" ]] \
  || die "on branch '$CURRENT_BRANCH', but this run's base is '$RUN_BASE' — the driver dispatches from its base branch only. Switch to it, or name the intended base with --base <branch>"
# A dead run routinely leaves worktrees behind — that is part of what makes it
# a dead run — so the recovery path must not refuse over the very debris it is
# there to record.
if [[ "$LAND_ONLY" -eq 0 ]] \
   && [[ -d .worktrees ]] && [[ -n "$(ls -A .worktrees 2>/dev/null)" ]]; then
  die "leftover worktrees under .worktrees/ — a previous run did not finish assembling; inspect and remove them first"
fi

# ------------------------------------------------- readiness, said out loud
# The owner's ruling: "if the script says the repo is not ready to run
# unattended, then block and fail very loudly. i really need to know before i
# go." So the preflight announces itself before it runs, and both outcomes are
# unmissable — the whole point is that the owner is about to walk away.
banner() { printf '\n%s\n' "════════════════════════════════════════════════════════════════════"; }

# WHICH BRANCH BELONGS TO WHICH RUN — said before anything else, every run.
# The owner's ruling: with several drivers running at once, each session must
# establish exactly which branch it considers its base, out loud, at start.
banner
echo "  THIS RUN'S BASE BRANCH: $RUN_BASE"
echo "  Every pull request this run opens will merge into '$RUN_BASE',"
echo "  and this run waits only on pull requests targeting '$RUN_BASE'."
if [[ -n "$LANE" ]]; then
  echo "  Non-default base: every branch this run pushes is suffixed '$LANE'."
fi
banner

if [[ "${DELIVER_SKIP_READY:-0}" != "1" && "$LAND_ONLY" -eq 0 ]]; then
  echo "deliver-loop: checking whether this repository can run unattended…"
  # The refusal, not a warning (docs/DECISIONS.md): a run that cannot succeed
  # is refused at dispatch time, while someone can still act on it. RUN_BASE
  # travels along so the readiness check verifies the gates bind on THIS run's
  # base branch, not only on the default one.
  if ! RUN_BASE="$RUN_BASE" .github/scripts/unattended-ready.sh; then
    banner
    echo "  STOP — this repository is NOT ready to run unattended."
    echo "  Nothing has been dispatched. Fix the items listed above and re-run."
    banner
    exit 2
  fi
fi

# Workspace trust (anvil F6). An untrusted workspace makes the claude engine
# silently DROP the permissions.allow entries in .claude/settings.json — the
# workers run with a quieter grant than the template believes it granted, and
# the only trace is one line at the top of each worker's own log. Refuse now,
# loudly, while someone can act, rather than run every worker degraded. jq is
# already a hard dependency of the pipeline's scripts.
if [[ "${DELIVER_SKIP_READY:-0}" != "1" && "$LAND_ONLY" -eq 0 ]]; then
  CLAUDE_CFG="${CLAUDE_CONFIG_PATH:-$HOME/.claude.json}"
  if [[ -f "$CLAUDE_CFG" ]] \
     && ! jq -e --arg p "$ROOT" '.projects[$p].hasTrustDialogAccepted == true' \
          "$CLAUDE_CFG" >/dev/null 2>&1; then
    banner
    echo "  STOP — this workspace is not trusted by the claude engine."
    echo "  Untrusted, the engine drops the permissions.allow entries in"
    echo "  .claude/settings.json and every worker runs with a narrower grant"
    echo "  than the one this repository documents. Run claude interactively"
    echo "  here once and accept the trust dialog, then re-run."
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
# The identity refusal guards a RUN — pull requests must not be opened as the
# owner. Landing evidence opens at most one, and land_evidence() already
# degrades honestly without a token (the branch pushes; the missing pull
# request is said out loud). A recovery that refuses for want of an App would
# hold a dead run's only record hostage to configuration.
APP_TOKEN=""
if [[ "$LAND_ONLY" -eq 1 ]]; then
  :
elif ! APP_TOKEN="$("$APP_TOKEN_CMD" 2>&1)"; then
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
[[ "$LAND_ONLY" -eq 1 || -n "$APP_TOKEN" ]] || die "the App token command printed nothing"
unset APP_TOKEN  # minted fresh per pull request; installation tokens last 1h

mkdir -p "$STATE_DIR"
if [[ "$LAND_ONLY" -eq 1 ]]; then
  # LANDING A DEAD RUN'S BUFFER, NOT STARTING A RUN. The buffer is the run
  # being landed: no rotation (that would file it as "unlanded" beside a run
  # that does not exist), no new header (it carries its own), no touching the
  # per-run state a post-mortem has no business resetting. The evidence lands
  # under the dead run's OWN id, read from its header, so the report, the
  # branch and the pull request are named for the run they record.
  if [[ ! -s "$STATE_DIR/run.md" ]]; then
    echo "deliver-loop: no leftover run buffer — nothing to land."
    exit 0
  fi
  PREV_RUN="$(sed -n 's/^# Delivery run //p' "$STATE_DIR/run.md" | head -1)"
  RUN_ID="${PREV_RUN:-$(date -u +%Y%m%dT%H%M%SZ)-recovered}"
  # Collision means COMMITTED — at HEAD, or as a landing branch. An
  # uncommitted docs/runs/<id>/ on disk is not a collision, it is the dead
  # run's own stranded evidence (the died-commit case this mode exists for,
  # ESC-60), and dodging to a -recovered id would land the buffer while
  # abandoning exactly those files.
  while git rev-parse -q --verify "HEAD:docs/runs/$RUN_ID" >/dev/null 2>&1 \
     || git rev-parse -q --verify "refs/heads/docs/run-$RUN_ID$LANE" >/dev/null 2>&1; do
    RUN_ID="$RUN_ID-recovered"
  done
  RUN_DIR="docs/runs/$RUN_ID"
  # collect-evidence needs a --since; the run id IS a UTC timestamp, so derive
  # it, falling back to a day ago when the header did not parse.
  RUN_STARTED_AT="$(date -u -d "${PREV_RUN:0:8} ${PREV_RUN:9:2}:${PREV_RUN:11:2}:${PREV_RUN:13:2}" \
                    +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
  [[ -n "$RUN_STARTED_AT" ]] \
    || RUN_STARTED_AT="$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
                         || date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "deliver-loop: landing the leftover buffer of run ${PREV_RUN:-<unknown>} — dispatching nothing."
else
# One identifier for this run, used for the evidence directory, its branch and
# its pull request, so all three can be found from any one of them.
#
# Disambiguated if a second run starts inside the same second — two runs sharing
# an id would append into one report and one branch, which is a record of
# neither. Rare in life, routine in the test suite, and the failure is silent.
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_N=1
while [[ -d "docs/runs/$RUN_ID" ]] \
   || git rev-parse -q --verify "refs/heads/docs/run-$RUN_ID$LANE" >/dev/null 2>&1; do
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
# THE BUFFER CARRIES ONE RUN. It is appended to during the run and landed at
# the stop — but a run killed too hard for its EXIT trap to fire leaves its
# lines behind, and the next run's landed report then opened with the previous
# run's header (ESC-44: a report named for one run began with another run's).
# Wiping would destroy the dead run's only evidence — the exact defect this
# whole arrangement repairs — so a leftover buffer is set aside under the run
# id its own first line names, and land_evidence ships it beside THIS run's
# report, labeled as what it is. (When there is no next run to do this, the
# dead run's owner runs --land-evidence instead, which lands the buffer under
# its own id directly — see the branch above.)
if [[ -s "$STATE_DIR/run.md" ]]; then
  PREV_RUN="$(sed -n 's/^# Delivery run //p' "$STATE_DIR/run.md" | head -1)"
  cat "$STATE_DIR/run.md" >> "$STATE_DIR/unlanded-${PREV_RUN:-unknown}.md" \
    && rm -f "$STATE_DIR/run.md"
fi
{ echo "# Delivery run $RUN_ID"; echo
  echo "Started $RUN_STARTED_AT."
  echo "Base branch: $RUN_BASE${LANE:+ (branch suffix '$LANE')}."; echo
} >> "$STATE_DIR/run.md"
fi

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
    if [[ "$LAND_ONLY" -eq 1 ]]; then
      # No invented exit code: this run's stop was never recorded, and writing
      # one here would be the report lying about the one thing it exists to
      # tell the truth about.
      echo "Landed post-mortem $(date -u +%Y-%m-%dT%H:%M:%SZ) by --land-evidence:"
      echo "the run stopped without its exit landing firing, so its stop and"
      echo "its exit code were never recorded. The last lines above are the"
      echo "closest thing to a cause of death this report can offer."
    else
      echo "Stopped $(date -u +%Y-%m-%dT%H:%M:%SZ) with exit code $rc."
      echo
      echo "See .claude/scripts/deliver-loop.sh's header for what each exit code"
      echo "means. Every stop says why; none degrades silently."
    fi
  } > "$RUN_DIR/run.md"

  # A previous run's set-aside buffer (the run-start rotation above) travels
  # with this run's evidence, under unlanded/ rather than inside this run's
  # report — preserved, and labeled as what it is.
  if compgen -G "$STATE_DIR/unlanded-*.md" >/dev/null 2>&1; then
    mkdir -p "$RUN_DIR/unlanded"
    cp "$STATE_DIR"/unlanded-*.md "$RUN_DIR/unlanded/" 2>/dev/null || true
  fi

  RUN_BASE="$RUN_BASE" .claude/scripts/collect-evidence.sh --run-dir "$RUN_DIR" \
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
  # CUT FROM THE REMOTE TIP, NOT THE LOCAL ONE (ESC-70). The gates ruleset sets
  # strict_required_status_checks_policy, so a pull request must be up to date
  # with its base to merge. The evidence branch is cut at the STOP, from a
  # checkout that is two or three merges old by then, so it was born BEHIND —
  # and the only job that brings stale branches up to date, update-open-prs,
  # fires on a merge. The evidence pull request is by construction the LAST
  # pull request of a run, so no further merge happens on that base and nothing
  # ever updates it: eleven green checks, auto-merge armed by the App, waiting
  # for ever on a condition that cannot change. Observed live, and it is the
  # answer to ESC-40 — the evidence pull request never merged because it could
  # not. Fetching first costs one network call at a stop that is already
  # talking to the remote.
  local ref="docs/run-$RUN_ID$LANE" token base_point="$RUN_BASE"
  git fetch -q origin "$RUN_BASE" 2>/dev/null \
    && git rev-parse -q --verify FETCH_HEAD >/dev/null 2>&1 \
    && base_point="FETCH_HEAD"
  git switch -q "$RUN_BASE" 2>/dev/null || true
  if git switch -qc "$ref" "$base_point" 2>/dev/null || git switch -q "$ref" 2>/dev/null; then
    git add "$RUN_DIR" 2>/dev/null || true
    if git diff --cached --quiet 2>/dev/null; then
      echo "deliver-loop: nothing to land."
    elif ! git commit -q -m "Run evidence for $RUN_ID" 2>/dev/null; then
      echo "deliver-loop: could not commit the run evidence."
    else
      # Committed: the buffer's content is in git history now, so the buffer is
      # cleared. Left in place, the NEXT run's start rotation would set an
      # already-landed report aside as "unlanded" and land it a second time —
      # the mirror image of ESC-44. Kept when the commit failed, because then
      # the buffer is still the only copy.
      : > "$STATE_DIR/run.md"
      rm -f "$STATE_DIR"/unlanded-*.md 2>/dev/null
      if ! git push -q origin "$ref" 2>/dev/null; then
        echo "deliver-loop: could not push $ref — the evidence is committed locally."
      elif token="$("$APP_TOKEN_CMD" 2>/dev/null)" && [[ -n "$token" ]]; then
        GH_TOKEN="$token" "$GH" pr create --head "$ref" --base "$RUN_BASE" \
          --title "Run evidence for $RUN_ID" \
          --body "The run report and the review gate's payloads and replies, collected by .claude/scripts/collect-evidence.sh. Opened mechanically at the run's stop." \
          >/dev/null 2>&1 || echo "deliver-loop: could not open the pull request for $ref"
      else
        echo "deliver-loop: no App token — $ref is pushed but has no pull request."
      fi
    fi
  else
    echo "deliver-loop: could not create $ref — the report is at $RUN_DIR/run.md."
  fi
  git switch -q "$RUN_BASE" 2>/dev/null || true
  return "$rc"
}
trap land_evidence EXIT

# Landing is the EXIT trap's job, so a land-only invocation is done the moment
# the trap is armed. Exiting here also keeps the budget interview, the steering
# snapshot and the loop out of a code path whose whole point is that the run
# they belong to is already dead.
if [[ "$LAND_ONLY" -eq 1 ]]; then
  exit 0
fi

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
  # reset= is the probe's LAST field by contract and its value contains
  # spaces ("Aug 20, 11am (Europe/Amsterdam)"), so it is captured to end of
  # line — the word-parse truncated it to a bare month (anvil mobo F13), and
  # since BOTH sides of the rollover comparison truncated identically, the
  # mid-run re-baseline could never fire.
  read_reset() { sed -n "s/.*\\breset=\\(.*\\)$/\\1/p" <<<"$BUDGET_LINE" | head -1; }
  BUDGET_START="$(read_field week)"
  BUDGET_START_MODEL="$(read_field week_model)"
  BUDGET_RESET="$(read_reset)"
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
command_prompt() { # command_prompt <path> — a command file's body, sans frontmatter
  # The YAML frontmatter is loader metadata, not instructions. Sent verbatim it
  # tells the model to read its own catalogue entry as a task — and it begins
  # with `---`, which is what killed every dispatch of the first unattended run
  # before spawn-worker.sh gained its `--` terminator (ESC-37). Both fixes
  # stand: this one removes the noise, that one stops any future `---`-leading
  # prompt dying as a flag.
  awk 'NR==1 && $0=="---" { infm=1; next }
       infm && $0=="---"  { infm=0; next }
       infm               { next }
       { print }' "$1"
}

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
  # NOTHING TO OPEN is its own answer, not a failure (ESC-66). A worker can
  # exit 0 having committed on ITS branch and still leave the LANE unchanged —
  # an oracle re-deriving rulings that already merged is the ordinary case —
  # and GitHub then refuses the pull request with "No commits between". Those
  # are different facts and only this one predicts it, so it is checked here,
  # before a pointless push, and reported with a code the caller can count.
  local base_ref="$RUN_BASE"
  git rev-parse -q --verify "origin/$RUN_BASE" >/dev/null 2>&1 && base_ref="origin/$RUN_BASE"
  if [[ "$(git rev-list --count "$base_ref..$1" 2>/dev/null || echo 0)" == "0" ]]; then
    log "$1 adds nothing to $RUN_BASE — no pull request to open"
    return 2
  fi
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
  # --base, always explicit. Without it gh targets the repository's default
  # branch, which is right for exactly one run — the default-base one — and
  # silently wrong for every other lane.
  GH_TOKEN="$token" "$GH" pr create --head "${2}" --base "$RUN_BASE" \
    --title "$3" \
    --body "Opened mechanically by deliver-loop.sh, as the GitHub App. The content is the branch; the gates are the review." \
    >/dev/null || { log "gh pr create for $2 failed"; return 3; }
  PR_COUNT=$((PR_COUNT + 1))
}

# Appended to EVERY unattended worker prompt (ESC-69). A headless worker
# asked a human to approve its push and ended with a numbered menu — in a run
# that is unattended by construction, where nobody can pick. Two faults in one
# log: it tried to push at all (pushing is the driver's job, and the worker's
# grant correctly denies it), and once denied it addressed a person instead of
# reporting to the machine that commissioned it. The marker alone did not say
# so; now it does.
UNATTENDED_ADDENDUM='
UNATTENDED CONTRACT — read this before you finish.
- NOBODY IS WATCHING. This session is headless and commissioned by a script.
  Never address a human, never offer a menu or numbered choices, never ask for
  approval or confirmation, and never wait for one. There is no one to answer.
- DO NOT PUSH, and do not ask to. Pushing and opening the pull request are the
  driver'"'"'s job, and your tool grant excludes them deliberately. Commit your
  work on your branch and stop there.
- FINISH BY STATING WHERE THE WORK IS, on the last line, exactly:
      WORK_ON_BRANCH <branch-name>
  If you created or switched to a branch of your own, that is the one to name.
  A driver reads this line; a paragraph addressed to a person it cannot.
- If you are blocked, say what blocked you in one plain sentence and stop.
  A blocked worker that reports the blocker is useful; one that waits is not.'

run_worker() { # run_worker <id> <role> <prompt> <docs-ref> <pr-title>
  local id="$1" role="$2" prompt="$3" ref="$4" title="$5"
  log "dispatch $role worker ($id)"
  local out_file="$STATE_DIR/worker-$id.out"
  if ! timeout "$SESSION_TIMEOUT" "$SPAWN" --id "$id" --role "$role" \
       --engine "$ENGINE" --base "$RUN_BASE" --prompt "$prompt" \
       > "$out_file" 2>&1; then
    cat "$out_file" >> "$STATE_DIR/run.md"; rm -f "$out_file"
    log "$role worker failed — see .claude/orchestration-logs/$id.log"
    return 1
  fi
  cat "$out_file" >> "$STATE_DIR/run.md"
  # PUSH THE BRANCH THE WORKER SAYS IT USED, not the one this driver assumed
  # (ESC-68). A worker may create and switch to a branch of its own inside its
  # worktree; spawn-worker reports whichever branch carries the commits, and
  # pushing the assumed name instead sends an empty ref — a pull request with
  # no content, recorded as a successful iteration.
  local src
  src="$(sed -n 's/.*WORKER_RESULT .*[[:space:]]branch=\([^[:space:]]*\).*/\1/p' "$out_file" | tail -1)"
  rm -f "$out_file"
  if [[ -n "$src" && "$src" != "worker/$id" ]]; then
    log "the worker's work is on '$src', not 'worker/$id' — pushing what it reported"
  fi
  [[ -n "$src" ]] || src="worker/$id"
  mechanical_pr "$src" "$ref" "$title"
}

# Consecutive dispatches that produced no pull request. A run whose worker
# keeps succeeding while the lane never moves is a livelock the three-strike
# rule cannot see: that rule keys on the same CHECKS failing on one branch,
# and here no checks ever run and every branch has a fresh name, so the
# signature never repeats and the counter never accumulates (ESC-66).
NO_PROGRESS=0
note_dispatch_outcome() { # note_dispatch_outcome <rc-from-run_worker> [scope ids...]
  local rc="$1"; shift
  if [[ "$rc" -eq 0 ]]; then NO_PROGRESS=0; return 0; fi
  NO_PROGRESS=$((NO_PROGRESS + 1))
  # The ids this dispatch was commissioned to work are now PROCESSED whatever
  # the worker thought: the phase detector re-derives its scope from the tree,
  # so without this it re-summons the same worker over the same evidence for
  # ever. Recording them is what lets the run walk on to the next phase.
  local id
  for id in "$@"; do
    [[ -n "$id" ]] || continue
    printf '%s\n' "$id" >> "$PROCESSED_FILE"
  done
  sort -u "$PROCESSED_FILE" -o "$PROCESSED_FILE"
  if [[ "$NO_PROGRESS" -ge 2 ]]; then
    log "STOPPED: $NO_PROGRESS dispatches in a row produced no pull request. The"
    log "workers ran and the lane did not move, so nothing here will change on its"
    log "own — every further iteration would spend a model worker to learn the same"
    log "thing. Evidence is being landed; read it before restarting."
    exit 5
  fi
  log "that dispatch produced no pull request ($NO_PROGRESS in a row) — recording its scope as processed and re-detecting"
  return 0
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
  # --fail-fast: leave the watch the moment any check fails. Without it the
  # watch holds until NO check is pending — and a required check that never
  # reports at all (observed: `test-the-tests` stuck while `review` was already
  # red) is indistinguishable from one still running, so the driver sat on a
  # decided pull request for the full WAIT_TIMEOUT (ESC-39). A failed required
  # check is terminal for the head; nothing a pending one reports changes it.
  timeout "$WAIT_TIMEOUT" "$GH" pr checks "$pr" --watch --fail-fast --interval 30 \
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
    git pull -q --ff-only origin "$RUN_BASE" 2>/dev/null \
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
    # Same end-of-line capture as the start-of-run parse (mobo F13).
    now_reset="$(sed -n "s/.*\\breset=\\(.*\\)$/\\1/p" <<<"$out" | head -1)"
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
      # SAY IT EVERY ITERATION (ESC-67). The reading was taken every time
      # already, but only ever logged at the start and at the stop — so a run
      # whose budget check had quietly stopped working looked exactly like a
      # run comfortably inside its allowance, and the only way to tell them
      # apart was to read the gauge by hand. A limit nobody can see working is
      # a limit nobody can see break.
      log "budget: weekly at $(f week)% (model $(f week_model)%), spent ${spent} of ${BUDGET_POINTS} points on the ${which} limit"
    fi
  fi

  # What next? Recomputed from the world, never remembered.
  PHASE=""; PR=""; HEADREF=""; UNRULED=""; UNCITED=""; ODS=""; REQS=""; SLUG=""; REASON=""
  CRITERIA=""; rc=0
  while IFS='=' read -r k v; do
    case "$k" in
      PHASE) PHASE="$v" ;; PR) PR="$v" ;; HEADREF) HEADREF="$v" ;;
      UNRULED) UNRULED="$v" ;; UNCITED) UNCITED="$v" ;; ODS) ODS="$v" ;;
      REQS) REQS="$v" ;; SLUG) SLUG="$v" ;; REASON) REASON="$v" ;;
      CRITERIA) CRITERIA="$v" ;;
    esac
  done < <(GH="$GH" PROCESSED_FILE="$PROCESSED_FILE" RUN_BASE="$RUN_BASE" "$PHASE_SH")
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
        "$(command_prompt .claude/commands/oracle.md)

UNATTENDED RUN. The delivery driver commissioned this session. $scope
$UNATTENDED_ADDENDUM" \
        "docs/oracle-$(date -u +%Y%m%d%H%M%S)$LANE" \
        "Oracle: rulings and handoff" && rc=0 || rc=$?
      record_dismissed_evidence
      note_dispatch_outcome "$rc" $UNRULED $UNCITED ;;
    STEWARD)
      od="${ODS%% *}"
      run_worker "steward-${od,,}" steward \
        "$(command_prompt .claude/commands/steward.md)

UNATTENDED RUN. The decision to plan: $od
$UNATTENDED_ADDENDUM" \
        "docs/oracle-plan-${od,,}$LANE" \
        "Plan for $od" && rc=0 || rc=$?
      note_dispatch_outcome "$rc" ;;
    PLAN)
      run_worker "plan-$(date -u +%Y%m%d%H%M%S)" steward \
        "$(command_prompt .claude/commands/plan.md)

UNATTENDED. The delivery driver commissioned this session; follow the
unattended branches of the gate above. Requirements still unplanned: $REQS.
Plan the next milestone of docs/DESIGN.md that delivers them (or file the
uncertainties that block it).
$UNATTENDED_ADDENDUM" \
        "docs/plan-$(date -u +%Y%m%d%H%M%S)$LANE" \
        "Plan: next milestone ($REQS)" && rc=0 || rc=$?
      note_dispatch_outcome "$rc" ;;
    ORCHESTRATE)
      # UNATTENDED RUN is the marker the worker prompts have always carried and
      # this dispatch did not — which is exactly how it kept opening its own
      # pull request as the owner through the whole of ESC-26's remediation. A
      # command file that cannot tell which mode it is in has to write prose
      # that is right for both, and "open the pull request" was right for one.
      FEAT_REF="feat/$SLUG$LANE"
      if run_session "orchestrate" "/orchestrate $SLUG

UNATTENDED RUN. The delivery driver commissioned this session. This run's base
branch is $RUN_BASE — create the feature branch off $RUN_BASE, never off any
other branch, and name it EXACTLY $FEAT_REF. Build the feature, commit it, and
PUSH $FEAT_REF — then stop. Do NOT open the pull request: you have no grant
to, and the driver opens it as the GitHub App so it is not authored by the
owner."; then
        if git rev-parse -q --verify "refs/heads/$FEAT_REF" >/dev/null 2>&1; then
          mechanical_pr "$FEAT_REF" "$FEAT_REF" "Build: $SLUG" && rc=0 || rc=$?
        else
          log "orchestrate session finished but $FEAT_REF does not exist — nothing to open"
          rc=2
        fi
        # Counted like every other dispatch (ESC-66): a session that keeps
        # finishing without leaving a branch is the same livelock as a worker
        # whose branch adds nothing, and it looped just as invisibly.
        note_dispatch_outcome "$rc"
      else
        note_dispatch_outcome 1
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
      ACC_REF="docs/acceptance-$RUN_ID$LANE"
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
