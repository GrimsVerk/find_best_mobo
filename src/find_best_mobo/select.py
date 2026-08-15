"""Narrowing the index to the videos actually about AM5 boards.

The channel is a hardware channel, not a motherboard channel: most of what it
uploads mentions a board in passing or not at all. Selection is the stage that
turns "every regular upload since the start date" into "the videos worth paying
a model to read" (`docs/DESIGN.md` R4).

Two rules, and the second is the whole point. A board named in the *title* is an
automatic include — a video called "X870E boards are a mess" is about X870E, and
no body count can argue with that. Everything else is admitted on the number of
DISTINCT canonicals in its body, never on the raw mention count: ten mentions of
one board is one board being discussed at length, while three different boards
in the same video is a comparison, which is exactly the shape this pipeline
wants to find.

The threshold is a lever (R17), so the run reports what it cost: how many videos
came in each way, how many were excluded, and what moving the threshold one step
in either direction would change. That report is why excluded videos are
returned and written rather than dropped — an exclusion is recorded, never
implied, the same rule the index follows.
"""

from __future__ import annotations

import errno
import json
import os
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from find_best_mobo.aliases import (
    Mention,
    compile_matcher,
    find_mentions,
    find_title_hits,
    load_aliases,
)
from find_best_mobo.config import Config
from find_best_mobo.index import Video, read_index
from find_best_mobo.transcripts import Transcript, load_cached

TITLE_HIT = "title_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"


@dataclass(frozen=True)
class Selection:
    video: Video
    reason: str  # "title_hit" | "threshold" | "excluded_below_threshold"
    mentions: tuple[Mention, ...]
    distinct_canonicals: int


@dataclass(frozen=True)
class ThresholdReport:
    threshold: int
    title_hits: int
    threshold_passes: int
    excluded: int
    would_include_at_minus_one: int
    would_exclude_at_plus_one: int


def select_video(
    video: Video, transcript: Transcript, matcher: re.Pattern[str], config: Config
) -> Selection:
    """Decide one video's fate. Pure: no I/O, no clock.

    `mentions` is the full body mentions in cue order whatever the reason, and
    `distinct_canonicals` is their true distinct count — both are populated even
    for a title hit, whose decision ignores them, because slice 5 excerpts
    around those mentions and a title hit with nothing recorded would have
    nothing to excerpt. A video with no cached transcript arrives here as a
    `Transcript` with no cues: still eligible on its title, otherwise zero.
    """
    mentions = find_mentions(transcript, matcher)
    distinct_canonicals = len({mention.canonical for mention in mentions})
    if find_title_hits(video, matcher):
        reason = TITLE_HIT
    elif distinct_canonicals >= config.mention_threshold:
        reason = THRESHOLD
    else:
        reason = EXCLUDED
    return Selection(
        video=video,
        reason=reason,
        mentions=mentions,
        distinct_canonicals=distinct_canonicals,
    )


def select_all(config: Config) -> tuple[Selection, ...]:
    """Select over the whole pending corpus, in the index file's order.

    That order is upload date then video id, which slice 1 already established,
    so the result is deterministic (R23) without sorting anything here. One
    transcript is loaded, selected on, and released before the next is read, so
    memory does not grow with the corpus (R22) — only the selections survive the
    loop, and a selection holds mentions rather than cues.

    Raises `FileNotFoundError` if the index or the alias table is missing; a
    missing transcript cache is not an error, because a video with no captions
    can still be selected on its title.
    """
    index_path = config.data_dir / "index.jsonl"
    if not index_path.exists():
        # Raised in the shape `open` would have raised it, `filename` included,
        # so the command can name the missing file without parsing a message.
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(index_path))
    matcher = compile_matcher(load_aliases(config.data_dir / "aliases.toml"))

    selections: list[Selection] = []
    for video in read_index(index_path):
        if video.inclusion != "pending":
            continue
        cached = load_cached(video.video_id, config)
        transcript = cached if cached is not None else Transcript(video_id=video.video_id, cues=())
        selections.append(select_video(video, transcript, matcher, config))
    return tuple(selections)


def threshold_report(selections: Sequence[Selection], config: Config) -> ThresholdReport:
    """Count what the threshold in force did, and what one step would do.

    The two what-if numbers are DELTAS, not new totals: `would_include_at_minus_one`
    is how many currently excluded videos a threshold one lower would let in, and
    `would_exclude_at_plus_one` is how many current threshold passes a threshold
    one higher would drop. Title hits never appear in the second number — they
    are admitted on evidence the threshold has no say over.

    Nothing is clamped at a threshold of 1: a threshold of 0 really would admit
    every video with any mention at all, and the honest count of those is more
    useful to whoever is tuning the lever than a silent zero.
    """
    threshold = config.mention_threshold
    title_hits = sum(1 for selection in selections if selection.reason == TITLE_HIT)
    threshold_passes = [selection for selection in selections if selection.reason == THRESHOLD]
    excluded = [selection for selection in selections if selection.reason == EXCLUDED]
    return ThresholdReport(
        threshold=threshold,
        title_hits=title_hits,
        threshold_passes=len(threshold_passes),
        excluded=len(excluded),
        would_include_at_minus_one=sum(
            1 for selection in excluded if selection.distinct_canonicals >= threshold - 1
        ),
        would_exclude_at_plus_one=sum(
            1 for selection in threshold_passes if selection.distinct_canonicals < threshold + 1
        ),
    )


def write_selected(selections: Iterable[Selection], path: Path) -> int:
    """Write one JSON record per line and return how many were written.

    Every selection is written, the excluded ones included: the threshold report
    and any later re-tuning of the lever both need to see what was left out.

    Deterministic, following `write_index`'s conventions (R23): sorted keys,
    compact separators, ISO-8601 dates, one trailing newline per line and no
    trailing whitespace. The order given is the order written — `select_all`
    hands over the index's order, and re-sorting here would silently discard
    whatever order a caller chose.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for selection in selections:
            handle.write(json.dumps(_record(selection), sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            written += 1
    return written


def read_selected(path: Path) -> Iterator[Selection]:
    """Yield the `Selection` records of a selected file, equal to what went in."""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            video = record["video"]
            yield Selection(
                video=Video(
                    video_id=video["video_id"],
                    title=video["title"],
                    upload_date=date.fromisoformat(video["upload_date"]),
                    duration_seconds=video["duration_seconds"],
                    was_live=video["was_live"],
                    classification=video["classification"],
                    inclusion=video["inclusion"],
                ),
                reason=record["reason"],
                mentions=tuple(
                    Mention(
                        video_id=mention["video_id"],
                        canonical=mention["canonical"],
                        start_seconds=float(mention["start_seconds"]),
                        matched_form=mention["matched_form"],
                    )
                    for mention in record["mentions"]
                ),
                distinct_canonicals=record["distinct_canonicals"],
            )


def _record(selection: Selection) -> dict[str, object]:
    """One selection as the nested shape on disk.

    Nested rather than flattened so a reader reconstructs the video and its
    mentions without guessing which prefix belonged to what; the video sub-record
    is exactly what `index.jsonl` carries, date included.
    """
    video = asdict(selection.video)
    video["upload_date"] = selection.video.upload_date.isoformat()
    return {
        "video": video,
        "reason": selection.reason,
        "mentions": [asdict(mention) for mention in selection.mentions],
        "distinct_canonicals": selection.distinct_canonicals,
    }
