"""The video index: classification rules and the JSONL form on disk.

Every video the channel listing yields becomes exactly one record, carrying
its classification and the reason it was included or excluded — exclusions are
recorded, never implied (`docs/DESIGN.md` R1). Given the same input the index
is byte-identical (R23): records sort by upload date then video id, and JSON
serialises with sorted keys.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from find_best_mobo.config import Config
from find_best_mobo.ytdlp import list_channel_entries

_LIVE_STATUSES = frozenset({"is_live", "was_live", "post_live"})

# Fixed by owner ruling, not configuration: the listing's dates are bucketed to
# roughly mid-month, so the comparison date is moved back far enough that no
# video uploaded on or after config.start_date can be excluded. Two months is
# deliberately more than the observed bucketing needs.
DATE_SLOP_DAYS: int = 62


def effective_start_date(config: Config) -> date:
    """The date videos are compared against: the configured start, minus slop."""
    return config.start_date - timedelta(days=DATE_SLOP_DAYS)


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    upload_date: date
    duration_seconds: int
    was_live: bool
    classification: str  # "regular" | "short"
    inclusion: str  # "pending" | "excluded_short" | "excluded_out_of_range"


def classify(entry: dict[str, object], config: Config) -> Video:
    """Turn one raw yt-dlp entry dict into a classified `Video`.

    Pure: no I/O, no network, no clock. Duration is checked before date, so a
    Short uploaded before the start date is excluded as a Short (owner ruling
    recorded in the plan). Livestreams are never excluded, and neither is any
    duration above the Shorts threshold — only Shorts are excluded.

    The date comes from `upload_date` (yt-dlp's `YYYYMMDD` string, the
    per-video extraction path) or, when that is absent or unparseable, from
    `timestamp` (epoch seconds as UTC, the flat channel listing path). The
    listing's dates are bucketed, so the range comparison uses
    `effective_start_date` rather than the configured start — but the date
    recorded on the `Video` is always the real one, never the shifted one.
    """
    duration = _duration(entry.get("duration"))
    upload_date = _upload_date(entry.get("upload_date"))
    if upload_date is None:
        upload_date = _timestamp_date(entry.get("timestamp"))
    if duration <= config.shorts_max_seconds:
        classification, inclusion = "short", "excluded_short"
    elif upload_date is None or upload_date < effective_start_date(config):
        classification, inclusion = "regular", "excluded_out_of_range"
    else:
        classification, inclusion = "regular", "pending"
    return Video(
        video_id=str(entry.get("id", "")),
        title=str(entry.get("title", "")),
        upload_date=upload_date if upload_date is not None else date.min,
        duration_seconds=duration,
        was_live=_was_live(entry),
        classification=classification,
        inclusion=inclusion,
    )


def enumerate_channel(config: Config) -> Iterator[Video]:
    """Lazily classify every upload the channel listing yields."""
    for entry in list_channel_entries(config.channel_url, config.start_date):
        yield classify(entry, config)


def write_index(videos: Iterable[Video], path: Path) -> int:
    """Write one JSON record per line and return how many were written.

    Deterministic: records sort by upload date then video id, keys sort within
    each record, dates serialise as ISO-8601, and no line carries trailing
    whitespace.
    """
    ordered = sorted(videos, key=lambda video: (video.upload_date, video.video_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for video in ordered:
            record = asdict(video)
            record["upload_date"] = video.upload_date.isoformat()
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    return len(ordered)


def read_index(path: Path) -> Iterator[Video]:
    """Yield the `Video` records of an index file, equal to what went in."""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            yield Video(
                video_id=record["video_id"],
                title=record["title"],
                upload_date=date.fromisoformat(record["upload_date"]),
                duration_seconds=record["duration_seconds"],
                was_live=record["was_live"],
                classification=record["classification"],
                inclusion=record["inclusion"],
            )


def _duration(value: object) -> int:
    """A missing or null duration is 0, which classifies as a Short."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return int(value)
    return 0


def _upload_date(value: object) -> date | None:
    """Parse yt-dlp's `YYYYMMDD` string; anything unparseable is None."""
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _timestamp_date(value: object) -> date | None:
    """Interpret epoch seconds as a UTC date; zero is 1970-01-01, not missing."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC).date()
    except (OverflowError, OSError, ValueError):
        return None


def _was_live(entry: dict[str, object]) -> bool:
    """Record livestream status faithfully; it never affects inclusion."""
    if entry.get("was_live"):
        return True
    return entry.get("live_status") in _LIVE_STATUSES
