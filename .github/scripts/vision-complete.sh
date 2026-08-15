#!/usr/bin/env bash
#
# vision-complete.sh — docs/VISION.md must be finished before implementation is
# planned.
#
# WHY THIS IS A GATE AND NOT ADVICE.
#
# docs/VISION.md is the tiebreaker an unattended agent reaches for when the
# evidence is ambiguous, and every decision in docs/DESIGN.oracle.md must quote
# the statement it relied on. An unfilled vision file therefore does not fail
# loudly — it fails at 3am, in the one role that exists to keep work moving,
# which then either stops or invents the owner's priorities. Neither shows up as
# a red check anywhere.
#
# WHY IT FIRES ON PLANS RATHER THAN ON THE DESIGN.
#
# The vision does NOT have to be written first. Writing it after the design is
# often easier — you understand what the thing is by then, and a vision written
# before you do is a guess about your own priorities. What must not happen is
# IMPLEMENTATION starting while it is still empty, and the moment implementation
# starts is the moment a plan lands: plans precede code by rule
# (`AGENTS.md`, "A plan lands before the code it plans"), so a pull request that
# adds or edits a plan is the exact boundary worth checking. Design-doc pull
# requests pass freely; so does every code pull request, whose plan already
# cleared this.
#
# WHAT "COMPLETE" MEANS.
#
# Every `##` section carries at least one line that is not a heading, not blank,
# and not an HTML comment. That catches the realistic failure — two sections
# filled in and the rest left as prompts — without prescribing length or
# wording. A section a project does not want is DELETED rather than left empty,
# which reads as a decision instead of as an omission.
#
# An ABSENT docs/VISION.md passes. Deleting the file is how a project opts out
# of the oracle entirely, and that is a legitimate choice; a skeleton left
# unfilled is not the same thing, and is the only state this rejects.
#
# Required env:
#   BASE_SHA   the PR's base commit — used to see whether this PR touches a plan
# Optional env:
#   HEAD_SHA   default: HEAD
#   VISION     default: docs/VISION.md
#   PLANS_DIR  default: docs/plans

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
HEAD_SHA="${HEAD_SHA:-HEAD}"
VISION="${VISION:-docs/VISION.md}"
PLANS_DIR="${PLANS_DIR:-docs/plans}"

# Does this pull request touch a plan? If not, it is not the moment this check
# is about, and it says nothing.
TOUCHED="$(git -C "$ROOT" diff --name-only "${BASE_SHA}...${HEAD_SHA}" -- "$PLANS_DIR" \
  | grep -v '/_' || true)"
if [[ -z "$TOUCHED" ]]; then
  echo "vision-complete: this pull request touches no plan — nothing to check."
  exit 0
fi

if [[ ! -f "$ROOT/$VISION" ]]; then
  echo "vision-complete: no $VISION — this project has opted out of it. Nothing to check."
  exit 0
fi

# Sections with no content of their own. awk over the file: a `## ` line opens a
# section; anything that is not blank, not a comment line, and not a heading
# counts as content for whichever section is open.
mapfile -t EMPTY < <(awk '
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
' "$ROOT/$VISION")

if [[ ${#EMPTY[@]} -gt 0 ]]; then
  echo "vision-complete: $VISION still has unfilled section(s):" >&2
  printf '  ## %s\n' "${EMPTY[@]}" >&2
  cat >&2 <<MSG

This pull request adds or edits a plan, which is where implementation begins —
and $VISION is where an unattended agent looks when the evidence is ambiguous.
Every decision in docs/DESIGN.oracle.md must quote a statement from it, so an
unfilled section does not fail here; it fails overnight, in the one role that
exists to keep work moving, which then stops or invents your priorities.

The vision does NOT have to be written before the design — writing it after is
often easier, because by then you know what the thing is. It only has to be
finished before implementation is planned, which is now.

Fill the sections in, or DELETE the ones this project does not want: an absent
section reads as a decision, an empty one reads as an omission. Deleting the
whole file is how a project opts out of the oracle, and that passes.
MSG
  exit 1
fi

echo "vision-complete: $VISION is filled in; this pull request may plan work."
