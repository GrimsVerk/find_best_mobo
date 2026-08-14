#!/usr/bin/env bash
#
# coverage.sh — is every requirement in the design actually planned?
#
# Reads the requirement ids (R1, R2, ...) from docs/DESIGN.md and the `covers:`
# field from every plan under docs/plans/, and reports which requirements no plan
# claims. Also reports the reverse: plans covering ids the design doesn't define,
# which usually means a requirement was renumbered or a typo crept in.
#
# This answers the question "all the slices merged, so are we done?" — which the
# backlog cannot answer. An empty backlog is a statement about the backlog. A
# requirement no plan covers is work nobody scheduled, and it stays invisible
# right up until someone goes looking for the feature.
#
# NOT a CI gate and deliberately not wired into one: mid-project, uncovered
# requirements are the normal state. It exits non-zero when gaps exist so the
# project loop can branch on it, not so a pull request can fail on it.
#
# Usage:  coverage.sh
#
# Exit codes are distinct because /deliver branches on them, and "there is work
# left to plan" is a completely different situation from "this project is not
# set up yet". Collapsing both into 1, as this once did, made the delivery loop
# unable to tell a to-do list from a broken repository.
#
#   0  every requirement is covered by a plan
#   1  gaps: some requirement has no plan (NORMAL mid-project — this is the
#      to-do list, not a failure)
#   2  setup problem: no docs/DESIGN.md, or its section 5 has no requirement ids

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
DESIGN="${DESIGN:-$ROOT/docs/DESIGN.md}"
PLANS_DIR="${PLANS_DIR:-$ROOT/docs/plans}"

[[ -f "$DESIGN" ]] || {
  echo "coverage: no $DESIGN — run /design first" >&2
  exit 2
}

# Requirement ids, taken from section 5 only so that an "R1" mentioned in prose
# elsewhere doesn't invent a requirement.
mapfile -t REQS < <(awk '
  /^## 5\./ { in5 = 1; next }
  /^## /    { in5 = 0 }
  in5 {
    line = $0
    while (match(line, /\*\*R[0-9]+\*\*/)) {
      id = substr(line, RSTART + 2, RLENGTH - 4)
      if (!(id in seen)) { seen[id] = 1; print id }
      line = substr(line, RSTART + RLENGTH)
    }
  }' "$DESIGN")

if [[ ${#REQS[@]} -eq 0 ]]; then
  echo "coverage: no requirement ids (R1, R2, ...) found in section 5 of ${DESIGN#"$ROOT"/}."
  echo "          Give each requirement a stable id so coverage can be checked."
  exit 2
fi

# id -> space-separated list of plan slugs claiming it
declare -A CLAIMED=()
declare -a UNKNOWN=()
if [[ -d "$PLANS_DIR" ]]; then
  while IFS= read -r file; do
    [[ "$(basename "$file")" == _* ]] && continue
    plan="$(basename "$file" .md)"
    covers="$(awk '
      NR==1 && $0=="---" { infm = 1; next }
      infm && $0=="---"  { exit }
      infm && /^covers:/ { sub(/^covers:[[:space:]]*/, ""); gsub(/[][,]/, " "); print; exit }
    ' "$file")"
    for id in $covers; do
      [[ "$id" =~ ^R[0-9]+$ ]] || continue
      if printf '%s\n' "${REQS[@]}" | grep -qx "$id"; then
        CLAIMED["$id"]="${CLAIMED[$id]:-}${CLAIMED[$id]:+ }$plan"
      else
        UNKNOWN+=("$id (in $plan)")
      fi
    done
  done < <(find "$PLANS_DIR" -maxdepth 1 -name '*.md' | sort)
fi

echo "===== REQUIREMENT COVERAGE ====="
echo
covered=0
declare -a GAPS=()
for id in "${REQS[@]}"; do
  if [[ -n "${CLAIMED[$id]:-}" ]]; then
    printf '  %-5s covered by  %s\n' "$id" "${CLAIMED[$id]}"
    covered=$((covered + 1))
  else
    printf '  %-5s NOT PLANNED\n' "$id"
    GAPS+=("$id")
  fi
done

echo
echo "Covered: ${covered}/${#REQS[@]}"

if [[ ${#UNKNOWN[@]} -gt 0 ]]; then
  echo
  echo "Plans covering ids the design doesn't define:"
  printf '  %s\n' "${UNKNOWN[@]}"
  echo "  (a renumbered requirement or a typo — one of the two is wrong)"
fi

if [[ ${#GAPS[@]} -gt 0 ]]; then
  echo
  echo "${#GAPS[@]} requirement(s) with no plan: ${GAPS[*]}"
  echo "Mid-project this is normal — it is the list of what to plan next."
  exit 1
fi

echo
echo "Every requirement is covered by a plan."
echo "Note: covered means PLANNED, not delivered and not verified. Whether the"
echo "built system satisfies the success criteria is the acceptance pass —"
echo "see docs/acceptance.md."
exit 0
