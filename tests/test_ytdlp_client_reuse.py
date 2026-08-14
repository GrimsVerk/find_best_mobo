"""The caption client is built once per process, not once per video.

`docs/DECISIONS.md` rules that yt-dlp is imported as a library specifically so
one client is reused across ~1000 videos rather than standing up fresh HTTP
state per video. `fetch_caption_track` is the function called once per video,
so it is the one the ruling is about — and an implementation that constructs a
client inside the function satisfies every other test in this suite, because
they all fake `fetch_caption_track` itself and never reach the real thing.

That gap is why this file exists: the review gate caught the regression once,
by reading, and a check that only a human can run is not a check. `YoutubeDL` is
faked here, so nothing touches the network.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from find_best_mobo import ytdlp
from find_best_mobo.config import Config


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class FakeClient:
    """Counts how many times a client was constructed, across all instances."""

    constructions = 0

    def __init__(self, options: dict[str, object]) -> None:
        type(self).constructions += 1
        self.options = options

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        return {"automatic_captions": {"en": [{"ext": "vtt", "url": "https://x/track.vtt"}]}}

    def urlopen(self, url: str) -> FakeResponse:
        return FakeResponse(b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello\n")


@pytest.fixture
def fake_youtubedl(monkeypatch: pytest.MonkeyPatch) -> type[FakeClient]:
    FakeClient.constructions = 0
    # The cached client is process-wide, so it must be cleared or an earlier
    # test's instance would be reused and the count would read as zero.
    monkeypatch.setattr(ytdlp, "_CAPTION_CLIENT", None)
    monkeypatch.setattr(ytdlp, "YoutubeDL", FakeClient)
    return FakeClient


def make_config(tmp_path: Path) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@test",
        start_date=date(2023, 1, 1),
        data_dir=tmp_path / "data",
        shorts_max_seconds=120,
        mention_threshold=3,
        window_before_seconds=120,
        window_after_seconds=300,
        per_video_excerpt_cap=10,
        bundle_token_cap=24000,
        calibration_batch_size=12,
        batch_count=3,
        chars_per_token=4.0,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


def test_one_client_serves_many_videos(fake_youtubedl: type[FakeClient], tmp_path: Path) -> None:
    config = make_config(tmp_path)

    for video_id in ("aaa11111111", "bbb22222222", "ccc33333333"):
        assert ytdlp.fetch_caption_track(video_id, config) is not None

    assert fake_youtubedl.constructions == 1, (
        "fetch_caption_track built a client per video; docs/DECISIONS.md rules "
        "that one client is reused across the run"
    )


def test_importing_the_module_opens_no_client(fake_youtubedl: type[FakeClient]) -> None:
    # Lazy construction is what lets an offline test suite import this module
    # freely. A client built at import time would open HTTP state on collection.
    assert fake_youtubedl.constructions == 0
