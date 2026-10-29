"""The `fetch` subcommand: cache every pending video's transcript.

Reads the index slice 1 wrote, fetches what is not already cached, and reports
what is now missing and why. A halt is a deliberate stop, so it reaches the
owner as a named trigger, the ledger, and exit code 1 — never a traceback.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Mapping, Sequence

from find_best_mobo.artifacts import MissingArtifact, require_file
from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import Config
from find_best_mobo.index import Video, read_index
from find_best_mobo.ledger import HaltTriggered, Ledger
from find_best_mobo.transcripts import cache_path, fetch_all, load_cached
from find_best_mobo.ytdlp import JSON3


def parse_args(argv: Sequence[str]) -> Namespace:
    """This stage declares no flags, so anything left over is its error (R1006)."""
    return subcommand_parser(
        "fetch", "Cache every pending video's transcript, and log what failed."
    ).parse_args(list(argv))


def run(config: Config, args: Namespace) -> int:
    """Fetch the pending videos' transcripts and print what happened."""
    try:
        index_path = require_file(config.data_dir / "index.jsonl", "index", "index")
    except MissingArtifact as error:
        print(error.message())
        return 1

    # Create the cache directory whether or not anything is cached — including
    # when the run halts part-way (R24). Before R1005 it appeared only on the
    # first successful write, so "fetch never ran" and "fetch ran and everything
    # failed" were one state on disk, which is the conflation R1005 forbids and
    # which the stages downstream now read as their precondition.
    (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)

    pending = [video for video in read_index(index_path) if video.inclusion == "pending"]
    # Which pending videos were ALREADY cached, recorded before the fetch so the
    # provenance counts below describe THIS RUN. A cache holding older entries
    # in another format is what those counts must not average away (R1013).
    already_cached = {
        video.video_id for video in pending if cache_path(video.video_id, config).exists()
    }
    ledger = Ledger(config.data_dir / "failures.jsonl", config, len(pending))
    try:
        fetched = fetch_all(pending, config, ledger)
    except HaltTriggered as halt:
        _print_halt(halt)
        # A halt must not hide the provenance of what DID land before it.
        _print_caption_formats(_formats_cached_this_run(pending, already_cached, config))
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
    _print_caption_formats(_formats_cached_this_run(pending, already_cached, config))

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


def _formats_cached_this_run(
    pending: Sequence[Video], already_cached: set[str], config: Config
) -> Mapping[str, int]:
    """Count the caption format of every transcript THIS RUN cached (R1013).

    Read from the records just written, restricted to the pending videos that
    were not already on disk when the run began. A walk of `data/transcripts/`
    would fold in a corpus no longer in the index and every plain cache hit,
    which is the averaging-away R1013 exists to prevent.
    """
    counts: dict[str, int] = {}
    for video in pending:
        if video.video_id in already_cached:
            continue
        transcript = load_cached(video.video_id, config)
        if transcript is None:
            continue
        counts[transcript.source_format] = counts.get(transcript.source_format, 0) + 1
    return counts


def _print_caption_formats(by_format: Mapping[str, int]) -> None:
    """Say which caption format every transcript this run cached came from (R1013).

    Both counts print on every run, zero included — the rule R1009, R1010 and
    R1012 already follow, and for the same reason: a count that appears only
    when it fired cannot be told from one that never ran.

    The fallback is CALLED OUT rather than merely counted. A transcript
    reconstructed from roll-up frames and one read verbatim from json3 are both
    fine to use and must never be indistinguishable when a later question is
    asked about one claim\'s timestamp — which is exactly what R5 cuts every
    excerpt window from.
    """
    from_json3 = by_format.get(JSON3, 0)
    fallback = sum(count for name, count in by_format.items() if name != JSON3)
    print(f"  {from_json3} transcripts read from json3")
    print(f"  {fallback} fell back to the vtt path")
    if fallback:
        print()
        print("!" * 72)
        print(f"WARNING: {fallback} transcripts came from the WebVTT fallback.")
        print("Those are reconstructed from roll-up display frames rather than read")
        print("verbatim, and their cue timings are the frames' rather than json3's")
        print("per-segment ones. The text agrees to within a fraction of a percent,")
        print("but a question about one claim's timestamp has a different answer")
        print("depending on which path produced it. Check whether json3 is still")
        print("offered for these videos.")
        print("!" * 72)
