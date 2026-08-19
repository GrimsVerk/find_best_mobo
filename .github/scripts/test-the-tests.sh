#!/usr/bin/env bash
#
# test-the-tests.sh — do the new tests actually test anything?
#
# Reverts the IMPLEMENTATION portion of the pull request, leaves the tests at
# their new state, and re-runs the suite. If the suite STILL PASSES, the new
# tests do not depend on the code they claim to cover — they are testing nothing,
# and this check fails.
#
# This is the one seeded check of the ratchet (AGENTS.md). It is the highest
# value single check available to a maintainer who does not read the tests: a
# test suite that passes without its implementation is worse than no suite, it
# is a green light wired to nothing. Every further check should be added because
# docs/escapes.md asked for it, not on speculation.
#
# It runs only when a PR changes BOTH implementation and tests. A PR touching
# only one of the two has nothing to cross-check, and is skipped rather than
# guessed at.
#
# Required env:
#   BASE_SHA, HEAD_SHA   commits bounding the PR diff (base...head)
# Optional env:
#   TEST_THE_TESTS_IMPL_DIR / TEST_THE_TESTS_TEST_DIR
#                        name the two directories explicitly, for a repository
#                        whose implementation is neither src/ nor Sources/.
#                        See the block below for why this exists.
#   TEST_THE_TESTS_SUITE the shell command that runs the suite, required
#                        whenever the two above are set — the built-in runners
#                        are pytest and xcodebuild, and neither fits a tree
#                        that is neither language.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
: "${BASE_SHA:?BASE_SHA is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

skip() { echo "test-the-tests: SKIP — $*"; exit 0; }

# A template sync is machine-generated: reverting "the implementation" of a
# `copier update` and asking whether the tests still pass is not a question with
# a meaningful answer, and a template that touches both a scaffold test and a
# scaffold source file would fail this check for no reason anyone could act on.
# The template-sync check governs those branches instead, and it is stricter.
if [[ "${HEAD_REF:-}" == template/* ]]; then
  skip "'$HEAD_REF' is a template sync — verified by the template-sync check"
fi

# Language is detected from the files present, so this script stays the same for
# every variant; only the runner in ci.yml differs.
#
# THE OVERRIDE IS NOT A CONVENIENCE. Detection covers the two languages this
# template renders, and a repository that is neither — the template repository
# itself, which builds `template/` and checks it from `tests/` — hits the `else`
# branch and SKIPS. A skip here exits 0, and GitHub reports a required check
# that exited 0 as PASSING. So the one check that makes a coder's tests worth
# anything would report green on every pull request while never running, which
# is the failure this script exists to catch, committed by the script itself.
#
# Both variables must be set together: naming one and detecting the other would
# pair a deliberate directory with a guessed one, and the guess is the half that
# is wrong. A run where only one is set is a misconfiguration, so it refuses
# rather than half-applying.
if [[ -n "${TEST_THE_TESTS_IMPL_DIR:-}" || -n "${TEST_THE_TESTS_TEST_DIR:-}" ]]; then
  if [[ -z "${TEST_THE_TESTS_IMPL_DIR:-}" || -z "${TEST_THE_TESTS_TEST_DIR:-}" \
     || -z "${TEST_THE_TESTS_SUITE:-}" ]]; then
    cat >&2 <<'EOF'
test-the-tests: the override is all three variables or none of them.

  TEST_THE_TESTS_IMPL_DIR   the directory this repository BUILDS
  TEST_THE_TESTS_TEST_DIR   the directory that CHECKS it
  TEST_THE_TESTS_SUITE      the shell command that runs the suite

Exit 2, not a skip: a skip exits 0, and GitHub reports a required check that
exited 0 as passing — so a half-configured override would report green while
checking nothing, which is the exact failure this script exists to catch.
EOF
    exit 2
  fi
  IMPL_DIR="$TEST_THE_TESTS_IMPL_DIR"; TEST_DIR="$TEST_THE_TESTS_TEST_DIR"
  echo "test-the-tests: directories named explicitly — implementation '$IMPL_DIR', tests '$TEST_DIR'"
elif [[ -f pyproject.toml ]]; then
  IMPL_DIR="src"; TEST_DIR="tests"
elif [[ -f project.yml ]]; then
  IMPL_DIR="Sources"; TEST_DIR="Tests"
else
  skip "no pyproject.toml or project.yml, and no TEST_THE_TESTS_IMPL_DIR/TEST_THE_TESTS_TEST_DIR — cannot tell implementation from tests"
fi

# THE DIFF IS COMPUTED ONCE, AND A FAILURE TO COMPUTE IT IS NOT A SKIP.
#
# This used to be `changed() { git diff ... -- "$1"; }` called inside `$( )`.
# Inside a command substitution a git failure produces empty stdout, and empty
# stdout was read as "this pull request changes nothing there" — so a bad
# revision, an unfetched base, or any other git error skipped the check, and a
# skip exits 0, which GitHub reports as a PASSING required check. That is the
# same "I could not look" / "there is nothing" collapse `pr-queue.sh` refuses
# by name, in the one script whose whole purpose is to catch checks that report
# green without running.
#
# So: the range is stated out loud on every run, git's exit status is honoured,
# and a pull request whose total diff is EMPTY is a refusal rather than a skip.
# A pull request that changes no file at all does not exist; an empty total diff
# means the range is wrong, and continuing past it would report green for a
# comparison that never happened.
echo "test-the-tests: comparing ${BASE_SHA}...${HEAD_SHA}"
if ! ALL_CHANGED="$(git diff --name-only "${BASE_SHA}...${HEAD_SHA}")"; then
  cat >&2 <<EOF
test-the-tests: could not diff ${BASE_SHA}...${HEAD_SHA}.

Exit 2, not a skip. A git error here produces no file names, and no file names
used to read as "nothing changed" — which exits 0 and is reported as a passing
required check. Refusing to pass on a comparison that did not happen.
EOF
  exit 2
fi
if [[ -z "$ALL_CHANGED" ]]; then
  cat >&2 <<EOF
test-the-tests: ${BASE_SHA}...${HEAD_SHA} reports NO changed files at all.

A pull request that changes nothing does not exist, so this range is wrong —
usually a base ref that was never fetched, or a HEAD that already contains the
base. Exit 2 rather than a skip: every check below would report green having
compared nothing.
EOF
  exit 2
fi

# Anchored at the start, so a directory called `template` is not matched by a
# path called `my-template/x`.
changed() { printf '%s\n' "$ALL_CHANGED" | grep -E "^$1/" || true; }
[[ -n "$(changed "$IMPL_DIR")" ]] || \
  skip "this PR changes no files under $IMPL_DIR/ ($(printf '%s\n' "$ALL_CHANGED" | wc -l) file(s) changed in total)"
[[ -n "$(changed "$TEST_DIR")" ]] || \
  skip "this PR changes no files under $TEST_DIR/ ($(printf '%s\n' "$ALL_CHANGED" | wc -l) file(s) changed in total)"

run_suite() {
  # A repository that had to name its own directories has to name its own
  # runner too — the branch below picks pytest or xcodebuild from the directory
  # name, and neither is right for a tree that is neither language. Naming the
  # directories without naming the runner would revert the implementation, run
  # the wrong command, and report whatever that command happened to say.
  if [[ -n "${TEST_THE_TESTS_SUITE:-}" ]]; then
    bash -c "$TEST_THE_TESTS_SUITE"
  elif [[ "$IMPL_DIR" == "src" ]]; then
    if command -v uv >/dev/null 2>&1; then uv run pytest -q; else pytest -q; fi
  else
    # The .xcodeproj is generated from project.yml and is not committed, so it
    # must be regenerated after the working tree changes underneath it.
    xcodegen generate >/dev/null
    local proj scheme
    proj="$(find . -maxdepth 1 -name '*.xcodeproj' | head -1)"
    scheme="$(basename "$proj" .xcodeproj)"
    xcodebuild test -project "$proj" -scheme "$scheme" \
      -destination 'platform=iOS Simulator,name=iPhone 16' \
      CODE_SIGNING_ALLOWED=NO
  fi
}

# shellcheck disable=SC2317  # invoked via the EXIT trap below, not inline
restore() { git checkout "$HEAD_SHA" -- "$IMPL_DIR" 2>/dev/null || true; }
trap restore EXIT

echo "test-the-tests: reverting $IMPL_DIR/ to $BASE_SHA, keeping $TEST_DIR/ at $HEAD_SHA"

# Files this PR ADDED under the implementation dir won't be removed by a checkout
# of the base tree — they simply didn't exist there — so delete them explicitly.
while IFS= read -r f; do
  [[ -n "$f" ]] && rm -f "$f"
done < <(git diff --diff-filter=A --name-only "${BASE_SHA}...${HEAD_SHA}" -- "$IMPL_DIR")

# Restore the rest to their base state, if the directory existed at base at all.
if git rev-parse --verify --quiet "${BASE_SHA}:${IMPL_DIR}" >/dev/null 2>&1; then
  git checkout "$BASE_SHA" -- "$IMPL_DIR"
fi

set +e
run_suite
SUITE_RC=$?
set -e

echo
if [[ "$SUITE_RC" -eq 0 ]]; then
  cat >&2 <<EOF
test-the-tests: FAIL

The suite PASSED with this PR's implementation reverted. The tests added here do
not exercise the code they are supposed to cover — they would stay green if the
implementation were deleted, so they cannot tell you it works.

Usual causes:
  - the test asserts on a mock or fixture rather than the real code path
  - the test only checks that something doesn't raise
  - the behaviour under test is never actually invoked
  - the test duplicates an existing one and the new code is untested

Fix the tests, not this check. If you believe this is a false positive, it is an
escape: record it in docs/escapes.md with the reasoning.
EOF
  exit 1
fi

echo "test-the-tests: PASS — the suite fails without the implementation, so the tests depend on it."
exit 0
