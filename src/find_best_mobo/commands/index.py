"""The `index` subcommand: enumerate the channel into `data/index.jsonl`."""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import Config
from find_best_mobo.index import Video, enumerate_channel, write_index


@dataclass(frozen=True)
class ZeroDuration:
    """The zero-duration videos, split by which shape their listing entry has.

    Ids only: the warning names ids, and the summary counts them.
    """

    expected_shorts: tuple[str, ...]
    anomalies: tuple[str, ...]


def parse_args(argv: Sequence[str]) -> Namespace:
    """This stage declares no flags, so anything left over is its error (R1006)."""
    return subcommand_parser("index", "Enumerate the channel into data/index.jsonl.").parse_args(
        list(argv)
    )


def run(config: Config, args: Namespace) -> int:
    """Write the video index and print the classification summary."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    path = config.data_dir / "index.jsonl"
    videos = list(enumerate_channel(config))
    write_index(videos, path)
    out_of_range = sum(1 for video in videos if video.inclusion == "excluded_out_of_range")
    shorts = sum(1 for video in videos if video.inclusion == "excluded_short")
    kept = sum(1 for video in videos if video.inclusion == "pending")
    zero_duration = classify_zero_duration(videos)
    print(f"Found {len(videos)} videos on the channel; index written to {path}")
    print(f"  {out_of_range} outside the date range")
    print(f"  {shorts} excluded as Shorts")
    print(f"  {kept} kept")
    # Both lines print every run, including as zero: a number present on every
    # run is comparable across runs, and BL-15's second cost was a signal with
    # nowhere to appear.
    print(f"  {len(zero_duration.expected_shorts)} Shorts reported no duration (expected)")
    print(f"  {len(zero_duration.anomalies)} dated videos reported no duration")
    if zero_duration.anomalies:
        _warn_zero_duration(zero_duration.anomalies)
    return 0


def classify_zero_duration(videos: Sequence[Video]) -> ZeroDuration:
    """Split the zero-duration videos by the SHAPE of their listing entry (R1009).

    An entry with no duration and no date in either listing field is how the
    flat channel listing returns a Short: `classify` reads `upload_date` and
    then `timestamp`, and records `date.min` when neither parsed, so the built
    record already carries the answer and no second parser is needed. Measured
    on the first real run after the `timestamp` fix: eight such entries, all
    genuine Shorts, every run (BL-15).

    An entry with a real date and no duration is the other thing entirely — a
    video whose duration reads as 0, classifies as a Short, and is excluded. It
    is the silent drop the warning was written for, and the count threshold that
    used to gate the warning made it unreachable: a ninth id inside a list of
    eight expected ones is invisible.

    Both tuples are sorted the way `write_index` sorts — upload date, then video
    id — so an id printed here is findable in `index.jsonl` at the position it
    was printed in. `enumerate_channel` yields in channel-listing order, which
    is not that order, so sort rather than trusting what arrived.
    """
    zeros = sorted(
        (video for video in videos if video.duration_seconds == 0),
        key=lambda video: (video.upload_date, video.video_id),
    )
    return ZeroDuration(
        expected_shorts=tuple(v.video_id for v in zeros if v.upload_date == date.min),
        anomalies=tuple(v.video_id for v in zeros if v.upload_date != date.min),
    )


def _warn_zero_duration(video_ids: tuple[str, ...]) -> None:
    """Say loudly that videos with a REAL DATE are being dropped for no known reason.

    This is the case the warning was always for. A missing duration reads as 0,
    which classifies as a Short and excludes the video — but an entry carrying a
    real upload date is not the listing's Shorts shape, so something else zeroed
    its duration and a real video is vanishing from the corpus. Name the ids, or
    there is nothing to chase.

    It fires for ONE such entry. The old "more than one" threshold rested on a
    premise BL-15 measured false — that only one video can legitimately lack a
    duration — and any fixed count is wrong the day the channel posts one more
    Short.
    """
    print()
    print("!" * 72)
    print(f"WARNING: {len(video_ids)} videos have an upload date but no duration.")
    print("A missing duration is read as 0, which classifies as a Short and")
    print("excludes the video. These entries carry a real date, so they are not")
    print("the flat listing's Shorts shape and something else has zeroed their")
    print("duration — which means real videos are being dropped from the corpus.")
    print("Check these video ids against the channel:")
    for video_id in video_ids:
        print(f"  - {video_id}")
    print("!" * 72)
