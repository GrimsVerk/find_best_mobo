#!/usr/bin/env bash
#
# escape-refs.sh — every escape citation must resolve at the base commit.
#
# Entries in docs/escapes.md carry ids (ESC-1, ESC-2, ...). A gated document —
# AGENTS.md, docs/DESIGN.md, a plan — cites an entry by that id, and the
# citation must point BACKWARD: the entry must already exist in docs/escapes.md
# at the pull request's BASE commit. This script reads every citation from the
# gated documents as this pull request leaves them, resolves each against the
# ledger as the base commit has it, and fails when one dangles.
#
# WHY THE BASE COMMIT. The review gate reads gated documents at the base, so a
# document citing an entry that sits unmerged in some other pull request is
# making a claim that is false at the only moment anything checks it. That
# blocked the same pull request twice downstream — the second time purely
# because of ordering. The fix is not to soften the reviewer but to make the
# dangling state fail mechanically, on the pull request that creates it, with a
# message that names the citation.
#
# WHY RIGID IDS. An earlier candidate check — "resolve every 'logged in
# docs/escapes.md' claim against the base" — was recorded as unverified and not
# built, because parsing citation PROSE reliably is hopeless and a false
# positive on a fail-closed gate costs more than the rereading it saves. A
# rigid token has no such problem: ESC- followed by digits is a citation and
# nothing else is, so ordinary prose — including lint codes like E501 — can
# never trip it.
#
# docs/escapes.md ITSELF IS NOT SCANNED. A row there DEFINES its id rather than
# citing it, and the stub-then-complete lifecycle (see the ledger's header)
# means new rows land before the work they will eventually describe — scanning
# the ledger would forbid exactly the ordering the rule exists to enable.
#
# Required env:
#   BASE_SHA   the PR's base commit — citations must resolve against the ledger
#              as it exists here
# Optional env:
#   PLANS_DIR  where plans live (default: docs/plans)
#   ORACLE_DOC the oracle's design ledger (default: docs/DESIGN.oracle.md)
#   LEDGER     the escapes ledger (default: docs/escapes.md)

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
PLANS_DIR="${PLANS_DIR:-docs/plans}"
LEDGER="${LEDGER:-docs/escapes.md}"
ORACLE_DOC="${ORACLE_DOC:-docs/DESIGN.oracle.md}"

# Ids that exist at the base. An absent or empty ledger is not an error here:
# it just means every citation dangles, which is exactly the right answer for
# a document citing entries that have not landed.
mapfile -t HAVE < <(git -C "$ROOT" show "${BASE_SHA}:${LEDGER}" 2>/dev/null \
  | grep -oE 'ESC-[0-9]+' | sort -u)

have() {
  local id
  for id in "${HAVE[@]:-}"; do [[ "$id" == "$1" ]] && return 0; done
  return 1
}

# The gated documents, read from the working tree: the point is to fail the
# pull request that introduces the dangling citation. Underscore-prefixed plan
# files are skeletons, not plans.
DOCS=()
[[ -f "$ROOT/AGENTS.md" ]] && DOCS+=("AGENTS.md")
[[ -f "$ROOT/docs/DESIGN.md" ]] && DOCS+=("docs/DESIGN.md")
# The second design document. An oracle decision cites its evidence by id, and
# an ESC- citation there is exactly as capable of dangling as one in a plan —
# more so, since it is written unattended.
[[ -f "$ROOT/$ORACLE_DOC" ]] && DOCS+=("$ORACLE_DOC")
if [[ -d "$ROOT/$PLANS_DIR" ]]; then
  while IFS= read -r f; do
    [[ "$(basename "$f")" == _* ]] && continue
    DOCS+=("${f#"$ROOT"/}")
    # No -maxdepth: plans also live in subdirectories (docs/plans/oracle/).
  done < <(find "$ROOT/$PLANS_DIR" -name '*.md' | sort)
fi

declare -a DANGLING=()
declare -i CITES=0
for doc in "${DOCS[@]}"; do
  while IFS= read -r id; do
    [[ -z "$id" ]] && continue
    CITES+=1
    have "$id" || DANGLING+=("$doc cites $id")
  done < <(grep -oE 'ESC-[0-9]+' "$ROOT/$doc" 2>/dev/null | sort -u)
done

if [[ ${#DANGLING[@]} -gt 0 ]]; then
  echo "escape-refs: citation(s) that do not resolve at the base commit:" >&2
  printf '  %s\n' "${DANGLING[@]}" >&2
  cat >&2 <<'MSG'

A gated document may cite an escapes entry only once that entry exists on the
default branch. The review gate reads gated documents at the BASE commit, so a
citation to an unmerged entry is false at the only moment anything checks it —
and it will block again on the next push, because nothing about the ordering
changes on its own.

Land the entry first — a one-line stub (id, what escaped, gate column, check
column marked "unverified — pending") is enough and blocks on nothing — then
cite it from here. If the id is a typo, fix the citation instead.
MSG
  exit 1
fi

echo "escape-refs: $CITES citation(s) across ${#DOCS[@]} document(s), all resolve at ${BASE_SHA:0:12}."
