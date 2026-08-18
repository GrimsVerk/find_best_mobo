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
# IT ALSO REPORTS PLAN ADEQUACY, AND ONLY REPORTS IT.
#
# "Covered" means some plan's `covers:` names the id. That is a CLAIM, and
# nothing downstream compares the claim to what the plan's slices actually
# build: a plan naming twelve requirements and building three passes every gate
# green, and the run then walks to acceptance reporting "every requirement is
# covered by a plan". So this additionally reports which covered ids no slice in
# the claiming plan ever mentions.
#
# A NOTE, NEVER A FAILURE — the owner's ruling, in one word: "yes, note, not
# red." And it is the right call. A platform requirement, an offline
# requirement, a privacy constraint: these are legitimately owned by no single
# slice, so a strict check would fire on honest plans and teach authors to route
# around it by padding slice text with ids. A requirement marked
# `*(non-functional)*` in the design's section 5 is reported as an EXPECTED
# absence rather than a gap, which is what keeps the signal readable.
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
#   2  setup problem: no docs/DESIGN.md, its section 5 has no requirement ids, or
#      the design or a plan contains a MALFORMED id (see below)
#
# A GATE THAT IGNORES WHAT IT CANNOT PARSE FAILS OPEN.
#
# This once recognised `**R<digits>**` and nothing else, and silently skipped
# anything else — `R2a`, a typo, a renumbering slip. Such an id was never
# counted as covered and never reported as missing: it simply did not exist as
# far as this script was concerned, while reading like a requirement to every
# human. A plan claiming it was then rejected with no hint why.
#
# So a malformed id is now an error. "Malformed" is anchored on a digit: an id
# is `R` or `S` followed by digits, and a bold token that starts `R<digit>` or
# `S<digit>` but is not all digits after the letter is a broken id. Prose is
# untouched by that rule — `**Rationale**` and `**Scope**` do not have a digit
# after the letter — which is why the check is anchored there rather than on any
# bold word beginning with R or S. It cannot catch every conceivable typo; it
# catches every id-shaped one, and it never guesses about ordinary prose.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
# A LIST, space-separated. There are two design documents: the owner's, and the
# oracle's evidence-driven ledger (docs/DESIGN.oracle.md), which an agent may
# append to unattended. Requirements are the UNION of both — a plan covering an
# oracle requirement was otherwise reported as "an id the design doesn't
# define", which reads as a typo and is not one.
DESIGN="${DESIGN:-$ROOT/docs/DESIGN.md $ROOT/docs/DESIGN.oracle.md}"
PLANS_DIR="${PLANS_DIR:-$ROOT/docs/plans}"

read -r -a DESIGN_DOCS <<< "$DESIGN"
declare -a PRESENT=()
for doc in "${DESIGN_DOCS[@]}"; do
  [[ -f "$doc" ]] && PRESENT+=("$doc")
done

[[ ${#PRESENT[@]} -gt 0 ]] || {
  echo "coverage: no ${DESIGN_DOCS[0]} — run /design first" >&2
  exit 2
}

# Requirement ids from one document. Two rules, applied uniformly to every
# design document so there is no per-file magic:
#
#   - section 5 only, so that an "R1" mentioned in prose elsewhere doesn't
#     invent a requirement. This is what docs/DESIGN.md uses;
#   - `**Requirements added:**` lines, which is how a decision in the oracle
#     ledger declares the ids it introduces. That document is a list of dated
#     decisions and has no section 5, and its rationales legitimately mention
#     ids they did NOT define — a superseded one, for instance — so reading the
#     whole file would invent requirements out of prose.
#
#     The line must START with a list marker, and that is not cosmetic. The
#     shipped ledger skeleton documents its own schema in an INDENTED code
#     block, example ids and all — so a rule that matched the label anywhere
#     defined R1000 and R1001 in every generated project on day one, as
#     requirements no plan would ever cover and that no amount of work could
#     clear. Column-anchoring excludes the indented example and matches every
#     real decision, which writes the field at column 0.
#
# A document that has neither shape simply contributes nothing.
ids_from() {
  awk '
    /^## 5\./ { in5 = 1; next }
    /^## /    { in5 = 0 }
    in5 || /^[-*] \*\*Requirements added:\*\*/ {
      line = $0
      if (!in5) sub(/^.*\*\*Requirements added:\*\*/, "", line)
      while (match(line, /\*\*R[0-9]+\*\*/)) {
        print substr(line, RSTART + 2, RLENGTH - 4)
        line = substr(line, RSTART + RLENGTH)
      }
      if (!in5) {
        # Split on non-alphanumerics rather than using a word-boundary escape:
        # \b is a backspace to awk, not a boundary, and the difference is
        # silent — the pattern simply never matches and every oracle
        # requirement vanishes from the coverage report.
        n = split(line, parts, /[^A-Za-z0-9]+/)
        for (i = 1; i <= n; i++) if (parts[i] ~ /^R[0-9]+$/) print parts[i]
      }
    }' "$1"
}

mapfile -t REQS < <(
  for doc in "${PRESENT[@]}"; do ids_from "$doc"; done | awk '!seen[$0]++'
)

# Requirements the design marks `*(non-functional)*`. A platform, offline,
# privacy or cost requirement is legitimately owned by no single slice, so the
# adequacy report below calls its absence expected rather than a gap. The mark
# is the design's, and the design is CODEOWNERS-owned, so what counts as
# "expected" stays the owner's rather than the planner's.
declare -A NONFUNCTIONAL=()
while IFS= read -r id; do
  [[ -n "$id" ]] && NONFUNCTIONAL["$id"]=1
done < <(
  for doc in "${PRESENT[@]}"; do
    awk '
      /^## 5\./ { in5 = 1; next }
      /^## /    { in5 = 0 }
      in5 && /\*\(non-functional\)\*/ {
        line = $0
        while (match(line, /\*\*R[0-9]+\*\*/)) {
          print substr(line, RSTART + 2, RLENGTH - 4)
          line = substr(line, RSTART + RLENGTH)
        }
      }' "$doc"
  done | sort -u
)

# Malformed ids anywhere in a design document — not just section 5. An id-shaped
# token in section 12's milestones or section 13's criteria is read as an id by
# every human who passes it, so it has to be one.
mapfile -t BAD_IDS < <(
  for doc in "${PRESENT[@]}"; do
    awk -v doc="${doc#"$ROOT"/}" '
      {
        line = $0
        while (match(line, /\*\*[RS][0-9][^*]*\*\*/)) {
          id = substr(line, RSTART + 2, RLENGTH - 4)
          if (id !~ /^[RS][0-9]+$/ && !(id in seen)) {
            seen[id] = 1; print id " (in " doc ")"
          }
          line = substr(line, RSTART + RLENGTH)
        }
      }' "$doc"
  done
)

if [[ ${#BAD_IDS[@]} -gt 0 ]]; then
  echo "coverage: malformed requirement id(s):" >&2
  printf '  %s\n' "${BAD_IDS[@]}" >&2
  cat >&2 <<'MSG'

An id is R or S followed by digits — R1, R12, S3. Anything else cannot be
matched against a plan's `covers:` field, and the failure is silent in the worst
direction: the id is neither counted as covered nor reported as missing, so it
reads like a tracked requirement while being tracked by nothing.

Renumber it (R2a and R2b become R2 and R3), or if it is deliberately not a
requirement id, write it without the bold id form.
MSG
  exit 2
fi

if [[ ${#REQS[@]} -eq 0 ]]; then
  echo "coverage: no requirement ids (R1, R2, ...) found in ${PRESENT[*]#"$ROOT"/}."
  echo "          Give each requirement a stable id so coverage can be checked."
  exit 2
fi

# id -> space-separated list of plan slugs claiming it
declare -A CLAIMED=()
declare -a UNKNOWN=()
declare -a MALFORMED=()
declare -a UNSLICED=()
declare -a EXPECTED_ABSENCES=()
if [[ -d "$PLANS_DIR" ]]; then
  while IFS= read -r file; do
    [[ "$(basename "$file")" == _* ]] && continue
    plan="$(basename "$file" .md)"
    covers="$(awk '
      NR==1 && $0=="---" { infm = 1; next }
      infm && $0=="---"  { exit }
      infm && /^covers:/ { sub(/^covers:[[:space:]]*/, ""); gsub(/[][,]/, " "); print; exit }
    ' "$file")"
    # Which of the ids this plan CLAIMS does its own slice text ever mention?
    # From the first slice heading onward, so the summary's prose — which
    # legitimately restates the covers list — cannot satisfy the check on the
    # body's behalf. An id a plan claims and never speaks of again is the
    # over-claim this reports.
    sliced="$(awk '
      /^#+[[:space:]]*Slice[[:space:]]/ { inslices = 1 }
      inslices {
        line = $0
        n = split(line, parts, /[^A-Za-z0-9]+/)
        for (i = 1; i <= n; i++) if (parts[i] ~ /^R[0-9]+$/) print parts[i]
      }' "$file" | sort -u)"
    for id in $covers; do
      # Same rule as the design side, and for the same reason: an id this cannot
      # parse must not be quietly dropped. It was, and a plan covering `R2a`
      # counted for nothing while looking like it counted for something.
      if [[ ! "$id" =~ ^R[0-9]+$ ]]; then
        MALFORMED+=("$id (in $plan)")
        continue
      fi
      if printf '%s\n' "${REQS[@]}" | grep -qx "$id"; then
        CLAIMED["$id"]="${CLAIMED[$id]:-}${CLAIMED[$id]:+ }$plan"
        if ! grep -qxF "$id" <<<"$sliced"; then
          if [[ -n "${NONFUNCTIONAL[$id]:-}" ]]; then
            EXPECTED_ABSENCES+=("$id (in $plan) — marked non-functional")
          else
            UNSLICED+=("$id (in $plan)")
          fi
        fi
      else
        UNKNOWN+=("$id (in $plan)")
      fi
    done
    # No -maxdepth: plans also live in subdirectories (docs/plans/oracle/),
    # and a depth limit made those invisible to coverage — silently, which is
    # the worst way for a coverage report to be wrong.
  done < <(find "$PLANS_DIR" -name '*.md' | sort)
fi

if [[ ${#MALFORMED[@]} -gt 0 ]]; then
  echo "coverage: malformed id(s) in a plan's covers: field:" >&2
  printf '  %s\n' "${MALFORMED[@]}" >&2
  echo >&2
  echo "An id is R followed by digits. One that is not can never match a" >&2
  echo "requirement, so the plan claims coverage it will never be credited with." >&2
  exit 2
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

# ------------------------------------------------------- plan adequacy (NOTE)
# Reported, never failed, on the owner's ruling — "yes, note, not red." A
# requirement legitimately owned by no single slice is common enough that a
# strict check would fire on honest plans and teach authors to pad slice text
# with ids, which would make the report worthless in exactly the way that keeps
# a green pipeline meaningless.
echo
echo "----- plan adequacy (a NOTE, never a failure) -----"
if [[ ${#UNSLICED[@]} -gt 0 ]]; then
  echo
  echo "Claimed by a plan, mentioned by none of its slices:"
  printf '  %s\n' "${UNSLICED[@]}"
  echo
  echo "  'Covered' means a plan NAMED the id. Nothing else compares that claim"
  echo "  to what the plan's slices build, so a plan naming twelve requirements"
  echo "  and building three passes every gate green. Either a slice delivers"
  echo "  each id above and should say so, or the covers: list is over-claimed."
else
  echo "  Every claimed requirement is mentioned by a slice of the plan claiming it."
fi
if [[ ${#EXPECTED_ABSENCES[@]} -gt 0 ]]; then
  echo
  echo "Expected absences (marked *(non-functional)* in the design):"
  printf '  %s\n' "${EXPECTED_ABSENCES[@]}"
  echo "  A platform, offline, privacy or cost requirement is owned by no single"
  echo "  slice by nature. Listed so the absence reads as a decision."
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
