"""The index tells the flat listing's Shorts shape from a silent drop (OD-14, R1009).

**This module was rewritten on 2026-08-24, and the old rule is why.** It used to
assert that a zero-duration count above ONE triggers a loud banner, on the
reasoning that only one video can legitimately lack a duration — a stream in
progress, and he can only be live in one place at a time. BL-15 measured that
premise false on the first real run after the `timestamp` fix: **eight** videos
reported no duration and all eight were genuine Shorts, so the banner is a
permanent false positive and a ninth id inside a list of eight expected ones is
invisible. OD-14 replaced the count test with an evidence test, and these tests
follow the rule rather than the other way round.

The rule now: an entry with no duration AND no date in either listing field
(`upload_date`, `timestamp`) is the flat listing's Shorts shape — counted on one
line, no banner. An entry with a real date and no duration is a video being
silently dropped — banner, at any count, naming each id.

The only surface faked here is ``list_channel_entries``, patched where
``find_best_mobo.index`` uses it, because that module imports the name directly.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.commands.index import ZeroDuration, classify_zero_duration, run
from find_best_mobo.config import Config
from find_best_mobo.index import Video, read_index

START_DATE = date(2023, 1, 1)


def make_config(data_dir: Path) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=START_DATE,
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
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


def entry(
    video_id: str,
    upload_date: str,
    duration: int | None = 3600,
    *,
    omit_duration: bool = False,
) -> dict[str, object]:
    """A raw entry in the shape yt-dlp yields from a flat channel listing."""
    record: dict[str, object] = {
        "id": video_id,
        "title": f"Board rant {video_id}",
        "duration": duration,
        "upload_date": upload_date,
        "was_live": False,
        "live_status": "not_live",
    }
    if omit_duration:
        del record["duration"]
    return record


def shorts_shape(video_id: str, title: str = "clip") -> dict[str, object]:
    """The flat listing's Shorts shape, exactly as BL-15 measured it.

    No `duration` key, no `upload_date` key and no `timestamp` key. All three
    absences matter: `classify` reads `upload_date` then `timestamp`, so an
    entry missing both records `date.min`, and that is what marks the entry as
    the listing's Shorts shape rather than an anomaly.
    """
    return {
        "id": video_id,
        "title": title,
        "was_live": False,
        "live_status": "not_live",
    }


def dated_no_duration(video_id: str, upload_date: str = "20240715") -> dict[str, object]:
    """The silent-drop shape: a real upload date, and no duration at all.

    Its duration reads as 0, so it classifies as a Short and is excluded — but
    it is not the listing's Shorts shape, so something else zeroed it and a real
    video is leaving the corpus. This is the case the banner was written for.
    """
    return entry(video_id, upload_date, omit_duration=True)


# Videos with a real, non-zero duration. Counts chosen so the summary numbers
# are unambiguous: 1 kept, 1 out of range, 1 genuine Short.
BACKDROP: list[dict[str, object]] = [
    entry("keptVideo01", "20240310", 3600),
    entry("oldVideo002", "20220601", 2400),
    entry("shortVid003", "20240501", 45),
]

# BL-15's eight, measured on the 2026-08-20 local-lane run against the real
# channel. The ids and titles are the real ones and are recorded as provenance;
# nothing asserts on the titles, because the rule turns on the listing SHAPE and
# not on wording. Every one of these was a genuine Short — two say so in their
# own hashtags, the rest are the short-form collection clips.
BL15_MEASURED: list[dict[str, object]] = [
    shorts_shape("0pgWWFCvf6w", "simple and effective DDR5 cooling"),
    shorts_shape("FUCLMRq5oOM", "motherboard collection: ASUS WS Z390 PRO #motherboard"),
    shorts_shape("OffiCcQMK-4", "Adding a POST code display to the Gigabyte B850M Force"),
    shorts_shape("PB1iPWcibbw", "stock MSI 3060Ti Gaming X vcore regulation. #Shorts"),
    shorts_shape("T94q9a4JZiI", "Buildzoid's collection: Gigabyte B850M Force"),
    shorts_shape("qd3flkh_eg0", "My first LN2 overclocking motherboard"),
    shorts_shape("rNMZqqg1NI4", "VRM cooling upgrade for an itx motherboard #overclocking"),
    shorts_shape("wEFp9Eo-QZ4", "Buildzoid's collection: ASRock 970M Pro3"),
]


def run_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    entries: list[dict[str, object]],
) -> tuple[int, Config]:
    """Run the command over ``entries`` with the network boundary faked."""

    def fake_list_channel_entries(
        channel_url: str, start_date: date
    ) -> Iterator[dict[str, object]]:
        yield from (dict(item) for item in entries)

    import find_best_mobo.index as index_module
    import find_best_mobo.ytdlp as ytdlp_boundary

    monkeypatch.setattr(ytdlp_boundary, "list_channel_entries", fake_list_channel_entries)
    monkeypatch.setattr(index_module, "list_channel_entries", fake_list_channel_entries)

    config = make_config(tmp_path / "data")
    return run(config, Namespace()), config


def summary(capsys: pytest.CaptureFixture[str]) -> str:
    return capsys.readouterr().out


def assert_summary_block(
    out: str,
    config: Config,
    *,
    total: int,
    out_of_range: int,
    shorts: int,
    kept: int,
) -> None:
    """The four pre-existing lines, unchanged in wording and order."""
    index_path = config.data_dir / "index.jsonl"
    lines = out.splitlines()
    header = f"Found {total} videos on the channel; index written to {index_path}"
    assert header in lines, out

    positions = [lines.index(header)]
    for line in (
        f"  {out_of_range} outside the date range",
        f"  {shorts} excluded as Shorts",
        f"  {kept} kept",
    ):
        assert line in lines, out
        positions.append(lines.index(line))
    assert positions == sorted(positions), f"summary lines out of order: {out!r}"


def assert_no_warning(out: str) -> None:
    """No banner anywhere in the output.

    Asserted on the banner's own marker rather than on the whole text, so
    rewording the message does not fail the test. The header line ends in a
    ``tmp_path`` built from the test's own name, so it is truncated first.
    """
    body = "\n".join(line.split("; index written to ")[0] for line in out.splitlines())
    assert "!" * 72 not in body, out
    assert "WARNING" not in body, out


def warning_text(out: str) -> str:
    """Everything from the first WARNING line onwards."""
    lines = out.splitlines()
    for number, line in enumerate(lines):
        if "WARNING" in line:
            return "\n".join(lines[number:])
    raise AssertionError(f"no WARNING line in output: {out!r}")


class TestClassifyZeroDuration:
    """The split itself, as a function, on the evidence in each entry."""

    def test_a_dateless_durationless_video_is_the_shorts_shape(self) -> None:
        video = Video(
            video_id="clip",
            title="clip",
            upload_date=date.min,
            duration_seconds=0,
            was_live=False,
            classification="short",
            inclusion="excluded_short",
        )

        assert classify_zero_duration([video]) == ZeroDuration(("clip",), ())

    def test_a_dated_durationless_video_is_an_anomaly(self) -> None:
        video = Video(
            video_id="dropped",
            title="dropped",
            upload_date=date(2024, 7, 15),
            duration_seconds=0,
            was_live=False,
            classification="short",
            inclusion="excluded_short",
        )

        assert classify_zero_duration([video]) == ZeroDuration((), ("dropped",))

    def test_a_video_with_a_duration_is_neither_shape(self) -> None:
        """Whatever its date. A dateless entry with a real duration is out of range."""
        videos = [
            Video("real", "t", date(2024, 1, 1), 3600, False, "regular", "pending"),
            Video("dateless", "t", date.min, 3600, False, "regular", "excluded_out_of_range"),
        ]

        assert classify_zero_duration(videos) == ZeroDuration((), ())

    def test_ids_sort_the_way_the_index_file_sorts(self) -> None:
        """So an id printed here is findable in index.jsonl at the position printed."""
        videos = [
            Video("zzz", "t", date.min, 0, False, "short", "excluded_short"),
            Video("aaa", "t", date.min, 0, False, "short", "excluded_short"),
            Video("later", "t", date(2025, 1, 1), 0, False, "short", "excluded_short"),
            Video("earlier", "t", date(2024, 1, 1), 0, False, "short", "excluded_short"),
        ]

        result = classify_zero_duration(videos)

        assert result.expected_shorts == ("aaa", "zzz")
        assert result.anomalies == ("earlier", "later")


class TestTheDistinguishingPair:
    """R1009 names this pair explicitly, and it is what tells the two cases apart."""

    def test_a_dateless_durationless_entry_does_not_trip_the_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, shorts_shape("clip000001")])
        out = summary(capsys)

        assert code == 0
        assert "  1 Shorts reported no duration (expected)" in out.splitlines(), out
        assert_no_warning(out)
        assert_summary_block(out, config, total=4, out_of_range=1, shorts=2, kept=1)

    def test_a_dated_durationless_entry_does_trip_the_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """ONE is enough. The old rule needed two, which is the rule OD-14 retired."""
        code, _ = run_index(monkeypatch, tmp_path, [*BACKDROP, dated_no_duration("dr0pped0001")])
        out = summary(capsys)

        assert code == 0
        assert "  1 dated videos reported no duration" in out.splitlines(), out
        assert "dr0pped0001" in warning_text(out)


class TestBL15Regression:
    """The measured run, pinned. This is what the old rule got wrong every time."""

    def test_bl15s_eight_produce_a_count_and_no_banner(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Eight entries, eight false alarms per run, every run. Now silent."""
        code, _ = run_index(monkeypatch, tmp_path, [*BACKDROP, *BL15_MEASURED])
        out = summary(capsys)

        assert code == 0
        assert "  8 Shorts reported no duration (expected)" in out.splitlines(), out
        assert "  0 dated videos reported no duration" in out.splitlines(), out
        assert_no_warning(out)

    def test_a_ninth_dated_entry_is_visible_among_the_eight(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """BL-15's second cost, undone.

        Under the old rule the eight already tripped the banner, so a ninth id
        appeared inside a list the operator had learned to ignore. It is now the
        only id named.
        """
        entries = [*BACKDROP, *BL15_MEASURED, dated_no_duration("dr0pped0001")]

        code, _ = run_index(monkeypatch, tmp_path, entries)
        out = summary(capsys)

        assert code == 0
        assert "  8 Shorts reported no duration (expected)" in out.splitlines(), out
        assert "  1 dated videos reported no duration" in out.splitlines(), out
        banner = warning_text(out)
        assert "dr0pped0001" in banner
        for measured in BL15_MEASURED:
            video_id = str(measured["id"])
            assert video_id not in banner, f"{video_id} should not be named"

    def test_the_eight_are_still_classified_and_recorded_exactly_as_before(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R1009 changes what is REPORTED. Classification is untouched (OD-14)."""
        _, config = run_index(monkeypatch, tmp_path, [*BACKDROP, *BL15_MEASURED])
        capsys.readouterr()

        by_id = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}

        for measured in BL15_MEASURED:
            video = by_id[str(measured["id"])]
            assert video.inclusion == "excluded_short"
            assert video.upload_date == date.min

    def test_a_dated_zero_duration_video_is_still_excluded_as_a_short(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The banner makes the drop visible; it does not undo it (OD-14)."""
        _, config = run_index(monkeypatch, tmp_path, [*BACKDROP, dated_no_duration("dr0pped0001")])
        capsys.readouterr()

        by_id = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}

        assert by_id["dr0pped0001"].inclusion == "excluded_short"


class TestTheCountsAlwaysPrint:
    """A number present on every run is comparable across runs (R1009)."""

    def test_both_lines_print_as_zero_when_nothing_lacks_a_duration(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(monkeypatch, tmp_path, list(BACKDROP))
        out = summary(capsys)

        assert code == 0
        assert "  0 Shorts reported no duration (expected)" in out.splitlines(), out
        assert "  0 dated videos reported no duration" in out.splitlines(), out
        assert_no_warning(out)
        assert_summary_block(out, config, total=3, out_of_range=1, shorts=1, kept=1)

    def test_the_warning_comes_after_the_summary_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(
            monkeypatch, tmp_path, [*BACKDROP, dated_no_duration("dr0pped0001")]
        )
        out = summary(capsys)

        assert code == 0
        lines = out.splitlines()
        assert lines.index("  0 Shorts reported no duration (expected)") < next(
            number for number, line in enumerate(lines) if "WARNING" in line
        )
