"""Tests for the zero-duration report in the ``index`` command's summary.

Written blind from the slice-1 addendum in ``docs/plans/corpus-and-checkpoint.md``
while the implementation is authored in parallel, so failures are the expected
state until assembly.

The rule under test: a missing duration is read as 0, which classifies the video
as a Short and drops it. That is acceptable for exactly one video — he can only
be live in one place at a time — so the command always reports the zero-duration
count, and warns loudly, naming the affected ids, once the count exceeds one.

The only surface faked here is ``list_channel_entries``, patched where
``find_best_mobo.index`` uses it, because that module imports the name directly.
"""

from __future__ import annotations

import re
from argparse import Namespace
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.commands.index import run
from find_best_mobo.config import Config
from find_best_mobo.index import read_index

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


# Videos with a real, non-zero duration. Counts chosen so the summary numbers
# are unambiguous: 1 kept, 1 out of range, 1 genuine Short.
BACKDROP: list[dict[str, object]] = [
    entry("keptVideo01", "20240310", 3600),
    entry("oldVideo002", "20221115", 2400),
    entry("shortVid003", "20240501", 45),
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
    """No warning text anywhere in the output.

    The header line ends in a ``tmp_path`` built from the test's own name, so
    it is truncated before the check rather than searched.
    """
    body = "\n".join(line.split("; index written to ")[0] for line in out.splitlines())
    assert "WARNING" not in body, out
    assert "warning" not in body.lower(), out


def warning_text(out: str) -> str:
    """Everything from the first WARNING line onwards."""
    lines = out.splitlines()
    for number, line in enumerate(lines):
        if "WARNING" in line:
            return "\n".join(lines[number:])
    raise AssertionError(f"no WARNING line in output: {out!r}")


class TestZeroDurationCountLine:
    def test_line_is_printed_when_no_video_reports_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(monkeypatch, tmp_path, list(BACKDROP))
        out = summary(capsys)

        assert code == 0
        assert "  0 with no duration reported" in out.splitlines(), out
        assert_summary_block(out, config, total=3, out_of_range=1, shorts=1, kept=1)

    def test_no_warning_when_no_video_reports_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run_index(monkeypatch, tmp_path, list(BACKDROP))

        assert_no_warning(summary(capsys))

    @pytest.mark.parametrize(
        ("label", "zero_entry"),
        [
            ("null", entry("nu11Durat05", "20250102", None)),
            ("absent", entry("nu11Durat05", "20250102", omit_duration=True)),
            ("explicit_zero", entry("nu11Durat05", "20250102", 0)),
        ],
    )
    def test_single_zero_duration_is_counted_but_not_warned_about(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        label: str,
        zero_entry: dict[str, object],
    ) -> None:
        # One zero is expected — a stream in progress reports no duration.
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, dict(zero_entry)])
        out = summary(capsys)

        assert code == 0, label
        assert "  1 with no duration reported" in out.splitlines(), out
        assert_no_warning(out)
        # The zero-duration video counts toward the Shorts total as well: the
        # new line reports it in addition, it does not remove it.
        assert_summary_block(out, config, total=4, out_of_range=1, shorts=2, kept=1)

    def test_zero_duration_video_is_still_indexed_as_an_excluded_short(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        zero = entry("nu11Durat05", "20250102", None)
        _, config = run_index(monkeypatch, tmp_path, [*BACKDROP, zero])
        summary(capsys)

        records = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}

        assert records["nu11Durat05"].duration_seconds == 0
        assert records["nu11Durat05"].inclusion == "excluded_short"


# Three zero-duration entries whose input order differs from the order the
# index is written in (upload date, then video id), so a warning that echoed
# the listing order would be caught.
ZERO_ENTRIES: list[dict[str, object]] = [
    entry("zzz99nodur1", "20230303", 0),
    entry("aaa11nodur2", "20240701", None),
    entry("mmm55nodur3", "20230303", omit_duration=True),
]
ZERO_IDS_IN_INDEX_ORDER = ["mmm55nodur3", "zzz99nodur1", "aaa11nodur2"]
ZERO_IDS_IN_INPUT_ORDER = [str(item["id"]) for item in ZERO_ENTRIES]


def test_fixture_orders_differ() -> None:
    # Guards the ordering test below against being silently trivial.
    assert ZERO_IDS_IN_INPUT_ORDER != ZERO_IDS_IN_INDEX_ORDER


class TestZeroDurationWarning:
    def test_two_zeroes_trigger_a_warning_naming_both(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        zeroes = [dict(item) for item in ZERO_ENTRIES[:2]]
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, *zeroes])
        out = summary(capsys)

        assert code == 0
        assert "  2 with no duration reported" in out.splitlines(), out
        assert_summary_block(out, config, total=5, out_of_range=1, shorts=3, kept=1)

        warning = warning_text(out)
        assert re.search(r"\b2\b", warning), f"warning omits the count: {warning!r}"
        for video_id in ("zzz99nodur1", "aaa11nodur2"):
            assert video_id in warning, f"warning omits {video_id}: {warning!r}"

    def test_three_zeroes_warn_and_leave_the_summary_intact(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [*BACKDROP, *(dict(item) for item in ZERO_ENTRIES)]
        code, config = run_index(monkeypatch, tmp_path, entries)
        out = summary(capsys)

        # The warning is not an error: the exit code is unchanged.
        assert code == 0
        # 6 found = 1 kept + 4 Shorts (3 of them zero-duration) + 1 out of range.
        assert_summary_block(out, config, total=6, out_of_range=1, shorts=4, kept=1)
        assert "  3 with no duration reported" in out.splitlines(), out

        warning = warning_text(out)
        assert re.search(r"\b3\b", warning), f"warning omits the count: {warning!r}"

    def test_warning_comes_after_the_summary_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [*BACKDROP, *(dict(item) for item in ZERO_ENTRIES)]
        run_index(monkeypatch, tmp_path, entries)
        out = summary(capsys)
        lines = out.splitlines()

        warning_line = next(number for number, line in enumerate(lines) if "WARNING" in line)
        count_line = lines.index("  3 with no duration reported")
        kept_line = lines.index("  1 kept")

        assert warning_line > kept_line
        assert warning_line > count_line
        # Distinguishable from the ordinary detail lines, which are indented
        # two spaces and carry no such marker.
        assert "WARNING" not in "\n".join(lines[:warning_line])

    def test_affected_ids_are_listed_in_index_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [*BACKDROP, *(dict(item) for item in ZERO_ENTRIES)]
        _, config = run_index(monkeypatch, tmp_path, entries)
        out = summary(capsys)

        warning = warning_text(out)
        for video_id in ZERO_IDS_IN_INDEX_ORDER:
            assert video_id in warning, f"warning omits {video_id}: {warning!r}"

        positions = [warning.index(video_id) for video_id in ZERO_IDS_IN_INDEX_ORDER]
        assert positions == sorted(positions), (
            f"ids not listed in index order {ZERO_IDS_IN_INDEX_ORDER}: {warning!r}"
        )

        # The same order the records are written to the index in.
        written = [video.video_id for video in read_index(config.data_dir / "index.jsonl")]
        assert [
            video_id for video_id in written if video_id in ZERO_IDS_IN_INPUT_ORDER
        ] == ZERO_IDS_IN_INDEX_ORDER
