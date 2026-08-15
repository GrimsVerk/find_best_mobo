#!/usr/bin/env bash
#
# run.sh — the whole pipeline, in order, stopping at the cost projection.
#
#   ./scripts/run.sh                  every stage
#   ./scripts/run.sh select estimate  just those, in the order given
#   ./scripts/run.sh --help
#
# THE RUN STOPS AT THE PROJECTION, AND THAT IS THE POINT. No model is invoked by
# anything here: `estimate` prints what a run WOULD cost and exits. There is no
# flag to continue, because there is no code that continues — see
# `docs/DESIGN.md` R20. Nothing in this script spends money.
#
# TRANSCRIPTS ARE NOT RE-DOWNLOADED. `fetch` skips any video already in the
# cache under `data/transcripts/` (`transcripts.py:fetch_all`), so a second run
# refetches nothing and reports "N already cached". The cache is what makes the
# pipeline restartable (R2): interrupt this at any point, run it again, and it
# picks up where it stopped. `data/` is gitignored, so the cache is local to
# this machine and survives everything except deleting it.
#
# WHAT IS NOT SKIPPED: a video that FAILED to fetch — no captions, or an error —
# is not cached, so every run tries it again. That is correct for a transient
# error and wasteful for a video that will never have captions. It is a known
# behaviour rather than a bug; if the retries become annoying, that is worth
# logging in `docs/BACKLOG.md`.

set -euo pipefail
cd "$(dirname "$0")/.."

ALL_STAGES=(index fetch select estimate)

usage() {
  cat <<'USAGE'
usage: ./scripts/run.sh [stage ...]

Stages, in the order they must run:

  index      list the channel's videos into data/index.jsonl
  fetch      download and cache the transcripts (skips anything already cached)
  select     narrow to videos with real alias evidence -> data/selected.jsonl
  estimate   cut excerpts, pack bundles, print the cost projection, and STOP

With no arguments, all four run in order. Name stages to run only those — useful
after changing config.toml, when the index and transcripts are already on disk:

  ./scripts/run.sh select estimate

Diagnostics, not part of the pipeline:

  ./scripts/run.sh aliases   how much of the corpus the alias table matches

No model is invoked by any of this, and nothing here spends money.
USAGE
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Run ./scripts/install.sh first." >&2
  exit 1
fi

# `aliases` reports the alias table's recall; it is a diagnostic and produces no
# data the pipeline reads, so it is not in ALL_STAGES.
#
# It is invoked through Python rather than the CLI because it REQUIRES --check
# and the dispatcher cannot pass per-subcommand flags — logged as BL-5 in
# docs/BACKLOG.md. This is a visible workaround for that, not a fix: when BL-5
# is ruled on, this block should become a plain `uv run find-best-mobo aliases`.
run_aliases() {
  uv run python -c "
from argparse import Namespace
from pathlib import Path
from find_best_mobo.config import load_config
from find_best_mobo.commands import aliases
raise SystemExit(aliases.run(load_config(Path('config.toml')), Namespace(check=True)))
"
}

if [ "$#" -gt 0 ]; then
  STAGES=("$@")
else
  STAGES=("${ALL_STAGES[@]}")
fi

# Validate the whole list BEFORE running any of it: a typo in the second name
# should not cost you the first stage's work.
for stage in "${STAGES[@]}"; do
  case "$stage" in
    aliases|index|fetch|select|estimate) ;;
    *) echo "unknown stage '$stage' — run ./scripts/run.sh --help" >&2; exit 2 ;;
  esac
done

STARTED="$(date '+%H:%M:%S')"
for stage in "${STAGES[@]}"; do
  echo
  echo "=============================================================="
  echo "  $stage"
  echo "=============================================================="
  case "$stage" in
    aliases) run_aliases ;;
    *) uv run find-best-mobo "$stage" ;;
  esac
done

echo
echo "Started $STARTED, finished $(date '+%H:%M:%S')."
echo "The pipeline stops here by design: no model has been invoked."
