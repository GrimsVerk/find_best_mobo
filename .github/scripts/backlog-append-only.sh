#!/usr/bin/env bash
#
# backlog-append-only.sh — the backlog and its done-log are append-only.
#
# WHY THIS AND NOT AN APPROVAL GATE. `oracle-decisions.sh` resolves a decision's
# evidence against `BL-<n>` ids grepped out of `docs/BACKLOG.md`, so a token in
# that file is what authorises an amendment to the design layer. The file was
# owned by nobody, protected by nothing, and explicitly writable by the steward
# role — so a planner could file `BL-7` in one pull request and, two pull
# requests later, the pipeline could amend the design on evidence it had written
# itself forty minutes earlier. Every check green.
#
# The obvious fix — require the owner's approval before an item may be cited —
# was considered and REJECTED, on the owner's ruling. The unattended planner
# files uncertainties here mid-run; an owner review on this path stops work at
# 3am, which is the one thing this whole arrangement exists to prevent. A coder
# that hits a genuinely bad spec must be able to file evidence, and the oracle
# must be able to rule on it. That is the main path, not an attack.
#
# So the countermeasure is immutability and provenance rather than permission:
# an item, once landed, cannot be quietly reworded into evidence for something
# else, and it carries who filed it. The owner reading a decision can then see
# whether its evidence came from reality or from the pipeline that wanted it —
# which is the thing they could not see before, and the thing their plan for
# supervising the oracle needs.
#
# THE RULE: every line carrying a real `BL-<digits>` id at the base commit
# appears byte-identical at HEAD, in the same relative order. New items append
# freely, anywhere. Nothing already landed moves or changes. Marking an item
# done is an APPEND to `docs/BACKLOG.done.md`, never an edit here — which is why
# that file exists at all.
#
# Line-based rather than table-based (contrast escapes-append-only.sh, whose
# ledger is a table): the backlog is a bullet list, and its rows are wrapped
# prose. Only lines that actually carry an id are protected, so reflowing the
# surrounding explanation is free and rewriting an item is not.
#
# The skeleton writes its placeholder as `BL-<n>` — literally, with the angle
# brackets — precisely so it does not match `BL-[0-9]+` and this check never
# fires on a fresh project. Same trick as the escapes ledger's `_ESC-<n>_`.
#
# Required env:
#   BASE_SHA   the PR's base commit — the ledgers there are the protected state
# Optional env:
#   LEDGERS    space-separated; default: the three backlog ledgers —
#              docs/BACKLOG.md (what was asked for), docs/BACKLOG.done.md (what
#              came of it), docs/BACKLOG.approved.md (who said yes, and whether
#              it was the owner or the oracle). All three hold the same shape:
#              a landed line carrying a BL-<n> never changes and never moves.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
: "${BASE_SHA:?BASE_SHA is required (the PR base commit)}"
LEDGERS="${LEDGERS:-docs/BACKLOG.md docs/BACKLOG.done.md docs/BACKLOG.approved.md}"

declare -a PROBLEMS=()
CHECKED=0
PROTECTED=0

items_of() { grep -E 'BL-[0-9]+' <<<"$1" || true; }

for LEDGER in $LEDGERS; do
  BASE_CONTENT="$(git -C "$ROOT" show "${BASE_SHA}:${LEDGER}" 2>/dev/null || true)"
  # Absent at base means everything at HEAD is new, which is the correct
  # reading for a file that did not exist yet.
  [[ -n "$BASE_CONTENT" ]] || continue

  BASE_ITEMS="$(items_of "$BASE_CONTENT")"
  [[ -n "$BASE_ITEMS" ]] || continue
  CHECKED=$((CHECKED + 1))

  if [[ ! -f "$ROOT/$LEDGER" ]]; then
    PROBLEMS+=("$LEDGER was deleted — its ids are cited as evidence by landed decisions")
    continue
  fi
  HEAD_ITEMS="$(items_of "$(cat "$ROOT/$LEDGER")")"

  n=0
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    n=$((n + 1))
    grep -qxF -- "$item" <<<"$HEAD_ITEMS" \
      || PROBLEMS+=("$LEDGER: a landed item was modified or removed: $(printf '%s' "${item:0:110}" | sed 's/^[[:space:]]*//')")
  done <<<"$BASE_ITEMS"
  PROTECTED=$((PROTECTED + n))

  # And in the same relative order. An item moved out of its place changes what
  # its position says about it, and reordering is rewriting with extra steps.
  SURVIVORS="$(while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    if grep -qxF -- "$item" <<<"$BASE_ITEMS"; then printf '%s\n' "$item"; fi
  done <<<"$HEAD_ITEMS"; true)"
  if [[ "$SURVIVORS" != "$BASE_ITEMS" ]]; then
    PROBLEMS+=("$LEDGER: landed items were reordered — items append below, they do not move")
  fi
done

if [[ ${#PROBLEMS[@]} -gt 0 ]]; then
  echo "backlog-append-only: ${#PROBLEMS[@]} problem(s):" >&2
  printf '  %s\n' "${PROBLEMS[@]}" >&2
  cat >&2 <<'MSG'

The backlog is append-only because it is EVIDENCE: oracle-decisions.sh resolves
a decision's citation against the `BL-<n>` ids in it, so an item quietly
reworded is a landed decision's justification quietly rewritten — by the same
pipeline that benefits from the rewrite.

What to do instead:

  - finished an item?    append a line to docs/BACKLOG.done.md naming its id.
  - approved an item?    append a line to docs/BACKLOG.approved.md naming its id
                         and WHO approved it — owner or oracle. Approval by
                         MOVING the item is structurally impossible here, which
                         is why that file exists.
  - changed your mind?   append a NEW item saying so, and cite the old id.
  - wrong wording?       append a correction that repeats the id, exactly as
                         docs/escapes.md handles the same problem.

Nothing here stops you FILING items — an unattended run files them constantly
and that is the design. It stops landed ones from changing underneath a
decision that already cited them.

Relaxing this check to get an edit through is gate tampering.
MSG
  exit 1
fi

if [[ "$CHECKED" -eq 0 ]]; then
  echo "backlog-append-only: no landed backlog items at ${BASE_SHA:0:12}; nothing to protect yet."
else
  echo "backlog-append-only: $PROTECTED landed item(s) intact across $CHECKED ledger(s) at ${BASE_SHA:0:12}."
fi
