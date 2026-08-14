"""The network boundary: the only module that imports or touches `yt-dlp`.

`yt-dlp` is imported as a library, never shelled out to, and one client is
reused for the whole run (owner rulings in `docs/DECISIONS.md`). Everything
else in the pipeline talks to YouTube exclusively through
`list_channel_entries`, which is also the only surface a test may fake.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]


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
