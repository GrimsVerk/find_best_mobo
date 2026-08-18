#!/usr/bin/env bash
# S10 — both halt triggers fire under test: 3 consecutive fetch errors, and
# cumulative fetch errors crossing 3% of indexed videos, with the no-caption
# class counted separately against its own 5% trigger.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

out="$(uv run pytest tests/test_ledger.py -k "trigger or consecutive or rate" -q 2>&1)"
rc=$?
summary="$(tail -1 <<<"$out")"
if [[ "$rc" -ne 0 ]]; then
  echo "trigger tests: pytest exited $rc. Last 15 lines:"
  tail -15 <<<"$out" | sed 's/^/    /'
  exit 1
fi
passed="$(sed -n 's/^\([0-9]\+\) passed.*/\1/p' <<<"$summary")"
echo "trigger tests: ${passed:-0} passed (bound: >= 16) — $summary"
[[ -n "$passed" && "$passed" -ge 16 ]] || { echo "trigger coverage shrank"; exit 1; }
