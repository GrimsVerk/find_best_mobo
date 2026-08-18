#!/usr/bin/env bash
#
# escapes-append-only.sh — the escape ledger is append-only, mechanically.
#
# docs/escapes.md has said "never rewrite an entry" since the day it existed,
# and docs/DESIGN.oracle.md gets the same promise ENFORCED by
# oracle-decisions.sh. The asymmetry was the gap (ESC-15): the escape ledger is
# the oracle's other evidence source, and an agent editing an inconvenient row
# — its own escape, say — would change what a landed decision's citation means,
# with a diff that reads as an edit rather than as history being rewritten.
# This is the same check over the other file.
#
# THE RULE: every entry row present at the base commit appears byte-identical
# at HEAD, in the same relative order. New rows may be appended anywhere below;
# nothing already landed moves or changes. A correction is an APPENDED row that
# repeats the id — the lifecycle the ledger has always documented (a stub lands
# first, the demonstrated check appends later under the same id) — so
# corrections pass and rewrites fail, which is exactly the distinction wanted.
#
# An "entry row" is a table line carrying a real id: `^\|` and `ESC-<digits>`.
# The skeleton's placeholder row spells its id `_ESC-<n>_` precisely so it is
# not one — and so the check never fires on a fresh project.
#
# The surrounding prose is NOT protected. It is template-maintained text,
# updated by `copier update`, and freezing it would make every template release
# conflict with this check. The record is the rows.
#
# THE SECOND LEDGER. `docs/escapes.done.md` records which escapes are FINISHED,
# and it exists because of this very check: an append-only ledger cannot be
# edited to mark something done, so "done" lived only in the Check-added prose
# that no script reads, and the log grew forever without converging. The backlog
# hit the same wall and got docs/BACKLOG.done.md; this is the same answer.
#
# It gets one rule the ledger itself does not need. **A closure row must name at
# least one repository path, and that path must exist.** The delivery driver
# reads this file and stops handing closed ids to the oracle, so a row here is a
# mechanism for making the oracle look away — and a closure saying "it is fine
# now" would be exactly the party that wanted it closed doing the closing.
#
# The rule is deliberately weak: it proves a file is there, not that the file
# checks anything. The stronger versions were rejected, and the reasons are the
# ones this repository keeps logging — requiring the named check to RUN puts a
# test harness inside a gate, and requiring the owner's approval puts them back
# in the loop at 3am (ESC-28). If a bogus closure is ever observed, that is an
# escape and the ratchet applies.
#
# Required env:
#   BASE_SHA   the PR's base commit — the ledgers there are the protected state
# Optional env:
#   LEDGERS    space-separated; default: "docs/escapes.md docs/escapes.done.md"
#   LEDGER     the old single-file name, still honoured so a caller that sets it
#              is not silently ignored

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
DONE_LEDGER="${DONE_LEDGER:-docs/escapes.done.md}"
LEDGERS="${LEDGERS:-${LEDGER:-docs/escapes.md} $DONE_LEDGER}"

declare -a PROBLEMS=()
CHECKED=0
PROTECTED=0

rows_of() { grep -E '^\|' <<<"$1" | grep -E 'ESC-[0-9]+' || true; }

# --- the closure rule, applied only to the done-log ------------------------
# Every row there must name a repository path that exists. See the header.
check_closure_rows() { # check_closure_rows <head content>
  local row paths p found
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    local id; id="$(grep -oE 'ESC-[0-9]+' <<<"$row" | head -1)"
    # Backticked tokens containing a slash or a dot are candidate paths. A row
    # citing only prose names nothing anybody can open.
    mapfile -t paths < <(grep -oE '`[^`]+`' <<<"$row" | tr -d '`' | grep -E '[/.]' || true)
    if [[ ${#paths[@]} -eq 0 ]]; then
      PROBLEMS+=("$DONE_LEDGER: $id names no check — a closure cites a path in backticks, because a row here makes the delivery driver stop giving this escape to the oracle")
      continue
    fi
    found=0
    for p in "${paths[@]}"; do
      [[ -e "$ROOT/$p" ]] && found=1 && break
    done
    [[ "$found" -eq 1 ]] || PROBLEMS+=("$DONE_LEDGER: $id cites ${paths[*]}, and none of those exists in this repository — a closure names something a reader can open")
  done <<<"$(rows_of "$1")"
}

for LEDGER in $LEDGERS; do
  # The ledger as the base commit has it. Absent there means everything at HEAD
  # is new, which is the correct reading for a file that did not exist yet.
  BASE_CONTENT="$(git -C "$ROOT" show "${BASE_SHA}:${LEDGER}" 2>/dev/null || true)"
  HEAD_CONTENT=""
  [[ -f "$ROOT/$LEDGER" ]] && HEAD_CONTENT="$(cat "$ROOT/$LEDGER")"

  # The closure rule runs on HEAD whether or not the file existed at base — a
  # done-log created by THIS pull request is exactly when a bogus closure would
  # first appear.
  [[ "$LEDGER" == "$DONE_LEDGER" && -n "$HEAD_CONTENT" ]] && check_closure_rows "$HEAD_CONTENT"

  [[ -n "$BASE_CONTENT" ]] || continue

  BASE_ROWS="$(rows_of "$BASE_CONTENT")"
  [[ -n "$BASE_ROWS" ]] || continue
  CHECKED=$((CHECKED + 1))

  if [[ ! -f "$ROOT/$LEDGER" ]]; then
    PROBLEMS+=("$LEDGER was deleted — the ledger is append-only, and its entries are cited by id from gated documents")
    continue
  fi
  HEAD_ROWS="$(rows_of "$HEAD_CONTENT")"

  # Every base row survives, byte-identical. Fixed-string, whole-line: a row
  # that was "only reworded" is a row that changed.
  n=0
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    n=$((n + 1))
    grep -qxF "$row" <<<"$HEAD_ROWS" \
      || PROBLEMS+=("$LEDGER: a landed row was modified or removed: ${row:0:100}")
  done <<<"$BASE_ROWS"
  PROTECTED=$((PROTECTED + n))

  # And in the same relative order. Take HEAD's rows, keep only the ones that
  # were present at base, and the sequence must BE the base sequence —
  # reordering is rewriting with extra steps, and an entry moved out of its
  # place changes what "newest at the bottom" says about it.
  SURVIVORS="$(while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    if grep -qxF "$row" <<<"$BASE_ROWS"; then printf '%s\n' "$row"; fi
  done <<<"$HEAD_ROWS"; true)"
  if [[ "$SURVIVORS" != "$BASE_ROWS" ]]; then
    PROBLEMS+=("$LEDGER: landed rows were reordered — entries append below, they do not move")
  fi
done

if [[ ${#PROBLEMS[@]} -gt 0 ]]; then
  echo "escapes-append-only: ${#PROBLEMS[@]} problem(s):" >&2
  printf '  %s\n' "${PROBLEMS[@]}" >&2
  cat >&2 <<MSG

These ledgers are append-only: entries are cited by id from gated documents, and
the agent that caused an escape is often the one that logs it — which is safe
only while a landed row cannot be quietly revised. To correct an entry, APPEND a
correction row with the same id, exactly as the file's own header says.

And a row in $DONE_LEDGER makes the delivery driver stop handing that escape to
the oracle, so it has to name a check somebody can open. "Closed, it is fine
now" is the shape this refuses.

Relaxing either rule to get an edit through is gate tampering.
MSG
  exit 1
fi

if [[ "$CHECKED" -eq 0 ]]; then
  echo "escapes-append-only: no landed entry rows at ${BASE_SHA:0:12}; nothing to protect yet."
else
  echo "escapes-append-only: $PROTECTED landed row(s) intact across $CHECKED ledger(s) at ${BASE_SHA:0:12}."
fi
