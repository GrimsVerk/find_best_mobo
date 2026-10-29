"""The caption client is built once per process, and the extraction runs once.

`docs/DECISIONS.md` rules that yt-dlp is imported as a library specifically so
one client is reused across ~1000 videos rather than standing up fresh HTTP
state per video. `fetch_video` is the function called once per video, so it is
the one the ruling is about — and an implementation that constructs a client
inside the function satisfies every other test in this suite, because they all
fake `fetch_video` itself and never reach the real thing.

That gap is why this file exists: the review gate caught the regression once,
by reading, and a check that only a human can run is not a check. `YoutubeDL` is
faked here, so nothing touches the network.

OD-8/R1004 adds a second property of the same shape and for the same reason.
The description is free *because* it arrives in the extraction the caption fetch
already runs — that is the whole answer to BL-11's "an extra request per video"
objection — so a `fetch_video` that extracted twice, once per field, would be
the regression this file is here to catch. The call count is asserted, not the
absence of a second network hop, because the count is what a test can see.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from find_best_mobo import ytdlp
from find_best_mobo.config import Config
from find_best_mobo.ytdlp import VTT, VideoFetch

VTT_BODY = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello\n"

CAPTION_TRACK: dict[str, Any] = {
    "automatic_captions": {"en": [{"ext": "vtt", "url": "https://x/track.vtt"}]}
}

DESCRIPTION = "Full teardown of the little board.\n#AMD #ryzen #MSI #B850 #ITX\n"


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class FakeClient:
    """Counts how many times a client was constructed, across all instances.

    Also records every `extract_info` URL, because "the description is free"
    means exactly one extraction per video.
    """

    constructions = 0
    extractions: list[str] = []
    info: dict[str, Any] = dict(CAPTION_TRACK)
    error: Exception | None = None

    def __init__(self, options: dict[str, object]) -> None:
        type(self).constructions += 1
        self.options = options

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        type(self).extractions.append(url)
        error = type(self).error
        if error is not None:
            raise error
        return dict(type(self).info)

    def urlopen(self, url: str) -> FakeResponse:
        return FakeResponse(VTT_BODY)


@pytest.fixture
def fake_youtubedl(monkeypatch: pytest.MonkeyPatch) -> type[FakeClient]:
    FakeClient.constructions = 0
    FakeClient.extractions = []
    FakeClient.info = dict(CAPTION_TRACK)
    FakeClient.error = None
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
        assert ytdlp.fetch_video(video_id, config).captions is not None

    assert fake_youtubedl.constructions == 1, (
        "fetch_video built a client per video; docs/DECISIONS.md rules "
        "that one client is reused across the run"
    )


def test_importing_the_module_opens_no_client(fake_youtubedl: type[FakeClient]) -> None:
    # Lazy construction is what lets an offline test suite import this module
    # freely. A client built at import time would open HTTP state on collection.
    assert fake_youtubedl.constructions == 0


class TestOneExtractionPerVideo:
    def test_captions_and_description_come_from_the_same_call(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        fake_youtubedl.info = dict(CAPTION_TRACK) | {"description": DESCRIPTION}

        fetched = ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert len(fake_youtubedl.extractions) == 1, (
            "OD-8: the description is free only because it rides the extraction "
            f"the caption fetch already runs, but it extracted {fake_youtubedl.extractions}"
        )
        assert fetched.captions is not None
        assert fetched.description == DESCRIPTION

    def test_the_extraction_is_the_watch_url(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert fake_youtubedl.extractions == ["https://www.youtube.com/watch?v=aaa11111111"]

    def test_three_videos_are_three_extractions_and_no_more(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)

        for video_id in ("aaa11111111", "bbb22222222", "ccc33333333"):
            ytdlp.fetch_video(video_id, config)

        assert len(fake_youtubedl.extractions) == 3


class TestWhatFetchVideoReturns:
    def test_the_captions_are_the_decoded_track_body(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        """`VideoFetch.captions` is exactly what `fetch_caption_track` returned."""
        fake_youtubedl.info = dict(CAPTION_TRACK) | {"description": DESCRIPTION}

        fetched = ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert fetched == VideoFetch(
            captions=VTT_BODY.decode("utf-8"), description=DESCRIPTION, caption_format=VTT
        )

    def test_a_video_with_no_english_track_returns_none_captions(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        fake_youtubedl.info = {"subtitles": {}, "description": DESCRIPTION}

        fetched = ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert fetched.captions is None
        assert fetched.description == DESCRIPTION, (
            "the description is read from the extraction whether or not a track was found"
        )

    def test_the_result_is_frozen(self, fake_youtubedl: type[FakeClient], tmp_path: Path) -> None:
        fetched = ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        with pytest.raises(FrozenInstanceError):
            fetched.description = "rewritten"  # type: ignore[misc]

    def test_a_failure_reaching_youtube_still_raises(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        """A boundary that swallowed this would erase the ledger's two classes."""
        error = RuntimeError("HTTP 503 from YouTube")
        fake_youtubedl.error = error

        with pytest.raises(RuntimeError) as caught:
            ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert caught.value is error


class TestTheDescriptionIsNeverNone:
    @pytest.mark.parametrize(
        ("extra", "case"),
        [
            ({}, "the key is missing"),
            ({"description": None}, "the key is null"),
            ({"description": 850}, "the key is a number"),
            ({"description": ["#B850"]}, "the key is a list"),
            ({"description": {"text": "#B850"}}, "the key is a table"),
        ],
    )
    def test_anything_that_is_not_a_string_becomes_empty(
        self,
        fake_youtubedl: type[FakeClient],
        tmp_path: Path,
        extra: dict[str, Any],
        case: str,
    ) -> None:
        fake_youtubedl.info = dict(CAPTION_TRACK) | extra

        fetched = ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert fetched.description == "", case
        assert fetched.captions is not None, "a bad description never costs the captions"

    def test_an_empty_description_stays_empty(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        fake_youtubedl.info = dict(CAPTION_TRACK) | {"description": ""}

        assert ytdlp.fetch_video("aaa11111111", make_config(tmp_path)).description == ""

    def test_a_real_description_is_taken_verbatim(
        self, fake_youtubedl: type[FakeClient], tmp_path: Path
    ) -> None:
        # No stripping, no truncation, no parsing of hashtags or links.
        raw = "  \n#B850  #ITX\nhttps://example.com/affiliate?x=1\n  "
        fake_youtubedl.info = dict(CAPTION_TRACK) | {"description": raw}

        assert ytdlp.fetch_video("aaa11111111", make_config(tmp_path)).description == raw
