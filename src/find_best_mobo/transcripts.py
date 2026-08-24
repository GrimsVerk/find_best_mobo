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
from find_best_mobo.ledger import FetchFailure as FetchFailure
from find_best_mobo.ledger import HaltTriggered, Ledger
from find_best_mobo.ytdlp import JSON3, fetch_video

# What a cached record says about where its cues came from. `json3` is
# YouTube's own segment format — one event per line of speech, with per-segment
# timing. `vtt` is the same track rendered for display, which for automatic
# captions means ROLL-UP: a cue per display frame, so every line arrives three
# times and a name inside a two-line frame inherits the FIRST line's timestamp
# (BL-28, OD-24). `unknown` is a record written before this field existed —
# never guessed at, because guessing would be true today and a lie the moment
# anyone replays the reasoning.
# `JSON3` and `VTT` are the boundary's, because they name what it asks YouTube
# for. `UNKNOWN_FORMAT` is this module's, because it describes a CACHED RECORD
# whose provenance was never written down — never guessed at as `vtt`, which
# would be true today and a lie the moment anyone replays the reasoning.
UNKNOWN_FORMAT = "unknown"

# `FetchFailure` is re-exported above in mypy's explicit `X as X` form. It is
# the ledger's record type and is defined there, but this module is where a
# failure is CONSTRUCTED, so callers reasonably reach for it here. Defining it
# in this module instead would be circular: `fetch_all` raises `HaltTriggered`
# at run time, so the import of `ledger` cannot be deferred to type-checking.

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
    # The video's description, verbatim, from the same per-video extraction that
    # fetched the captions — no additional request (OD-8, R1004). Defaults to
    # `""` so that a cache entry written before descriptions were recorded still
    # loads: R1004 forbids a forced refetch, and a record with no description
    # simply has no description signal.
    description: str = ""
    # Which caption format this transcript was parsed from, so a later question
    # about one claim's timestamp has an answer (R1013).
    source_format: str = UNKNOWN_FORMAT


def parse_vtt(raw: str) -> tuple[Cue, ...]:
    """Parse WebVTT text into cues, in file order.

    Auto-generated captions are messy in ways that must never stop a run:
    unknown blocks, stray settings on the timing line, cues that are pure
    markup. Anything unparseable is skipped rather than raised on, because one
    malformed cue in a two-hour video is not a reason to lose the video.
    """
    parsed: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n")):
        cue = _parse_block(block)
        if cue is not None:
            parsed.append(cue)
    return _without_rollup_frames(parsed)


def _without_rollup_frames(cues: list[Cue]) -> tuple[Cue, ...]:
    """Drop the display frames a roll-up caption track repeats (R1013, OD-24).

    YouTube renders AUTOMATIC captions as roll-up: two lines scroll on screen
    and the track emits a cue per display FRAME rather than per line of speech.
    The sequence is `A`, `A B`, `B`, `B C`, `C` — so every line arrives three
    times, and BL-28 measured that at 2.84x across all 285 cached transcripts,
    with no video escaping it.

    A cue that merely EXTENDS the previous kept one is such a frame and is
    dropped; so is one wholly contained in it, which is the same frame seen from
    the other side. What survives is `A`, `B`, `C`, each carrying the start time
    it was displayed ALONE at — the timing the frames cannot give, and the one
    R5 cuts every excerpt window from.

    Comparison is against the last SURVIVING cue, not the last raw one. In
    `A`, `A B`, `B` the solo `B` is contained in its raw predecessor `A B`, so
    comparing against the raw one would drop the line itself.

    THE LAST LINE IS KEPT. If the final cue is a frame extending its
    predecessor, its new tail has no solo cue to follow it, so that tail becomes
    its own cue. Without this the last line of every fallback transcript
    disappears silently.

    Structural, and only ever applied to ADJACENT cues, so genuinely repeated
    speech survives unless a speaker repeats exactly the words at a cue
    boundary. A non-roll-up track is untouched: no cue in an ordinary WebVTT
    extends its predecessor, so every rule here is a no-op.
    """
    kept: list[Cue] = []
    for index, cue in enumerate(cues):
        if not kept:
            kept.append(cue)
            continue
        previous = kept[-1].text
        if cue.text == previous or previous.endswith(f" {cue.text}"):
            continue
        if cue.text.startswith(f"{previous} "):
            if index == len(cues) - 1:
                kept.append(
                    Cue(start_seconds=cue.start_seconds, text=cue.text[len(previous) + 1 :])
                )
            continue
        kept.append(cue)
    return tuple(kept)


def parse_json3(raw: str) -> tuple[Cue, ...]:
    """Parse YouTube's json3 caption document into cues, in event order (R1013).

    ONE CUE PER TEXT-BEARING EVENT. An event's text is the concatenation of its
    segments' `utf8` in order, and its start is `tStartMs / 1000`.

    Segments are concatenated VERBATIM, never stripped: json3 puts the leading
    space on the following word (`'Hey'`, `' guys,'`), so stripping per segment
    would fuse every word in the event.

    An event whose concatenated text is empty or whitespace contributes no cue.
    That is what an `aAppend` event is — every one of the 2,257 measured on a
    real track carries a single newline and nothing else. They are the LINE
    BREAK, which is why the break must not be dropped from the text of the cues
    around them: cue texts are joined with a single space downstream, so a break
    that became nothing would fuse `we're` and `going`.

    A document that is not JSON at all RAISES, unlike `parse_vtt`, which
    tolerates one malformed cue because one bad cue in a two-hour video is not
    worth losing the video. A json3 payload that does not parse is a different
    failure, and a transcript of zero cues from a video that has captions would
    be indistinguishable from a video with none — a line the failure ledger
    already draws and this keeps drawn.
    """
    try:
        document: Any = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise ValueError(f"not a json3 caption document: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("json3 caption document is not an object")

    cues: list[Cue] = []
    for event in document.get("events") or ():
        if not isinstance(event, dict):
            continue
        text = "".join(
            str(segment.get("utf8", ""))
            for segment in (event.get("segs") or ())
            if isinstance(segment, dict)
        )
        if not text.strip():
            continue
        cues.append(Cue(start_seconds=float(event.get("tStartMs", 0)) / 1000.0, text=text))
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
            # `.get`, and this is the single most important line here: today a
            # KeyError is caught below and read as "no usable cache entry", so a
            # strict read would silently invalidate every cache entry the owner
            # already has and refetch the whole corpus — the opposite of
            # R1004's "no forced refetch".
            description=str(record.get("description", "")),
            source_format=str(record.get("source_format", UNKNOWN_FORMAT)),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def fetch_transcript(video: Video, config: Config) -> Transcript:
    """Fetch and parse one video's captions. Never touches the cache.

    Raises `NoCaptions` when the video has no caption track at all, and lets
    every other exception propagate untouched so that the caller — which owns
    the ledger — is the one place that decides what a failure means.
    """
    fetched = fetch_video(video.video_id, config)
    if fetched.captions is None:
        # Before the description is used for anything: R1004 says a description
        # cannot conjure a transcript, and the failure ledger governs this video.
        raise NoCaptions(video.video_id)
    # The parser is chosen from what the boundary ASKED FOR, never by sniffing
    # the payload: the boundary knows, and a sniffer is a second reader of one
    # answer — the shape ESC-21 and BL-28 both punish.
    cues = (
        parse_json3(fetched.captions)
        if fetched.caption_format == JSON3
        else parse_vtt(fetched.captions)
    )
    return Transcript(
        video_id=video.video_id,
        cues=cues,
        description=fetched.description,
        source_format=fetched.caption_format,
    )


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
            # The counts so far ride the exception: a halt must not hide the
            # provenance of what DID land (R1013).
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
        "description": transcript.description,
        "source_format": transcript.source_format,
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
