#!/bin/bash
# Rebuild events.jsonl, collision-check.md and coverage.md from the repository.
#
# Run from anywhere inside a clone of GrimsVerk/find_best_mobo that has all
# remote branches fetched. Read-only: it makes no commit, branch or push.
#
#   git fetch origin 'refs/heads/*:refs/remotes/origin/*' --prune
#   docs/postmortem/2026-08-20-window/tools/rebuild.sh [OUTDIR]
#
# OUTDIR defaults to a temporary directory. The three deliverables land there.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export S="${1:-$(mktemp -d)}"
mkdir -p "$S/src" "$S/cmp"
cp "$HERE"/*.py "$HERE"/dump.sh "$S"/
chmod +x "$S/dump.sh"

PIN=89351d71b44fcc5382f2708cbeba6c2c905c7ae0   # run/local, pinned. NOT the tip.

echo "== dumping source documents"
for stamp in 20260820T085531Z 20260820T102917Z 20260820T112543Z; do
  git show "$PIN:docs/runs/$stamp/run.md" > "$S/src/run-$stamp.md"
done
git show origin/chore/test-report-local:docs/runs/operator/local.md          > "$S/src/local.md"
git show origin/chore/test-report-web:docs/runs/operator/web.md             > "$S/src/web.md"
git show origin/main:docs/runs/operator/runner-2026-08-20.md                > "$S/src/runner.md"
git show origin/chore/test-report-local:docs/runs/operator/driver-logs/run-20260820T112543Z-console.log \
                                                                            > "$S/src/console.log"

echo "== dumping commit metadata"
"$S/dump.sh" "$PIN"                        > "$S/src/dump-runlocal.txt"
"$S/dump.sh" origin/run/web                > "$S/src/dump-runweb.txt"
"$S/dump.sh" origin/chore/test-report-local> "$S/src/dump-ledgerlocal.txt"
"$S/dump.sh" origin/chore/test-report-web  > "$S/src/dump-ledgerweb.txt"
"$S/dump.sh" origin/main                   > "$S/src/dump-main.txt"

echo "== sectioning the design and backlog layers, both lanes"
for f in DESIGN.oracle BACKLOG; do
  python3 "$S/split2.py" "$PIN"          "docs/$f.md" "$S/cmp/local-$f.json"
  python3 "$S/split2.py" origin/run/web  "docs/$f.md" "$S/cmp/web-$f.json"
done

echo "== extracting events"
for g in gen_local gen_all gen_ledger gen_rows gen_runner gen_recon; do
  python3 "$S/$g.py" > /dev/null
done
python3 "$S/assemble.py"

echo "== writing reports"
python3 "$S/mk_collision.py" > /dev/null
python3 "$S/mk_coverage.py"  > /dev/null
cp "$HERE/coverage_narrative.md" "$S/coverage_part2.md"
cat "$S/coverage_part1.md" "$S/coverage_part2.md" > "$S/coverage.md"

echo
echo "done. deliverables in $S :"
wc -l "$S/events.jsonl" "$S/collision-check.md" "$S/coverage.md"
