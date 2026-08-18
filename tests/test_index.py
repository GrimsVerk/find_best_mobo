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


# Stable markers for the zero-duration ruling. The ruling promises that the
# count is reported and that two or more warn loudly with the ids named — it
# says nothing about what the summary calls them. Matching the ruling's own
# phrase ("zero duration") pinned prose the plan never promised, and failed
# against a summary that reports the same fact as "N with no duration
# reported". Match the subject instead, and let the assertions below carry the
# behaviour: the count, the ids, and the presence or absence of a warning.
ZERO_DURATION_MARKER = re.compile(r"duration", re.IGNORECASE)
WARNING_MARKER = re.compile(r"warn", re.IGNORECASE)


class TestZeroDurationReporting:
    """Owner's ruling (plan amendment): at most one zero duration is benign.

    A missing duration reads as 0 and excludes the video as a Short. Exactly
    one such video is explained — a stream in progress reports no duration,
    and he can only be live in one place at a time. Two or more mean the zero
    has some other cause and videos are being dropped silently, so the summary
    must always report the zero-duration count and warn loudly, naming the
    affected video ids, when it exceeds one.
    """

    @pytest.fixture
    def channel_entries(self, request: pytest.FixtureRequest) -> list[dict[str, object]]:
        """Override the module fixture: a listing with N zero-duration entries.

        The parameter is the number of zero-duration entries. Both ways a zero
        can arrive — a null duration and a literal 0 — are represented, since
        the ruling counts videos that "report a zero duration" either way.
        """
        zero_count: int = request.param
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
            make_entry(
                id=f"zeroDur{i:04d}",
                title=f"Listing entry {i} with no reported duration",
                duration=None if i % 2 == 0 else 0,
                upload_date="20240701",
            )
            for i in range(zero_count)
        )
        return entries

    @staticmethod
    def _zero_ids(channel_entries: list[dict[str, object]]) -> list[str]:
        return [str(entry["id"]) for entry in channel_entries if not entry["duration"]]

    @staticmethod
    def _zero_duration_report(out: str) -> str:
        lines = [line for line in out.splitlines() if ZERO_DURATION_MARKER.search(line)]
        assert lines, f"summary never reports the zero-duration count: {out!r}"
        return "\n".join(lines)

    @pytest.mark.parametrize("channel_entries", [0, 1], indirect=True)
    def test_counts_of_zero_and_one_are_reported_without_warning(
        self,
        boundary_calls: list[tuple[str, date]],
        channel_entries: list[dict[str, object]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        zero_count = len(self._zero_ids(channel_entries))

        assert run(make_config(tmp_path / "data"), Namespace()) == 0

        captured = capsys.readouterr()
        # The count is reported even when it is 0, on the same line that names
        # the zero-duration concept, so 0 cannot be confused with silence.
        report = self._zero_duration_report(captured.out)
        assert re.search(rf"\b{zero_count}\b", report), (
            f"zero-duration report omits the count {zero_count}: {report!r}"
        )
        # One zero is the live-stream-in-progress case: explained, no warning.
        assert not WARNING_MARKER.search(captured.out + captured.err)

    @pytest.mark.parametrize("channel_entries", [2, 3], indirect=True)
    def test_two_or_more_warn_and_name_the_affected_videos(
        self,
        boundary_calls: list[tuple[str, date]],
        channel_entries: list[dict[str, object]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        zero_ids = self._zero_ids(channel_entries)

        # A warning, not a failure: the ruling changes reporting only.
        assert run(make_config(tmp_path / "data"), Namespace()) == 0

        captured = capsys.readouterr()
        everything = captured.out + captured.err
        report = self._zero_duration_report(captured.out)
        assert re.search(rf"\b{len(zero_ids)}\b", report)
        assert WARNING_MARKER.search(everything), (
            f"no warning for {len(zero_ids)} zero-duration videos: {everything!r}"
        )
        # The ids are what let the cause be chased; the calm summary never
        # prints ids, so their presence is attributable to the warning.
        for video_id in zero_ids:
            assert video_id in everything, f"warning does not name {video_id}: {everything!r}"

    @pytest.mark.parametrize("channel_entries", [2], indirect=True)
    def test_warning_changes_reporting_only_not_classification(
        self,
        boundary_calls: list[tuple[str, date]],
        channel_entries: list[dict[str, object]],
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Guard against a future "fix" that reacts to the warning by keeping
        # the videos: zero-duration videos are still excluded Shorts, and the
        # summary's kept/excluded counts are unchanged by the warning.
        config = make_config(tmp_path / "data")
        assert run(config, Namespace()) == 0

        by_id = {video.video_id: video for video in read_index(config.data_dir / "index.jsonl")}
        assert len(by_id) == 4
        for video_id in self._zero_ids(channel_entries):
            assert by_id[video_id].duration_seconds == 0
            assert by_id[video_id].classification == "short"
            assert by_id[video_id].inclusion == "excluded_short"
        kept = [video for video in by_id.values() if video.inclusion == "pending"]
        assert [video.video_id for video in kept] == ["b0ardLong01"]

        out = capsys.readouterr().out
        # 4 found, 1 kept, 3 Shorts (the real Short plus both zero-duration
        # videos) — all distinct from the zero-duration count of 2.
        for count in (4, 1, 3):
            assert re.search(rf"\b{count}\b", out), f"summary omits the count {count}: {out!r}"
