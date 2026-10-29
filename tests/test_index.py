"""Tests for slice 1 — the channel becomes a video index on disk.

Written blind from the slice spec while the implementation is authored in
parallel, so failing imports are the expected state until assembly. The only
surface faked here is ``list_channel_entries``, the declared network boundary
in ``find_best_mobo.ytdlp``.
"""

from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.cli import main
from find_best_mobo.commands.index import run
from find_best_mobo.config import Config
from find_best_mobo.index import (
    DATE_SLOP_DAYS,
    Video,
    classify,
    effective_start_date,
    enumerate_channel,
    read_index,
    write_index,
)

FIXTURE = Path(__file__).parent / "fixtures" / "channel_entries.json"

# Counts baked into the fixture, all distinct so the summary numbers cannot be
# mistaken for one another: 12 found = 7 kept + 3 Shorts + 2 out-of-range.
# (The null-duration entry counts as a Short: a missing duration is 0, and 0 is
# at-or-under the Shorts ceiling.) The fixture carries both real entry shapes:
# the full per-video extraction shape (upload_date as YYYYMMDD) and the flat
# channel listing shape (no upload_date, epoch seconds in timestamp) — the
# listing shape is the one the first real run received and the original
# fixture lacked, which is how 1215 videos came out excluded while every test
# passed.
FIXTURE_TOTAL = 12
FIXTURE_KEPT = 7
FIXTURE_SHORTS = 3
FIXTURE_OUT_OF_RANGE = 2

START_DATE = date(2023, 1, 1)
# START_DATE minus DATE_SLOP_DAYS (62): the comparison boundary under the
# default config, pinned here as a literal so the tests cannot inherit an
# implementation mistake in the subtraction.
EFFECTIVE_START = date(2022, 10, 31)


def make_config(
    data_dir: Path,
    *,
    start_date: date = START_DATE,
    shorts_max_seconds: int = 120,
) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=start_date,
        data_dir=data_dir,
        shorts_max_seconds=shorts_max_seconds,
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


def make_entry(**overrides: object) -> dict[str, object]:
    """A raw entry in the shape yt-dlp yields from a full per-video extraction.

    This shape carries ``upload_date`` as a ``YYYYMMDD`` string. It is real,
    but it is NOT what a flat channel listing sends — see
    ``make_listing_entry`` for that shape.
    """
    entry: dict[str, object] = {
        "id": "b0ardLong01",
        "title": "X670E Taichi VRM breakdown",
        "duration": 3600,
        "upload_date": "20230615",
        "was_live": False,
        "live_status": "not_live",
    }
    entry.update(overrides)
    return entry


def make_listing_entry(**overrides: object) -> dict[str, object]:
    """A raw entry in the shape a flat channel listing actually yields.

    No ``upload_date`` and no live markers: the date arrives only as
    ``timestamp``, epoch seconds interpreted as UTC. This is the shape the
    first real run received for all 1215 videos, and the shape the original
    fixture never exercised.
    """
    entry: dict[str, object] = {
        "id": "tsInRange08",
        "title": "ASUS Crosshair X870E Hero and Strix X870 ITX Vcore regulation",
        "duration": 5100,
        "timestamp": 1764720000,  # 2025-12-03 00:00:00 UTC
        "url": "https://www.youtube.com/watch?v=tsInRange08",
    }
    entry.update(overrides)
    return entry


class TestClassify:
    """classify() is pure — the owner's rulings live here."""

    def test_regular_video_is_kept_pending(self, tmp_path: Path) -> None:
        video = classify(make_entry(), make_config(tmp_path))

        assert video == Video(
            video_id="b0ardLong01",
            title="X670E Taichi VRM breakdown",
            upload_date=date(2023, 6, 15),
            duration_seconds=3600,
            was_live=False,
            classification="regular",
            inclusion="pending",
        )

    def test_duration_at_shorts_ceiling_is_excluded_short(self, tmp_path: Path) -> None:
        video = classify(make_entry(duration=120), make_config(tmp_path))

        assert video.classification == "short"
        assert video.inclusion == "excluded_short"

    def test_duration_just_over_shorts_ceiling_is_regular(self, tmp_path: Path) -> None:
        video = classify(make_entry(duration=121), make_config(tmp_path))

        assert video.classification == "regular"
        assert video.inclusion == "pending"

    def test_shorts_ceiling_comes_from_config(self, tmp_path: Path) -> None:
        config = make_config(tmp_path, shorts_max_seconds=600)

        video = classify(make_entry(duration=500), config)

        assert video.inclusion == "excluded_short"

    def test_upload_well_before_start_date_is_out_of_range(self, tmp_path: Path) -> None:
        # Well before the slop window, not merely before start_date: the
        # comparison boundary is start_date minus DATE_SLOP_DAYS (see
        # TestSlopBoundary), so a late-2022 date would be kept.
        video = classify(make_entry(upload_date="20220615"), make_config(tmp_path))

        assert video.classification == "regular"
        assert video.inclusion == "excluded_out_of_range"

    def test_upload_on_start_date_is_kept(self, tmp_path: Path) -> None:
        video = classify(make_entry(upload_date="20230101"), make_config(tmp_path))

        assert video.inclusion == "pending"

    def test_start_date_comes_from_config(self, tmp_path: Path) -> None:
        config = make_config(tmp_path, start_date=date(2024, 1, 1))

        video = classify(make_entry(upload_date="20230615"), config)

        assert video.inclusion == "excluded_out_of_range"

    def test_recent_upload_has_no_end_date_exclusion(self, tmp_path: Path) -> None:
        video = classify(make_entry(upload_date="20260401"), make_config(tmp_path))

        assert video.inclusion == "pending"

    def test_livestream_is_kept_and_recorded_faithfully(self, tmp_path: Path) -> None:
        # Owner's ruling (docs/DECISIONS.md): livestreams stay in the corpus.
        # was_live never causes exclusion — getting this wrong silently deletes
        # the most valuable content and nothing downstream would reveal it.
        entry = make_entry(
            id="l1veStream4",
            duration=10800,
            upload_date="20230920",
            was_live=True,
            live_status="was_live",
        )

        video = classify(entry, make_config(tmp_path))

        assert video.was_live is True
        assert video.classification == "regular"
        assert video.inclusion == "pending"

    def test_no_duration_ceiling_on_regular_uploads(self, tmp_path: Path) -> None:
        video = classify(make_entry(duration=11000), make_config(tmp_path))

        assert video.inclusion == "pending"

    def test_short_before_start_date_is_excluded_as_short(self, tmp_path: Path) -> None:
        # Settled contract: duration is checked before date, so the Short
        # classification/inclusion pair wins over out-of-range.
        video = classify(make_entry(duration=45, upload_date="20220601"), make_config(tmp_path))

        assert video.classification == "short"
        assert video.inclusion == "excluded_short"

    @pytest.mark.parametrize("null_style", ["absent", "null"])
    def test_missing_duration_counts_as_zero(self, tmp_path: Path, null_style: str) -> None:
        entry = make_entry(duration=None)
        if null_style == "absent":
            del entry["duration"]

        video = classify(entry, make_config(tmp_path))

        assert video.duration_seconds == 0
        # 0 is at-or-under the Shorts ceiling, so the video is a Short.
        assert video.inclusion == "excluded_short"

    @pytest.mark.parametrize("null_style", ["absent", "null"])
    def test_missing_upload_date_without_timestamp_is_out_of_range(
        self, tmp_path: Path, null_style: str
    ) -> None:
        # make_entry carries no timestamp, so this is the neither-field case:
        # the sentinel date and the out-of-range exclusion, unchanged.
        entry = make_entry(upload_date=None)
        if null_style == "absent":
            del entry["upload_date"]

        video = classify(entry, make_config(tmp_path))

        assert video.upload_date == date.min
        assert video.classification == "regular"
        assert video.inclusion == "excluded_out_of_range"


class TestDateFromTimestamp:
    """The date source contract: prefer upload_date, fall back to timestamp.

    The first real run enumerated 1215 videos and kept none, because classify
    read only upload_date and the flat channel listing sends the date as
    timestamp (epoch seconds, UTC). Video Q6fJWPZMC5M, uploaded 2025-12-03,
    was excluded as out of range. The first test here is the one that would
    have caught that on day one.
    """

    def test_timestamp_only_video_in_range_is_kept(self, tmp_path: Path) -> None:
        # 1764720000 is 2025-12-03 00:00:00 UTC — the spot-check video's date,
        # arriving the only way the listing delivers it.
        video = classify(make_listing_entry(timestamp=1764720000), make_config(tmp_path))

        assert video.inclusion == "pending"
        assert video.classification == "regular"
        assert video.upload_date == date(2025, 12, 3)
        # The listing shape carries no live markers; that must read as not-live.
        assert video.was_live is False

    @pytest.mark.parametrize(
        ("timestamp", "expected"),
        [
            # Just after and just before UTC midnight: a local-time reading in
            # any non-UTC zone lands one of these on the wrong day.
            (1672533000, date(2023, 1, 1)),  # 2023-01-01 00:30:00 UTC
            (1686871800, date(2023, 6, 15)),  # 2023-06-15 23:30:00 UTC
        ],
    )
    def test_timestamp_is_epoch_seconds_read_as_utc(
        self, tmp_path: Path, timestamp: int, expected: date
    ) -> None:
        video = classify(make_listing_entry(timestamp=timestamp), make_config(tmp_path))

        assert video.upload_date == expected

    def test_upload_date_wins_when_both_fields_are_present(self, tmp_path: Path) -> None:
        # A timestamp from 2020 would be excluded; the upload_date must win on
        # both the recorded date and the inclusion decision.
        entry = make_listing_entry(upload_date="20230615", timestamp=1589587200)

        video = classify(entry, make_config(tmp_path))

        assert video.upload_date == date(2023, 6, 15)
        assert video.inclusion == "pending"

    def test_upload_date_wins_even_when_it_excludes(self, tmp_path: Path) -> None:
        # The preference is not "whichever keeps the video": an in-range
        # timestamp does not rescue an out-of-range upload_date.
        entry = make_listing_entry(upload_date="20220615", timestamp=1710547200)

        video = classify(entry, make_config(tmp_path))

        assert video.upload_date == date(2022, 6, 15)
        assert video.inclusion == "excluded_out_of_range"

    @pytest.mark.parametrize("bad_date", ["", "unknown"])
    def test_unparseable_upload_date_falls_back_to_timestamp(
        self, tmp_path: Path, bad_date: str
    ) -> None:
        entry = make_listing_entry(upload_date=bad_date, timestamp=1764720000)

        video = classify(entry, make_config(tmp_path))

        assert video.upload_date == date(2025, 12, 3)
        assert video.inclusion == "pending"

    def test_timestamp_zero_is_the_epoch_not_a_missing_value(self, tmp_path: Path) -> None:
        # 0 is a real instant, 1970-01-01 UTC — falsy, but not absent. It must
        # produce the real epoch date and an ordinary out-of-range exclusion,
        # never the missing-date sentinel.
        video = classify(make_listing_entry(timestamp=0), make_config(tmp_path))

        assert video.upload_date == date(1970, 1, 1)
        assert video.upload_date != date.min
        assert video.inclusion == "excluded_out_of_range"

    @pytest.mark.parametrize("null_style", ["absent", "null"])
    def test_neither_field_present_yields_the_sentinel(
        self, tmp_path: Path, null_style: str
    ) -> None:
        entry = make_listing_entry(timestamp=None)
        entry["upload_date"] = None
        if null_style == "absent":
            del entry["timestamp"]
            del entry["upload_date"]

        video = classify(entry, make_config(tmp_path))

        assert video.upload_date == date.min
        assert video.classification == "regular"
        assert video.inclusion == "excluded_out_of_range"

    def test_short_wins_over_date_on_the_listing_path_too(self, tmp_path: Path) -> None:
        # Duration is still checked before date: an in-range timestamp does not
        # save a Short, on this path any more than on the upload_date path.
        video = classify(make_listing_entry(duration=45), make_config(tmp_path))

        assert video.classification == "short"
        assert video.inclusion == "excluded_short"


class TestSlopBoundary:
    """The comparison moves back by a fixed slop; the recorded date does not.

    Owner's ruling: the listing's timestamps are bucketed to roughly mid-month,
    so the boundary is start_date minus a fixed DATE_SLOP_DAYS = 62 —
    deliberately a constant, not configuration — guaranteeing nothing uploaded
    on or after start_date can be excluded. The price, accepted explicitly, is
    that late-2022 videos ride along as pending.
    """

    def test_date_slop_is_the_owner_fixed_constant(self) -> None:
        assert DATE_SLOP_DAYS == 62

    def test_effective_start_date_moves_back_by_the_slop(self, tmp_path: Path) -> None:
        assert effective_start_date(make_config(tmp_path)) == EFFECTIVE_START

    def test_effective_start_date_follows_the_configured_start(self, tmp_path: Path) -> None:
        config = make_config(tmp_path, start_date=date(2024, 1, 1))

        assert effective_start_date(config) == date(2023, 10, 31)

    def test_december_2022_video_is_kept_under_the_default_config(self, tmp_path: Path) -> None:
        # The owner's accepted trade, not a bug: December 2022 sits inside the
        # slop window, so it is pending — and the recorded date is the real
        # one, not shifted by the slop.
        video = classify(make_entry(upload_date="20221216"), make_config(tmp_path))

        assert video.inclusion == "pending"
        assert video.upload_date == date(2022, 12, 16)

    def test_upload_on_the_effective_start_date_is_kept(self, tmp_path: Path) -> None:
        # Out of range means strictly before the effective start, so the
        # boundary day itself is kept.
        video = classify(make_entry(upload_date="20221031"), make_config(tmp_path))

        assert video.inclusion == "pending"
        assert video.upload_date == EFFECTIVE_START

    def test_upload_just_before_the_effective_start_date_is_excluded(self, tmp_path: Path) -> None:
        video = classify(make_entry(upload_date="20221030"), make_config(tmp_path))

        assert video.inclusion == "excluded_out_of_range"
        assert video.upload_date == date(2022, 10, 30)

    @pytest.mark.parametrize(
        ("timestamp", "expected_inclusion"),
        [
            # 2022-10-31 00:00:00 UTC — first second of the boundary day, kept.
            (1667174400, "pending"),
            # 2022-10-30 23:59:59 UTC — last second before it, excluded.
            (1667174399, "excluded_out_of_range"),
        ],
    )
    def test_boundary_applies_to_the_timestamp_path_too(
        self, tmp_path: Path, timestamp: int, expected_inclusion: str
    ) -> None:
        video = classify(make_listing_entry(timestamp=timestamp), make_config(tmp_path))

        assert video.inclusion == expected_inclusion

    def test_slop_shifts_with_the_configured_start_date(self, tmp_path: Path) -> None:
        # With start_date 2024-01-01 the effective start is 2023-10-31, so a
        # mid-2023 video is out of range even though the default config keeps it.
        config = make_config(tmp_path, start_date=date(2024, 1, 1))

        video = classify(make_entry(upload_date="20230615"), config)

        assert video.inclusion == "excluded_out_of_range"


def sample_videos() -> list[Video]:
    return [
        Video(
            video_id="b0ardLong01",
            title="X670E Taichi VRM breakdown",
            upload_date=date(2023, 6, 15),
            duration_seconds=3600,
            was_live=False,
            classification="regular",
            inclusion="pending",
        ),
        Video(
            video_id="l1veStream4",
            title="B650E memory tuning stream",
            upload_date=date(2023, 9, 20),
            duration_seconds=10800,
            was_live=True,
            classification="regular",
            inclusion="pending",
        ),
        Video(
            video_id="sh0rtVid002",
            title="This VRM heatsink is fake",
            upload_date=date(2024, 5, 1),
            duration_seconds=45,
            was_live=False,
            classification="short",
            inclusion="excluded_short",
        ),
        Video(
            video_id="o1dRange003",
            title="B550 board rant from before the cutoff",
            upload_date=date(2022, 11, 15),
            duration_seconds=2400,
            was_live=False,
            classification="regular",
            inclusion="excluded_out_of_range",
        ),
    ]


class TestIndexFile:
    def test_write_index_returns_count_and_round_trips(self, tmp_path: Path) -> None:
        videos = sample_videos()
        path = tmp_path / "index.jsonl"

        # Handed a plain iterator: the signature promises Iterable, not list.
        assert write_index(iter(videos), path) == 4

        # write_index emits a canonical order — upload date, then video id — so
        # the file is byte-identical no matter what order the channel listing
        # yields its entries (DESIGN R23). The round-trip is lossless, and the
        # order on disk is the canonical one rather than the input's.
        expected = sorted(videos, key=lambda video: (video.upload_date, video.video_id))
        assert list(read_index(path)) == expected
        assert expected != videos, "fixture must not already be in canonical order"

    def test_write_index_empty_round_trips(self, tmp_path: Path) -> None:
        path = tmp_path / "index.jsonl"

        assert write_index([], path) == 0

        assert list(read_index(path)) == []

    def test_index_file_is_jsonl_with_reasons_recorded(self, tmp_path: Path) -> None:
        # DESIGN R1: exclusions are recorded in the index, not implied. Every
        # video — kept or excluded — is one JSON record on its own line, and an
        # excluded record carries its exclusion reason.
        path = tmp_path / "index.jsonl"
        write_index(sample_videos(), path)

        lines = path.read_text().splitlines()

        assert len(lines) == 4
        for line in lines:
            assert isinstance(json.loads(line), dict)
        assert sum("b0ardLong01" in line for line in lines) == 1
        assert sum("excluded_short" in line for line in lines) == 1
        assert sum("excluded_out_of_range" in line for line in lines) == 1

    def test_write_index_is_byte_identical_for_same_input(self, tmp_path: Path) -> None:
        # DESIGN R23: same input, byte-identical output.
        first = tmp_path / "first.jsonl"
        second = tmp_path / "second.jsonl"

        write_index(sample_videos(), first)
        write_index(sample_videos(), second)

        content = first.read_bytes()
        assert content
        assert content == second.read_bytes()


@pytest.fixture
def channel_entries() -> list[dict[str, object]]:
    data: list[dict[str, object]] = json.loads(FIXTURE.read_text())
    assert len(data) == FIXTURE_TOTAL
    return data


@pytest.fixture
def boundary_calls(
    monkeypatch: pytest.MonkeyPatch, channel_entries: list[dict[str, object]]
) -> list[tuple[str, date]]:
    """Fake ``list_channel_entries`` — the one surface a test may fake.

    The function is patched on ``find_best_mobo.ytdlp`` where it is declared,
    and additionally wherever the calling modules bound the same name via
    ``from ... import`` — still the same declared surface, never a level
    deeper. Returns the (channel_url, start_date) argument pairs received.
    """
    calls: list[tuple[str, date]] = []

    def fake_list_channel_entries(
        channel_url: str, start_date: date
    ) -> Iterator[dict[str, object]]:
        calls.append((channel_url, start_date))
        yield from (dict(entry) for entry in channel_entries)

    import find_best_mobo.ytdlp as ytdlp_boundary

    monkeypatch.setattr(ytdlp_boundary, "list_channel_entries", fake_list_channel_entries)

    import find_best_mobo.cli as cli_module
    import find_best_mobo.commands.index as command_module
    import find_best_mobo.index as index_module

    for module in (index_module, command_module, cli_module):
        if hasattr(module, "list_channel_entries"):
            monkeypatch.setattr(module, "list_channel_entries", fake_list_channel_entries)
    return calls


class TestEnumerateChannel:
    def test_classifies_the_whole_listing(
        self, boundary_calls: list[tuple[str, date]], tmp_path: Path
    ) -> None:
        config = make_config(tmp_path)

        videos = list(enumerate_channel(config))

        assert boundary_calls == [(config.channel_url, config.start_date)]
        assert len(videos) == FIXTURE_TOTAL
        by_id = {video.video_id: video for video in videos}
        assert len(by_id) == FIXTURE_TOTAL

        livestream = by_id["l1veStream4"]
        assert livestream.was_live is True
        assert livestream.inclusion == "pending"
        assert by_id["sh0rtVid002"].inclusion == "excluded_short"
        assert by_id["o1dRange003"].inclusion == "excluded_out_of_range"
        assert by_id["startDate06"].inclusion == "pending"

        # The listing-shape entries: dates arriving only as timestamp survive
        # the whole enumerate path, with the real UTC date recorded.
        spot_check = by_id["tsInRange08"]
        assert spot_check.inclusion == "pending"
        assert spot_check.upload_date == date(2025, 12, 3)
        assert by_id["tsDecSlop09"].inclusion == "pending"
        assert by_id["tsTooOld010"].inclusion == "excluded_out_of_range"
        assert by_id["tsShortV011"].inclusion == "excluded_short"
        assert by_id["nullDate012"].inclusion == "pending"

        kept = [video for video in videos if video.inclusion == "pending"]
        assert len(kept) == FIXTURE_KEPT


class TestRunAndCli:
    def test_run_writes_index_creates_data_dir_and_prints_summary(
        self,
        boundary_calls: list[tuple[str, date]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config = make_config(tmp_path / "data")
        assert not config.data_dir.exists()

        # Settled contract: run() works with a Namespace carrying no
        # attributes, creates data_dir, writes data_dir/index.jsonl, prints
        # the summary itself, and returns 0.
        assert run(config, Namespace()) == 0

        index_path = config.data_dir / "index.jsonl"
        assert index_path.is_file()
        lines = index_path.read_text().splitlines()
        assert len(lines) == FIXTURE_TOTAL
        # Settled contract: excluded videos still appear, with their reason.
        assert sum("excluded_short" in line for line in lines) == FIXTURE_SHORTS
        assert sum("excluded_out_of_range" in line for line in lines) == FIXTURE_OUT_OF_RANGE
        assert len(list(read_index(index_path))) == FIXTURE_TOTAL

        out = capsys.readouterr().out
        for count in (FIXTURE_TOTAL, FIXTURE_KEPT, FIXTURE_SHORTS, FIXTURE_OUT_OF_RANGE):
            assert re.search(rf"\b{count}\b", out), f"summary omits the count {count}: {out!r}"

    def _config_toml(self, data_dir: Path) -> str:
        return (
            'channel_url = "https://www.youtube.com/@ActuallyHardcoreOverclocking"\n'
            "start_date = 2023-01-01\n"
            f"data_dir = '{data_dir}'\n"
            "shorts_max_seconds = 120\n"
        )

    def test_main_index_with_explicit_config(
        self,
        boundary_calls: list[tuple[str, date]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config_path = tmp_path / "custom.toml"
        data_dir = tmp_path / "data"
        config_path.write_text(self._config_toml(data_dir))

        # main() takes argv without the program name.
        assert main(["index", "--config", str(config_path)]) == 0

        assert (data_dir / "index.jsonl").is_file()

    def test_main_index_defaults_to_config_toml_in_cwd(
        self,
        boundary_calls: list[tuple[str, date]],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.toml").write_text(self._config_toml(Path("data")))

        assert main(["index"]) == 0

        assert (tmp_path / "data" / "index.jsonl").is_file()


# Stable markers for the zero-duration reporting rule (OD-14, R1009). R1009
# quotes the expected-Shorts line ("N Shorts reported no duration (expected)")
# but fixes nothing about the banner's wording — OD-14 in fact requires that
# wording to change, because the old text asserted the premise it retired. So
# the banner is matched on its own marker and the count lines on their
# subject, and the assertions below carry the behaviour: the two counts, the
# ids, and the presence or absence of the banner.
DURATION_MARKER = re.compile(r"duration", re.IGNORECASE)
EXPECTED_MARKER = re.compile(r"expected", re.IGNORECASE)
BANNER_MARKER = re.compile(r"warn|!!!", re.IGNORECASE)


def make_shorts_listing_entry(video_id: str, title: str) -> dict[str, object]:
    """A raw entry in the flat listing's Shorts shape (BL-15's measurement).

    No ``duration`` key, no ``upload_date`` key and no ``timestamp`` key: this
    is how the flat channel listing returns a Short, which is why R1009 reads
    it as expected rather than anomalous. Distinct from ``make_entry`` and
    ``make_listing_entry``, which both carry a date.
    """
    return {
        "id": video_id,
        "title": title,
        "was_live": False,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


class TestZeroDurationReporting:
    """R1009: the summary judges each entry's evidence, never the count.

    **The rule this class used to hold, and why it is gone.** The owner's
    plan amendment ruled that at most one zero duration is benign — a stream
    in progress reports none, and he can only be live in one place at a time —
    so the summary warned loudly, naming the ids, once the *count* exceeded
    one. BL-15 measured that premise false on the first real run after the
    ``timestamp`` fix: eight videos reported no duration and every one was a
    genuine Short, because a flat listing returns Shorts with no ``duration``
    field and no date in either field. OD-14 retired the threshold: it is a
    permanent false positive, and it hid the very case the warning existed
    for, since a ninth id with a real date would be invisible in a list of
    eight expected ones.

    What replaces it: a dateless, durationless entry is the expected Shorts
    shape and reports as a count with no banner, at any count; an entry with a
    real date and no duration is the silent-drop shape and fires the banner,
    at a count of one. Both counts print on every run, including as zero.
    """

    @pytest.fixture
    def channel_entries(self, request: pytest.FixtureRequest) -> list[dict[str, object]]:
        """Override the module fixture: (expected Shorts, anomalies) entries.

        The parameter is a pair of counts. The expected-Shorts entries carry
        no duration and no date in either listing field; the anomalies carry a
        real ``upload_date`` and no duration, arriving both ways a zero can —
        an absent key and a literal 0 — since the record cannot tell them
        apart once ``classify`` has read it.
        """
        expected_count, anomaly_count = request.param
        entries = [
            make_entry(),
            make_entry(
                id="sh0rtVid002",
                title="This VRM heatsink is fake",
                duration=45,
                upload_date="20240501",
            ),
        ]
        entries.extend(
            make_shorts_listing_entry(f"listShort{i:02d}", f"Listing Short {i}")
            for i in range(expected_count)
        )
        for i in range(anomaly_count):
            anomaly = make_entry(
                id=f"dr0pped{i:04d}",
                title=f"Dated entry {i} with no reported duration",
                upload_date="20240701",
            )
            if i % 2 == 0:
                del anomaly["duration"]
            else:
                anomaly["duration"] = 0
            entries.append(anomaly)
        return entries

    @staticmethod
    def _expected_ids(channel_entries: list[dict[str, object]]) -> list[str]:
        return [
            str(entry["id"])
            for entry in channel_entries
            if not entry.get("duration") and not entry.get("upload_date")
        ]

    @staticmethod
    def _anomaly_ids(channel_entries: list[dict[str, object]]) -> list[str]:
        return [
            str(entry["id"])
            for entry in channel_entries
            if not entry.get("duration") and entry.get("upload_date")
        ]

    @staticmethod
    def _visible(text: str) -> str:
        """Printed output with the index path stripped off the header line.

        The header ends in a ``tmp_path`` named after the running test, so it
        is truncated before anything searches the output for a marker.
        """
        return "\n".join(line.split("; index written to ")[0] for line in text.splitlines())

    @classmethod
    def _calm_lines(cls, text: str) -> list[str]:
        """The summary lines, up to the banner if one fired."""
        lines = cls._visible(text).splitlines()
        for number, line in enumerate(lines):
            if BANNER_MARKER.search(line):
                return lines[:number]
        return lines

    @classmethod
    def _count_lines(cls, text: str) -> tuple[str, str]:
        """The expected-Shorts count line and the anomaly count line."""
        duration_lines = [line for line in cls._calm_lines(text) if DURATION_MARKER.search(line)]
        expected = [line for line in duration_lines if EXPECTED_MARKER.search(line)]
        anomalies = [line for line in duration_lines if not EXPECTED_MARKER.search(line)]
        assert len(expected) == 1, f"no single expected-Shorts count line: {duration_lines!r}"
        assert len(anomalies) == 1, f"no single anomaly count line: {duration_lines!r}"
        return expected[0], anomalies[0]

    @classmethod
    def _assert_counts(cls, text: str, *, expected: int, anomalies: int) -> None:
        expected_line, anomaly_line = cls._count_lines(text)
        assert re.search(rf"\b{expected}\b", expected_line), (
            f"expected-Shorts line omits the count {expected}: {expected_line!r}"
        )
        assert re.search(r"shorts", expected_line, re.IGNORECASE), (
            f"expected-Shorts line never says Shorts: {expected_line!r}"
        )
        assert re.search(rf"\b{anomalies}\b", anomaly_line), (
            f"anomaly line omits the count {anomalies}: {anomaly_line!r}"
        )

    @pytest.mark.parametrize("channel_entries", [(0, 0), (1, 0), (2, 0), (8, 0)], indirect=True)
    def test_the_listing_shorts_shape_reports_a_count_and_no_banner(
        self,
        boundary_calls: list[tuple[str, date]],
        channel_entries: list[dict[str, object]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        expected_ids = self._expected_ids(channel_entries)

        assert run(make_config(tmp_path / "data"), Namespace()) == 0

        captured = capsys.readouterr()
        everything = self._visible(captured.out + captured.err)
        # Both counts print on every run, so 0 cannot be confused with
        # silence and the numbers stay comparable run to run.
        self._assert_counts(captured.out + captured.err, expected=len(expected_ids), anomalies=0)
        # No threshold anywhere: eight of them are as quiet as one, which is
        # precisely what BL-15 measured and the old rule got wrong.
        assert not BANNER_MARKER.search(everything), f"banner fired for Shorts: {everything!r}"

    @pytest.mark.parametrize("channel_entries", [(0, 1), (3, 2)], indirect=True)
    def test_a_dated_entry_with_no_duration_fires_the_banner_and_is_named(
        self,
        boundary_calls: list[tuple[str, date]],
        channel_entries: list[dict[str, object]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        expected_ids = self._expected_ids(channel_entries)
        anomaly_ids = self._anomaly_ids(channel_entries)

        # A banner, not a failure: R1009 changes reporting only.
        assert run(make_config(tmp_path / "data"), Namespace()) == 0

        captured = capsys.readouterr()
        everything = self._visible(captured.out + captured.err)
        self._assert_counts(everything, expected=len(expected_ids), anomalies=len(anomaly_ids))
        # One is enough — the count of one that the old rule called benign is
        # exactly the silent drop this banner exists to surface.
        assert BANNER_MARKER.search(everything), (
            f"no banner for {len(anomaly_ids)} dated zero-duration videos: {everything!r}"
        )
        # The ids are what let the cause be chased; the calm summary never
        # prints ids, so their presence is attributable to the banner.
        for video_id in anomaly_ids:
            assert video_id in everything, f"banner does not name {video_id}: {everything!r}"
        for video_id in expected_ids:
            assert video_id not in everything, f"an expected Short was named: {everything!r}"

    @pytest.mark.parametrize("channel_entries", [(2, 1)], indirect=True)
    def test_reporting_changes_only_never_classification(
        self,
        boundary_calls: list[tuple[str, date]],
        channel_entries: list[dict[str, object]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Guard against a future "fix" that answers the banner by keeping the
        # video: every zero-duration video is still an excluded Short,
        # whichever shape it has, and the kept/excluded counts are unmoved.
        config = make_config(tmp_path / "data")
        assert run(config, Namespace()) == 0

        by_id = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}
        assert len(by_id) == 5
        for video_id in self._expected_ids(channel_entries) + self._anomaly_ids(channel_entries):
            assert by_id[video_id].duration_seconds == 0
            assert by_id[video_id].classification == "short"
            assert by_id[video_id].inclusion == "excluded_short"
        # The sentinel date is what tells the two shapes apart on the record.
        assert by_id["listShort00"].upload_date == date.min
        assert by_id["dr0pped0000"].upload_date == date(2024, 7, 1)
        kept = [video for video in by_id.values() if video.inclusion == "pending"]
        assert [video.video_id for video in kept] == ["b0ardLong01"]

        out = capsys.readouterr().out
        # 5 found, 1 kept, 4 Shorts (the real Short, both expected ones and
        # the anomaly) — all distinct from the two zero-duration counts.
        for count in (5, 1, 4):
            assert re.search(rf"\b{count}\b", out), f"summary omits the count {count}: {out!r}"
