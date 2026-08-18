#!/usr/bin/env bash
#
# acceptance-criteria.sh — the success criteria are scripts, and they run.
#
# `docs/acceptance.md` is the one artifact in an unattended run whose pull
# request requires the owner's review — the single guaranteed connection between
# a run and a human. Until this check existed, the evidence in that table was an
# agent's narration: "I ran X and it printed Y." Everywhere else this template
# rigorously separates computed facts from judged verdicts. That table was the
# one place narration was admitted as evidence, and it is the last thing the
# owner reads.
#
# So each criterion §13 does NOT mark `(owner)` gets `acceptance/S<n>.sh`, and
# this runs them.
#
# ON EVERY PULL REQUEST, not once at the acceptance pass. A criterion verified
# once and trusted thereafter is exactly the "verified once, trusted forever"
# shape this template distrusts everywhere else: one that passed at acceptance
# and regressed three merges later is caught by nothing until the next
# acceptance pass, which may be the last one.
#
# WHAT IT FAILS ON, and each rule exists because of a specific way this check
# could otherwise be worth nothing:
#
#   1. A SCRIPT THAT EXITS NON-ZERO. The live gate. A criterion is waived out of
#      this only by a landed oracle decision (below).
#
#   2. A LANDED SCRIPT THAT WAS DELETED OR EMPTIED. Deleting the measurement is
#      the cheapest way to make a failing criterion stop failing, and it looks
#      like tidying. A script goes away when its criterion leaves §13, and §13
#      is CODEOWNERS-owned, so that removal is the owner's.
#
#   3. A CRITERION `docs/acceptance.md` CLAIMS AS `pass` WITH NO SCRIPT. This is
#      the narration hole, closed from the other side: the table may not report a
#      criterion passed by an agent unless the thing that re-runs it is in the
#      repository. An `owner` row is untouched by this — those are judgement
#      calls the design assigned to the owner and no script can hold them.
#
# WHAT IT ONLY REPORTS, and why that is not a hole:
#
#   an agent-verifiable id in §13 with NO script yet is listed on every pull
#   request and does not fail the check. A criterion for work that has not been
#   built is failing correctly, and failing the pipeline for it would stop the
#   build that would make it pass — the run would deadlock on its own definition
#   of done before the first feature merged. The gap is visible on every pull
#   request and it is fatal at the acceptance pass, where rule 3 catches any
#   attempt to claim a pass without one.
#
# THE WAIVER. A decision in `docs/DESIGN.oracle.md` may carry an eighth field:
#
#     - **Criterion waived:** S3 — <why the test does not recognise what was built>
#
# read at the BASE commit. A waived criterion is skipped here, and this is an
# exception rather than a hole for four reasons: it names a criterion and never
# the check, so a waiver on S3 leaves S4 gating; it lives in the append-only
# evidence-citing ledger, so it inherits immutability for free; it is visible
# twice, here and as `pending / owner` in the acceptance table; and it is
# self-clearing, because a later change that makes S3 genuinely pass records
# `pass` at the next acceptance pass and the waiver is moot.
#
# THE ORACLE MAY NOT MARK A CRITERION PASSED. It rules, it records, it may waive
# — the row stays `pending / owner`. The owner's own success criterion is
# adjudicated by the owner, or the last checkpoint before the human becomes
# something an agent can talk its way past.
#
# Required env:
#   BASE_SHA   the PR's base commit — §13, the acceptance table, the landed
#              scripts and the waivers are all read there. The standard a change
#              is measured against is never the standard the change is proposing.
# Optional env:
#   DESIGN_DOC      default: docs/DESIGN.md
#   ORACLE_DOC      default: docs/DESIGN.oracle.md
#   ACCEPTANCE_DOC  default: docs/acceptance.md
#   ACCEPTANCE_DIR  default: acceptance
#   CRITERION_TIMEOUT  default: 600 (seconds, per script)

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 2
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
DESIGN_DOC="${DESIGN_DOC:-docs/DESIGN.md}"
ORACLE_DOC="${ORACLE_DOC:-docs/DESIGN.oracle.md}"
ACCEPTANCE_DOC="${ACCEPTANCE_DOC:-docs/acceptance.md}"
ACCEPTANCE_DIR="${ACCEPTANCE_DIR:-acceptance}"
CRITERION_TIMEOUT="${CRITERION_TIMEOUT:-600}"

show_base() { git show "${BASE_SHA}:$1" 2>/dev/null || true; }

declare -a PROBLEMS=()
fail() { PROBLEMS+=("$1"); }

# ------------------------------------------------- §13, as the owner wrote it
# A criterion is a list item whose first token is a bold `S<digits>` id. It runs
# until the next such item or the next `##` heading, because a criterion wraps
# across lines and the `(owner)` mark may land on any of them.
#
# The skeleton writes its placeholder as `**S<n>**` — literally, angle brackets
# and all — precisely so it carries no digit and never matches here. Same trick
# as `BL-<n>` and `ESC-<n>`. Without it this required check would be red on the
# first pull request of every generated project, demanding a script for a
# criterion nobody has written yet.
criteria_of() { # criteria_of <content>  ->  "<id>\t<owner|agent>" per line
  awk '
    /^## 13\./ { in13 = 1; next }
    /^## /     { if (in13) exit }
    !in13      { next }
    {
      if (match($0, /^[[:space:]]*[-*][[:space:]]*\*\*S[0-9]+\*\*/)) {
        if (id != "") print id "\t" (owner ? "owner" : "agent")
        id = $0
        sub(/^[[:space:]]*[-*][[:space:]]*\*\*/, "", id)
        sub(/\*\*.*$/, "", id)
        owner = 0
      }
      if (id != "" && index($0, "(owner)")) owner = 1
    }
    END { if (id != "") print id "\t" (owner ? "owner" : "agent") }
  ' <<<"$1"
}

DESIGN_AT_BASE="$(show_base "$DESIGN_DOC")"
if [[ -z "$DESIGN_AT_BASE" ]]; then
  echo "acceptance-criteria: no $DESIGN_DOC at ${BASE_SHA:0:12} — nothing to check yet."
  exit 0
fi

declare -a AGENT_IDS=() OWNER_IDS=()
while IFS=$'\t' read -r id kind; do
  [[ -z "$id" ]] && continue
  if [[ "$kind" == "owner" ]]; then OWNER_IDS+=("$id"); else AGENT_IDS+=("$id"); fi
done < <(criteria_of "$DESIGN_AT_BASE")

# -------------------------------------------------------------- the waivers
# Read at the base commit, from LANDED decisions only. A pull request cannot
# waive the criterion it is failing: the waiver has to have merged first, which
# is the same ordering every other citation in this repository obeys.
declare -A WAIVED=()
ORACLE_AT_BASE="$(show_base "$ORACLE_DOC")"
if [[ -n "$ORACLE_AT_BASE" ]]; then
  while IFS=$'\t' read -r od sid; do
    [[ -z "$sid" ]] && continue
    WAIVED["$sid"]="$od"
  done < <(awk '
    /^## OD-[0-9]+/ { od = $2 }
    /^[[:space:]]*[-*][[:space:]]*\*\*Criterion waived:\*\*/ {
      line = $0
      sub(/^.*\*\*Criterion waived:\*\*/, "", line)
      n = split(line, parts, /[^A-Za-z0-9]+/)
      for (i = 1; i <= n; i++) if (parts[i] ~ /^S[0-9]+$/) print od "\t" parts[i]
    }' <<<"$ORACLE_AT_BASE")
fi

# ------------------------------------------ 2. a landed script never vanishes
mapfile -t LANDED < <(git ls-tree -r --name-only "$BASE_SHA" -- "$ACCEPTANCE_DIR" 2>/dev/null \
  | grep -E "^${ACCEPTANCE_DIR}/S[0-9]+\.sh$" || true)
for f in "${LANDED[@]:-}"; do
  [[ -z "$f" ]] && continue
  sid="$(basename "$f" .sh)"
  # A criterion the owner removed from §13 takes its script with it, and that
  # removal landed on a CODEOWNERS-reviewed pull request. Everything else is a
  # measurement being deleted to stop it measuring.
  still_named=0
  for id in "${AGENT_IDS[@]:-}" "${OWNER_IDS[@]:-}"; do [[ "$id" == "$sid" ]] && still_named=1; done
  if [[ ! -s "$f" ]]; then
    if [[ "$still_named" -eq 1 ]]; then
      fail "$f was deleted or emptied while $sid is still a criterion in $DESIGN_DOC §13 — a measurement is removed when its criterion is, and §13 is the owner's"
    fi
  fi
done

# ------------------------------- 3. the table may not claim what it cannot rerun
# One row per criterion: `| S1 | pass | agent | ... |`. Read at base for the
# same reason as everything else — this pull request does not get to write the
# claim and be judged against its own version of it.
ACC_AT_BASE="$(show_base "$ACCEPTANCE_DOC")"
if [[ -n "$ACC_AT_BASE" ]]; then
  while IFS=$'\t' read -r sid status by; do
    [[ -z "$sid" ]] && continue
    [[ "$status" == "pass" && "$by" == "agent" ]] || continue
    [[ -n "${WAIVED[$sid]:-}" ]] && continue
    [[ -f "$ACCEPTANCE_DIR/$sid.sh" ]] \
      || fail "$ACCEPTANCE_DOC records $sid as 'pass / agent', but there is no $ACCEPTANCE_DIR/$sid.sh — a pass an agent claims is a pass somebody else can re-run, or it is narration"
  done < <(awk -F'|' '
    /^[[:space:]]*\|/ {
      gsub(/[[:space:]]|[_*`]/, "")
      if (NF < 4) next
      if ($2 ~ /^S[0-9]+$/) print $2 "\t" tolower($3) "\t" tolower($4)
    }' <<<"$ACC_AT_BASE")
fi

# ------------------------------------------------------ 1. run what is there
echo "===== ACCEPTANCE CRITERIA ====="
echo
echo "Criteria in $DESIGN_DOC §13 at ${BASE_SHA:0:12}: \
${#AGENT_IDS[@]} agent-verifiable, ${#OWNER_IDS[@]} marked (owner)."
echo

RAN=0; PASSED=0; SKIPPED=0
declare -a UNSCRIPTED=()
for id in "${AGENT_IDS[@]:-}"; do
  [[ -z "$id" ]] && continue
  script="$ACCEPTANCE_DIR/$id.sh"
  if [[ -n "${WAIVED[$id]:-}" ]]; then
    printf '  %-5s WAIVED   by %s (%s)\n' "$id" "${WAIVED[$id]}" "$ORACLE_DOC"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  if [[ ! -f "$script" ]]; then
    printf '  %-5s no script yet (%s)\n' "$id" "$script"
    UNSCRIPTED+=("$id")
    continue
  fi
  RAN=$((RAN + 1))
  printf '  %-5s running %s\n' "$id" "$script"
  out=""; rc=0
  out="$(timeout "$CRITERION_TIMEOUT" bash "$script" 2>&1)" || rc=$?
  printf '%s\n' "$out" | sed 's/^/         | /'
  if [[ "$rc" -eq 0 ]]; then
    printf '  %-5s PASS\n\n' "$id"
    PASSED=$((PASSED + 1))
  else
    printf '  %-5s FAIL (exit %s)\n\n' "$id" "$rc"
    fail "$id failed: $script exited $rc"
  fi
done

for id in "${OWNER_IDS[@]:-}"; do
  [[ -z "$id" ]] && continue
  printf '  %-5s (owner) — judged by the owner, never by a script\n' "$id"
  # An (owner) criterion with a script is an agent having decided it could
  # verify something the design says it cannot. Reported, not failed: the file
  # may be a leftover from before the owner marked it, and the honest fix is a
  # deletion rather than a red pipeline.
  [[ -f "$ACCEPTANCE_DIR/$id.sh" ]] \
    && echo "         note: $ACCEPTANCE_DIR/$id.sh exists for an (owner) criterion — §13 says no script can settle this one."
done

echo
echo "Ran ${RAN}, passed ${PASSED}, waived ${SKIPPED}, not yet scripted ${#UNSCRIPTED[@]}."
if [[ ${#UNSCRIPTED[@]} -gt 0 ]]; then
  echo
  echo "No script yet: ${UNSCRIPTED[*]}"
  echo "Not a failure here — a criterion for work that is not built yet fails"
  echo "correctly, and failing the pipeline for it would stop the build that"
  echo "would make it pass. It IS a failure the moment $ACCEPTANCE_DOC claims"
  echo "one of them passed."
fi

# --------------------------------------------------------------------- verdict

if [[ ${#PROBLEMS[@]} -gt 0 ]]; then
  echo
  echo "acceptance-criteria: ${#PROBLEMS[@]} problem(s):" >&2
  printf '  %s\n' "${PROBLEMS[@]}" >&2
  cat >&2 <<MSG

A success criterion is the owner's definition of done, and $ACCEPTANCE_DOC is
the one artifact in an unattended run whose pull request requires their review.
These scripts are what keep the evidence in that table something anyone can
re-run, instead of a sentence an agent wrote about itself.

If a criterion is failing:

  - the implementation is wrong    -> fix it; this is the ordinary loop working.
  - the test is wrong              -> file it as a BL-<n> in docs/BACKLOG.md and
                                      let the oracle rule; correct the script on
                                      its own pull request.
  - the criterion is met by other
    means the script cannot see    -> the ORACLE rules that, records it in
                                      $ORACLE_DOC, and adds
                                      "- **Criterion waived:** <id> — <why>".
                                      The row in $ACCEPTANCE_DOC stays
                                      'pending / owner'. The oracle may NOT mark
                                      a criterion passed.

Weakening a script to get green is gate tampering, and it is the one kind that
edits the definition of done.
MSG
  exit 1
fi

echo
echo "acceptance-criteria: nothing claims more than it can show."
exit 0
