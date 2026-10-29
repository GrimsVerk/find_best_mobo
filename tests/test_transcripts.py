"""Tests for slice 2 — transcripts land in a local cache, and gaps are visible.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so failing imports are the expected
state until assembly. The only surface faked here is ``fetch_video``, the
declared per-video boundary in ``find_best_mobo.ytdlp`` — patched where
``transcripts.py`` uses it, never a level deeper, and never the unit under test.

``fetch_caption_track`` was that boundary until OD-8/R1004: a function that also
returns the description is not a caption-track fetcher, so it was renamed in the
slice that changed what it returns, and this file fakes the new name.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-2 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Callable, Iterable
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.commands.fetch import run
from find_best_mobo.config import Config
from find_best_mobo.index import Video, write_index
from find_best_mobo.ledger import HaltTriggered, Ledger
from find_best_mobo.transcripts import (
    UNKNOWN_FORMAT,
    Cue,
    NoCaptions,
    Transcript,
    cache_path,
    fetch_all,
    fetch_transcript,
    load_cached,
    parse_vtt,
)
from find_best_mobo.ytdlp import VTT, VideoFetch

FIXTURE = Path(__file__).parent / "fixtures" / "captions_vtt.txt"

# What the fixture means, cue by cue. Two cues in the file are deliberately not
# here: the one that is empty once its tags are stripped, and the stray block
# that carries no timing line.
EXPECTED_CUES = (
    Cue(start_seconds=1.0, text="So the X670E Taichi board"),
    Cue(start_seconds=4.5, text="has a twelve phase VRM and it is actually quite good"),
    Cue(start_seconds=62.25, text="the B650E is fine too"),
    Cue(start_seconds=67.0, text="VRM thermals matter"),
    Cue(start_seconds=3723.75, text="two hours in, still talking about VRMs"),
)

SIMPLE_VTT = "WEBVTT\n\n00:00:02.000 --> 00:00:03.000\nhello there\n"

# BL-11's measured description, verbatim, with invented surroundings. The
# hashtag line is the evidence OD-8 was decided on; everything around it is
# padding, and no assertion in this file reads the padding.
DESCRIPTION = (
    "Full teardown of the little board.\nLinks and timestamps below.\n#AMD #ryzen #MSI #B850 #ITX\n"
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
        classification="regular" if inclusion != "excluded_short" else "short",
        inclusion=inclusion,
    )


class Boundary:
    """The faked per-video boundary, plus the record of how it was called.

    Captions and description are answered together, from one call, because
    ``fetch_video`` gets both out of one extraction (OD-8).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.handler: Callable[[str], str | None] = lambda video_id: SIMPLE_VTT
        self.descriptions: dict[str, str] = {}
        self.caption_formats: dict[str, str] = {}
        self.default_caption_format = VTT
        self.default_description = ""

    def set_caption_formats(self, mapping: dict[str, str]) -> None:
        """Answer these video ids with these caption formats, others with `vtt`."""
        self.caption_formats = dict(mapping)

    def set_descriptions(self, mapping: dict[str, str]) -> None:
        """Answer these video ids with these descriptions, others with ``""``."""
        self.descriptions = dict(mapping)

    def set_map(self, mapping: dict[str, str | None | Exception]) -> None:
        """Answer per video id: WebVTT text, None (no captions), or an exception."""

        def handler(video_id: str) -> str | None:
            answer = mapping[video_id]
            if isinstance(answer, Exception):
                raise answer
            return answer

        self.handler = handler

    def always_raise(self, error: Exception) -> None:
        def handler(video_id: str) -> str | None:
            raise error

        self.handler = handler

    def always_none(self) -> None:
        def handler(video_id: str) -> str | None:
            return None

        self.handler = handler


@pytest.fixture
def boundary(monkeypatch: pytest.MonkeyPatch) -> Boundary:
    """Fake ``fetch_video`` — the one surface a test may fake here."""
    fake = Boundary()

    def fake_fetch_video(video_id: str, config: Config) -> VideoFetch:
        assert isinstance(config, Config)
        fake.calls.append(video_id)
        # The handler runs first: whatever goes wrong reaching YouTube raises
        # here rather than being folded into a returned value.
        captions = fake.handler(video_id)
        return VideoFetch(
            captions=captions,
            description=fake.descriptions.get(video_id, fake.default_description),
            # R1013 made this required. The existing fixtures answer with WebVTT
            # bodies, so `vtt` is what this fake is honestly reporting; the
            # json3 tests set it explicitly.
            caption_format=fake.caption_formats.get(video_id, fake.default_caption_format),
        )

    import find_best_mobo.ytdlp as ytdlp_boundary

    monkeypatch.setattr(ytdlp_boundary, "fetch_video", fake_fetch_video)

    import find_best_mobo.commands.fetch as command_module
    import find_best_mobo.transcripts as transcripts_module

    for module in (transcripts_module, command_module):
        if hasattr(module, "fetch_video"):
            monkeypatch.setattr(module, "fetch_video", fake_fetch_video)
    return fake


def make_ledger(config: Config, indexed_count: int) -> Ledger:
    return Ledger(config.data_dir / "failures.jsonl", config, indexed_count)


class TestParseVtt:
    def test_parses_the_whole_fixture_in_file_order(self) -> None:
        assert parse_vtt(FIXTURE.read_text()) == EXPECTED_CUES

    def test_returns_a_tuple(self) -> None:
        assert isinstance(parse_vtt(FIXTURE.read_text()), tuple)

    def test_header_note_and_numeric_ids_never_reach_a_cue(self) -> None:
        cues = parse_vtt(FIXTURE.read_text())

        joined = " ".join(cue.text for cue in cues)
        assert "WEBVTT" not in joined
        assert "NOTE" not in joined
        assert "generated automatically" not in joined
        assert "Kind: captions" not in joined
        assert "no timing line" not in joined
        assert not any(cue.text.strip().isdigit() for cue in cues)

    def test_both_timestamp_forms_parse(self) -> None:
        raw = (
            "WEBVTT\n\n"
            "02:03.500 --> 02:05.000\nshort form\n\n"
            "01:00:00.250 --> 01:00:02.000\nlong form\n"
        )

        assert parse_vtt(raw) == (
            Cue(start_seconds=123.5, text="short form"),
            Cue(start_seconds=3600.25, text="long form"),
        )

    def test_trailing_cue_settings_are_ignored(self) -> None:
        raw = "WEBVTT\n\n00:00:10.000 --> 00:00:12.000 align:start position:0% line:90%\nsettings\n"

        assert parse_vtt(raw) == (Cue(start_seconds=10.0, text="settings"),)

    def test_inline_tags_are_stripped(self) -> None:
        raw = (
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n"
            "<v Buildzoid><c.colorE5E5E5>the</c> <00:00:01.500><c>VRM</c> is fine\n"
        )

        assert parse_vtt(raw) == (Cue(start_seconds=1.0, text="the VRM is fine"),)

    def test_multi_line_cue_text_is_joined_with_one_space(self) -> None:
        raw = "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nfirst line\nsecond line\nthird line\n"

        assert parse_vtt(raw) == (Cue(start_seconds=1.0, text="first line second line third line"),)

    def test_surrounding_whitespace_is_trimmed(self) -> None:
        raw = "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\n   padded text   \n"

        assert parse_vtt(raw) == (Cue(start_seconds=1.0, text="padded text"),)

    def test_cue_empty_after_stripping_is_dropped(self) -> None:
        raw = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:02.000\n<c> </c>\n\n"
            "00:00:02.000 --> 00:00:03.000\nkept\n"
        )

        assert parse_vtt(raw) == (Cue(start_seconds=2.0, text="kept"),)

    def test_empty_input_returns_empty_tuple(self) -> None:
        assert parse_vtt("") == ()

    def test_header_only_input_returns_empty_tuple(self) -> None:
        assert parse_vtt("WEBVTT\n\n") == ()

    @pytest.mark.parametrize(
        "raw",
        [
            "not webvtt at all",
            "WEBVTT\n\n99:99 --> nonsense\nbroken\n",
            "WEBVTT\n\n-->\n\n\n",
            "\n\n\n",
            "WEBVTT\n\n00:00:01.000 --> \ndangling\n",
        ],
    )
    def test_malformed_input_never_raises(self, raw: str) -> None:
        result = parse_vtt(raw)

        assert isinstance(result, tuple)
        for cue in result:
            assert isinstance(cue.start_seconds, float)


class TestCachePath:
    def test_is_a_json_file_named_for_the_video_under_transcripts(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        assert cache_path("b0ardLong01", config) == tmp_path / "transcripts" / "b0ardLong01.json"

    def test_follows_the_configured_data_dir(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "elsewhere")

        assert cache_path("x", config) == tmp_path / "elsewhere" / "transcripts" / "x.json"


class TestLoadCached:
    def test_absent_file_returns_none(self, tmp_path: Path) -> None:
        assert load_cached("nothing_here", make_config(tmp_path)) is None

    def test_reads_back_the_documented_json_shape(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        path = cache_path("abc123", config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "cues": [
                        {"start_seconds": 1.5, "text": "first"},
                        {"start_seconds": 9.0, "text": "second"},
                    ],
                    "video_id": "abc123",
                },
                sort_keys=True,
            )
            + "\n"
        )

        assert load_cached("abc123", config) == Transcript(
            video_id="abc123",
            cues=(Cue(start_seconds=1.5, text="first"), Cue(start_seconds=9.0, text="second")),
            source_format=UNKNOWN_FORMAT,
        )

    @pytest.mark.parametrize("junk", ["{not json at all", "", "[1, 2, 3]"])
    def test_corrupt_file_is_treated_as_absent(self, tmp_path: Path, junk: str) -> None:
        config = make_config(tmp_path)
        path = cache_path("damaged", config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(junk)

        assert load_cached("damaged", config) is None


class TestFetchTranscript:
    def test_returns_the_parsed_transcript_for_the_video(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": FIXTURE.read_text()})

        transcript = fetch_transcript(make_video("vid1"), config)

        assert boundary.calls == ["vid1"]
        assert transcript == Transcript(video_id="vid1", cues=EXPECTED_CUES, source_format=VTT)

    def test_raises_no_captions_when_the_boundary_returns_none(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        boundary.always_none()

        with pytest.raises(NoCaptions):
            fetch_transcript(make_video("vid1"), make_config(tmp_path))

    def test_other_exceptions_propagate_unchanged(self, boundary: Boundary, tmp_path: Path) -> None:
        error = RuntimeError("HTTP 429 from YouTube")
        boundary.always_raise(error)

        with pytest.raises(RuntimeError) as caught:
            fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert caught.value is error

    def test_never_writes_the_cache(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        fetch_transcript(make_video("vid1"), config)

        assert not cache_path("vid1", config).exists()

    def test_never_reads_the_cache(self, boundary: Boundary, tmp_path: Path) -> None:
        # A cached transcript is sitting on disk, and the boundary is broken.
        # fetch_transcript owns no cache logic, so it must still call out and
        # still fail: the cache decision belongs to fetch_all alone.
        config = make_config(tmp_path)
        path = cache_path("vid1", config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cues": [], "video_id": "vid1"}) + "\n")
        boundary.always_raise(RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            fetch_transcript(make_video("vid1"), config)

        assert boundary.calls == ["vid1"]


class TestFetchAll:
    def test_writes_the_cache_and_counts_what_it_fetched(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": FIXTURE.read_text(), "vid2": SIMPLE_VTT})
        ledger = make_ledger(config, 2)

        fetched = fetch_all([make_video("vid1"), make_video("vid2")], config, ledger)

        assert fetched == 2
        assert boundary.calls == ["vid1", "vid2"]
        assert ledger.failures() == ()
        assert load_cached("vid1", config) == Transcript(
            video_id="vid1", cues=EXPECTED_CUES, source_format=VTT
        )
        assert load_cached("vid2", config) == Transcript(
            video_id="vid2",
            cues=(Cue(start_seconds=2.0, text="hello there"),),
            source_format=VTT,
        )

    def test_cache_file_is_deterministic_json_with_a_trailing_newline(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        first = make_config(tmp_path / "one")
        second = make_config(tmp_path / "two")
        boundary.set_map({"vid1": FIXTURE.read_text()})

        fetch_all([make_video("vid1")], first, make_ledger(first, 1))
        boundary.set_map({"vid1": FIXTURE.read_text()})
        fetch_all([make_video("vid1")], second, make_ledger(second, 1))

        text = cache_path("vid1", first).read_text()
        assert text.endswith("\n")
        assert text == cache_path("vid1", second).read_text()
        record = json.loads(text)
        assert record["video_id"] == "vid1"
        assert record["cues"][0] == {"start_seconds": 1.0, "text": "So the X670E Taichi board"}

    def test_accepts_a_plain_iterator(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        videos: Iterable[Video] = iter([make_video("vid1")])

        assert fetch_all(videos, config, make_ledger(config, 1)) == 1

    def test_cached_videos_are_skipped_entirely(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        # vid1 was fetched on an earlier run; only vid2 is missing.
        fetch_all([make_video("vid1")], config, make_ledger(config, 1))
        boundary.calls.clear()
        ledger = make_ledger(config, 2)

        fetched = fetch_all([make_video("vid1"), make_video("vid2")], config, ledger)

        assert fetched == 1, "a cache hit must not be counted as newly fetched"
        assert boundary.calls == ["vid2"], "a cached video must never reach the boundary"
        assert ledger.failures() == ()

    def test_a_rerun_with_everything_cached_fetches_nothing(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        videos = [make_video("vid1"), make_video("vid2")]
        assert fetch_all(videos, config, make_ledger(config, 2)) == 2
        boundary.calls.clear()

        assert fetch_all(videos, config, make_ledger(config, 2)) == 0
        assert boundary.calls == []

    def test_no_captions_is_recorded_and_not_counted(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, missing_caption_rate_limit=0.9)
        boundary.set_map({"vid1": SIMPLE_VTT, "vid2": None})
        ledger = make_ledger(config, 2)

        fetched = fetch_all([make_video("vid1"), make_video("vid2")], config, ledger)

        assert fetched == 1
        assert [failure.video_id for failure in ledger.failures()] == ["vid2"]
        failure = ledger.failures()[0]
        assert failure.failure_class == "no_captions"
        assert failure.detail == ""
        assert failure.title == "vid2 VRM breakdown"
        assert failure.upload_date == date(2023, 6, 15)
        assert failure.attempts == 1
        assert not cache_path("vid2", config).exists()

    def test_fetch_error_carries_the_exception_text(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, fetch_error_rate_limit=0.9)
        boundary.set_map({"vid1": RuntimeError("HTTP 503 from YouTube")})
        ledger = make_ledger(config, 100)

        fetched = fetch_all([make_video("vid1")], config, ledger)

        assert fetched == 0
        failure = ledger.failures()[0]
        assert failure.failure_class == "fetch_error"
        assert failure.detail == "HTTP 503 from YouTube"
        assert failure.attempts == 1

    def test_a_failure_does_not_stop_the_remaining_videos(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, fetch_error_rate_limit=0.9)
        boundary.set_map({"vid1": RuntimeError("nope"), "vid2": SIMPLE_VTT, "vid3": SIMPLE_VTT})
        ledger = make_ledger(config, 100)

        fetched = fetch_all(
            [make_video("vid1"), make_video("vid2"), make_video("vid3")], config, ledger
        )

        assert fetched == 2
        assert boundary.calls == ["vid1", "vid2", "vid3"]
        assert len(ledger.failures()) == 1

    def test_halt_propagates_with_the_ledger_already_on_disk(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, consecutive_fetch_error_limit=2, fetch_error_rate_limit=0.9)
        boundary.always_raise(RuntimeError("network down"))
        ledger_path = config.data_dir / "failures.jsonl"
        ledger = Ledger(ledger_path, config, 100)
        videos = [make_video(f"vid{n}") for n in range(1, 6)]

        with pytest.raises(HaltTriggered) as caught:
            fetch_all(videos, config, ledger)

        assert caught.value.trigger == "consecutive_fetch_errors"
        assert tuple(caught.value.ledger) == ledger.failures()
        # The halt stops the run where it fired, and the evidence is on disk.
        assert boundary.calls == ["vid1", "vid2"]
        assert ledger_path.is_file()
        lines = [line for line in ledger_path.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        assert {json.loads(line)["video_id"] for line in lines} == {"vid1", "vid2"}

    def test_everything_fetched_before_a_halt_stays_cached(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, consecutive_fetch_error_limit=2, fetch_error_rate_limit=0.9)
        boundary.set_map(
            {
                "vid1": SIMPLE_VTT,
                "vid2": RuntimeError("down"),
                "vid3": RuntimeError("down"),
                "vid4": SIMPLE_VTT,
            }
        )
        videos = [make_video(f"vid{n}") for n in range(1, 5)]

        with pytest.raises(HaltTriggered):
            fetch_all(videos, config, make_ledger(config, 100))

        assert cache_path("vid1", config).is_file()
        assert not cache_path("vid4", config).exists()


class TestFetchCommand:
    def write_index_file(self, config: Config, videos: list[Video]) -> None:
        write_index(videos, config.data_dir / "index.jsonl")

    def test_missing_index_returns_one_with_a_helpful_message(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "index" in out.lower(), f"the message must point at the index command: {out!r}"
        assert boundary.calls == []

    def test_a_halted_run_still_leaves_the_cache_directory(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R1005: "fetch never ran" and "fetch ran and got nothing" must differ on disk.

        Before this, `data/transcripts/` appeared only on the first successful
        write, so a run whose every video had no captions — halting on R24's
        missing-caption trigger before caching anything — left the same tree as
        a run nobody had started. Every stage downstream reads that directory as
        its precondition, so the two states must not be one.
        """
        config = make_config(tmp_path / "data", missing_caption_rate_limit=0.5)
        self.write_index_file(config, [make_video("vid1"), make_video("vid2")])
        boundary.set_map({"vid1": None, "vid2": None})

        assert run(config, Namespace()) == 1, "the missing-caption trigger should have halted this"
        capsys.readouterr()

        cache_dir = config.data_dir / "transcripts"
        assert cache_dir.is_dir(), "fetch ran, halted, and left no cache directory"
        assert list(cache_dir.glob("*.json")) == []

    def test_a_run_with_no_pending_videos_still_leaves_the_cache_directory(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An empty corpus is a real result, and it has to look like one downstream."""
        config = make_config(tmp_path / "data")
        self.write_index_file(config, [])

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert (config.data_dir / "transcripts").is_dir()
        assert boundary.calls == []

    def test_normal_run_prints_the_summary_and_returns_zero(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Six pending videos, two of them already cached, so four are attempted:
        # three succeed and one has no captions. Every count is distinct so the
        # summary numbers cannot be mistaken for one another.
        config = make_config(tmp_path / "data", missing_caption_rate_limit=0.9)
        pending = [make_video(f"vid{n}") for n in range(1, 7)]
        excluded = [
            make_video("shortVid", inclusion="excluded_short"),
            make_video("oldVid", inclusion="excluded_out_of_range"),
        ]
        self.write_index_file(config, pending + excluded)
        boundary.set_map(dict.fromkeys([f"vid{n}" for n in range(1, 7)], SIMPLE_VTT))
        fetch_all(pending[:2], config, make_ledger(config, 2))
        boundary.calls.clear()
        boundary.set_map(
            {
                "vid3": SIMPLE_VTT,
                "vid4": SIMPLE_VTT,
                "vid5": SIMPLE_VTT,
                "vid6": None,
            }
        )

        assert run(config, Namespace()) == 0

        assert boundary.calls == ["vid3", "vid4", "vid5", "vid6"], (
            "excluded and cached videos must never reach the boundary"
        )
        assert not cache_path("shortVid", config).exists()
        out = capsys.readouterr().out
        for count in (6, 2, 3, 1):
            assert re.search(rf"\b{count}\b", out), f"summary omits the count {count}: {out!r}"
        assert "no_captions" in out
        assert "Traceback" not in out

    def test_halt_prints_the_trigger_and_the_ledger_and_returns_one(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(
            tmp_path / "data", consecutive_fetch_error_limit=2, fetch_error_rate_limit=0.9
        )
        pending = [make_video(f"vid{n}", title=f"Board rant {n}") for n in range(1, 6)]
        self.write_index_file(config, pending)
        boundary.always_raise(RuntimeError("HTTP 503 from YouTube"))

        # A halt is a deliberate stop: it must not escape as a traceback.
        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "consecutive_fetch_errors" in out
        assert "Traceback" not in out
        for expected in ("vid1", "vid2", "Board rant 1", "2023-06-15", "fetch_error"):
            assert expected in out, f"the printed ledger omits {expected!r}: {out!r}"
        assert "vid3" not in out, "the run stops at the halt rather than working on"
        assert (config.data_dir / "failures.jsonl").is_file()

    def test_a_rerun_after_a_clean_run_fetches_nothing(
        self, boundary: Boundary, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        pending = [make_video(f"vid{n}") for n in range(1, 4)]
        self.write_index_file(config, pending)

        assert run(config, Namespace()) == 0
        assert len(boundary.calls) == 3
        boundary.calls.clear()

        assert run(config, Namespace()) == 0
        assert boundary.calls == [], "R2: a rerun never refetches what is cached"


class TestVideoFetch:
    """The boundary's return type: captions as before, description beside them."""

    def test_it_carries_both_fields_and_compares_by_value(self) -> None:
        assert VideoFetch(
            captions=SIMPLE_VTT, description=DESCRIPTION, caption_format=VTT
        ) == VideoFetch(captions=SIMPLE_VTT, description=DESCRIPTION, caption_format=VTT)

    def test_the_field_order_is_captions_then_description(self) -> None:
        # Positional construction is part of the declared signature.
        positional = VideoFetch(SIMPLE_VTT, DESCRIPTION, VTT)

        assert positional.captions == SIMPLE_VTT
        assert positional.description == DESCRIPTION

    def test_it_is_frozen(self) -> None:
        fetched = VideoFetch(captions=SIMPLE_VTT, description=DESCRIPTION, caption_format=VTT)

        with pytest.raises(FrozenInstanceError):
            fetched.description = "rewritten"  # type: ignore[misc]

    def test_captions_may_be_none_and_description_still_stands(self) -> None:
        # The no-caption case: R1004 hands the video to the failure ledger, but
        # the boundary has still read a description and says so honestly.
        fetched = VideoFetch(captions=None, description=DESCRIPTION, caption_format=VTT)

        assert fetched.captions is None
        assert fetched.description == DESCRIPTION


class TestTranscriptDescriptionField:
    def test_the_field_defaults_to_empty_so_old_constructions_still_compile(self) -> None:
        transcript = Transcript(video_id="vid1", cues=())

        assert transcript.description == ""

    def test_it_is_the_last_field_and_takes_a_positional(self) -> None:
        transcript = Transcript("vid1", (Cue(start_seconds=1.0, text="hi"),), "notes")

        assert transcript.description == "notes"

    def test_two_transcripts_differing_only_in_description_are_not_equal(self) -> None:
        assert Transcript(
            video_id="vid1",
            cues=(),
            description="a",
            source_format=VTT,
        ) != Transcript(
            video_id="vid1",
            cues=(),
            description="b",
            source_format=VTT,
        )


class TestFetchTranscriptDescription:
    def test_the_description_rides_along_with_the_cues(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": FIXTURE.read_text()})
        boundary.set_descriptions({"vid1": DESCRIPTION})

        transcript = fetch_transcript(make_video("vid1"), config)

        assert transcript == Transcript(
            video_id="vid1",
            cues=EXPECTED_CUES,
            description=DESCRIPTION,
            source_format=VTT,
        )

    def test_one_boundary_call_produces_both(self, boundary: Boundary, tmp_path: Path) -> None:
        """OD-8's whole answer to BL-11's cost objection: no second request."""
        config = make_config(tmp_path)
        boundary.set_descriptions({"vid1": DESCRIPTION})

        transcript = fetch_transcript(make_video("vid1"), config)

        assert boundary.calls == ["vid1"], "the description must cost no extra fetch"
        assert transcript.cues != ()
        assert transcript.description == DESCRIPTION

    def test_no_description_is_the_empty_string_not_a_failure(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        transcript = fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert transcript.description == ""

    def test_the_description_is_taken_verbatim(self, boundary: Boundary, tmp_path: Path) -> None:
        # No stripping, no truncation, no parsing of hashtags or links: whatever
        # normalization matching needs is matching's business, one stage later.
        raw = "  \n\n#B850   #ITX\nhttps://example.com/a-very-long-affiliate-link?x=1\n  "
        boundary.set_descriptions({"vid1": raw})

        transcript = fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert transcript.description == raw

    def test_no_captions_still_raises_even_with_a_description(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        """R1004: a description cannot conjure a transcript."""
        boundary.always_none()
        boundary.set_descriptions({"vid1": DESCRIPTION})

        with pytest.raises(NoCaptions):
            fetch_transcript(make_video("vid1"), make_config(tmp_path))

    def test_a_fetch_error_still_propagates_even_with_a_description(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        error = RuntimeError("HTTP 429 from YouTube")
        boundary.always_raise(error)
        boundary.set_descriptions({"vid1": DESCRIPTION})

        with pytest.raises(RuntimeError) as caught:
            fetch_transcript(make_video("vid1"), make_config(tmp_path))

        assert caught.value is error


class TestDescriptionInTheCache:
    def test_it_is_written_and_read_back(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": SIMPLE_VTT})
        boundary.set_descriptions({"vid1": DESCRIPTION})

        fetch_all([make_video("vid1")], config, make_ledger(config, 1))

        assert load_cached("vid1", config) == Transcript(
            video_id="vid1",
            cues=(Cue(start_seconds=2.0, text="hello there"),),
            description=DESCRIPTION,
            source_format=VTT,
        )

    def test_each_video_keeps_its_own(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        boundary.set_map({"vid1": SIMPLE_VTT, "vid2": SIMPLE_VTT})
        boundary.set_descriptions({"vid1": DESCRIPTION, "vid2": "a different one"})

        fetch_all([make_video("vid1"), make_video("vid2")], config, make_ledger(config, 2))

        first = load_cached("vid1", config)
        second = load_cached("vid2", config)
        assert first is not None and second is not None
        assert first.description == DESCRIPTION
        assert second.description == "a different one"

    def test_the_record_gains_exactly_one_key(self, boundary: Boundary, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        boundary.set_descriptions({"vid1": DESCRIPTION})

        fetch_all([make_video("vid1")], config, make_ledger(config, 1))

        record = json.loads(cache_path("vid1", config).read_text())
        # R1013 adds `source_format`. The set stays EXACT rather than being
        # widened to a subset check — that is the assertion that catches a
        # stray key, and relaxing it to accommodate one addition would retire
        # it.
        assert set(record) == {"video_id", "cues", "description", "source_format"}
        assert record["description"] == DESCRIPTION

    def test_the_file_is_still_deterministic_json_with_one_trailing_newline(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        """R23: two runs over the same video produce byte-identical files."""
        first = make_config(tmp_path / "one")
        second = make_config(tmp_path / "two")
        boundary.set_map({"vid1": FIXTURE.read_text()})
        boundary.set_descriptions({"vid1": DESCRIPTION})

        fetch_all([make_video("vid1")], first, make_ledger(first, 1))
        boundary.set_map({"vid1": FIXTURE.read_text()})
        fetch_all([make_video("vid1")], second, make_ledger(second, 1))

        text = cache_path("vid1", first).read_text()
        assert text == cache_path("vid1", second).read_text()
        assert text.endswith("\n")
        assert not text.endswith("\n\n")
        assert text == json.dumps(json.loads(text), sort_keys=True) + "\n"

    def test_an_empty_description_is_still_written_as_a_key(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        # A key that appears only when it fired cannot be told from one that
        # never ran, and the shape on disk should not vary per video.
        config = make_config(tmp_path)

        fetch_all([make_video("vid1")], config, make_ledger(config, 1))

        assert json.loads(cache_path("vid1", config).read_text())["description"] == ""

    def test_a_video_with_no_captions_caches_nothing_however_long_its_description(
        self, boundary: Boundary, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, missing_caption_rate_limit=0.9)
        boundary.always_none()
        boundary.set_descriptions({"vid1": DESCRIPTION})
        # A corpus large enough that one missing track cannot trip R24's rate.
        ledger = make_ledger(config, 100)

        assert fetch_all([make_video("vid1")], config, ledger) == 0

        assert not cache_path("vid1", config).exists()
        assert [failure.failure_class for failure in ledger.failures()] == ["no_captions"]


class TestLoadCachedWithoutADescription:
    """The single most important behaviour in the slice.

    Every cache entry the owner already has was written before this field
    existed. `load_cached` catches `KeyError` and reads it as "no usable cache
    entry", so a strict read would silently invalidate the whole corpus and
    refetch it — the exact opposite of R1004's "no forced refetch".
    """

    def write_legacy_record(self, video_id: str, config: Config) -> Path:
        """A cache file in the pre-slice shape: `video_id` and `cues`, nothing else."""
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

    def test_a_record_with_no_description_key_still_loads_with_its_cues(
        self, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)
        self.write_legacy_record("old1", config)

        loaded = load_cached("old1", config)

        assert loaded == Transcript(
            video_id="old1",
            cues=(Cue(start_seconds=1.5, text="first"), Cue(start_seconds=9.0, text="second")),
            description="",
            source_format=UNKNOWN_FORMAT,
        )

    def test_it_is_not_read_as_an_unusable_entry(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        self.write_legacy_record("old1", config)

        assert load_cached("old1", config) is not None, (
            "a pre-slice cache entry must not read as absent: that refetches the whole corpus"
        )

    def test_fetch_all_still_skips_it(self, boundary: Boundary, tmp_path: Path) -> None:
        """Nothing backfills — the cache-hit skip is what R1004 relies on."""
        config = make_config(tmp_path)
        path = self.write_legacy_record("old1", config)
        before = path.read_bytes()
        boundary.set_descriptions({"old1": DESCRIPTION})

        fetched = fetch_all([make_video("old1")], config, make_ledger(config, 1))

        assert fetched == 0
        assert boundary.calls == [], "an old entry must never be refetched to acquire a description"
        assert path.read_bytes() == before

    def test_a_non_string_description_is_coerced_rather_than_rejected(self, tmp_path: Path) -> None:
        # `video_id` is already read through `str`; a number here is a damaged
        # record, not a reason to throw the cues away.
        config = make_config(tmp_path)
        path = cache_path("odd1", config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"cues": [], "description": 850, "video_id": "odd1"}, sort_keys=True) + "\n"
        )

        loaded = load_cached("odd1", config)

        assert loaded is not None
        assert loaded.description == "850"

    def test_a_null_description_loads_as_a_string(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        path = cache_path("null1", config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"cues": [{"start_seconds": 1.0, "text": "kept"}], "video_id": "null1"}
                | {"description": None},
                sort_keys=True,
            )
            + "\n"
        )

        loaded = load_cached("null1", config)

        assert loaded is not None, "a null description is not a reason to lose the cues"
        assert loaded.cues == (Cue(start_seconds=1.0, text="kept"),)
        assert isinstance(loaded.description, str)
