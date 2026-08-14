"""The `index` subcommand: enumerate the channel into `data/index.jsonl`."""

from __future__ import annotations

from argparse import Namespace

from find_best_mobo.config import Config
from find_best_mobo.index import Video, enumerate_channel, write_index


def run(config: Config, args: Namespace) -> int:
    """Write the video index and print the classification summary."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    path = config.data_dir / "index.jsonl"
    videos = list(enumerate_channel(config))
    write_index(videos, path)
    out_of_range = sum(1 for video in videos if video.inclusion == "excluded_out_of_range")
    shorts = sum(1 for video in videos if video.inclusion == "excluded_short")
    kept = sum(1 for video in videos if video.inclusion == "pending")
    zero_duration = _zero_duration_ids(videos)
    print(f"Found {len(videos)} videos on the channel; index written to {path}")
    print(f"  {out_of_range} outside the date range")
    print(f"  {shorts} excluded as Shorts")
    print(f"  {kept} kept")
    print(f"  {len(zero_duration)} with no duration reported")
    if len(zero_duration) > 1:
        _warn_zero_duration(zero_duration)
    return 0


def _zero_duration_ids(videos: list[Video]) -> list[str]:
    """Ids of videos reporting no duration, in index order.

    Sorted the way `write_index` sorts — upload date, then video id — so the
    ids named in the warning can be found in `index.jsonl` in the order they
    are printed. `enumerate_channel` yields in channel-listing order, which is
    not that order, so sort rather than trusting what arrived.
    """
    zeros = [video for video in videos if video.duration_seconds == 0]
    zeros.sort(key=lambda video: (video.upload_date, video.video_id))
    return [video.video_id for video in zeros]


def _warn_zero_duration(video_ids: list[str]) -> None:
    """Say loudly that videos are being dropped for a reason we don't know.

    A missing duration reads as 0, which classifies as a Short and excludes the
    video. Exactly one is expected and harmless — a stream in progress reports
    no duration, and he can only be live in one place at a time. Two or more
    means the zero has some other cause and real videos are vanishing from the
    corpus, so the count alone is not enough: name the ids, or there is nothing
    to chase.
    """
    print()
    print("!" * 72)
    print(f"WARNING: {len(video_ids)} videos reported no duration.")
    print("A missing duration is read as 0, which classifies as a Short and")
    print("excludes the video. Only one such video is expected (a stream in")
    print("progress); more than one means something else is zeroing durations")
    print("and these videos are being dropped from the corpus for no good")
    print("reason. Check these video ids against the channel:")
    for video_id in video_ids:
        print(f"  - {video_id}")
    print("!" * 72)
