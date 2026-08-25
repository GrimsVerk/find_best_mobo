#!/usr/bin/env bash
#
# run.sh — the whole pipeline, in order, stopping at the cost projection.
#
#   ./scripts/run.sh                  every stage
#   ./scripts/run.sh select estimate  just those, in the order given
#   ./scripts/run.sh --help
#
# THIS SCRIPT SPENDS MONEY, and the last stage is where. `extract` sends bundles
# to a model on the owner's subscription. Three things bound it, and none of them
# is this script being timid:
#
#   - `estimate` prints the cost projection BEFORE anything is spent, every run.
#   - `extract` does ONE batch unless told otherwise (`--batches N`, or
#     `--batches all`), then stops, reports what it cost and what remains, and
#     waits.
#   - R26's ceiling stops a run before it passes 10% above where it started,
#     read from the real subscription meter — not from the projection.
#
# Running this is a deliberate act and nothing here schedules itself
# (`docs/DESIGN.md` §3, R7, R26).
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

ALL_STAGES=(index fetch select estimate extract)

usage() {
  cat <<'USAGE'
usage: ./scripts/run.sh [stage ...]

Stages, in the order they must run:

  index      list the channel's videos into data/index.jsonl
  fetch      download and cache the transcripts (skips anything already cached)
  select     narrow to videos with real alias evidence -> data/selected.jsonl
  estimate   cut excerpts, pack bundles, print the cost projection
  extract    read bundles into claims -- THIS SPENDS MONEY

With no arguments, all five run in order, each skipping what is already done:
cached transcripts are not refetched, and batches already in the claim store are
not re-extracted. Name stages to run only those — useful after changing
config.toml, when the index and transcripts are already on disk:

  ./scripts/run.sh select estimate

Anything after the first stage name is passed to that stage:

  ./scripts/run.sh extract --batches all
  ./scripts/run.sh extract --batch 1

Diagnostics, not part of the pipeline:

  ./scripts/run.sh aliases   how much of the corpus the alias table matches

`extract` sends bundles to a model on your subscription. Everything before it
spends nothing. The projection is printed before any of it, `extract` does one
batch unless told otherwise, and R26's ceiling stops a run before it passes 10%
above where it started.
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
# data the pipeline reads, so it is not in ALL_STAGES. It requires --check, and
# the flag now reaches it through the CLI like any other (OD-10, R1006). The
# `python -c` block that used to live here was BL-5's workaround; it is gone,
# and tests/test_run_script.py is what stops it coming back.

# Stage names first, then that stage's own arguments. Splitting at the first
# token that is not a stage name is what lets `./scripts/run.sh extract
# --batches all` work without this script knowing what `--batches` means: the
# stages own their flags (R1006), and a wrapper that parsed them would be a
# second place to keep in step.
STAGES=()
FORWARDED=()
for token in "$@"; do
  if [ "${#FORWARDED[@]}" -eq 0 ]; then
    case "$token" in
      aliases|index|fetch|select|estimate|extract) STAGES+=("$token"); continue ;;
    esac
  fi
  FORWARDED+=("$token")
done

if [ "${#STAGES[@]}" -eq 0 ]; then
  if [ "${#FORWARDED[@]}" -gt 0 ]; then
    echo "unknown stage '${FORWARDED[0]}' — run ./scripts/run.sh --help" >&2
    exit 2
  fi
  STAGES=("${ALL_STAGES[@]}")
fi

# Arguments belong to ONE stage. Forwarding them to several would run the same
# flag against stages that never declared it, and the first of those to reject
# it would report an error about a command the reader did not think they were
# running.
if [ "${#FORWARDED[@]}" -gt 0 ] && [ "${#STAGES[@]}" -gt 1 ]; then
  echo "arguments follow a single stage: ./scripts/run.sh <stage> [args...]" >&2
  exit 2
fi

STARTED="$(date '+%H:%M:%S')"
for stage in "${STAGES[@]}"; do
  echo
  echo "=============================================================="
  echo "  $stage"
  echo "=============================================================="
  case "$stage" in
    aliases) uv run find-best-mobo aliases --check "${FORWARDED[@]}" ;;
    *) uv run find-best-mobo "$stage" "${FORWARDED[@]}" ;;
  esac
done

echo
echo "Started $STARTED, finished $(date '+%H:%M:%S')."
echo "Extraction stops after the batches it was asked for, or at R26's ceiling."
echo "Run again to continue, or ./scripts/run.sh extract --batches all."
