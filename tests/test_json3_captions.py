"""R1013 — captions come from json3, and the VTT fallback says so.

Written blind from ``docs/plans/oracle/json3-captions.md``, OD-24 and BL-28
alone, in a worktree at a commit where none of this exists, so failing imports
are the expected state until assembly. The plan's own correction to OD-24 is
what the json3 tests here are built around: every ``aAppend`` event in the
measured track is TEXT-FREE — a single newline — so it is the LINE BREAK, and
dropping the break from the text does not shorten a transcript, it fuses it
(``we'regoing`` for ``we're going``). That is pinned directly.

This file is new rather than an edit to ``tests/test_transcripts.py`` so that
the slice's assertions arrive as one readable block and nothing already written
for R1004's boundary rename is disturbed. It fakes exactly one surface, the
same one that file fakes: ``fetch_video``, the per-video network boundary in
``find_best_mobo.ytdlp`` — patched where each module uses it, never a level
deeper — plus ``YoutubeDL`` itself in the two tests that are about the
boundary's own choice of track, which is the pattern
``tests/test_ytdlp_client_reuse.py`` already established.

The two caption fixtures carry THE SAME FIVE SPOKEN LINES in the two formats:
``captions_json3.json`` as the events YouTube emits, ``captions_rollup_vtt.txt``
as the display frames it emits for the same speech. That is what makes
``TestTheTwoPathsAgree`` mean anything — it is BL-28's ground-truth comparison,
reproduced at fixture scale with invented words (R21).
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as it is in
# tests/test_transcripts.py: the names below do not exist yet, so the isort rule
# classifies their modules as third-party and would demand a different grouping
# from the one it demands once they do. The block is written in its
# post-assembly order, which is the stable one.
from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from find_best_mobo import ytdlp
from find_best_mobo.commands.fetch import run
from find_best_mobo.config import Config
from find_best_mobo.index import Video, write_index
from find_best_mobo.ledger import Ledger
from find_best_mobo.transcripts import (
    UNKNOWN_FORMAT,
    Cue,
    NoCaptions,
    Transcript,
    cache_path,
    fetch_all,
    fetch_transcript,
    load_cached,
    parse_json3,
    parse_vtt,
)
from find_best_mobo.ytdlp import JSON3, VTT, CaptionTrack, VideoFetch, _caption_track

FIXTURES = Path(__file__).parent / "fixtures"
JSON3_FIXTURE = FIXTURES / "captions_json3.json"
ROLLUP_FIXTURE = FIXTURES / "captions_rollup_vtt.txt"
PLAIN_FIXTURE = FIXTURES / "captions_vtt.txt"

# The five spoken lines both caption fixtures carry, in order. Invented words,
# real geometry (R21) — the shape is BL-28's, the speech is not Buildzoid's.
LINES = (
    "Right, so the Quorvex B940 here and we're",
    "going to walk the twelve phase VRM",
    "layout on this thing and see whether",
    "the doubler story actually holds up",
    "under a sustained all core load",
)

# What `captions_json3.json` means, cue by cue: one cue per TEXT-BEARING event,
# starting at that event's own `tStartMs`. Four events in the file deliberately
# produce nothing — the window definition with no `segs` key, and the three
# `aAppend` events, each of which carries a single newline and no speech.
EXPECTED_JSON3_CUES = (
    Cue(start_seconds=1.5, text=LINES[0]),
    Cue(start_seconds=4.51, text=LINES[1]),
    Cue(start_seconds=6.87, text=LINES[2]),
    Cue(start_seconds=9.32, text=LINES[3]),
    Cue(start_seconds=11.9, text=LINES[4]),
)

# What `captions_rollup_vtt.txt` means once the display frames are dropped: the
# same five lines, each at the start time it was displayed ALONE at. The last
# line is the exception and the point — it never appears alone in the file, so
# it survives only as the tail of the closing frame and carries that frame's
# start.
EXPECTED_ROLLUP_CUES = (
    Cue(start_seconds=1.5, text=LINES[0]),
    Cue(start_seconds=4.51, text=LINES[1]),
    Cue(start_seconds=6.87, text=LINES[2]),
    Cue(start_seconds=9.32, text=LINES[3]),
    Cue(start_seconds=9.33, text=LINES[4]),
)

# The shipped non-roll-up fixture, exactly as it parses today. Copied from
# tests/test_transcripts.py on purpose: this file's job is to prove that
# de-duplicating roll-up frames changes nothing about an ordinary WebVTT, and a
# guard that imports the number it is guarding is not a guard.
EXPECTED_PLAIN_CUES = (
    Cue(start_seconds=1.0, text="So the X670E Taichi board"),
    Cue(start_seconds=4.5, text="has a twelve phase VRM and it is actually quite good"),
    Cue(start_seconds=62.25, text="the B650E is fine too"),
    Cue(start_seconds=67.0, text="VRM thermals matter"),
    Cue(start_seconds=3723.75, text="two hours in, still talking about VRMs"),
)

SIMPLE_VTT = "WEBVTT\n\n00:00:02.000 --> 00:00:03.000\nhello there\n"

SIMPLE_JSON3 = json.dumps(
    {
        "wireMagic": "pb3",
        "events": [
            {"tStartMs": 2000, "dDurationMs": 1000, "segs": [{"utf8": "hello"}, {"utf8": " there"}]}
        ],
    }
)


def make_config(
    data_dir: Path,
    *,
    consecutive_fetch_error_limit: int = 3,
    fetch_error_rate_limit: float = 0.03,
    missing_caption_rate_limit: float = 0.05,
) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=date(2023, 1, 1),
        data_dir=data_dir,
        shorts_max_seconds=120,
        mention_threshold=3,
        window_before_seconds=120,
        window_after_seconds=300,
        per_video_excerpt_cap=10,
        bundle_token_cap=30000,
        calibration_batch_size=5,
        batch_count=3,
        chars_per_token=4.0,
        consecutive_fetch_error_limit=consecutive_fetch_error_limit,
        fetch_error_rate_limit=fetch_error_rate_limit,
        missing_caption_rate_limit=missing_caption_rate_limit,
    )


def make_video(video_id: str, *, inclusion: str = "pending", title: str = "") -> Video:
    return Video(
        video_id=video_id,
        title=title or f"{video_id} VRM breakdown",
        upload_date=date(2023, 6, 15),
        duration_seconds=3600,
        was_live=False,
        classification="regular",
        inclusion=inclusion,
    )


def make_ledger(config: Config, indexed_count: int) -> Ledger:
    return Ledger(config.data_dir / "failures.jsonl", config, indexed_count)


def json3_fetch(raw: str | None = None) -> VideoFetch:
    """What the boundary returns for a video whose track offered json3."""
    return VideoFetch(
        captions=JSON3_FIXTURE.read_text(encoding="utf-8") if raw is None else raw,
        description="",
        caption_format=JSON3,
    )


def vtt_fetch(raw: str | None = None) -> VideoFetch:
    """What the boundary returns for a video whose track offered no json3."""
    return VideoFetch(
        captions=ROLLUP_FIXTURE.read_text(encoding="utf-8") if raw is None else raw,
        description="",
        caption_format=VTT,
    )


class Boundary:
    """The faked per-video boundary, plus the record of how it was called."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.handler: Callable[[str], VideoFetch] = lambda video_id: json3_fetch()

    def set_map(self, mapping: dict[str, VideoFetch | Exception]) -> None:
        """Answer per video id: a ``VideoFetch``, or an exception to raise."""

        def handler(video_id: str) -> VideoFetch:
            answer = mapping[video_id]
            if isinstance(answer, Exception):
                raise answer
            return answer

        self.handler = handler


@pytest.fixture
def boundary(monkeypatch: pytest.MonkeyPatch) -> Boundary:
    """Fake ``fetch_video`` — the one surface a test above the boundary fakes."""
    fake = Boundary()

    def fake_fetch_video(video_id: str, config: Config) -> VideoFetch:
        assert isinstance(config, Config)
        fake.calls.append(video_id)
        return fake.handler(video_id)

    monkeypatch.setattr(ytdlp, "fetch_video", fake_fetch_video)

    import find_best_mobo.commands.fetch as command_module
    import find_best_mobo.transcripts as transcripts_module

    for module in (transcripts_module, command_module):
        if hasattr(module, "fetch_video"):
            monkeypatch.setattr(module, "fetch_video", fake_fetch_video)
    return fake


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class FakeCaptionClient:
    """A yt-dlp stand-in: one canned extraction result, one canned track body.

    Class-level state because the real client is a lazily built process-wide
    singleton, so the instance the boundary uses is not one a test holds.
    """

    info: dict[str, Any] = {}
    bodies: dict[str, bytes] = {}
    requested: list[str] = []

    def __init__(self, options: dict[str, object]) -> None:
        self.options = options

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        return dict(type(self).info)

    def urlopen(self, url: str) -> FakeResponse:
        type(self).requested.append(url)
        return FakeResponse(type(self).bodies.get(url, b""))


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> type[FakeCaptionClient]:
    FakeCaptionClient.info = {}
    FakeCaptionClient.bodies = {}
    FakeCaptionClient.requested = []
    # The cached client is process-wide; leaving an earlier test's instance in
    # place would answer from that test's canned data.
    monkeypatch.setattr(ytdlp, "_CAPTION_CLIENT", None)
    monkeypatch.setattr(ytdlp, "YoutubeDL", FakeCaptionClient)
    return FakeCaptionClient


def track(ext: str | None, url: str) -> dict[str, str]:
    """One entry of a yt-dlp caption-track list."""
    return {"url": url} if ext is None else {"ext": ext, "url": url}


class TestCaptionTrackChoice:
    """`_caption_url` became `_caption_track`: it returns the format it chose.

    Two readers of one extraction result is the shape ESC-21 and BL-28 both
    punish, so the function that already picks the track is the one that says
    which format that track is in.
    """

    def test_returns_a_caption_track_carrying_url_and_format(self) -> None:
        info = {"automatic_captions": {"en": [track("json3", "https://x/en.json3")]}}

        assert _caption_track(info) == CaptionTrack(url="https://x/en.json3", caption_format=JSON3)

    def test_json3_wins_when_both_formats_are_offered(self) -> None:
        info = {
            "automatic_captions": {
                "en": [
                    track("vtt", "https://x/en.vtt"),
                    track("srv3", "https://x/en.srv3"),
                    track("json3", "https://x/en.json3"),
                ]
            }
        }

        chosen = _caption_track(info)

        assert chosen is not None
        assert chosen.caption_format == JSON3
        assert chosen.url == "https://x/en.json3"

    def test_vtt_is_taken_when_json3_is_absent(self) -> None:
        info = {
            "automatic_captions": {
                "en": [track("srv1", "https://x/en.srv1"), track("vtt", "https://x/en.vtt")]
            }
        }

        assert _caption_track(info) == CaptionTrack(url="https://x/en.vtt", caption_format=VTT)

    def test_manual_subtitles_still_win_over_automatic_ones(self) -> None:
        # Even though only the automatic track offers json3: a human-written
        # track is not a guess at the audio, and that ordering predates R1013.
        info = {
            "subtitles": {"en": [track("vtt", "https://x/manual.vtt")]},
            "automatic_captions": {"en": [track("json3", "https://x/auto.json3")]},
        }

        assert _caption_track(info) == CaptionTrack(url="https://x/manual.vtt", caption_format=VTT)

    def test_json3_wins_within_the_manual_track_too(self) -> None:
        info = {
            "subtitles": {
                "en": [
                    track("vtt", "https://x/manual.vtt"),
                    track("json3", "https://x/manual.json3"),
                ]
            },
            "automatic_captions": {"en": [track("json3", "https://x/auto.json3")]},
        }

        assert _caption_track(info) == CaptionTrack(
            url="https://x/manual.json3", caption_format=JSON3
        )

    def test_first_offered_is_the_last_resort_and_reports_what_it_advertises(self) -> None:
        info = {
            "automatic_captions": {
                "en": [track("ttml", "https://x/en.ttml"), track("srv3", "https://x/en.srv3")]
            }
        }

        assert _caption_track(info) == CaptionTrack(url="https://x/en.ttml", caption_format="ttml")

    def test_a_track_advertising_no_extension_reports_the_unknown_format(self) -> None:
        info = {"automatic_captions": {"en": [track(None, "https://x/en.whatever")]}}

        assert _caption_track(info) == CaptionTrack(
            url="https://x/en.whatever", caption_format=UNKNOWN_FORMAT
        )

    def test_no_english_track_is_still_none(self) -> None:
        info = {"automatic_captions": {"de": [track("json3", "https://x/de.json3")]}}

        assert _caption_track(info) is None

    def test_no_captions_at_all_is_still_none(self) -> None:
        assert _caption_track({}) is None

    @pytest.mark.parametrize("language", ["en", "en-orig", "en-US", "en-en"])
    def test_every_english_track_code_still_matches(self, language: str) -> None:
        info = {"automatic_captions": {language: [track("json3", "https://x/en.json3")]}}

        chosen = _caption_track(info)

        assert chosen is not None
        assert chosen.caption_format == JSON3


class TestFetchVideoCarriesTheFormat:
    """The boundary fetches the track it chose and says which format it was."""

    def test_a_json3_track_is_fetched_and_reported_as_json3(
        self, fake_client: type[FakeCaptionClient], tmp_path: Path
    ) -> None:
        fake_client.info = {
            "description": "Timestamps below.",
            "automatic_captions": {
                "en": [track("vtt", "https://x/en.vtt"), track("json3", "https://x/en.json3")]
            },
        }
        fake_client.bodies = {"https://x/en.json3": SIMPLE_JSON3.encode("utf-8")}

        fetched = ytdlp.fetch_video("aaa11111111", make_config(tmp_path))

        assert fetched.caption_format == JSON3
        assert fetched.captions == SIMPLE_JSON3
        assert fake_client.requested == ["https://x/en.json3"], (
            "the boundary must fetch the track it chose, and only that one"
        )

    def test_a_vtt_only_track_is_reported_as_vtt(
        self, fake_client: type[FakeCaptionClient], tmp_path: Path
    ) -> None:
        fake_client.info = {"automatic_captions": {"en": [track("vtt", "https://x/en.vtt")]}}
        fake_client.bodies = {"https://x/en.vtt": SIMPLE_VTT.encode("utf-8")}

        fetched = ytdlp.fetch_video("bbb22222222", make_config(tmp_path))

        assert fetched.caption_format == VTT
        assert fetched.captions == SIMPLE_VTT

    def test_a_video_with_no_track_still_reports_no_captions(
        self, fake_client: type[FakeCaptionClient], tmp_path: Path
    ) -> None:
        fake_client.info = {"description": "no captions on this one"}

        fetched = ytdlp.fetch_video("ccc33333333", make_config(tmp_path))

        assert fetched.captions is None
        assert fake_client.requested == []


class TestParseJson3:
    def test_parses_the_fixture_into_one_cue_per_spoken_line(self) -> None:
        assert parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8")) == EXPECTED_JSON3_CUES

    def test_returns_a_tuple(self) -> None:
        assert isinstance(parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8")), tuple)

    def test_no_line_is_stored_twice(self) -> None:
        cues = parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8"))

        texts = [cue.text for cue in cues]
        assert len(texts) == len(set(texts)), f"a line was stored more than once: {texts!r}"

    def test_an_append_event_contributes_no_cue(self) -> None:
        # The measured track's 2,257 `aAppend` events are text-free — one
        # newline each, which is exactly the 2,257-character difference OD-24
        # read as lost speech. Nothing text-free may become a cue.
        raw = json.dumps(
            {
                "events": [
                    {"tStartMs": 1000, "segs": [{"utf8": "first line"}]},
                    {"tStartMs": 2000, "aAppend": 1, "segs": [{"utf8": "\n"}]},
                    {"tStartMs": 2000, "segs": [{"utf8": "second line"}]},
                ]
            }
        )

        assert parse_json3(raw) == (
            Cue(start_seconds=1.0, text="first line"),
            Cue(start_seconds=2.0, text="second line"),
        )

    def test_the_line_break_is_not_lost_from_the_text_of_the_cues_around_it(self) -> None:
        """The correction OD-24 needs: `aAppend` is the BREAK, not the speech.

        Cue texts are joined with a single space downstream, so a break that
        survives as a cue boundary reproduces the sentence. A parser that drops
        the break WITHOUT leaving a boundary — concatenating the events instead
        — fuses the words either side of it, and `we'regoing` matches nothing.
        """
        cues = parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8"))

        joined = " ".join(cue.text for cue in cues)
        assert "we're going" in joined
        assert "we'regoing" not in joined
        assert "whetherthe" not in joined
        assert "VRMlayout" not in joined

    def test_segment_whitespace_is_preserved_verbatim(self) -> None:
        # json3 puts the leading space on the FOLLOWING word, so stripping per
        # segment fuses every word in the event.
        raw = json.dumps(
            {
                "events": [
                    {
                        "tStartMs": 0,
                        "segs": [
                            {"utf8": "Hey"},
                            {"utf8": " guys"},
                            {"utf8": ","},
                            {"utf8": " Quorvex", "tOffsetMs": 610},
                        ],
                    }
                ]
            }
        )

        assert parse_json3(raw) == (Cue(start_seconds=0.0, text="Hey guys, Quorvex"),)

    def test_the_fixture_words_are_not_fused(self) -> None:
        first = parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8"))[0]

        assert first.text == LINES[0]
        # Neither fused (`"".join` of stripped segments) nor spaced out
        # (`" ".join` of them): the punctuation arrives as its own segment and
        # the space arrives on the word after it.
        assert "Right,so" not in first.text
        assert "Right ," not in first.text

    def test_the_start_is_the_events_own_tstartms_in_seconds(self) -> None:
        raw = json.dumps(
            {"events": [{"tStartMs": 754320, "segs": [{"utf8": "late in the video"}]}]}
        )

        assert parse_json3(raw) == (Cue(start_seconds=754.32, text="late in the video"),)

    def test_a_segment_offset_never_moves_the_cue_start(self) -> None:
        # Per-segment `tOffsetMs` is carried no further than the event: R5 cuts
        # its window from the cue start, and the event IS the improvement.
        raw = json.dumps(
            {
                "events": [
                    {
                        "tStartMs": 5000,
                        "segs": [
                            {"utf8": "board", "tOffsetMs": 380},
                            {"utf8": " talk", "tOffsetMs": 900},
                        ],
                    }
                ]
            }
        )

        assert parse_json3(raw) == (Cue(start_seconds=5.0, text="board talk"),)

    def test_an_event_with_no_segs_key_contributes_no_cue(self) -> None:
        raw = json.dumps(
            {
                "events": [
                    {"tStartMs": 0, "dDurationMs": 1500, "id": 1, "wpWinPosId": 0, "wWinId": 1},
                    {"tStartMs": 1500, "segs": [{"utf8": "the only line"}]},
                ]
            }
        )

        assert parse_json3(raw) == (Cue(start_seconds=1.5, text="the only line"),)

    @pytest.mark.parametrize(
        "segs",
        [
            [],
            [{"utf8": ""}],
            [{"utf8": " "}, {"utf8": "  "}],
            [{"utf8": "\n"}],
            [{"tOffsetMs": 10}],
        ],
        ids=["empty-list", "empty-string", "spaces", "newline", "no-utf8-key"],
    )
    def test_an_event_with_no_text_contributes_no_cue(self, segs: list[dict[str, Any]]) -> None:
        raw = json.dumps(
            {
                "events": [
                    {"tStartMs": 1000, "segs": segs},
                    {"tStartMs": 2000, "segs": [{"utf8": "kept"}]},
                ]
            }
        )

        assert parse_json3(raw) == (Cue(start_seconds=2.0, text="kept"),)

    def test_events_are_read_in_document_order(self) -> None:
        cues = parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8"))

        starts = [cue.start_seconds for cue in cues]
        assert [cue.text for cue in cues] == list(LINES)
        assert starts == sorted(starts)

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "not json at all",
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello\n",
            "<html><body>429</body></html>",
            '{"events": [',
        ],
        ids=["empty", "prose", "webvtt", "html", "truncated"],
    )
    def test_a_document_that_is_not_json_raises(self, raw: str) -> None:
        """Unlike `parse_vtt`, which tolerates one malformed cue in two hours.

        A json3 payload that is not JSON at all is a different failure: a
        transcript of zero cues from a video that HAS captions would be
        indistinguishable from a video that has none, and the ledger's line
        between "could not fetch" and "nothing to fetch" is drawn on exactly
        that distinction.
        """
        with pytest.raises(ValueError):
            parse_json3(raw)


class TestFetchTranscriptChoosesTheParserFromTheFormat:
    def test_a_json3_fetch_is_parsed_as_json3_and_says_so(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        boundary.set_map({"vid1": json3_fetch()})

        transcript = fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert transcript.cues == EXPECTED_JSON3_CUES
        assert transcript.source_format == JSON3

    def test_a_vtt_fetch_is_parsed_as_vtt_and_says_so(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        boundary.set_map({"vid1": vtt_fetch()})

        transcript = fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert transcript.cues == EXPECTED_ROLLUP_CUES
        assert transcript.source_format == VTT

    def test_the_declared_format_is_obeyed_even_when_the_payload_disagrees(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        """The boundary knows what it asked for; a sniffer is a second reader.

        A WebVTT payload arriving under a `json3` declaration is a broken
        boundary, and it has to surface as one — `parse_json3` raising — rather
        than being quietly rescued by guessing from the bytes.
        """
        boundary.set_map(
            {"vid1": VideoFetch(captions=SIMPLE_VTT, description="", caption_format=JSON3)}
        )

        with pytest.raises(ValueError):
            fetch_transcript(make_video("vid1"), make_config(tmp_path))

    def test_a_vtt_declaration_is_obeyed_even_over_a_json3_payload(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        payload = JSON3_FIXTURE.read_text(encoding="utf-8")
        boundary.set_map({"vid1": VideoFetch(captions=payload, description="", caption_format=VTT)})

        transcript = fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert transcript.cues == parse_vtt(payload)
        assert transcript.source_format == VTT

    def test_no_captions_is_still_raised_before_any_parser_runs(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        boundary.set_map(
            {"vid1": VideoFetch(captions=None, description="d", caption_format=UNKNOWN_FORMAT)}
        )

        with pytest.raises(NoCaptions):
            fetch_transcript(make_video("vid1"), make_config(tmp_path))


class TestTheCacheCarriesTheFormat:
    def test_transcript_defaults_to_the_unknown_format(self) -> None:
        transcript = Transcript(video_id="vid1", cues=())

        assert transcript.source_format == UNKNOWN_FORMAT

    def test_a_json3_run_writes_the_format_into_the_record(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": json3_fetch()})

        fetch_all([make_video("vid1")], config, make_ledger(config, 1))

        record = json.loads(cache_path("vid1", config).read_text(encoding="utf-8"))
        assert record["source_format"] == JSON3

    def test_a_fallback_run_writes_vtt_into_the_record(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": vtt_fetch()})

        fetch_all([make_video("vid1")], config, make_ledger(config, 1))

        record = json.loads(cache_path("vid1", config).read_text(encoding="utf-8"))
        assert record["source_format"] == VTT

    def test_the_format_round_trips_through_the_cache(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": json3_fetch(), "vid2": vtt_fetch()})

        fetch_all([make_video("vid1"), make_video("vid2")], config, make_ledger(config, 2))

        first = load_cached("vid1", config)
        second = load_cached("vid2", config)
        assert first is not None and second is not None
        assert first.source_format == JSON3
        assert first.cues == EXPECTED_JSON3_CUES
        assert second.source_format == VTT
        assert second.cues == EXPECTED_ROLLUP_CUES

    def test_the_cache_file_is_still_deterministic(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        first = make_config(tmp_path / "one")
        second = make_config(tmp_path / "two")
        boundary.set_map({"vid1": json3_fetch()})
        fetch_all([make_video("vid1")], first, make_ledger(first, 1))
        fetch_all([make_video("vid1")], second, make_ledger(second, 1))

        text = cache_path("vid1", first).read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert text == cache_path("vid1", second).read_text(encoding="utf-8")


class TestARecordWrittenBeforeThisPlan:
    """A cache entry with no `source_format` key is unknown, never invalid.

    A strict read would invalidate the owner's whole cache and refetch the
    corpus, which is the opposite of the ruling R1004 already made for the
    description field, one slice earlier and for this exact situation.
    """

    def write_old_record(self, video_id: str, config: Config) -> Path:
        path = cache_path(video_id, config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "cues": [
                        {"start_seconds": 1.5, "text": "first"},
                        {"start_seconds": 9.0, "text": "second"},
                    ],
                    "video_id": video_id,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_it_loads_with_the_unknown_format_and_its_cues_intact(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        self.write_old_record("abc123", config)

        loaded = load_cached("abc123", config)

        assert loaded is not None, "an entry written before this plan must still load"
        assert loaded.source_format == UNKNOWN_FORMAT
        assert loaded.cues == (
            Cue(start_seconds=1.5, text="first"),
            Cue(start_seconds=9.0, text="second"),
        )

    def test_the_unknown_format_is_the_string_unknown(self) -> None:
        # Not "vtt": guessing that an old entry came from the VTT path would be
        # true today and a lie the moment anyone replays this reasoning, and it
        # is what keeps the run summary's fallback count honest.
        assert UNKNOWN_FORMAT == "unknown"

    def test_it_is_never_refetched(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        path = self.write_old_record("abc123", config)
        before = path.read_bytes()

        assert fetch_all([make_video("abc123")], config, make_ledger(config, 1)) == 0
        assert boundary.calls == [], "an old cache entry must not be refetched for its provenance"
        assert path.read_bytes() == before


class TestParseVttDropsRollUpFrames:
    def test_the_roll_up_fixture_yields_one_cue_per_spoken_line(self) -> None:
        assert parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8")) == EXPECTED_ROLLUP_CUES

    def test_no_line_appears_more_than_once(self) -> None:
        cues = parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8"))

        texts = [cue.text for cue in cues]
        assert len(texts) == len(set(texts))
        assert len(texts) == len(LINES)

    def test_the_starts_are_the_solo_frames_not_the_hundredth_second_twins(self) -> None:
        cues = parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8"))

        # 1.51, 4.52 and 6.88 are display frames — the same speech drawn again
        # with the next line appended — and no cue may be timed from one.
        assert [cue.start_seconds for cue in cues[:4]] == [1.5, 4.51, 6.87, 9.32]

    def test_the_last_line_survives_as_its_own_cue(self) -> None:
        """The silent loss this rule exists to prevent.

        The closing cue is a frame extending its predecessor, so its new tail
        has no solo cue anywhere after it. Drop the frame without keeping the
        tail and the last line of every fallback transcript disappears.
        """
        cues = parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8"))

        assert cues[-1].text == LINES[4]
        assert cues[-1].start_seconds == 9.33
        assert LINES[3] not in cues[-1].text, "the tail is kept, not the whole frame"

    def test_a_frame_extending_the_previous_cue_is_dropped(self) -> None:
        # A, "A B", B, "B C", C — the whole roll-up sequence in miniature,
        # ending on a solo cue so nothing here depends on the last-line rule.
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nthe fan header sits low\n\n"
            "00:00:01.010 --> 00:00:04.000\nthe fan header sits low and to the right\n\n"
            "00:00:04.000 --> 00:00:06.000\nand to the right\n\n"
            "00:00:04.010 --> 00:00:06.000\nand to the right which is where the pump goes\n\n"
            "00:00:06.000 --> 00:00:08.000\nwhich is where the pump goes\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=1.0, text="the fan header sits low"),
            Cue(start_seconds=4.0, text="and to the right"),
            Cue(start_seconds=6.0, text="which is where the pump goes"),
        )

    def test_a_closing_frames_tail_is_kept_as_its_own_cue(self) -> None:
        # The same rule the fixture exercises, reduced to two cues: the frame
        # is dropped, but the line it added is not.
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nthe fan header sits low\n\n"
            "00:00:01.010 --> 00:00:04.000\nthe fan header sits low and to the right\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=1.0, text="the fan header sits low"),
            Cue(start_seconds=1.01, text="and to the right"),
        )

    def test_a_cue_wholly_contained_in_the_previous_one_is_dropped(self) -> None:
        # The same frame seen from the other side: the roll-up scroll leaves a
        # suffix of what was just displayed.
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nthe fan header sits low and to the right\n\n"
            "00:00:04.000 --> 00:00:06.000\nand to the right\n\n"
            "00:00:06.000 --> 00:00:08.000\nwhich is where the pump goes\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=1.0, text="the fan header sits low and to the right"),
            Cue(start_seconds=6.0, text="which is where the pump goes"),
        )

    def test_an_adjacent_exact_repeat_is_dropped(self) -> None:
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nsame line twice\n\n"
            "00:00:04.000 --> 00:00:06.000\nsame line twice\n"
        )

        assert parse_vtt(raw) == (Cue(start_seconds=1.0, text="same line twice"),)

    def test_a_line_repeated_later_in_the_video_is_kept(self) -> None:
        # The rule is structural and only ever compares ADJACENT cues, so
        # genuinely repeated speech survives.
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nit is a good board\n\n"
            "00:00:04.000 --> 00:00:06.000\nfor the money\n\n"
            "00:00:06.000 --> 00:00:08.000\nit is a good board\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=1.0, text="it is a good board"),
            Cue(start_seconds=4.0, text="for the money"),
            Cue(start_seconds=6.0, text="it is a good board"),
        )

    def test_a_prefix_that_does_not_end_at_a_word_boundary_is_not_a_frame(self) -> None:
        # "the VRMs" merely starts with the letters of "the VRM"; a frame is the
        # previous cue's text followed by a SEPARATOR, which this is not.
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nthe VRM\n\n"
            "00:00:04.000 --> 00:00:06.000\nthe VRMs are what matter\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=1.0, text="the VRM"),
            Cue(start_seconds=4.0, text="the VRMs are what matter"),
        )


class TestAnOrdinaryWebvttIsUntouched:
    """The guard that this de-duplication cannot damage a normal track.

    No cue in an ordinary WebVTT extends its predecessor, so every rule above
    is a no-op on one. That is asserted, not assumed — ESC-21 is the fixture
    agreeing with the code while both disagree with what YouTube sends, and the
    answer to it is not to stop checking the fixture.
    """

    def test_the_shipped_fixture_parses_exactly_as_it_does_today(self) -> None:
        assert parse_vtt(PLAIN_FIXTURE.read_text(encoding="utf-8")) == EXPECTED_PLAIN_CUES

    def test_a_plain_two_cue_track_keeps_both_cues(self) -> None:
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\nfirst thing\n\n"
            "00:00:04.000 --> 00:00:06.000\nsecond thing\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=1.0, text="first thing"),
            Cue(start_seconds=4.0, text="second thing"),
        )

    def test_a_single_cue_track_is_unchanged(self) -> None:
        assert parse_vtt(SIMPLE_VTT) == (Cue(start_seconds=2.0, text="hello there"),)

    def test_an_empty_track_is_still_empty(self) -> None:
        assert parse_vtt("WEBVTT\n\n") == ()


class TestTheTwoPathsAgree:
    """BL-28's ground-truth comparison, at fixture scale.

    The reconstruction landed within 0.05% of json3 over a whole video — 73,121
    characters against 73,159 — and that agreement is the property that makes
    the fallback trustworthy rather than merely available. Both fixtures carry
    the same five spoken lines, so the two parsers are being asked the same
    question in the two formats YouTube answers it in.
    """

    def json3_text(self) -> str:
        return " ".join(cue.text for cue in parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8")))

    def rollup_text(self) -> str:
        return " ".join(cue.text for cue in parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8")))

    def test_the_character_totals_are_within_a_few_percent(self) -> None:
        from_json3 = len(self.json3_text())
        from_vtt = len(self.rollup_text())

        assert from_json3 > 0
        drift = abs(from_vtt - from_json3) / from_json3
        assert drift <= 0.05, (
            f"the fallback stores {from_vtt} characters where json3 stores {from_json3} "
            f"({drift:.1%} apart); at 2.84x the roll-up frames are still being kept"
        )

    def test_the_two_paths_produce_the_same_words(self) -> None:
        assert self.rollup_text().split() == self.json3_text().split()

    def test_the_two_paths_produce_the_same_number_of_cues(self) -> None:
        assert len(parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8"))) == len(
            parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8"))
        )

    def test_the_solo_starts_agree_with_the_json3_event_starts(self) -> None:
        # Every line but the last: json3 times it from the event, roll-up VTT
        # from the frame it was displayed alone at, and those are the same
        # instant. The last line has no solo frame, which is exactly why the
        # timestamp R5 cuts from is better taken from json3.
        from_vtt = parse_vtt(ROLLUP_FIXTURE.read_text(encoding="utf-8"))
        from_json3 = parse_json3(JSON3_FIXTURE.read_text(encoding="utf-8"))

        assert [cue.start_seconds for cue in from_vtt[:4]] == [
            cue.start_seconds for cue in from_json3[:4]
        ]


def mentions(out: str, *needles: str) -> str:
    """Every output line mentioning any of `needles`, joined for assertion."""
    lowered = [needle.lower() for needle in needles]
    lines = [line for line in out.splitlines() if any(n in line.lower() for n in lowered)]
    return "\n".join(lines)


def says(text: str, count: int) -> bool:
    return re.search(rf"\b{count}\b", text) is not None


class TestTheRunSaysWhichPathEveryVideoTook:
    """R1013's last requirement: the summary reports the provenance counts.

    A fallback nobody notices is a reconstruction silently mixed in with
    verbatim text, and the run is the only place that can still tell the
    difference cheaply.
    """

    def write_index_file(self, config: Config, videos: list[Video]) -> None:
        write_index(videos, config.data_dir / "index.jsonl")

    def cache_record(self, video_id: str, config: Config, source_format: str) -> None:
        """A transcript some earlier run cached, in the given format."""
        path = cache_path(video_id, config)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "cues": [{"start_seconds": 1.0, "text": "cached earlier"}],
            "description": "",
            "source_format": source_format,
            "video_id": video_id,
        }
        path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    def test_a_mixed_run_reports_both_counts(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        videos = [make_video(f"vid{n}") for n in range(1, 4)]
        self.write_index_file(config, videos)
        boundary.set_map({"vid1": json3_fetch(), "vid2": json3_fetch(), "vid3": vtt_fetch()})

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        json3_lines = mentions(out, "json3")
        assert json3_lines, f"the summary never says how many videos came from json3: {out!r}"
        assert says(json3_lines, 2), f"json3 count is not 2: {json3_lines!r}"
        fallback_lines = mentions(out, "vtt", "fallback")
        assert fallback_lines, f"the summary never says how many took the fallback: {out!r}"
        assert says(fallback_lines, 1), f"fallback count is not 1: {fallback_lines!r}"

    def test_both_counts_print_when_nothing_took_the_fallback(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A count that appears only when it fired cannot be told from one that
        # never ran — the rule R1009, R1010 and R1012 already follow.
        config = make_config(tmp_path / "data")
        videos = [make_video(f"vid{n}") for n in range(1, 4)]
        self.write_index_file(config, videos)
        boundary.set_map(dict.fromkeys(["vid1", "vid2", "vid3"], json3_fetch()))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert says(mentions(out, "json3"), 3), f"json3 count is not 3: {out!r}"
        assert says(mentions(out, "vtt", "fallback"), 0), f"no zero fallback count: {out!r}"

    def test_both_counts_print_on_a_run_that_fetched_nothing(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        self.write_index_file(config, [])

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert says(mentions(out, "json3"), 0), f"no zero json3 count on an empty run: {out!r}"
        assert says(mentions(out, "vtt", "fallback"), 0), f"no zero fallback count: {out!r}"

    def test_the_counts_describe_this_run_and_not_the_cache_directory(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A cache holding older entries is what the counts must NOT average away.

        Four transcripts sit in the cache before this run: three from a corpus
        no longer in the index and one that is a plain cache hit. A count taken
        by walking `data/transcripts/` reports five fallbacks; a count taken
        from what this run cached reports one.
        """
        config = make_config(tmp_path / "data")
        videos = [make_video(f"vid{n}") for n in range(1, 5)]
        self.write_index_file(config, videos)
        for leftover in ("old1", "old2", "old3"):
            self.cache_record(leftover, config, VTT)
        self.cache_record("vid4", config, VTT)
        boundary.set_map({"vid1": json3_fetch(), "vid2": json3_fetch(), "vid3": vtt_fetch()})

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert boundary.calls == ["vid1", "vid2", "vid3"]
        fallback_lines = mentions(out, "vtt", "fallback")
        assert says(fallback_lines, 1), f"fallback count is not 1: {fallback_lines!r}"
        assert not says(fallback_lines, 5), f"the whole cache directory was counted: {out!r}"
        assert not says(fallback_lines, 4), f"the whole cache directory was counted: {out!r}"

    def test_the_fallback_is_called_out_when_it_was_used(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Called out, not merely counted — R1013 says prominently.

        The message has to say what it means: those transcripts were
        reconstructed from roll-up display frames rather than read verbatim.
        """
        config = make_config(tmp_path / "data")
        videos = [make_video(f"vid{n}") for n in range(1, 4)]
        self.write_index_file(config, videos)
        boundary.set_map({"vid1": json3_fetch(), "vid2": json3_fetch(), "vid3": vtt_fetch()})

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert "WARNING" in out.upper(), (
            f"a fallback that only shows up as a number is one nobody notices: {out!r}"
        )
        assert re.search(r"roll-?up|reconstruct", out, re.IGNORECASE), (
            f"the call-out never says what the fallback did to those transcripts: {out!r}"
        )

    def test_there_is_no_call_out_when_every_video_came_from_json3(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        videos = [make_video(f"vid{n}") for n in range(1, 4)]
        self.write_index_file(config, videos)
        boundary.set_map(dict.fromkeys(["vid1", "vid2", "vid3"], json3_fetch()))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert "WARNING" not in out.upper(), f"nothing took the fallback: {out!r}"

    def test_a_halted_run_still_reports_what_it_cached(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The R24 trigger path prints the ledger; the provenance of what did
        # land goes with it, or a halt hides it.
        config = make_config(
            tmp_path / "data", consecutive_fetch_error_limit=2, fetch_error_rate_limit=0.9
        )
        videos = [make_video(f"vid{n}") for n in range(1, 6)]
        self.write_index_file(config, videos)
        boundary.set_map(
            {
                "vid1": json3_fetch(),
                "vid2": RuntimeError("HTTP 503 from YouTube"),
                "vid3": RuntimeError("HTTP 503 from YouTube"),
            }
        )

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "consecutive_fetch_errors" in out
        assert says(mentions(out, "json3"), 1), f"the halt hid the json3 count: {out!r}"
        assert says(mentions(out, "vtt", "fallback"), 0), (
            f"the halt hid the fallback count: {out!r}"
        )
        assert "Traceback" not in out
