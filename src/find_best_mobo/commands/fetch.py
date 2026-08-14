"""The `fetch` subcommand: cache every pending video's transcript.

Reads the index slice 1 wrote, fetches what is not already cached, and reports
what is now missing and why. A halt is a deliberate stop, so it reaches the
owner as a named trigger, the ledger, and exit code 1 — never a traceback.
"""

from __future__ import annotations

from argparse import Namespace

from find_best_mobo.config import Config
from find_best_mobo.index import read_index
from find_best_mobo.ledger import HaltTriggered, Ledger
from find_best_mobo.transcripts import fetch_all


def run(config: Config, args: Namespace) -> int:
    """Fetch the pending videos' transcripts and print what happened."""
    index_path = config.data_dir / "index.jsonl"
    if not index_path.exists():
        print(f"No index at {index_path}. Run `find-best-mobo index` first.")
        return 1

    pending = [video for video in read_index(index_path) if video.inclusion == "pending"]
    ledger = Ledger(config.data_dir / "failures.jsonl", config, len(pending))
    try:
        fetched = fetch_all(pending, config, ledger)
    except HaltTriggered as halt:
        _print_halt(halt)
        return 1

    failures = ledger.failures()
    no_captions = sum(1 for failure in failures if failure.failure_class == "no_captions")
    fetch_errors = sum(1 for failure in failures if failure.failure_class == "fetch_error")
    # Cache hits are never reported by `fetch_all` — it skips them silently, by
    # design — so they are what is left once this run's work is accounted for.
    cached = len(pending) - fetched - len(failures)
    print(f"{len(pending)} pending videos in the index")
    print(f"  {cached} already cached")
    print(f"  {fetched} fetched this run")
    print(f"  {len(failures)} failed ({no_captions} no_captions, {fetch_errors} fetch_error)")
    return 0


def _print_halt(halt: HaltTriggered) -> None:
    """Report the trigger and the whole ledger the run stopped on.

    The ledger is already on disk; printing it too means the owner sees the
    reason without going looking for a file they may not know exists.
    """
    print(f"Halted: {halt.trigger}")
    print(f"{len(halt.ledger)} failures recorded this run:")
    for failure in halt.ledger:
        line = (
            f"  {failure.video_id}  {failure.upload_date.isoformat()}  "
            f"{failure.title}  {failure.failure_class}"
        )
        if failure.detail:
            line = f"{line}  {failure.detail}"
        print(line)
