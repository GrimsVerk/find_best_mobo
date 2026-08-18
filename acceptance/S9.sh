#!/usr/bin/env bash
# S9 — the suite passes offline and deterministically, with yt-dlp and every
# agent stage exercised against fixtures.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

marked="$(grep -rl '@pytest\.mark\.allow_network' tests/ --include='*.py' --exclude=conftest.py | wc -l || true)"
echo "tests opting out of the network guard: $marked (bound: 0)"
[[ "$marked" -eq 0 ]] || { echo "a test may reach the network"; exit 1; }

run() { # run -> prints pytest's summary line, or its output on failure
  local out rc
  out="$(uv run pytest -q 2>&1)"; rc=$?
  [[ "$rc" -eq 0 ]] || { printf 'pytest exited %s. Last 15 lines:\n' "$rc"
                         tail -15 <<<"$out" | sed 's/^/    /'; return "$rc"; }
  tail -1 <<<"$out"
}

first="$(run)"  || { echo "run 1: $first";  exit 1; }
second="$(run)" || { echo "run 2: $second"; exit 1; }
echo "run 1: $first"
echo "run 2: $second"
# Compare the counts only — the timing differs between runs by design.
[[ "$first" == *" passed"* ]] || { echo "the suite did not pass"; exit 1; }
[[ "${first%% in *}" == "${second%% in *}" ]] || { echo "not deterministic"; exit 1; }
