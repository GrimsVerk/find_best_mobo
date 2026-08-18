#!/usr/bin/env bash
#
# pr-queue.sh — what else this author has open, as a fact for the reviewer.
#
# ESC-17: nothing sees the QUEUE. Four pull requests were left open at once
# while the first was red, and two of them cited a ledger entry sitting unmerged
# inside it. The two that passed merged ahead of the one they depended on, so
# the blocked branch needed the default branch merged in and every check re-run
# by hand, by the owner. The ordering rule that prevents exactly this was quoted
# in the same pull request bodies that broke it.
#
# WHY NOTHING CAUGHT IT. Every check judges ONE pull request in isolation. The
# review gate caught each dangling citation, correctly, one pull request at a
# time — and "four open at once, two depending on a third" is not a property of
# any single one of them. It is a property of the set, and nothing was looking
# at the set.
#
# A NOTE, NEVER A FAILURE, and this is a decision rather than timidity:
#
#   - A hard check — fail while another pull request from this author is open
#     and not green — DEADLOCKS. Two opened seconds apart each observe the other
#     open and not green, and both fail. The tiebreak that fixes it (oldest
#     wins, plus a carve-out so it never blocks the owner) is more machinery
#     than the residual problem.
#   - The case that actually matters is already covered. An unattended run holds
#     ONE pipeline pull request at a time: deliver-phase.sh returns WAIT on any
#     open pull request, so the driver cannot build a queue. What is left is
#     attended work, where somebody is present to read a note.
#   - It follows the owner's ruling on the plan-adequacy report — "yes, note,
#     not red" — for the same reason: a check that fires on legitimate work
#     teaches people to route around it.
#
# If the note turns out to be ignored and the queue tangles again, that is an
# escape, and the ratchet asks for the hard version then.
#
# This script COMPUTES, it does not JUDGE, and it ALWAYS exits 0 — like
# plan-metrics.sh, whose section of the mechanical-facts region it sits beside.
#
# Optional env:
#   PR_AUTHOR    the login that opened this pull request; without it the query
#                cannot be scoped and the section says so
#   PR_NUMBER    this pull request, excluded from its own queue
#   GH           the GitHub CLI (tests substitute a stub)

set -uo pipefail

GH="${GH:-gh}"

echo "----- the author's open queue -----"
echo

if [[ -z "${PR_AUTHOR:-}" ]]; then
  echo "Not computed: the pull request author was not supplied, so the queue"
  echo "cannot be scoped to one author. Treat this as unknown rather than empty."
  exit 0
fi

if ! command -v "$GH" >/dev/null 2>&1; then
  echo "Not computed: '$GH' is not available in this job."
  exit 0
fi

# One call. `--json` rather than the human table, whose columns move between gh
# releases — a fact script that silently reports nothing is the failure this
# whole region exists to avoid.
ROWS="$("$GH" pr list --state open --limit 50 \
        --json number,title,headRefName,author,statusCheckRollup \
        --jq ".[] | select(.author.login == \"${PR_AUTHOR}\") \
              | [.number, (.statusCheckRollup // [] | map(select(.conclusion == \"FAILURE\" or .conclusion == \"TIMED_OUT\" or .conclusion == \"CANCELLED\")) | length), (.statusCheckRollup // [] | map(select(.status != \"COMPLETED\")) | length), .headRefName] | @tsv" \
        2>/dev/null || true)"

if [[ -z "$ROWS" ]]; then
  echo "No other open pull requests from '${PR_AUTHOR}'."
  echo
  echo "(If this repository's token cannot list pull requests, that also"
  echo "produces this line — it is 'nothing found', not 'nothing exists'.)"
  exit 0
fi

declare -i OTHERS=0 RED=0 PENDING=0
declare -a LINES=()
while IFS=$'\t' read -r num failing pending ref; do
  [[ -z "$num" ]] && continue
  [[ -n "${PR_NUMBER:-}" && "$num" == "$PR_NUMBER" ]] && continue
  OTHERS+=1
  state="green"
  if [[ "${failing:-0}" -gt 0 ]]; then state="RED ($failing failing)"; RED+=1
  elif [[ "${pending:-0}" -gt 0 ]]; then state="pending ($pending still running)"; PENDING+=1
  fi
  LINES+=("  #${num}  ${state}  ${ref}")
done <<<"$ROWS"

if [[ "$OTHERS" -eq 0 ]]; then
  echo "No other open pull requests from '${PR_AUTHOR}'."
  exit 0
fi

echo "'${PR_AUTHOR}' has ${OTHERS} other open pull request(s):"
printf '%s\n' "${LINES[@]}"
echo
echo "${RED} red, ${PENDING} still running."
echo
cat <<'MSG'
This is a NOTE. Nothing here fails a check, and a queue is not by itself wrong.

What it is for: every other check judges one pull request alone, so a chain —
several open at once, some depending on a ledger entry or a plan sitting
unmerged inside another — is invisible to all of them, and the cost lands on the
owner as a hand-merged branch and a full re-run. That has happened.

Worth asking when the count is high or something above is red: does THIS change
depend on anything unmerged in one of those, and would it merge ahead of what it
depends on? If so, say so — the ordering is the finding, not the count.
MSG
exit 0
