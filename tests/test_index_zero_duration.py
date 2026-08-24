"""Tests for the zero-duration report in the ``index`` command's summary.

Written blind from ``docs/plans/oracle/zero-duration-listing-shape.md`` (both
slices) while the implementation is authored in parallel, so failures are the
expected state until assembly.

**The rule that used to be tested here, and why it is gone.** The original
slice-1 addendum ruled that a missing duration reads as 0, classifies the video
as a Short and drops it, and that exactly one such video is benign — he can
only be live in one place at a time — so the command warned loudly once the
*count* of zero-duration videos exceeded one. BL-15 measured that premise
false on the first real index run after the ``timestamp`` fix: eight videos
reported no duration, the banner fired, and all eight were genuine Shorts. The
flat listing returns a Short with no ``duration`` field and no date in either
field, so the count threshold is a permanent false positive — and, worse, a
ninth id with a real date would be invisible inside a list of eight expected
ones. **OD-14 retired the count threshold** and added **R1009**: the judgement
is on the evidence in each entry, never on how many entries lack a duration.

The rule under test (R1009):

- no duration and no date in either listing field (``upload_date``,
  ``timestamp``) is the flat listing's Shorts shape — it classifies exactly as
  it did before and is reported as a one-line count, with no banner;
- a real date and no duration is the silent-drop shape — the banner fires for
  one such entry, and names each affected video id;
- both count lines print on every run, including as zero;
- classification is untouched either way: a dated, durationless video is still
  excluded as a Short. The banner makes the drop visible; it does not undo it.

The only surface faked here is ``list_channel_entries``, patched where
``find_best_mobo.index`` uses it, because that module imports the name directly.
"""

from __future__ import annotations

import re
from argparse import Namespace
from collections.abc import Iterator, Sequence
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.commands.index import ZeroDuration, classify_zero_duration, run
from find_best_mobo.config import Config
from find_best_mobo.index import Video, classify, read_index

START_DATE = date(2023, 1, 1)

# The banner's own marker, matched instead of its wording: OD-14 rewrites the
# message (its old text claimed only one video may legitimately lack a
# duration, which is the premise that was retired), so a test pinned to the
# prose would fail on a correct implementation. What R1009 promises is that a
# loud warning is there, or is not.
BANNER_MARKER = re.compile(r"warn|!!!", re.IGNORECASE)

# Both count lines are about durations; the expected-Shorts one is the one
# R1009 quotes ("N Shorts reported no duration (expected)").
DURATION_MARKER = re.compile(r"duration", re.IGNORECASE)
EXPECTED_MARKER = re.compile(r"expected", re.IGNORECASE)


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
    """A raw entry in the shape yt-dlp yields from a full per-video extraction.

    It carries a real ``upload_date``. With no duration, that is R1009's
    silent-drop shape.
    """
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


def shorts_entry(video_id: str, title: str = "") -> dict[str, object]:
    """A raw entry in the flat listing's Shorts shape, as BL-15 measured it.

    No ``duration`` key, no ``upload_date`` key, no ``timestamp`` key. That is
    how the flat channel listing returns a Short, so it recurs on every run —
    which is why R1009 calls it expected rather than anomalous.
    """
    return {
        "id": video_id,
        "title": title or f"Short {video_id}",
        "was_live": False,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


# Videos with a real, non-zero duration, so the four pre-existing summary
# numbers are unambiguous: 1 kept, 1 out of range, 1 genuine Short.
BACKDROP: list[dict[str, object]] = [
    entry("keptVideo01", "20240310", 3600),
    entry("oldVideo002", "20220601", 2400),
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

    import find_best_mobo.commands.index as command_module
    import find_best_mobo.index as index_module
    import find_best_mobo.ytdlp as ytdlp_boundary

    monkeypatch.setattr(ytdlp_boundary, "list_channel_entries", fake_list_channel_entries)
    for module in (index_module, command_module):
        if hasattr(module, "list_channel_entries"):
            monkeypatch.setattr(module, "list_channel_entries", fake_list_channel_entries)

    config = make_config(tmp_path / "data")
    return run(config, Namespace()), config


def output(capsys: pytest.CaptureFixture[str]) -> str:
    """Everything the run printed, on either stream.

    The banner's stream is not something R1009 fixes, so both are searched
    rather than assuming stdout.
    """
    captured = capsys.readouterr()
    return captured.out + captured.err


def visible_lines(out: str) -> list[str]:
    """Output lines with the index path stripped off the header.

    The header ends in a ``tmp_path`` built from the test's own name, so it is
    truncated before anything searches the output for a marker.
    """
    return [line.split("; index written to ")[0] for line in out.splitlines()]


def banner_start(lines: Sequence[str]) -> int | None:
    for number, line in enumerate(lines):
        if BANNER_MARKER.search(line):
            return number
    return None


def summary_block(out: str) -> list[str]:
    """The calm summary: everything before the banner, if there is one."""
    lines = visible_lines(out)
    start = banner_start(lines)
    return lines if start is None else lines[:start]


def assert_no_banner(out: str) -> None:
    lines = visible_lines(out)
    assert banner_start(lines) is None, f"banner fired but nothing anomalous: {out!r}"


def banner_text(out: str) -> str:
    """Everything from the banner's first line onwards."""
    lines = visible_lines(out)
    start = banner_start(lines)
    assert start is not None, f"no banner in output: {out!r}"
    return "\n".join(lines[start:])


def expected_shorts_line(out: str) -> str:
    """The "N Shorts reported no duration (expected)" line."""
    matches = [
        line
        for line in summary_block(out)
        if DURATION_MARKER.search(line) and EXPECTED_MARKER.search(line)
    ]
    assert len(matches) == 1, f"expected exactly one expected-Shorts count line: {out!r}"
    return matches[0]


def anomaly_count_line(out: str) -> str:
    """The count line for dated, durationless entries — the anomaly's own line."""
    matches = [
        line
        for line in summary_block(out)
        if DURATION_MARKER.search(line) and not EXPECTED_MARKER.search(line)
    ]
    assert len(matches) == 1, f"expected exactly one anomaly count line: {out!r}"
    return matches[0]


def assert_reports(out: str, *, expected_shorts: int, anomalies: int) -> None:
    """Both counts print on every run, including as zero."""
    shorts_line = expected_shorts_line(out)
    assert re.search(rf"\b{expected_shorts}\b", shorts_line), (
        f"expected-Shorts line omits the count {expected_shorts}: {shorts_line!r}"
    )
    assert re.search(r"shorts", shorts_line, re.IGNORECASE), (
        f"expected-Shorts line never says Shorts: {shorts_line!r}"
    )
    anomaly_line = anomaly_count_line(out)
    assert re.search(rf"\b{anomalies}\b", anomaly_line), (
        f"anomaly line omits the count {anomalies}: {anomaly_line!r}"
    )


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


def set_attribute(target: object, name: str, value: object) -> None:
    """Assign an attribute by name, for the frozen-dataclass check below."""
    setattr(target, name, value)


def make_video(
    video_id: str,
    upload_date: date,
    duration_seconds: int,
    *,
    inclusion: str = "excluded_short",
    classification: str = "short",
) -> Video:
    return Video(
        video_id=video_id,
        title=f"Title of {video_id}",
        upload_date=upload_date,
        duration_seconds=duration_seconds,
        was_live=False,
        classification=classification,
        inclusion=inclusion,
    )


class TestZeroDurationContract:
    """``ZeroDuration`` and ``classify_zero_duration`` as the plan declares them."""

    def test_zero_duration_is_a_frozen_dataclass_of_two_id_tuples(self) -> None:
        result = ZeroDuration(expected_shorts=("aaa",), anomalies=("bbb",))
        with pytest.raises(FrozenInstanceError):
            # Through a helper so the assignment stays legal under mypy once
            # the frozen dataclass exists; the runtime behaviour is the point.
            set_attribute(result, "anomalies", ())

        # Asserted after the construction above: narrowing ZeroDuration to a
        # DataclassInstance makes calling it a type error.
        assert is_dataclass(ZeroDuration)
        assert [field.name for field in fields(ZeroDuration)] == ["expected_shorts", "anomalies"]

    def test_empty_input_reports_both_shapes_as_empty(self) -> None:
        result = classify_zero_duration([])

        assert result == ZeroDuration(expected_shorts=(), anomalies=())
        assert isinstance(result.expected_shorts, tuple)
        assert isinstance(result.anomalies, tuple)

    def test_only_zero_duration_videos_enter_either_tuple(self) -> None:
        # A video with a duration is neither shape, whatever its date — and a
        # dateless one with a real duration is already excluded out of range
        # by classify and is not this rule's business.
        videos = [
            make_video("hasDurat001", date(2024, 3, 10), 3600, inclusion="pending"),
            make_video("hasDurat002", date(2024, 5, 1), 45),
            make_video(
                "noDateDur03",
                date.min,
                2100,
                inclusion="excluded_out_of_range",
                classification="regular",
            ),
        ]

        assert classify_zero_duration(videos) == ZeroDuration(expected_shorts=(), anomalies=())

    def test_the_split_is_the_sentinel_date(self) -> None:
        # date.min is what classify records when neither upload_date nor
        # timestamp parsed, so it is exactly "no date in either listing field".
        videos = [
            make_video("dateless001", date.min, 0),
            make_video("dated000001", date(2025, 1, 2), 0),
        ]

        result = classify_zero_duration(videos)

        assert result.expected_shorts == ("dateless001",)
        assert result.anomalies == ("dated000001",)

    def test_ids_sort_the_way_write_index_sorts(self) -> None:
        # Upload date, then video id — so an id printed here is findable in
        # index.jsonl at the position it was printed in. Input order below is
        # neither of the two sorted orders.
        videos = [
            make_video("zzzShort001", date.min, 0),
            make_video("bbbAnom0002", date(2025, 6, 1), 0),
            make_video("aaaShort003", date.min, 0),
            make_video("aaaAnom0004", date(2026, 1, 1), 0),
            make_video("cccAnom0005", date(2025, 6, 1), 0),
        ]

        result = classify_zero_duration(videos)

        assert result.expected_shorts == ("aaaShort003", "zzzShort001")
        # 2025-06-01 before 2026-01-01, and within the shared date by id.
        assert result.anomalies == ("bbbAnom0002", "cccAnom0005", "aaaAnom0004")

    @pytest.mark.parametrize(
        ("label", "raw"),
        [
            ("no duration key", shorts_entry("sh0rtVid001")),
            ("null duration", {**shorts_entry("sh0rtVid001"), "duration": None}),
            ("explicit zero", {**shorts_entry("sh0rtVid001"), "duration": 0}),
        ],
    )
    def test_every_way_a_dateless_zero_arrives_is_the_expected_shape(
        self, tmp_path: Path, label: str, raw: dict[str, object]
    ) -> None:
        video = classify(raw, make_config(tmp_path / "data"))

        assert classify_zero_duration([video]) == ZeroDuration(
            expected_shorts=("sh0rtVid001",), anomalies=()
        ), label

    @pytest.mark.parametrize(
        ("label", "raw"),
        [
            ("no duration key", entry("dr0ppedVid1", "20250102", omit_duration=True)),
            ("null duration", entry("dr0ppedVid1", "20250102", None)),
            ("explicit zero", entry("dr0ppedVid1", "20250102", 0)),
        ],
    )
    def test_every_way_a_dated_zero_arrives_is_the_anomaly(
        self, tmp_path: Path, label: str, raw: dict[str, object]
    ) -> None:
        video = classify(raw, make_config(tmp_path / "data"))

        assert classify_zero_duration([video]) == ZeroDuration(
            expected_shorts=(), anomalies=("dr0ppedVid1",)
        ), label


class TestBothCountsAlwaysPrint:
    def test_both_lines_print_as_zero_when_every_video_has_a_duration(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(monkeypatch, tmp_path, list(BACKDROP))
        out = output(capsys)

        assert code == 0
        # A number present on every run is comparable across runs; a signal
        # with nowhere to appear was BL-15's second cost.
        assert_reports(out, expected_shorts=0, anomalies=0)
        assert_no_banner(out)
        assert_summary_block(out, config, total=3, out_of_range=1, shorts=1, kept=1)


class TestTheDistinguishingPair:
    """R1009's pinned pair: dateless does not trip the warning, dated does."""

    def test_a_dateless_durationless_entry_does_not_trip_the_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, shorts_entry("sh0rtVid004")])
        out = output(capsys)

        assert code == 0
        assert_reports(out, expected_shorts=1, anomalies=0)
        assert_no_banner(out)
        # The expected Short counts toward the Shorts total as well: the new
        # line reports it in addition, it does not remove it.
        assert_summary_block(out, config, total=4, out_of_range=1, shorts=2, kept=1)

    def test_a_dated_durationless_entry_does_trip_the_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # ONE anomaly fires it. Under the retired rule a single zero-duration
        # video was benign, which is exactly how a silent drop stayed silent.
        dropped = entry("dr0ppedVid1", "20250102", omit_duration=True)
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, dropped])
        out = output(capsys)

        assert code == 0
        assert_reports(out, expected_shorts=0, anomalies=1)
        assert "dr0ppedVid1" in banner_text(out), out
        assert_summary_block(out, config, total=4, out_of_range=1, shorts=2, kept=1)


class TestManyExpectedShortsStayQuiet:
    def test_no_count_threshold_anywhere(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The retired rule warned once the count exceeded one, so five of the
        # listing's own Shorts shape used to shout. R1009 judges the shape.
        shorts = [shorts_entry(f"sh0rtVid{number:03d}") for number in range(5)]
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, *shorts])
        out = output(capsys)

        assert code == 0
        assert_reports(out, expected_shorts=5, anomalies=0)
        assert_no_banner(out)
        assert_summary_block(out, config, total=8, out_of_range=1, shorts=6, kept=1)


class TestBanner:
    """What the banner says about the entries that carry a real date."""

    # Input order differs from the index order (upload date, then video id),
    # so a banner echoing the listing order would be caught.
    ANOMALIES: list[dict[str, object]] = [
        entry("zzz99nodur1", "20230303", 0),
        entry("aaa11nodur2", "20240701", None),
        entry("mmm55nodur3", "20230303", omit_duration=True),
    ]
    IDS_IN_INDEX_ORDER = ["mmm55nodur3", "zzz99nodur1", "aaa11nodur2"]
    IDS_IN_INPUT_ORDER = [str(item["id"]) for item in ANOMALIES]

    def test_fixture_orders_differ(self) -> None:
        # Guards the ordering test below against being silently trivial.
        assert self.IDS_IN_INPUT_ORDER != self.IDS_IN_INDEX_ORDER

    def test_every_anomalous_id_is_named_in_index_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [*BACKDROP, *(dict(item) for item in self.ANOMALIES)]
        _, config = run_index(monkeypatch, tmp_path, entries)
        out = output(capsys)

        assert_reports(out, expected_shorts=0, anomalies=3)
        banner = banner_text(out)
        for video_id in self.IDS_IN_INDEX_ORDER:
            assert video_id in banner, f"banner omits {video_id}: {banner!r}"

        positions = [banner.index(video_id) for video_id in self.IDS_IN_INDEX_ORDER]
        assert positions == sorted(positions), (
            f"ids not listed in index order {self.IDS_IN_INDEX_ORDER}: {banner!r}"
        )

        # The same order the records are written to the index in.
        written = [video.video_id for video in read_index(config.data_dir / "index.jsonl")]
        assert [
            video_id for video_id in written if video_id in self.IDS_IN_INPUT_ORDER
        ] == self.IDS_IN_INDEX_ORDER

    def test_the_banner_names_the_anomalies_and_not_the_expected_shorts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        shorts = [shorts_entry(f"sh0rtVid{number:03d}") for number in range(4)]
        entries = [*BACKDROP, *shorts, dict(self.ANOMALIES[1])]
        code, _ = run_index(monkeypatch, tmp_path, entries)
        out = output(capsys)

        assert code == 0
        assert_reports(out, expected_shorts=4, anomalies=1)
        banner = banner_text(out)
        assert "aaa11nodur2" in banner, banner
        for number in range(4):
            assert f"sh0rtVid{number:03d}" not in banner, (
                f"banner names an expected Short: {banner!r}"
            )

    def test_the_banner_comes_after_the_summary_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entries = [*BACKDROP, *(dict(item) for item in self.ANOMALIES)]
        run_index(monkeypatch, tmp_path, entries)
        out = output(capsys)
        lines = visible_lines(out)

        start = banner_start(lines)
        assert start is not None
        assert start > lines.index("  1 kept")
        assert start > lines.index(anomaly_count_line(out))
        assert start > lines.index(expected_shorts_line(out))


class TestClassificationIsUntouched:
    """The banner reports; it never changes what the index says.

    Pinned so a later "fix" cannot answer the warning by keeping the video:
    OD-14 rejected reclassifying anything, and R1009 changes only what is
    reported. A dated, durationless video is still excluded as a Short — the
    banner is what makes that drop visible, which is the entire point.
    """

    def test_a_dated_zero_duration_video_is_still_an_excluded_short(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        dropped = entry("dr0ppedVid1", "20250102", omit_duration=True)
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, dropped])
        out = output(capsys)

        assert code == 0
        assert banner_text(out)

        records = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}
        anomaly = records["dr0ppedVid1"]
        assert anomaly.duration_seconds == 0
        assert anomaly.classification == "short"
        assert anomaly.inclusion == "excluded_short"
        assert anomaly.upload_date == date(2025, 1, 2)

        kept = [video for video in records.values() if video.inclusion == "pending"]
        assert [video.video_id for video in kept] == ["keptVideo01"]

    def test_a_dateless_zero_duration_video_classifies_exactly_as_before(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _, config = run_index(monkeypatch, tmp_path, [*BACKDROP, shorts_entry("sh0rtVid004")])
        output(capsys)

        records = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}
        short = records["sh0rtVid004"]
        assert short.duration_seconds == 0
        assert short.classification == "short"
        assert short.inclusion == "excluded_short"
        assert short.upload_date == date.min


# ---------------------------------------------------------------------------
# Slice 2 — BL-15's measured run, pinned as the shape that must stay quiet.
# ---------------------------------------------------------------------------

# The eight video ids BL-15 read out of data/index.jsonl on the first real
# index run after the `timestamp` fix (PR #67) landed, with the titles it
# recorded, as provenance. Every one is a genuine Short; every one carried no
# duration and no date in either listing field, and all eight were recorded
# `excluded_short`, which BL-15 confirms is where they belong.
#
# Nothing asserts on the titles: the rule turns on the listing shape, not on
# wording. They are here because they are what was measured.
BL15_MEASURED_SHORTS: tuple[tuple[str, str], ...] = (
    ("0pgWWFCvf6w", "simple and effective DDR5 cooling"),
    ("FUCLMRq5oOM", "motherboard collection: ASUS WS Z390 PRO #motherboard"),
    ("OffiCcQMK-4", "Adding a POST code display to the Gigabyte B850M Force"),
    ("PB1iPWcibbw", "stock MSI 3060Ti Gaming X vcore regulation. #Shorts"),
    ("T94q9a4JZiI", "Buildzoid's collection: Gigabyte B850M Force"),
    ("qd3flkh_eg0", "My first LN2 overclocking motherboard"),
    ("rNMZqqg1NI4", "VRM cooling upgrade for an itx motherboard #overclocking"),
    ("wEFp9Eo-QZ4", "Buildzoid's motherboard collection: ASRock 970M Pro3"),
)
BL15_IDS = [video_id for video_id, _ in BL15_MEASURED_SHORTS]

# The ninth id BL-15 argues would have been invisible: a real upload date and
# no duration, which is a genuine video being silently dropped.
NINTH_ID = "s1lentDrop9"


def bl15_entries() -> list[dict[str, object]]:
    """The eight, reproduced as listing entries in the shape that was measured.

    No ``duration`` key, no ``upload_date`` key, no ``timestamp`` key,
    ``was_live`` false — BL-15's measured shape rather than its captions.
    """
    return [shorts_entry(video_id, title) for video_id, title in BL15_MEASURED_SHORTS]


class TestBL15Regression:
    """The measured run: eight Shorts, one banner, and the ninth id it hid.

    Fails on the retired count-threshold rule (eight is more than one, so the
    72-character banner fired on every run) and passes on R1009's shape rule.
    """

    def test_the_measured_ids_are_all_distinct(self) -> None:
        # Guards the "not named in the banner" assertions below.
        assert len(set(BL15_IDS)) == len(BL15_IDS)
        assert NINTH_ID not in BL15_IDS

    def test_the_eight_are_the_expected_shorts_shape(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        videos = [classify(raw, config) for raw in bl15_entries()]

        result = classify_zero_duration(videos)

        assert len(result.expected_shorts) == 8
        assert set(result.expected_shorts) == set(BL15_IDS)
        assert result.anomalies == ()
        # date.min for all eight, so the index order is the id order.
        assert list(result.expected_shorts) == sorted(BL15_IDS)

    def test_the_eight_report_a_count_and_fire_no_banner(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, config = run_index(monkeypatch, tmp_path, [*BACKDROP, *bl15_entries()])
        out = output(capsys)

        assert code == 0
        assert_reports(out, expected_shorts=8, anomalies=0)
        assert_no_banner(out)
        # 11 found = 1 kept + 9 Shorts (the eight plus the real one) + 1 out
        # of range.
        assert_summary_block(out, config, total=11, out_of_range=1, shorts=9, kept=1)

    def test_the_eight_are_still_excluded_shorts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # BL-15's own conclusion: the outcome was right, only the alarm was
        # wrong. Demoting the banner to a count must not move any of them.
        _, config = run_index(monkeypatch, tmp_path, [*BACKDROP, *bl15_entries()])
        output(capsys)

        records = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}
        for video_id in BL15_IDS:
            assert records[video_id].duration_seconds == 0
            assert records[video_id].classification == "short"
            assert records[video_id].inclusion == "excluded_short"
            assert records[video_id].was_live is False

    def test_a_ninth_dated_entry_is_named_and_the_eight_are_not(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The silent drop the old rule could not surface: a ninth id inside a
        # list of eight expected ones was invisible, and under the threshold
        # rule the banner's text was identical either way.
        ninth = entry(NINTH_ID, "20250310", omit_duration=True)
        entries = [*BACKDROP, *bl15_entries(), ninth]
        code, config = run_index(monkeypatch, tmp_path, entries)
        out = output(capsys)

        assert code == 0
        assert_reports(out, expected_shorts=8, anomalies=1)

        banner = banner_text(out)
        assert NINTH_ID in banner, f"banner omits the dropped video: {banner!r}"
        for video_id in BL15_IDS:
            assert video_id not in banner, f"banner names the expected Short {video_id}: {banner!r}"

        assert_summary_block(out, config, total=12, out_of_range=1, shorts=10, kept=1)

        # And it is still dropped: the banner makes that visible, not undone.
        records = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}
        assert records[NINTH_ID].inclusion == "excluded_short"

    def test_the_ninth_is_visible_through_classify_zero_duration_too(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        raw = [*bl15_entries(), entry(NINTH_ID, "20250310", omit_duration=True)]
        videos = [classify(item, config) for item in raw]

        result = classify_zero_duration(videos)

        assert result.anomalies == (NINTH_ID,)
        assert len(result.expected_shorts) == 8
