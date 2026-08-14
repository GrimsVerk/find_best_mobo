"""Caption tracks become parsed transcripts in a local cache.

The cache is what makes the pipeline restartable (`docs/DESIGN.md` R2): a video
whose transcript is already on disk is never fetched again, so a run that halted
or crashed resumes where it stopped instead of paying for the whole channel
twice. Nothing here imports `yt-dlp` — every byte from YouTube arrives through
the single boundary in `ytdlp.py`, which is also the only surface the tests
fake.

The split of responsibility is deliberate: `fetch_transcript` fetches and parses
and nothing else, while `fetch_all` owns the cache and the ledger. Keeping the
"have we already got this?" decision in one function is what makes "retry only
what failed" a property that can be read off a single body rather than inferred
from two.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from find_best_mobo.config import Config
from find_best_mobo.index import Video
from find_best_mobo.ledger import FetchFailure, HaltTriggered, Ledger
from find_best_mobo.ytdlp import fetch_caption_track

# `<c>`, `</c.colorE5E5E5>`, `<00:00:01.000>`, `<v Roger>` — WebVTT's inline
# markup, all of which is presentation and none of which is speech.
_TAG = re.compile(r"<[^>]*>")

# `00:01:02.500` or `01:02.500`, with the hours field optional. Commas are
# accepted as the decimal separator because some tracks arrive SRT-flavoured.
_TIMESTAMP = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")

_ARROW = "-->"


class NoCaptions(Exception):
    """The video genuinely has no caption track.

    An ordinary outcome, not a failure to reach YouTube: the ledger classes it
    `no_captions` and it does not count against the network-health triggers.
    It exists because `fetch_transcript` returns a `Transcript`, which leaves
    no room in the return type to say "there was nothing to fetch".
    """


@dataclass(frozen=True)
class Cue:
    start_seconds: float
    text: str


@dataclass(frozen=True)
class Transcript:
    video_id: str
    cues: tuple[Cue, ...]


def parse_vtt(raw: str) -> tuple[Cue, ...]:
    """Parse WebVTT text into cues, in file order.

    Auto-generated captions are messy in ways that must never stop a run:
    unknown blocks, stray settings on the timing line, cues that are pure
    markup. Anything unparseable is skipped rather than raised on, because one
    malformed cue in a two-hour video is not a reason to lose the video.
    """
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n")):
        cue = _parse_block(block)
        if cue is not None:
            cues.append(cue)
    return tuple(cues)


def cache_path(video_id: str, config: Config) -> Path:
    """Where this video's transcript lives on disk."""
    return config.data_dir / "transcripts" / f"{video_id}.json"


def load_cached(video_id: str, config: Config) -> Transcript | None:
    """Return the cached transcript, or None if there isn't a usable one.

    A corrupt cache entry is treated as absent rather than raised on: the run
    can simply fetch it again, and a damaged file is a much worse reason to
    stop than it is to repeat one download.
    """
    path = cache_path(video_id, config)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            record: Any = json.load(handle)
        return Transcript(
            video_id=str(record["video_id"]),
            cues=tuple(
                Cue(start_seconds=float(cue["start_seconds"]), text=str(cue["text"]))
                for cue in record["cues"]
            ),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def fetch_transcript(video: Video, config: Config) -> Transcript:
    """Fetch and parse one video's captions. Never touches the cache.

    Raises `NoCaptions` when the video has no caption track at all, and lets
    every other exception propagate untouched so that the caller — which owns
    the ledger — is the one place that decides what a failure means.
    """
    raw = fetch_caption_track(video.video_id, config)
    if raw is None:
        raise NoCaptions(video.video_id)
    return Transcript(video_id=video.video_id, cues=parse_vtt(raw))


def fetch_all(videos: Iterable[Video], config: Config, ledger: Ledger) -> int:
    """Fetch and cache every video that isn't cached yet; return how many.

    Cache hits are skipped entirely — no fetch, no ledger entry, not counted —
    which is what makes a rerun retry only the videos that failed. Each
    transcript is written and released before the next is fetched, so the run's
    memory does not grow with the corpus (R22).

    Raises `HaltTriggered` as soon as a trigger fires. The ledger file is
    already on disk by then, because it is rewritten on every record.
    """
    fetched = 0
    for video in videos:
        if load_cached(video.video_id, config) is not None:
            continue
        try:
            transcript = fetch_transcript(video, config)
        except NoCaptions:
            failure = _failure(video, "no_captions", "")
        except Exception as error:
            # Deliberately broad: anything the boundary raises is "we could not
            # reach YouTube for this one", and the ledger's job is to record it
            # and let the triggers decide whether the run is still healthy.
            failure = _failure(video, "fetch_error", str(error))
        else:
            _write_cache(transcript, config)
            ledger.record_success()
            fetched += 1
            continue
        ledger.record(failure)
        trigger = ledger.check_triggers()
        if trigger is not None:
            raise HaltTriggered(trigger, ledger.failures())
    return fetched


def _failure(video: Video, failure_class: str, detail: str) -> FetchFailure:
    """Build the ledger record for one failed video.

    `attempts` is a placeholder: the ledger knows the previous run's count for
    this video id and is the only thing that can carry it forward.
    """
    return FetchFailure(
        video_id=video.video_id,
        title=video.title,
        upload_date=video.upload_date,
        failure_class=failure_class,
        detail=detail,
        attempts=1,
    )


def _write_cache(transcript: Transcript, config: Config) -> None:
    """Write one transcript as deterministic JSON (R23)."""
    path = cache_path(transcript.video_id, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "video_id": transcript.video_id,
        "cues": [{"start_seconds": cue.start_seconds, "text": cue.text} for cue in transcript.cues],
    }
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


def _parse_block(block: str) -> Cue | None:
    """Turn one blank-line-delimited WebVTT block into a cue, or None.

    None covers everything that is not a cue: the `WEBVTT` header, `NOTE`
    comments, styling blocks, and any block whose text is nothing but markup.
    """
    lines = [line for line in block.split("\n") if line.strip()]
    if not lines:
        return None
    timing_index = next((i for i, line in enumerate(lines) if _ARROW in line), None)
    if timing_index is None:
        return None
    start = _parse_start(lines[timing_index])
    if start is None:
        return None
    text = _clean_text(lines[timing_index + 1 :])
    if not text:
        return None
    return Cue(start_seconds=start, text=text)


def _parse_start(timing_line: str) -> float | None:
    """Seconds of the timestamp left of the arrow; None if it doesn't parse.

    Trailing cue settings (`align:start position:0%`) sit after the end
    timestamp and are ignored by only ever looking left of the arrow.
    """
    match = _TIMESTAMP.search(timing_line.split(_ARROW)[0])
    if match is None:
        return None
    hours, minutes, seconds, fraction = match.groups()
    whole: int = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
    scale: int = 10 ** len(str(fraction))
    return float(whole) + int(fraction) / scale


def _clean_text(lines: list[str]) -> str:
    """Join a cue's payload lines into one line of plain speech."""
    parts = [_TAG.sub("", line).strip() for line in lines]
    return " ".join(part for part in parts if part).strip()
