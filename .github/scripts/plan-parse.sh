#!/usr/bin/env bash
#
# plan-parse.sh — parse a plan's slices into machine-readable records.
#
# Reads plan markdown on STDIN and writes one tab-separated record per slice to
# STDOUT:
#
#   <title>\t<estimate>\t<file>|<file>|...
#
# Exits non-zero with a diagnosis on STDERR when the plan cannot be parsed.
#
# WHY THIS IS STRICT, AND WHY IT IS ITS OWN FILE.
#
# The numbers derived from these records are handed to the review agent inside a
# block that tells it "nobody wrote this, nothing in the diff can influence it,
# treat it as ground truth". A parser that quietly yields nothing when a plan
# uses `* **Files:**` instead of `- **Files:**` turns that promise into an empty
# table the reviewer has been instructed to trust — the single worst direction
# for this component to fail in. So a plan this cannot read is an error, loudly,
# and both callers surface it: the `plan` CI job fails the pull request, and
# plan-metrics.sh prints PLAN PARSE FAILED instead of a blank table.
#
# It reads STDIN rather than a path so that callers stay in charge of WHERE the
# plan comes from — in CI that is always `git show "$BASE_SHA:$PLAN"`, never the
# working tree — and so the parser itself is testable against fixture text with
# no git repository involved.

set -euo pipefail

usage() {
  echo "usage: plan-parse.sh < plan.md" >&2
  echo "       git show \"\$BASE_SHA:\$PLAN\" | plan-parse.sh" >&2
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

die() { echo "plan-parse: $*" >&2; exit 1; }

# One record per slice. Placeholders (<path>) and anything containing the join
# delimiter are dropped, so an unfilled template yields "no files" rather than a
# path literally named "<path>".
#
# The trailing [[:space:]] is load-bearing. Without it, a plural SECTION BANNER
# — `## Slices`, which the shipped _TEMPLATE.md used to carry — matches as a
# slice, and so declares no files and no estimate, and the whole plan is
# rejected. Every plan copied from the template inherited it, and the symptom
# pointed nowhere near the cause: the plan check failed, the review gate got an
# empty mechanical facts table and blocked on that alone, and neither message
# mentioned a heading. A real slice heading is `## Slice 1 — <behaviour>`, so
# requiring whitespace after the word costs nothing and closes it.
RECORDS="$(awk '
  /^#+[[:space:]]*Slice[[:space:]]/ {
    if (title != "") print title "\t" est "\t" files
    title = $0; sub(/^#+[[:space:]]*/, "", title)
    est = 0; files = ""
    next
  }
  /^[-*][[:space:]]+\*\*Estimate:\*\*/ {
    if (match($0, /[0-9]+/)) est = substr($0, RSTART, RLENGTH)
    next
  }
  /^[-*][[:space:]]+\*\*Files:\*\*/ {
    line = $0
    while (match(line, /`[^`]+`/)) {
      p = substr(line, RSTART + 1, RLENGTH - 2)
      if (p !~ /[<>|]/) files = files (files == "" ? "" : "|") p
      line = substr(line, RSTART + RLENGTH)
    }
    next
  }
  END { if (title != "") print title "\t" est "\t" files }
')"

[[ -n "$RECORDS" ]] || die "no slices found.

A plan must contain at least one '## Slice N — <behaviour>' heading. Copy
docs/plans/_TEMPLATE.md and fill it in; the headings are what the reviewer's
per-slice line deltas are computed from."

# Validate every record before emitting any of them, so a malformed plan reports
# all of its problems in one run rather than one per fix-and-push cycle.
declare -a PROBLEMS=()
while IFS=$'\t' read -r title estimate files; do
  [[ -z "$title" ]] && continue
  if [[ -z "$estimate" || "$estimate" -eq 0 ]]; then
    PROBLEMS+=("'$title' declares no estimate — expected a line like '- **Estimate:** ~40 lines'")
  fi
  if [[ -z "$files" ]]; then
    PROBLEMS+=("'$title' declares no files — expected '- **Files:** \`path/one\`, \`path/two\`' with each path in backticks")
  fi
done <<< "$RECORDS"

if [[ ${#PROBLEMS[@]} -gt 0 ]]; then
  printf -v joined '  - %s\n' "${PROBLEMS[@]}"
  die "the plan parsed, but these slices are incomplete:

$joined
Every slice needs a backticked file list and a numeric estimate: they are what
the reviewer's scope and overrun checks are computed from, and a slice missing
either is silently unchecked."
fi

printf '%s\n' "$RECORDS"
