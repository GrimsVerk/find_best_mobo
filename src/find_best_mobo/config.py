"""Every configuration lever the pipeline has, declared once.

Later slices read this module and never edit it: the levers for stages that do
not exist yet (mention threshold, excerpt windows, bundle caps, batch sizes,
halt triggers) are declared here up front so that no two slices touch the same
file. Values come from `config.toml` at the repository root, with in-code
defaults for anything absent — a missing key is never a crash.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

# The hand-authored alias table's default location. It is a full path to a
# FILE, not a directory: R1007 names the file, and a directory key would
# re-create the "assume the filename" half of BL-6 one level up. Used twice —
# as the field default below and as `load_config`'s fallback — so the two can
# never drift; `tests/test_config.py` pins them equal.
DEFAULT_ALIAS_TABLE = Path("data/aliases.toml")


@dataclass(frozen=True)
class Config:
    channel_url: str
    start_date: date
    data_dir: Path
    shorts_max_seconds: int
    mention_threshold: int
    window_before_seconds: int
    window_after_seconds: int
    per_video_excerpt_cap: int
    bundle_token_cap: int
    calibration_batch_size: int
    batch_count: int
    chars_per_token: float
    consecutive_fetch_error_limit: int
    fetch_error_rate_limit: float
    missing_caption_rate_limit: float
    # Last, because a defaulted field may not precede an undefaulted one. It
    # carries an in-code default where every other field's default lives only in
    # `load_config`, and the reason is blast radius: `Config` is frozen with no
    # defaults, so a required field would edit ten `make_config` test helpers for
    # a field eight of them never read (OD-11, R1007).
    alias_table_path: Path = DEFAULT_ALIAS_TABLE


def load_config(path: Path) -> Config:
    """Read `path` as flat TOML, falling back to the defaults for absent keys.

    A missing file behaves like an empty one: every field takes its default.
    """
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    return Config(
        channel_url=str(
            raw.get("channel_url", "https://www.youtube.com/@ActuallyHardcoreOverclocking")
        ),
        start_date=_as_date(raw.get("start_date", date(2023, 1, 1))),
        data_dir=Path(str(raw.get("data_dir", "data"))),
        shorts_max_seconds=int(raw.get("shorts_max_seconds", 120)),
        mention_threshold=int(raw.get("mention_threshold", 3)),
        window_before_seconds=int(raw.get("window_before_seconds", 120)),
        window_after_seconds=int(raw.get("window_after_seconds", 300)),
        per_video_excerpt_cap=int(raw.get("per_video_excerpt_cap", 10)),
        bundle_token_cap=int(raw.get("bundle_token_cap", 24000)),
        calibration_batch_size=int(raw.get("calibration_batch_size", 12)),
        batch_count=int(raw.get("batch_count", 3)),
        chars_per_token=float(raw.get("chars_per_token", 4.0)),
        consecutive_fetch_error_limit=int(raw.get("consecutive_fetch_error_limit", 3)),
        fetch_error_rate_limit=float(raw.get("fetch_error_rate_limit", 0.03)),
        missing_caption_rate_limit=float(raw.get("missing_caption_rate_limit", 0.05)),
        alias_table_path=Path(str(raw.get("alias_table_path", DEFAULT_ALIAS_TABLE))),
    )


def _as_date(value: object) -> date:
    """TOML dates parse as `date`, but a datetime or ISO string is folded too."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
