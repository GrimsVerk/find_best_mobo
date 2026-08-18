#!/usr/bin/env bash
#
# plan-metrics.sh — compute mechanical facts about a PR diff, for the reviewer.
#
# This script COMPUTES, it does not JUDGE. It emits numbers; the reviewer decides
# whether a deviation is justified. It ALWAYS exits 0 — an overrun is a question,
# never a build failure. (A missing plan IS a failure, but that is
# plan-resolve.sh's job, not this one.)
#
# Facts emitted:
#   - actual added lines per slice vs the slice's estimate, flagged past a
#     threshold
#   - new files added
#   - new dependencies added
#   - test-to-implementation added-line ratio
#
# Usage:  plan-metrics.sh [path/to/plan.md]
#   With no argument it reports the plan-independent facts only (used for
#   branches exempt from planning).
#
# Required env:
#   BASE_SHA, HEAD_SHA   commits bounding the PR diff (base...head)

set -euo pipefail

# A slice is flagged when actual > estimate * FACTOR, but never below FLOOR —
# without the floor a 4-line slice that lands at 13 would "overrun by 3x" and
# train the reviewer to ignore the signal.
FACTOR=3
FLOOR=80

PLAN="${1:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

# Added lines in the diff, optionally restricted to the given paths.
#
# --literal-pathspecs because the paths come from the plan's Files: lines, which
# are attacker-adjacent: the plan is a file in the repository. Without it, a
# path written as `:(exclude)src` would be read by git as a magic pathspec and
# silently remove a slice's real files from its own line count.
added_lines() {
  if [[ $# -eq 0 ]]; then
    git -C "$ROOT" --literal-pathspecs diff --numstat "${BASE_SHA}...${HEAD_SHA}" \
      | awk '{ s += $1 } END { print s + 0 }'
  else
    git -C "$ROOT" --literal-pathspecs diff --numstat "${BASE_SHA}...${HEAD_SHA}" -- "$@" \
      | awk '{ s += $1 } END { print s + 0 }'
  fi
}

# This script emits ONE SECTION of the mechanical-facts region. review.sh owns
# the region's header and footer and calls each fact script in turn, so a new
# fact — the ratchet will ask for some — is a new script and one call site, not
# an edit to this one.
echo "----- plan conformance -----"
echo

# ---------------------------------------------------------------- slice deltas
# The plan is read at BASE_SHA, not from the working tree. These numbers are
# handed to the reviewer as ground truth, so the estimates a diff is measured
# against must not be editable by that diff — otherwise an overrun is fixed by
# raising the estimate in the same commit. `plan-resolve.sh` has already
# guaranteed the plan exists at base; this reads that version of it.
if [[ -n "$PLAN" ]] && git -C "$ROOT" cat-file -e "${BASE_SHA}:${PLAN}" 2>/dev/null; then
  # Parsing is delegated to plan-parse.sh, which is STRICT: a plan it cannot
  # read is an error, not an empty result. Silence here would be the worst
  # possible failure — the reviewer is told to treat these numbers as ground
  # truth, so an empty table reads as "no overruns, no scope creep" when it
  # actually means "nothing was measured".
  echo "Plan: $PLAN (as of the base commit)"
  echo
  # plan-parse.sh writes nothing to stderr when it succeeds, so folding the two
  # streams together lets one capture serve as both the records and the
  # diagnosis, with the exit code deciding which it is.
  if PARSED="$(git -C "$ROOT" show "${BASE_SHA}:${PLAN}" \
      | "${HERE}/plan-parse.sh" 2>&1)"; then
    printf '%-38s %10s %10s   %s\n' "SLICE" "ESTIMATE" "ACTUAL" "NOTE"

    # Split with IFS rather than eval — the plan file is part of the diff under
    # review, so a PR could otherwise put shell metacharacters in a Files: line
    # and have this script run them.
    while IFS=$'\t' read -r title estimate files; do
      [[ -z "$title" ]] && continue
      IFS='|' read -r -a slice_files <<< "$files"
      actual="$(added_lines "${slice_files[@]}")"
      note=""
      threshold=$(( estimate * FACTOR ))
      [[ "$threshold" -lt "$FLOOR" ]] && threshold=$FLOOR
      if [[ "$actual" -gt "$threshold" ]]; then
        note="OVER — ${FACTOR}x estimate exceeded (>${threshold}); is the deviation justified?"
      fi
      printf '%-38s %10s %10s   %s\n' "${title:0:38}" "$estimate" "$actual" "$note"
    done <<< "$PARSED"
  else
    echo "!!!!! PLAN PARSE FAILED — NO SLICE METRICS COMPUTED !!!!!"
    echo
    printf '%s\n' "$PARSED"
    echo
    echo "This pull request has NO per-slice line deltas, no scope check, and no"
    echo "overrun detection. An empty result here is not 'nothing to report' —"
    echo "it is a gate that stopped working. Treat it as a blocking finding."
  fi
else
  echo "Plan: none (branch exempt from planning) — no slice estimates to check."
fi

# ------------------------------------------------------- plan adequacy (NOTE)
# The other half of the plan-conformance question, and the half nothing asked.
# The slice deltas above answer "does this diff match the plan". They cannot
# answer "is this plan enough for what it claims" — and `covers:` is a CLAIM
# that nothing compares to what the slices build, so a plan naming twelve
# requirements and building three passes every gate green.
#
# A NOTE, NEVER A FAILURE, on the owner's ruling: "yes, note, not red." A
# platform or offline requirement is legitimately owned by no slice, so a strict
# check would fire on honest plans and teach authors to pad slice text with ids.
# An id the design marks `*(non-functional)*` is reported as an expected absence
# instead. This script always exits 0 regardless.
if [[ -n "$PLAN" ]] && git -C "$ROOT" cat-file -e "${BASE_SHA}:${PLAN}" 2>/dev/null; then
  PLAN_TEXT="$(git -C "$ROOT" show "${BASE_SHA}:${PLAN}")"
  COVERS="$(printf '%s\n' "$PLAN_TEXT" \
    | awk 'NR==1 && $0=="---" { infm=1; next }
           infm && $0=="---"  { exit }
           infm && /^covers:/ { sub(/^covers:[[:space:]]*/, ""); gsub(/[][,]/, " "); print; exit }' \
    | grep -oE '\bR[0-9]+\b' | sort -u || true)"
  SLICED="$(printf '%s\n' "$PLAN_TEXT" \
    | awk '/^#+[[:space:]]*Slice[[:space:]]/ { inslices = 1 }
           inslices {
             n = split($0, parts, /[^A-Za-z0-9]+/)
             for (i = 1; i <= n; i++) if (parts[i] ~ /^R[0-9]+$/) print parts[i]
           }' | sort -u || true)"
  # The `*(non-functional)*` mark, read from the design at the BASE commit like
  # every other standard here.
  NONFUNC="$(git -C "$ROOT" show "${BASE_SHA}:docs/DESIGN.md" 2>/dev/null \
    | awk '/^## 5\./ { in5 = 1; next }
           /^## /    { in5 = 0 }
           in5 && /\*\(non-functional\)\*/ {
             line = $0
             while (match(line, /\*\*R[0-9]+\*\*/)) {
               print substr(line, RSTART + 2, RLENGTH - 4)
               line = substr(line, RSTART + RLENGTH)
             }
           }' | sort -u || true)"
  unsliced=""; expected=""
  for id in $COVERS; do
    grep -qxF "$id" <<<"$SLICED" && continue
    if grep -qxF "$id" <<<"$NONFUNC"; then expected="$expected $id"; else unsliced="$unsliced $id"; fi
  done
  echo
  if [[ -n "${unsliced# }" ]]; then
    echo "PLAN ADEQUACY (a note, not a failure): this plan claims${unsliced}, and no"
    echo "slice of it mentions them. 'Covered' means the plan NAMED the id; nothing"
    echo "else compares that claim to what the slices build. Ask whether the work is"
    echo "really in here, or whether the covers: list is over-claimed."
  else
    echo "Plan adequacy: every requirement this plan claims is mentioned by a slice."
  fi
  [[ -n "${expected# }" ]] && \
    echo "Expected absences (marked *(non-functional)* in the design):${expected}"
fi

echo
echo "Total added lines: $(added_lines)"

# ------------------------------------------------------------------ new files
echo
NEW_FILES="$(git -C "$ROOT" diff --diff-filter=A --name-only "${BASE_SHA}...${HEAD_SHA}" || true)"
if [[ -n "$NEW_FILES" ]]; then
  echo "New files added ($(printf '%s\n' "$NEW_FILES" | wc -l | tr -d ' ')):"
  printf '%s\n' "$NEW_FILES" | sed 's/^/  /'
else
  echo "New files added: none"
fi

# --------------------------------------------------------------- dependencies
# The cheapest speculative-machinery detector there is: compare the declared
# dependency list before and after, rather than grepping the diff for '+'.
deps_at() {
  local ref="$1"
  {
    # Covers [project].dependencies, [dependency-groups].dev, and every array
    # under [project.optional-dependencies] — an extra is still a dependency,
    # and adding one there was previously invisible to this check.
    git -C "$ROOT" show "${ref}:pyproject.toml" 2>/dev/null | awk '
      /^\[project\.optional-dependencies\]/ { inopt = 1; next }
      /^\[/ && !/^\[project\.optional-dependencies\]/ { inopt = 0 }
      inopt && /^[A-Za-z0-9_.-]+ *= *\[/ { inarr = 1 }
      /^(dependencies|dev) *= *\[/ { inarr = 1 }
      inarr {
        line = $0
        while (match(line, /"[^"]+"/)) {
          print substr(line, RSTART + 1, RLENGTH - 2)
          line = substr(line, RSTART + RLENGTH)
        }
        if (/\]/) inarr = 0
      }'
    git -C "$ROOT" show "${ref}:project.yml" 2>/dev/null | awk '
      /^packages:/ { inpkg = 1; next }
      inpkg && /^[^ ]/ { inpkg = 0 }
      inpkg && /^  [A-Za-z0-9_.-]+:/ { gsub(/[ :]/, ""); print }'
  } | sort -u
}
echo
ADDED_DEPS="$(comm -13 <(deps_at "$BASE_SHA") <(deps_at "$HEAD_SHA") || true)"
if [[ -n "$ADDED_DEPS" ]]; then
  echo "NEW DEPENDENCIES ($(printf '%s\n' "$ADDED_DEPS" | wc -l | tr -d ' ')):"
  printf '%s\n' "$ADDED_DEPS" | sed 's/^/  /'
  echo "  (AGENTS.md: no new dependencies without the owner's approval.)"
else
  echo "New dependencies: none"
fi

# ------------------------------------------------------------- test:impl ratio
echo
if [[ -f "$ROOT/pyproject.toml" ]]; then
  TEST_LINES="$(added_lines 'tests/')"; IMPL_LINES="$(added_lines 'src/')"
else
  TEST_LINES="$(added_lines 'Tests/')"; IMPL_LINES="$(added_lines 'Sources/')"
fi
if [[ "$IMPL_LINES" -gt 0 ]]; then
  echo "Test:implementation added lines: ${TEST_LINES}:${IMPL_LINES} \
($(awk -v t="$TEST_LINES" -v i="$IMPL_LINES" 'BEGIN { printf "%.2f", t / i }')x)"
elif [[ "$TEST_LINES" -gt 0 ]]; then
  echo "Test:implementation added lines: ${TEST_LINES}:0 (tests only, no implementation touched)"
else
  echo "Test:implementation added lines: no test or implementation files touched"
fi

exit 0
