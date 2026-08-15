#!/usr/bin/env bash
#
# oracle-decisions.sh — the oracle's design ledger is append-only, and every
# decision in it metabolises evidence that already exists.
#
# `docs/DESIGN.md` is CODEOWNERS-owned, so design corrections wait for the
# owner. That is correct and it is also the reason unattended work stops at the
# first thing the evidence contradicts. `docs/DESIGN.oracle.md` is the second
# design document: an agent may append to it while nobody is awake, and this
# check is what makes that safe. It is deliberately NOT CODEOWNERS-owned —
# ownership there would stop overnight work, which is the whole point.
#
# Four duties, and the first is the load-bearing one.
#
# 1. EVERY DECISION CITES EVIDENCE THAT EXISTS AT THE BASE COMMIT.
#
#    The oracle cannot invent a design change. It can only act on something the
#    process already logged: an escape (`ESC-<n>` in docs/escapes.md) or a
#    backlog item (`BL-<n>` in docs/BACKLOG.md). Citing nothing fails; citing
#    something that sits unmerged in another pull request fails, for the same
#    reason escape-refs.sh exists — a claim about a ledger must be true at the
#    only moment anything checks it.
#
#    This is what separates "the design was corrected by data" from "an agent
#    rewrote the design". Rigid ids make it a dumb string match, safe to fail
#    closed on; prose would not be.
#
# 2. APPEND-ONLY. A decision present at the base commit may not be modified or
#    removed. Supersession is a NEW decision naming the old id — the lifecycle
#    docs/escapes.md already uses. Without this, an oracle could quietly revise
#    yesterday's ruling and the diff would read as an edit rather than a
#    reversal. Ids must also increase: reusing an id is how a modification
#    disguises itself as an addition.
#
# 3. SCHEMA. Each decision carries a date, its evidence, the requirement ids it
#    adds or supersedes, the alternatives it weighed, its rationale, and the
#    `docs/VISION.md` statement it relied on. The last field is the point of the
#    whole role: when the owner disagrees with a decision they can see which
#    vision statement produced it and edit THAT, rather than guessing which of
#    ten sentences was doing the work.
#
# 4. A CAP. 150 decisions. Not a real bound — a runaway-loop backstop.
#
# Two smaller duties over the artifacts around the ledger:
#
#   - every plan under docs/plans/oracle/ cites a decision id that exists at the
#     base commit, so a steward cannot invent work either;
#   - a handoff file under docs/oracle/ present at the base commit is never
#     modified. Handoffs are per-run files, so they are append-only by
#     construction — a new file per run, never an edit to an old one.
#
# REQUIREMENT IDS SHARE ONE INTEGER SPACE with docs/DESIGN.md — the grammar is
# `R<digits>` with no namespace mechanism — so oracle requirements start at
# R1000 and this check enforces the offset. Without it the two documents would
# silently collide on R7 and coverage.sh would union two different requirements
# into one.
#
# Required env:
#   BASE_SHA        the PR's base commit — evidence and decisions are resolved
#                   against the tree as it exists here
# Optional env:
#   ORACLE_DOC      default: docs/DESIGN.oracle.md
#   ORACLE_DIR      default: docs/oracle       (handoffs)
#   PLANS_DIR       default: docs/plans        (oracle plans in <dir>/oracle/)
#   LEDGER          default: docs/escapes.md
#   BACKLOG         default: docs/BACKLOG.md
#   MAX_DECISIONS   default: 150
#   REQ_OFFSET      default: 1000

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
ORACLE_DOC="${ORACLE_DOC:-docs/DESIGN.oracle.md}"
ORACLE_DIR="${ORACLE_DIR:-docs/oracle}"
PLANS_DIR="${PLANS_DIR:-docs/plans}"
LEDGER="${LEDGER:-docs/escapes.md}"
BACKLOG="${BACKLOG:-docs/BACKLOG.md}"
MAX_DECISIONS="${MAX_DECISIONS:-150}"
REQ_OFFSET="${REQ_OFFSET:-1000}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

declare -a PROBLEMS=()
fail() { PROBLEMS+=("$1"); }

# The tree as the base commit has it. A file absent there is not an error: it
# just means everything in it is new, which is the correct reading for a
# document that did not exist yet.
show_base() { git -C "$ROOT" show "${BASE_SHA}:$1" 2>/dev/null || true; }

# Decision ids in a document, in file order.
ids_in() { grep -oE '^## OD-[0-9]+' "$1" 2>/dev/null | sed 's/^## //' || true; }

# One decision's block: its heading through to the next `## ` heading or EOF.
block_of() { # block_of <file> <id>
  awk -v id="$2" '
    $0 ~ "^## " id "([^0-9]|$)" { inb = 1; print; next }
    inb && /^## /                { exit }
    inb                          { print }
  ' "$1"
}

# ---------------------------------------------------------------- the ledger

BASE_DOC="$WORK/base-oracle.md"
show_base "$ORACLE_DOC" > "$BASE_DOC"
HEAD_DOC="$ROOT/$ORACLE_DOC"

mapfile -t BASE_IDS < <(ids_in "$BASE_DOC")
mapfile -t HEAD_IDS < <([[ -f "$HEAD_DOC" ]] && ids_in "$HEAD_DOC")

# Evidence that exists at the base commit. Read once; every decision resolves
# against these two sets.
mapfile -t HAVE_EVIDENCE < <(
  { show_base "$LEDGER"  | grep -oE 'ESC-[0-9]+'
    show_base "$BACKLOG" | grep -oE 'BL-[0-9]+'
  } | sort -u
)
has_evidence() {
  local id
  for id in "${HAVE_EVIDENCE[@]:-}"; do [[ "$id" == "$1" ]] && return 0; done
  return 1
}

# --- 2. append-only: nothing at base may be modified or removed -------------
for id in "${BASE_IDS[@]:-}"; do
  [[ -z "$id" ]] && continue
  if [[ ! -f "$HEAD_DOC" ]]; then
    fail "$id was removed ($ORACLE_DOC no longer exists)"
    continue
  fi
  before="$(block_of "$BASE_DOC" "$id")"
  after="$(block_of "$HEAD_DOC" "$id")"
  if [[ -z "$after" ]]; then
    fail "$id was removed — decisions are append-only"
  elif [[ "$before" != "$after" ]]; then
    fail "$id was modified — decisions are append-only; supersede it with a new decision citing $id"
  fi
done

# --- ids are unique, and new ones increase ---------------------------------
HIGHEST_AT_BASE=0
for id in "${BASE_IDS[@]:-}"; do
  [[ -z "$id" ]] && continue
  n="${id#OD-}"
  [[ "$n" -gt "$HIGHEST_AT_BASE" ]] && HIGHEST_AT_BASE="$n"
done

declare -a SEEN=()
for id in "${HEAD_IDS[@]:-}"; do
  [[ -z "$id" ]] && continue
  for prev in "${SEEN[@]:-}"; do
    [[ "$prev" == "$id" ]] && fail "$id appears more than once — ids identify a decision, so they cannot repeat"
  done
  SEEN+=("$id")
done

# --- 1, 3: every NEW decision cites resolvable evidence and carries the schema
declare -i NEW=0
for id in "${HEAD_IDS[@]:-}"; do
  [[ -z "$id" ]] && continue
  is_new=1
  for old in "${BASE_IDS[@]:-}"; do [[ "$old" == "$id" ]] && is_new=0; done
  [[ "$is_new" -eq 1 ]] || continue
  NEW+=1

  n="${id#OD-}"
  if [[ "$n" -le "$HIGHEST_AT_BASE" ]]; then
    fail "$id is not above the highest id at the base commit (OD-$HIGHEST_AT_BASE) — a reused or backdated id is how a modification disguises itself as an addition"
  fi

  block="$(block_of "$HEAD_DOC" "$id")"

  # Schema. Each field is asserted to be present AND to say something: a label
  # with nothing after it is the shape a schema check is most often satisfied by
  # and least often helped by.
  for field in "Date" "Evidence" "Requirements added" "Requirements superseded" \
               "Vision statement relied on" "Alternatives considered" "Rationale"; do
    value="$(printf '%s\n' "$block" \
      | sed -n "s/^[[:space:]]*[-*][[:space:]]*\*\*${field}:\*\*[[:space:]]*//p" | head -1)"
    if ! printf '%s\n' "$block" | grep -qF "**${field}:**"; then
      fail "$id has no **${field}:** field"
    elif [[ -z "$value" ]]; then
      fail "$id has an empty **${field}:** field"
    fi
  done

  # 1. Evidence must exist at the base commit.
  evidence_line="$(printf '%s\n' "$block" \
    | sed -n 's/^[[:space:]]*[-*][[:space:]]*\*\*Evidence:\*\*[[:space:]]*//p' | head -1)"
  mapfile -t CITED < <(printf '%s\n' "$evidence_line" | grep -oE '(ESC|BL)-[0-9]+' | sort -u)
  if [[ ${#CITED[@]} -eq 0 ]]; then
    fail "$id cites no evidence — an oracle decision resolves something already logged (ESC-<n> in $LEDGER, BL-<n> in $BACKLOG), never something it thought of"
  fi
  for cite in "${CITED[@]:-}"; do
    has_evidence "$cite" \
      || fail "$id cites $cite, which does not exist at the base commit"
  done

  # 3. Requirement ids: shape, and the offset that keeps the two design
  # documents out of each other's integer space.
  added="$(printf '%s\n' "$block" \
    | sed -n 's/^[[:space:]]*[-*][[:space:]]*\*\*Requirements added:\*\*[[:space:]]*//p' | head -1)"
  if [[ "$added" != *"(none)"* ]]; then
    mapfile -t ADDED_IDS < <(printf '%s\n' "$added" | grep -oE '\bR[0-9]+\b' | sort -u)
    if [[ ${#ADDED_IDS[@]} -eq 0 ]]; then
      fail "$id has a **Requirements added:** field that names no id — write ids as R<n>, or '(none)'"
    fi
    for req in "${ADDED_IDS[@]:-}"; do
      if [[ "${req#R}" -lt "$REQ_OFFSET" ]]; then
        fail "$id adds $req, below the oracle offset R$REQ_OFFSET — requirement ids share ONE integer space with $ORACLE_DOC's counterpart, so a low id silently collides with a requirement the owner wrote"
      fi
    done
  fi
done

# --- 4. the runaway-loop backstop ------------------------------------------
TOTAL=${#HEAD_IDS[@]}
if [[ "$TOTAL" -gt "$MAX_DECISIONS" ]]; then
  fail "$TOTAL decisions, over the cap of $MAX_DECISIONS — this is a runaway-loop backstop, not a real bound; if it has been reached legitimately, the owner raises it"
fi

# ------------------------------------------------------- handoffs, per run
# A handoff is written once and never modified. It is a new file per run, which
# is what makes it append-only by construction rather than by promise.
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if [[ ! -f "$ROOT/$f" ]]; then
    fail "$f was removed — a handoff is a record of one run and is never deleted"
  elif ! diff -q <(show_base "$f") "$ROOT/$f" >/dev/null 2>&1; then
    fail "$f was modified — a handoff is written once; a later run writes a NEW file"
  fi
done < <(git -C "$ROOT" ls-tree -r --name-only "$BASE_SHA" -- "$ORACLE_DIR" 2>/dev/null \
         | grep -E '/handoff-[^/]+\.md$' || true)

# ------------------------------------------------- plans built on a decision
# A steward writes plans under docs/plans/oracle/. Each must name the decision
# it implements, and that decision must already have landed — the same
# backward-only rule the ledger itself follows.
ORACLE_PLANS="$ROOT/$PLANS_DIR/oracle"
if [[ -d "$ORACLE_PLANS" ]]; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    [[ "$(basename "$f")" == _* ]] && continue
    rel="${f#"$ROOT"/}"
    mapfile -t PLAN_CITES < <(grep -oE '\bOD-[0-9]+\b' "$f" | sort -u)
    if [[ ${#PLAN_CITES[@]} -eq 0 ]]; then
      fail "$rel cites no oracle decision — a plan under $PLANS_DIR/oracle/ implements a decision, it does not propose one"
      continue
    fi
    resolved=0
    for cite in "${PLAN_CITES[@]}"; do
      for old in "${BASE_IDS[@]:-}"; do [[ "$old" == "$cite" ]] && resolved=1; done
    done
    [[ "$resolved" -eq 1 ]] || fail "$rel cites ${PLAN_CITES[*]}, none of which exists at the base commit — land the decision first, then plan it"
  done < <(find "$ORACLE_PLANS" -name '*.md' | sort)
fi

# --------------------------------------------------------------------- verdict

if [[ ${#PROBLEMS[@]} -gt 0 ]]; then
  echo "oracle-decisions: ${#PROBLEMS[@]} problem(s):" >&2
  printf '  %s\n' "${PROBLEMS[@]}" >&2
  cat >&2 <<MSG

$ORACLE_DOC is the one design document an agent may write unattended, and these
are the conditions that make that safe: every decision metabolises evidence that
already landed, nothing already decided is quietly revised, and each decision
says which docs/VISION.md statement it leaned on so the owner can steer by
editing that statement rather than by arguing with the decision.

Relaxing this check to get a decision through is gate tampering.
MSG
  exit 1
fi

echo "oracle-decisions: ${TOTAL} decision(s), ${NEW} new in this pull request, all resolve at ${BASE_SHA:0:12}."
