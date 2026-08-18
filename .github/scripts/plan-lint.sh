#!/usr/bin/env bash
#
# plan-lint.sh — every real plan in the tree must be readable by plan-parse.sh.
#
# The `plan` job already parses the ONE plan a pull request resolves to. That is
# the plan the reviewer is judged against, so it is the one that must be
# readable — but it means a malformed plan is invisible until some later branch
# happens to resolve to it, and then it fails on a pull request that did not
# write it, with a message pointing at a document its author never touched.
# A malformed plan should fail on its own pull request, where the error can
# point at the right file.
#
# UNDERSCORE-PREFIXED FILES ARE SKIPPED, DELIBERATELY.
#
# `docs/plans/_TEMPLATE.md` is placeholders — `<path>`, `~<N> lines` — and
# plan-parse.sh rejects those BY DESIGN, so a check that parsed the template
# would have been red on the day it was added and switched off shortly after.
# That exact check was proposed once and caught by chance before it landed. The
# template's own correctness is checked a different way: the shipped skeleton
# must contain no heading that looks like a slice to the parser without being
# one (see the template repository's tests).
#
# Reads the working tree, not the base commit: the point is to fail the pull
# request that introduces the malformed plan.
#
# Usage:  plan-lint.sh
# Env:    PLANS_DIR (default: docs/plans)

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
PLANS_DIR="${PLANS_DIR:-docs/plans}"
DIR="$ROOT/$PLANS_DIR"
# Beside this script, not at a fixed path under the repository root. In a
# generated project the two are the same place; in the TEMPLATE repository,
# which invokes the shipped scripts directly out of template/ rather than
# keeping a copy, a root-anchored path names a file that is not there. Every
# other script here already resolves its neighbours this way.
HERE="$(cd "$(dirname "$0")" && pwd)"
PARSE="$HERE/plan-parse.sh"

# No plans directory is not a failure here. Whether this branch NEEDED a plan is
# plan-resolve.sh's question, and answering it twice, differently, is how a gate
# starts contradicting itself.
[[ -d "$DIR" ]] || { echo "plan-lint: no $PLANS_DIR/ — nothing to check"; exit 0; }

declare -a BROKEN=()
declare -i CHECKED=0

while IFS= read -r file; do
  base="$(basename "$file")"
  [[ "$base" == _* ]] && continue
  CHECKED+=1
  if out="$("$PARSE" < "$file" 2>&1 >/dev/null)"; then
    echo "plan-lint: ${file#"$ROOT"/} parses"
  else
    BROKEN+=("${file#"$ROOT"/}")
    echo
    echo "plan-lint: ${file#"$ROOT"/} DOES NOT PARSE"
    printf '%s\n' "$out" | sed 's/^/  /'
  fi
  # No -maxdepth: plans also live in subdirectories (docs/plans/oracle/, written
  # by a steward). A depth limit left those unparsed — and a plan nothing parses
  # reaches the reviewer as an empty facts table it was told to trust, which is
  # the exact failure this script exists for.
done < <(find "$DIR" -name '*.md' | sort)

echo
if [[ ${#BROKEN[@]} -gt 0 ]]; then
  echo "plan-lint: ${#BROKEN[@]} of $CHECKED plan(s) cannot be read: ${BROKEN[*]}" >&2
  echo >&2
  echo "A plan the parser cannot read reaches the reviewer as an empty table it" >&2
  echo "has been told to treat as ground truth — no file list, no estimates, and" >&2
  echo "nothing said about it. Fix the plan; do not relax the parser." >&2
  exit 1
fi

echo "plan-lint: $CHECKED plan(s) parse."
