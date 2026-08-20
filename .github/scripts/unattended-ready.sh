#!/usr/bin/env bash
#
# unattended-ready.sh — ask the REPOSITORY whether tonight's run can succeed,
# and refuse it when the answer is no.
#
# The template ships files; every unattended failure this check exists for
# lived somewhere a file cannot reach. The auto-merge workflow shipped correct
# three times while merged branches piled up, because "Allow auto-merge" is a
# repository setting; the review gate is a required check whose credential is a
# secret; the required-check list itself lives in a ruleset. A driver that
# starts a run without reading those back is betting the night on configuration
# nobody has looked at since setup — so the driver's preflight runs this, and
# this REFUSES. A warning nobody reads at 3am is decoration; a refusal at
# dispatch time is the same information while someone can still act on it.
#
# Every refusal names the missing thing and where to fix it. Most fixes are one
# `scripts/setup-github.sh` run.
#
# WHAT REFUSES vs WHAT ONLY NOTES. A condition refuses when the run cannot
# reach its goal: nothing would merge (auto-merge off, required checks absent
# or misnamed, review credential missing) or a gate would misfire (CODEOWNERS
# unresolvable). A condition only notes when a designed fallback covers it —
# no merge identity configured means cleanup waits for the nightly sweep, which
# is degraded, not broken. The notes still print; they are just not this
# check's call to make.
#
# Exit codes: 0 ready, 1 refused (missing items listed), 2 cannot even ask
# (no gh, no auth, not a repository).
#
# --runtime: the checks a RUNTIME identity can honestly answer. The full check
# reads repository administration — secrets, rulesets — which only the owner's
# own login can; a driver running as the App (a web session, where gh holds an
# App token) cannot ask those questions, and refusing over a READ permission
# would block a run whose configuration the owner already verified at setup
# with the full check. Runtime mode verifies what that identity can and must:
# the answers file and auto-merge workflow, the vision, the App identity
# actually MINTING a token (a stronger claim than a secret's name existing),
# and the effective rules on the run's base branch. Everything else is the
# full check's job, run by the owner, from their machine, at setup. This is
# not an override of a refusal — it is a different question set for a
# different identity, and both sets still refuse loudly on what they check.
#
# Optional env, for tests and odd layouts:
#   READY_APP_TOKEN_CMD  --runtime only: the command that mints the App token
#                        (default .claude/scripts/app-token.sh; tests stub it)
#   GH               default: gh
#   ANSWERS          default: .copier-answers.yml
#   VISION           default: docs/VISION.md
#   CODEOWNERS_FILE  default: .github/CODEOWNERS
#   RUN_BASE         the base branch the asking run merges into (the driver
#                    exports it). When it is set and is NOT the repository's
#                    default branch, this check also reads the EFFECTIVE rules
#                    on that branch: a ruleset that binds only the default
#                    branch leaves a lane run's pull requests entirely ungated
#                    — auto-merge on an unprotected base waits for nothing —
#                    and that is a refusal, not a note. Fix:
#                    scripts/setup-github.sh --gate-branch <branch>.

set -uo pipefail

GH="${GH:-gh}"
ANSWERS="${ANSWERS:-.copier-answers.yml}"
VISION="${VISION:-docs/VISION.md}"
CODEOWNERS_FILE="${CODEOWNERS_FILE:-.github/CODEOWNERS}"
READY_APP_TOKEN_CMD="${READY_APP_TOKEN_CMD:-.claude/scripts/app-token.sh}"

RUNTIME=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime) RUNTIME=1; shift ;;
    *) echo "unattended-ready: unknown argument: $1 (only --runtime)" >&2; exit 2 ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "unattended-ready: not inside a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2

command -v "$GH" >/dev/null 2>&1 \
  || { echo "unattended-ready: '$GH' is not on PATH — install the GitHub CLI" >&2; exit 2; }

# The remote URL, not `gh repo view`: repo view is GraphQL, which a hosted
# session's proxy refuses outright — only REST is served there (ESC-51).
REPO="${REPO:-$(git remote get-url origin 2>/dev/null \
  | sed -E 's#^(git@[^:/]+:|https?://[^/]+/|ssh://git@[^/]+/)##; s#\.git$##')}"
[[ -n "$REPO" ]] \
  || { echo "unattended-ready: cannot resolve owner/repo from the origin remote" >&2; exit 2; }

declare -a MISSING=()
ok()      { echo "  ready    $1"; }
refuse()  { echo "  MISSING  $1"; MISSING+=("$1"); }
note()    { echo "  note     $1"; }

echo "unattended-ready: $REPO"

# ---------------------------------------------------------------- the answers
# language decides which build job the ruleset must require; auto_merge decides
# whether the pipeline can merge at all.
LANGUAGE="$(sed -n 's/^language:[[:space:]]*//p' "$ANSWERS" 2>/dev/null | tr -d "\"'" | head -1)"
AUTO_MERGE="$(sed -n 's/^auto_merge:[[:space:]]*//p' "$ANSWERS" 2>/dev/null | tr -d "\"'" | head -1)"

if [[ ! -f "$ANSWERS" ]]; then
  refuse "no $ANSWERS — this is not a generated project, so nothing below can be derived"
elif [[ "$AUTO_MERGE" != "true" ]]; then
  refuse "auto_merge is '$AUTO_MERGE' in $ANSWERS — nothing merges unattended; regenerate with auto_merge: true (copier update --data auto_merge=true)"
else
  ok "auto_merge: true in $ANSWERS"
fi

if [[ -f ".github/workflows/auto-merge.yml" ]]; then
  ok "auto-merge workflow is present"
else
  refuse "no .github/workflows/auto-merge.yml — the arming workflow did not render; re-run copier with auto_merge: true"
fi

# ------------------------------------------------------- repository settings
# Fetched in both modes — the base-branch section below needs default_branch —
# but the two admin-visible settings are judged only by the full check: the
# fields are simply absent from a non-admin identity's view of the repository,
# and absent must not read as off.
SETTINGS="$("$GH" api "repos/$REPO" 2>/dev/null)"
if [[ "$RUNTIME" -eq 1 ]]; then
  note "repository settings (auto-merge, branch deletion): the full check's job — a runtime identity cannot see them"
elif [[ -z "$SETTINGS" ]]; then
  refuse "cannot read repository settings (gh api repos/$REPO failed) — check gh auth status"
else
  if grep -q '"allow_auto_merge"[[:space:]]*:[[:space:]]*true' <<<"$SETTINGS"; then
    ok "repository allows auto-merge"
  else
    refuse "'Allow auto-merge' is off — every armed merge fails outright; enable it: scripts/setup-github.sh, or Settings → General → Allow auto-merge"
  fi
  if grep -q '"delete_branch_on_merge"[[:space:]]*:[[:space:]]*true' <<<"$SETTINGS"; then
    ok "repository deletes head branches on merge"
  else
    note "'Automatically delete head branches' is off — the workflow and sweep still clean up; scripts/setup-github.sh sets it"
  fi
  # DO THE GATES ACTUALLY BIND? (ESC-73.) Rulesets are enforced on public
  # repositories and on private ones under a paid plan; on a private repository
  # without one they can be CREATED and read back exactly as configured while
  # enforcing nothing. Every check above reads configuration, so all of them
  # pass — and pull requests merge with no review, no required check, and no
  # sign anything is wrong. Observed: a real project's template updates
  # auto-merged for weeks with zero approvals against a ruleset demanding code
  # owner review, and the first merge ever refused was the day the repository
  # went public and the gates began to bind.
  if grep -q '"private"[[:space:]]*:[[:space:]]*true' <<<"$SETTINGS"; then
    note "this repository is PRIVATE — rulesets enforce only under a paid plan there. If yours is not paid, every gate above is configured and NOT binding: pull requests merge unreviewed and unchecked. Make it public, or confirm the plan covers rulesets"
  fi
fi

# ------------------------------------------------------------------ rulesets
# The required checks are what makes "merges when green" mean anything. A
# required check whose name drifted from the workflow's job name waits forever;
# a missing one silently stops gating. Compare the union of every active
# ruleset's required checks against what the shipped workflows actually report.
EXPECTED=(plan template-sync secrets test-the-tests acceptance-criteria review)
case "$LANGUAGE" in
  python)    EXPECTED+=(checks) ;;
  swift-ios) EXPECTED+=(test) ;;
  *)         note "language '$LANGUAGE' unrecognised — cannot derive the build job's check name" ;;
esac

if [[ "$RUNTIME" -eq 1 ]]; then
  # Listing rulesets is an admin read. A runtime identity judges their EFFECT
  # instead — the effective-rules check on its base branch, below.
  note "the rulesets themselves: the full check's job — a runtime identity reads only their effect on its base branch, below"
  RULESET_IDS=""
elif ! RULESET_IDS="$("$GH" api "repos/$REPO/rulesets" --jq '.[].id' 2>/dev/null)" \
     || [[ -z "$RULESET_IDS" ]]; then
  refuse "no rulesets on the repository — nothing requires the gates before merge; create them: scripts/setup-github.sh"
else
  CONTEXTS=""
  HAVE_PR_RULE=0
  while IFS= read -r id; do
    [[ -z "$id" ]] && continue
    detail="$("$GH" api "repos/$REPO/rulesets/$id" 2>/dev/null)"
    grep -q '"enforcement"[[:space:]]*:[[:space:]]*"active"' <<<"$detail" || continue
    grep -q '"type"[[:space:]]*:[[:space:]]*"pull_request"' <<<"$detail" && HAVE_PR_RULE=1
    CONTEXTS+=$'\n'"$(grep -oE '"context"[[:space:]]*:[[:space:]]*"[^"]+"' <<<"$detail" \
                      | sed 's/.*:[[:space:]]*"//; s/"$//')"
  done <<<"$RULESET_IDS"

  for want in "${EXPECTED[@]}"; do
    if grep -qxF "$want" <<<"$CONTEXTS"; then
      ok "required check '$want' is configured"
    else
      refuse "check '$want' is not required by any active ruleset — a PR merges without it, or the list has drifted from the job names; fix: scripts/setup-github.sh"
    fi
  done
  if [[ "$HAVE_PR_RULE" -eq 1 ]]; then
    ok "a pull-request rule is active (merges only via PR)"
  else
    refuse "no active pull_request rule — pushes could land on the default branch directly; fix: scripts/setup-github.sh"
  fi
fi

# ------------------------------------------------- the run's base branch
# The union check above says the checks exist SOMEWHERE. A run on a non-default
# base branch needs them to bind on THAT branch, and a ruleset targeting only
# the default branch does not — its pull requests would merge with no gate at
# all. So when the driver names its base, read the branch's EFFECTIVE rules
# (the API resolves every active ruleset against the one branch) and refuse
# unless a pull_request rule and every required check bind there.
DEFAULT_BRANCH="$(grep -oE '"default_branch"[[:space:]]*:[[:space:]]*"[^"]+"' <<<"${SETTINGS:-}" \
                  | sed 's/.*:[[:space:]]*"//; s/"$//' | head -1)"
# Runtime mode has no rulesets union above, so the effective-rules read is its
# ONLY gate verification — it therefore runs for the default branch too, and a
# missing RUN_BASE falls back to the default branch rather than skipping.
if [[ "$RUNTIME" -eq 1 && -z "${RUN_BASE:-}" ]]; then
  RUN_BASE="$DEFAULT_BRANCH"
fi
# The base this run will actually use, for the checks below that need a name
# whether or not the caller supplied one.
RUN_BASE_EFF="${RUN_BASE:-$DEFAULT_BRANCH}"
if [[ -n "${RUN_BASE:-}" ]]; then
  if [[ "$RUNTIME" -eq 1 ]] \
     || [[ -n "$DEFAULT_BRANCH" && "$RUN_BASE" != "$DEFAULT_BRANCH" ]]; then
    BR_RULES="$("$GH" api "repos/$REPO/rules/branches/$RUN_BASE" 2>/dev/null)"
    if [[ -z "$BR_RULES" || "$BR_RULES" == "[]" ]]; then
      refuse "no rules bind the run's base branch '$RUN_BASE' — every pull request this run opens would merge ungated; add the branch to the gates ruleset: scripts/setup-github.sh --gate-branch '$RUN_BASE'"
    else
      if grep -q '"type"[[:space:]]*:[[:space:]]*"pull_request"' <<<"$BR_RULES"; then
        ok "base branch '$RUN_BASE': pull-request rule binds"
      else
        refuse "base branch '$RUN_BASE' has no pull_request rule — pushes could land on it directly; fix: scripts/setup-github.sh --gate-branch '$RUN_BASE'"
      fi
      BR_CONTEXTS="$(grep -oE '"context"[[:space:]]*:[[:space:]]*"[^"]+"' <<<"$BR_RULES" \
                     | sed 's/.*:[[:space:]]*"//; s/"$//')"
      for want in "${EXPECTED[@]}"; do
        if grep -qxF "$want" <<<"$BR_CONTEXTS"; then
          ok "base branch '$RUN_BASE': required check '$want' binds"
        else
          refuse "check '$want' is not required on the run's base branch '$RUN_BASE' — a PR into it merges without that gate; fix: scripts/setup-github.sh --gate-branch '$RUN_BASE'"
        fi
      done
    fi
  fi
fi

# ------------------------------------------------------------------- secrets
# The review gate is a required check that FAILS CLOSED without its credential:
# with the secret missing, every pull request is permanently red and nothing
# the run builds can ever merge. That is the one secret worth refusing over.
# Plain-column parsing, not --json: `gh secret list --json` arrived late enough
# in gh's history that depending on it turns a version skew into a refusal.
if [[ "$RUNTIME" -eq 1 ]]; then
  # Listing secrets is an admin read a runtime identity does not have. What it
  # CAN prove is stronger than a secret's name existing anyway: that the App
  # identity actually mints an installation token, here, now.
  #
  # EXCEPT on a hosted platform (ESC-50): its egress proxy replaces every
  # Authorization header with the platform's own credential and blocks the
  # /app endpoints outright, so the mint fails there BY DESIGN, with a
  # perfectly good key. The signature of that platform is a gh login that
  # works anyway (the proxy injects it). Such a session drives with the
  # ambient login and opens pull requests through the open-pr workflow, which
  # mints server-side where minting works — so what THIS check must prove
  # shifts: not "the mint works here" but "the opener exists here".
  # `gh api user`, NEVER `gh auth status`: auth status inspects the LOCAL
  # configuration and reports failure on exactly the platform this branch
  # exists for, while real requests succeed at the proxy (ESC-52). The probe
  # must ask the network, not the config.
  if "$READY_APP_TOKEN_CMD" >/dev/null 2>&1; then
    ok "App identity mints a token (the merge identity is live, not just named)"
  elif "$GH" api user >/dev/null 2>&1; then
    if [[ -f ".github/workflows/open-pr.yml" ]]; then
      note "App mint impossible here (a hosted platform's proxy owns the credential — ESC-50); the ambient login drives, and pull requests open as the App via the open-pr workflow"
    else
      refuse "App mint impossible here (ESC-50) and this scaffold carries no .github/workflows/open-pr.yml — every pull request this run opened would be owner-authored; update to a template release that ships the open-pr workflow"
    fi
  else
    refuse "no GitHub identity works here: the App cannot mint ($READY_APP_TOKEN_CMD failed) and gh api user answers nothing — fix the App id and key this environment carries, or run where the platform injects a credential"
  fi
  note "secret names (CLAUDE_CODE_OAUTH_TOKEN): the full check's job — a runtime identity cannot list secrets"
  SECRETS=""
elif SECRETS="$("$GH" secret list 2>/dev/null | awk '{print $1}')" && [[ -z "$SECRETS" ]]; then
  refuse "cannot list actions secrets — admin access is required to verify CLAUDE_CODE_OAUTH_TOKEN exists; check gh auth status"
else
  if grep -qxF "CLAUDE_CODE_OAUTH_TOKEN" <<<"$SECRETS"; then
    ok "CLAUDE_CODE_OAUTH_TOKEN is set (review gate can run)"
  else
    refuse "CLAUDE_CODE_OAUTH_TOKEN is not set — the review gate fails closed and no PR ever merges; set it: scripts/setup-github.sh"
  fi
  # This was a note until the identity argument landed (docs/synthesis.md D15).
  # The App is not a convenience for branch cleanup — it is the only thing that
  # gives the unattended driver a login that is NOT the owner's. Without it
  # owner-authored.sh compares the owner's login to the owner's login and
  # passes, so docs/DESIGN.md and docs/VISION.md have no protection at all
  # during an unattended run: the check prints its guarantee and does not hold
  # it. A PAT has the same defect, because a PAT also acts as the owner.
  if grep -qxF "APP_ID" <<<"$SECRETS" && grep -qxF "APP_PRIVATE_KEY" <<<"$SECRETS"; then
    ok "merge identity: GitHub App configured (a login that is not the owner's)"
    # There is deliberately no PAT alternative — a PAT acts as the owner
    # (hollowing owner-authored.sh) and expires, and the owner's ruling is
    # that the App and the review credential are the ONLY secrets a project
    # carries. What cannot be verified from here: that the App is also
    # INSTALLED on the template repository, which template-sync needs to read
    # a private template. Said rather than skipped:
    note "template reads are minted from this App — it must be installed on the TEMPLATE repository too, or template/ branches fail template-sync closed"
  else
    refuse "no merge identity configured — the driver would open pull requests as you, which makes owner-authored.sh a formality and leaves docs/DESIGN.md and docs/VISION.md unprotected overnight; set up the App: scripts/setup-github.sh --app (there is deliberately no PAT alternative)"
  fi
fi

# ---------------------------------------------------------------- CODEOWNERS
# An unresolvable owner makes every gated-path PR unmergeable in the worst way:
# the review requirement can never be satisfied, and nothing says so.
if [[ "$RUNTIME" -eq 1 ]]; then
  note "CODEOWNERS validation: the full check's job"
  CO_ERRORS="skipped"
  CO_REF=""
else
  # ESC-48, two defects in one line. The query carried no ?ref=, so it always
  # validated the DEFAULT branch's CODEOWNERS — every other branch-sensitive
  # check here is RUN_BASE-aware, and this one was missed, which turned a bare
  # default branch into a refusal against a lane whose CODEOWNERS was clean.
  # And the API's failure status was ignored: gh prints the error body on
  # stdout, so a 404 flowed INTO the count and was printed as raw JSON inside
  # a refusal, while the designed cannot-read note never fired. The ref
  # follows the run's base branch; the count must be a number or it is not a
  # count.
  CO_REF="${RUN_BASE:-$DEFAULT_BRANCH}"
  CO_PATH="repos/$REPO/codeowners/errors"
  [[ -n "$CO_REF" ]] && CO_PATH="$CO_PATH?ref=$CO_REF"
  if ! CO_ERRORS="$("$GH" api "$CO_PATH" --jq '.errors | length' 2>/dev/null)" \
     || ! [[ "$CO_ERRORS" =~ ^[0-9]+$ ]]; then
    CO_ERRORS=""
  fi
fi
if [[ "$CO_ERRORS" == "skipped" ]]; then
  :
elif [[ -z "$CO_ERRORS" ]]; then
  note "cannot read CODEOWNERS validation from the API"
elif [[ "$CO_ERRORS" == "0" ]]; then
  ok "CODEOWNERS resolves cleanly (at ${CO_REF:-the default branch})"
else
  refuse "$CODEOWNERS_FILE (at ${CO_REF:-the default branch}) has $CO_ERRORS unresolvable line(s) — gated-path PRs can never satisfy their review requirement; see Settings → Code owners errors, or the file itself"
fi

# -------------------------------------------------------------------- vision
# Every oracle decision must quote docs/VISION.md, so an unfilled section does
# not fail here — it fails at 3am, in the one role that keeps work moving. Same
# emptiness predicate as vision-complete.sh: a section with no line that is not
# a heading, blank, or a comment. An absent file is the documented opt-out.
if [[ ! -f "$VISION" ]]; then
  note "no $VISION — this project has opted out of the oracle; unattended runs cannot rule on uncertainties"
else
  EMPTY_SECTIONS="$(awk '
    /^##[^#]/ {
      if (section != "" && !filled) print section
      section = substr($0, 4); filled = 0; next
    }
    section == ""            { next }
    /^[[:space:]]*$/         { next }
    /^[[:space:]]*<!--/      { incomment = 1 }
    incomment                { if ($0 ~ /-->/) incomment = 0; next }
    /^#/                     { next }
    { filled = 1 }
    END { if (section != "" && !filled) print section }
  ' "$VISION")"
  if [[ -z "$EMPTY_SECTIONS" ]]; then
    ok "$VISION is filled in"
  else
    refuse "$VISION has unfilled section(s): $(tr '\n' ',' <<<"$EMPTY_SECTIONS" | sed 's/,$//; s/,/, /g') — the oracle quotes this file on every ruling; fill them or delete them"
  fi
fi

# ---------------------------------------------- an open pull request on the base
# A run cannot start into a base that already has a pull request open: the
# one-PR-per-base rule means the driver's first act is to WAIT on somebody
# else's change, and if that change needs the owner's review — a template
# update does, always, because it edits the gates themselves — the run stalls
# on a condition no unattended actor can clear, then stops at exit 4 having
# built nothing. Observed live on a real project: an update pull request left
# open at setup derailed the run that followed it.
#
# Caught HERE rather than mid-flight, because that is this check's whole job:
# a refusal costs a click, a mid-run stall costs the run. Merge it (a template
# update is yours to approve — template-sync proves the diff is exactly copier
# output, so the reading is quick) or close it, then start the run.
OPEN_ON_BASE="$("$GH" api "repos/$REPO/pulls?state=open&base=$RUN_BASE_EFF&per_page=10" \
  --jq '.[] | "#\(.number) \(.head.ref)"' 2>/dev/null || true)"
if [[ -n "$OPEN_ON_BASE" ]]; then
  refuse "a pull request is already open against '$RUN_BASE_EFF' ($(printf '%s' "$OPEN_ON_BASE" | tr '\n' ' ')) — the run's first act would be to wait on it, and a template update waits for YOUR review, which no unattended actor can give. Merge or close it first"
else
  ok "no pull request is open against '$RUN_BASE_EFF' — the run starts on a clear base"
fi

# ------------------------------------------------- debris from a dead run
# THE CHECK THAT SAYS "READY" MUST COVER WHAT THE DRIVER REFUSES ON (ESC-76).
# This script runs in the step immediately before "start your driver", so
# anything the driver rejects at startup and this script cannot see is a
# refusal that arrives minutes later, after the owner has walked away. Leftover
# worktrees are exactly that: a previous run that died mid-dispatch leaves them
# behind, the driver refuses to start on them, and readiness said ready.
#
# It is worth saying WHAT to do, because the obvious answer is wrong: a
# leftover worktree can hold a worker's finished, unpushed commits — a real
# plan was salvaged from one as a 562-line patch — so read it before removing
# it.
WORKTREES=""
if [[ -d .worktrees ]]; then
  WORKTREES="$(ls -A .worktrees 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
fi
if [[ -n "$WORKTREES" ]]; then
  refuse "leftover worktrees under .worktrees/ ($WORKTREES) — a previous run died mid-dispatch and the driver refuses to start on them. READ THEM FIRST (git -C .worktrees/<name> log --oneline; git -C .worktrees/<name> status): one can hold a worker's finished but unpushed work. Then 'git worktree remove' each, or 'git worktree prune' if the directories are already gone"
else
  ok "no leftover worktrees — no dead run's debris in the way"
fi

# ------------------------------------------------------------------- verdict
echo
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "unattended-ready: REFUSED — ${#MISSING[@]} missing item(s) above." >&2
  echo "An unattended run against this configuration fails while nobody is watching." >&2
  exit 1
fi
echo "unattended-ready: this repository can run unattended."
