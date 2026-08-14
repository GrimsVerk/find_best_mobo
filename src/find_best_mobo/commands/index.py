"""The `index` subcommand: enumerate the channel into `data/index.jsonl`."""

from __future__ import annotations

from argparse import Namespace

from find_best_mobo.config import Config
from find_best_mobo.index import enumerate_channel, write_index


def run(config: Config, args: Namespace) -> int:
    """Write the video index and print the classification summary."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    path = config.data_dir / "index.jsonl"
    videos = list(enumerate_channel(config))
    write_index(videos, path)
    out_of_range = sum(1 for video in videos if video.inclusion == "excluded_out_of_range")
    shorts = sum(1 for video in videos if video.inclusion == "excluded_short")
    kept = sum(1 for video in videos if video.inclusion == "pending")
    print(f"Found {len(videos)} videos on the channel; index written to {path}")
    print(f"  {out_of_range} outside the date range")
    print(f"  {shorts} excluded as Shorts")
    print(f"  {kept} kept")
    return 0
