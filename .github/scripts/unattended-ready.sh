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
# Optional env, for tests and odd layouts:
#   GH               default: gh
#   ANSWERS          default: .copier-answers.yml
#   VISION           default: docs/VISION.md
#   CODEOWNERS_FILE  default: .github/CODEOWNERS

set -uo pipefail

GH="${GH:-gh}"
ANSWERS="${ANSWERS:-.copier-answers.yml}"
VISION="${VISION:-docs/VISION.md}"
CODEOWNERS_FILE="${CODEOWNERS_FILE:-.github/CODEOWNERS}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "unattended-ready: not inside a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2

command -v "$GH" >/dev/null 2>&1 \
  || { echo "unattended-ready: '$GH' is not on PATH — install the GitHub CLI" >&2; exit 2; }

REPO="$("$GH" repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
[[ -n "$REPO" ]] \
  || { echo "unattended-ready: cannot resolve this repository — run: gh auth login" >&2; exit 2; }

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
SETTINGS="$("$GH" api "repos/$REPO" 2>/dev/null)"
if [[ -z "$SETTINGS" ]]; then
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

RULESET_IDS="$("$GH" api "repos/$REPO/rulesets" --jq '.[].id' 2>/dev/null)"
if [[ -z "$RULESET_IDS" ]]; then
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

# ------------------------------------------------------------------- secrets
# The review gate is a required check that FAILS CLOSED without its credential:
# with the secret missing, every pull request is permanently red and nothing
# the run builds can ever merge. That is the one secret worth refusing over.
# Plain-column parsing, not --json: `gh secret list --json` arrived late enough
# in gh's history that depending on it turns a version skew into a refusal.
SECRETS="$("$GH" secret list 2>/dev/null | awk '{print $1}')"
if [[ -z "$SECRETS" ]]; then
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
  elif grep -qxF "AUTO_MERGE_TOKEN" <<<"$SECRETS"; then
    refuse "merge identity is AUTO_MERGE_TOKEN (a PAT), which acts as YOU — so owner-authored.sh cannot tell an agent's edit to docs/DESIGN.md from one you wrote, and every driver-opened PR satisfies it by accident; set up the App: scripts/setup-github.sh --app"
  else
    refuse "no merge identity configured — the driver would open pull requests as you, which makes owner-authored.sh a formality and leaves docs/DESIGN.md and docs/VISION.md unprotected overnight; set up the App: scripts/setup-github.sh --app"
  fi
  if ! grep -qxF "TEMPLATE_TOKEN" <<<"$SECRETS"; then
    note "TEMPLATE_TOKEN is not set — template/ update branches will fail template-sync if the template repository is private"
  fi
fi

# ---------------------------------------------------------------- CODEOWNERS
# An unresolvable owner makes every gated-path PR unmergeable in the worst way:
# the review requirement can never be satisfied, and nothing says so.
CO_ERRORS="$("$GH" api "repos/$REPO/codeowners/errors" --jq '.errors | length' 2>/dev/null)"
if [[ -z "$CO_ERRORS" ]]; then
  note "cannot read CODEOWNERS validation from the API"
elif [[ "$CO_ERRORS" == "0" ]]; then
  ok "CODEOWNERS resolves cleanly"
else
  refuse "$CODEOWNERS_FILE has $CO_ERRORS unresolvable line(s) — gated-path PRs can never satisfy their review requirement; see Settings → Code owners errors, or the file itself"
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

# ------------------------------------------------------------------- verdict
echo
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "unattended-ready: REFUSED — ${#MISSING[@]} missing item(s) above." >&2
  echo "An unattended run against this configuration fails while nobody is watching." >&2
  exit 1
fi
echo "unattended-ready: this repository can run unattended."
