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
