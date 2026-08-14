"""The network boundary: the only module that imports or touches `yt-dlp`.

`yt-dlp` is imported as a library, never shelled out to, and one client is
reused for the whole run (owner rulings in `docs/DECISIONS.md`). Everything
else in the pipeline talks to YouTube exclusively through
`list_channel_entries` and `fetch_caption_track`, which are also the only
surfaces a test may fake.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]

from find_best_mobo.config import Config

# Auto-captions arrive under codes like `en`, `en-orig`, `en-US` and the
# translated `en-en`; manual tracks are usually a bare `en`. Matching on the
# prefix takes whichever of them the video actually has.
_ENGLISH = "en"


def list_channel_entries(channel_url: str, start_date: date) -> Iterator[dict[str, object]]:
    """Yield one raw flat-playlist entry dict per upload on the channel.

    Flat extraction lists the channel without downloading anything, but its
    entries omit `upload_date` unless the `youtubetab:approximate_date`
    extractor argument is set — without it every video parses as out-of-range
    and the corpus comes out silently empty. The dates it yields are
    approximate. Entries before `start_date` are still yielded, so exclusions
    can be recorded rather than implied; the argument exists for a future
    early-stop optimisation, not filtering.
    """
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "extractor_args": {"youtubetab": {"approximate_date": ["true"]}},
    }
    with YoutubeDL(options) as client:
        info = client.extract_info(channel_url, download=False)
        yield from _walk(info, client)


def _walk(info: dict[str, Any], client: Any) -> Iterator[dict[str, object]]:
    """Flatten a possibly nested extraction result into video entry dicts.

    A bare channel URL can resolve to a playlist of tab playlists (videos,
    shorts, streams); each nested or unresolved playlist is walked with the
    same client so HTTP state is stood up once for the whole run.
    """
    entries = info.get("entries")
    if entries is None:
        yield info
        return
    for entry in entries:
        if not entry:
            continue
        if entry.get("entries") is not None:
            yield from _walk(entry, client)
        elif entry.get("ie_key") == "YoutubeTab" or entry.get("_type") == "playlist":
            resolved = client.extract_info(entry["url"], download=False)
            yield from _walk(resolved, client)
        else:
            yield entry


def fetch_caption_track(video_id: str, config: Config) -> str | None:
    """Return one video's captions as raw WebVTT, or None if it has none.

    Both manual and automatic captions are requested — Buildzoid's uploads are
    overwhelmingly auto-captioned, so a manual-only fetch would class almost
    the whole channel as `no_captions` and trip the missing-caption halt on the
    first run. Manual tracks are preferred where they exist because they are
    not guesses at the audio.

    Returns None only when the video genuinely offers no English caption track.
    Anything that goes wrong reaching YouTube raises, so that the caller can
    tell "there is nothing to fetch" from "we could not fetch it" — they are
    different rows in the failure ledger and different halt triggers.
    """
    # `config` is unused: it is in the declared signature because the plan put
    # it there, and every lever this function needs is a yt-dlp concern rather
    # than a project one. Kept rather than dropped so the boundary the tests
    # fake stays the boundary the plan declares.
    del config
    client = _caption_client()
    url = f"https://www.youtube.com/watch?v={video_id}"
    info = client.extract_info(url, download=False)
    track_url = _caption_url(info)
    if track_url is None:
        return None
    # `urlopen` on the client rather than a bare HTTP call: it carries the
    # same cookies, headers and proxy settings the extraction used, and a
    # caption URL fetched without them is frequently rejected.
    raw: bytes = client.urlopen(track_url).read()
    return raw.decode("utf-8", errors="replace")


# One client for every caption fetch in a run, built on first use.
#
# `docs/DECISIONS.md` rules that yt-dlp is used as a library precisely so one
# client is reused across ~1000 videos instead of standing up fresh HTTP state
# per video. This is the function called once per video, so it is where that
# ruling actually bites — `list_channel_entries` runs once and never paid the
# cost the ruling is about. Built lazily rather than at import so that merely
# importing this module opens nothing, which is what keeps the offline test
# suite honest.
#
# Deliberately not closed: it lives for the process, and the run ends with it.
_CAPTION_CLIENT: Any = None


def _caption_client() -> Any:
    """The shared caption-fetching client, created once per process."""
    global _CAPTION_CLIENT
    if _CAPTION_CLIENT is None:
        _CAPTION_CLIENT = YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitlesformat": "vtt",
            }
        )
    return _CAPTION_CLIENT


def _caption_url(info: dict[str, Any]) -> str | None:
    """Pick the English WebVTT track from an extraction result, if there is one.

    Manual subtitles win over automatic ones; within either, an explicit `vtt`
    format wins, and the first offered format is taken only as a fallback for a
    track that does not advertise its extension.
    """
    for key in ("subtitles", "automatic_captions"):
        tracks = info.get(key) or {}
        if not isinstance(tracks, dict):
            continue
        for language, formats in tracks.items():
            if not str(language).lower().startswith(_ENGLISH) or not formats:
                continue
            chosen = next(
                (fmt for fmt in formats if fmt.get("ext") == "vtt"),
                formats[0],
            )
            candidate = chosen.get("url")
            if candidate:
                return str(candidate)
    return None
