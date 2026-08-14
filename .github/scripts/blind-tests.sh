#!/usr/bin/env bash
#
# blind-tests.sh — were the blind-written tests edited after they were written?
#
# Emits one section of the mechanical-facts region for the review agent. Like
# plan-metrics.sh it COMPUTES and does not JUDGE: it ALWAYS exits 0, and the
# reviewer decides whether an edit was justified.
#
# WHAT IT IS FOR.
#
# A slice's code and its tests are written by two agents in parallel, neither
# able to see the other's work (AGENTS.md, "Who writes the tests"). That
# separation is the whole reason the suite is worth anything: an agent that
# writes both describes what its code happens to do, bugs included, and calls
# it a test suite. The two meet at assembly, and a disagreement there is the
# payoff — it means two independent readings of the spec differed.
#
# The forbidden resolution is editing the test until it matches the code. That
# converts a caught defect into a green suite, and it is invisible in the final
# diff: a weakened test looks exactly like a test that was always correct.
# test-the-tests.sh does not catch it either, because a weakened-but-still-
# coupled test still fails when the implementation is reverted.
#
# So the orchestrator merges each slice's test-writer branch FIRST, as its own
# commit carrying a `Blind-Tests: <slug>-<n>` trailer, written while the
# implementation was provably absent from its worktree. This script finds those
# commits and reports any test file they introduced that a LATER commit in the
# same pull request modified. That turns "nobody weakened a test" from a promise
# into a fact the reviewer can see.
#
# Required env:
#   BASE_SHA, HEAD_SHA   commits bounding the PR (base...head)

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

echo "----- blind-test authorship -----"
echo

# Same detection as test-the-tests.sh: the language is read off the files that
# are present, so this script stays identical across template variants.
if [[ -f "$ROOT/pyproject.toml" ]]; then
  TEST_DIR="tests"
elif [[ -f "$ROOT/project.yml" ]]; then
  TEST_DIR="Tests"
else
  echo "Cannot tell tests from implementation (no pyproject.toml or project.yml)."
  echo "No blind-authorship facts for this pull request."
  exit 0
fi

# Commits in this PR carrying the trailer, oldest first.
mapfile -t BLIND < <(git -C "$ROOT" log --reverse --format='%H' \
  --grep='^Blind-Tests:' "${BASE_SHA}..${HEAD_SHA}" 2>/dev/null || true)

if [[ ${#BLIND[@]} -eq 0 ]]; then
  echo "No commits in this pull request carry a 'Blind-Tests:' trailer."
  echo
  echo "That is expected for a change built without /orchestrate — a hand-written"
  echo "fix, or a slice whose tests were not written blind. It is NOT expected for"
  echo "an orchestrated feature: there, every slice with behaviour worth asserting"
  echo "on should have a test-writer commit. If this diff adds tests for new"
  echo "behaviour and none of them were written blind, say so as a finding."
  exit 0
fi

echo "Blind test-authoring commits: ${#BLIND[@]}"
echo

TOUCHED_ANY=0
for sha in "${BLIND[@]}"; do
  short="$(git -C "$ROOT" rev-parse --short "$sha")"
  subject="$(git -C "$ROOT" log -1 --format='%s' "$sha")"
  slice="$(git -C "$ROOT" log -1 --format='%(trailers:key=Blind-Tests,valueonly)' "$sha" | tr -d '\n')"
  echo "  ${short}  ${slice:-(no slice id)}  ${subject}"

  # Test files this commit introduced or changed.
  mapfile -t FILES < <(git -C "$ROOT" diff-tree --no-commit-id --name-only -r \
    "$sha" -- "$TEST_DIR" 2>/dev/null || true)
  if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "      (touched no files under $TEST_DIR/ — a test-writer commit that wrote no tests)"
    TOUCHED_ANY=1
    continue
  fi

  for f in "${FILES[@]}"; do
    # Any LATER commit in this PR that also touched the same file.
    mapfile -t LATER < <(git -C "$ROOT" log --format='%h %s' \
      "${sha}..${HEAD_SHA}" -- "$f" 2>/dev/null || true)
    if [[ ${#LATER[@]} -eq 0 ]]; then
      echo "      $f — unmodified since it was written blind"
    else
      TOUCHED_ANY=1
      echo "      $f — MODIFIED AFTER BLIND AUTHORSHIP by ${#LATER[@]} later commit(s):"
      printf '          %s\n' "${LATER[@]}"
    fi
  done
done

echo
if [[ "$TOUCHED_ANY" -eq 1 ]]; then
  cat <<'EOF'
At least one test was changed after it was written blind. That is a QUESTION,
not a verdict — ask what the change was for:

  legitimate — the test asserted behaviour the slice never promised, so the test
               was wrong and the plan is the arbiter
  legitimate — a signature in the plan was ambiguous and both readings were
               defensible; the plan should have been fixed too, and an escape
               logged in docs/escapes.md
  FORBIDDEN  — the test was weakened, loosened, or deleted so that the existing
               implementation would pass it

The last one is the failure mode the whole blind-authorship split exists to
prevent. If the later commit relaxed an assertion, removed a case, or narrowed
what the test covers, and the implementation was not changed to match, that is a
blocking finding.
EOF
else
  echo "Every blind-written test is unmodified since its authoring commit."
fi

exit 0
