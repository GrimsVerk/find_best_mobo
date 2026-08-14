"""Tests for slice 2's failure ledger — the record of what could not be fetched.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel. Nothing here is faked: the ledger is
pure bookkeeping over a file, so these tests exercise the real thing against a
real `tmp_path`.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-2 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.config import Config
from find_best_mobo.ledger import HaltTriggered, Ledger
from find_best_mobo.transcripts import FetchFailure


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


def make_failure(
    video_id: str,
    *,
    failure_class: str = "fetch_error",
    detail: str = "HTTP 503 from YouTube",
    attempts: int = 1,
    title: str | None = None,
    upload_date: date = date(2023, 6, 15),
) -> FetchFailure:
    return FetchFailure(
        video_id=video_id,
        title=title if title is not None else f"{video_id} VRM breakdown",
        upload_date=upload_date,
        failure_class=failure_class,
        detail=detail if failure_class == "fetch_error" else "",
        attempts=attempts,
    )


def open_ledger(
    tmp_path: Path,
    *,
    indexed_count: int = 100,
    consecutive_fetch_error_limit: int = 3,
    fetch_error_rate_limit: float = 0.03,
    missing_caption_rate_limit: float = 0.05,
) -> Ledger:
    """A ledger over the conventional path inside `tmp_path`."""
    config = make_config(
        tmp_path,
        consecutive_fetch_error_limit=consecutive_fetch_error_limit,
        fetch_error_rate_limit=fetch_error_rate_limit,
        missing_caption_rate_limit=missing_caption_rate_limit,
    )
    return Ledger(ledger_path(tmp_path), config, indexed_count)


def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "failures.jsonl"


def records_on_disk(tmp_path: Path) -> list[dict[str, object]]:
    text = ledger_path(tmp_path).read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class TestEmptyLedger:
    def test_starts_with_nothing_recorded(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path)

        assert ledger.failures() == ()
        assert ledger.failed_ids() == frozenset()
        assert ledger.check_triggers() is None

    def test_failed_ids_is_a_frozenset(self, tmp_path: Path) -> None:
        assert isinstance(open_ledger(tmp_path).failed_ids(), frozenset)


class TestRecording:
    def test_failures_are_returned_in_the_order_recorded(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, fetch_error_rate_limit=0.9)
        ledger.record(make_failure("zzz"))
        ledger.record(make_failure("aaa", failure_class="no_captions"))
        ledger.record(make_failure("mmm"))

        assert [failure.video_id for failure in ledger.failures()] == ["zzz", "aaa", "mmm"]
        assert isinstance(ledger.failures(), tuple)

    def test_the_file_is_written_on_every_record_not_at_the_end(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path)

        ledger.record(make_failure("vid1"))
        assert [record["video_id"] for record in records_on_disk(tmp_path)] == ["vid1"]

        ledger.record(make_failure("vid2"))
        assert [record["video_id"] for record in records_on_disk(tmp_path)] == ["vid1", "vid2"]

    def test_a_record_carries_every_declared_field(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path)

        ledger.record(
            make_failure(
                "vid1", detail="HTTP 429", title="X670E rant", upload_date=date(2024, 2, 3)
            )
        )

        record = records_on_disk(tmp_path)[0]
        assert record == {
            "video_id": "vid1",
            "title": "X670E rant",
            "upload_date": "2024-02-03",
            "failure_class": "fetch_error",
            "detail": "HTTP 429",
            "attempts": 1,
        }

    def test_keys_are_sorted_on_disk(self, tmp_path: Path) -> None:
        # R23: deterministic output means sort_keys=True, not insertion order.
        ledger = open_ledger(tmp_path)
        ledger.record(make_failure("vid1"))

        line = ledger_path(tmp_path).read_text().splitlines()[0]
        keys = json.loads(line, object_pairs_hook=lambda pairs: [key for key, _ in pairs])

        assert keys == sorted(keys)

    def test_same_records_give_byte_identical_files(self, tmp_path: Path) -> None:
        for name in ("one", "two"):
            directory = tmp_path / name
            directory.mkdir()
            ledger = Ledger(ledger_path(directory), make_config(directory), 100)
            ledger.record(make_failure("vid1"))
            ledger.record(make_failure("vid2", failure_class="no_captions"))

        content = ledger_path(tmp_path / "one").read_bytes()
        assert content
        assert content == ledger_path(tmp_path / "two").read_bytes()


class TestAcrossRuns:
    def test_failed_ids_come_from_the_previous_run(self, tmp_path: Path) -> None:
        first = open_ledger(tmp_path, fetch_error_rate_limit=0.9)
        first.record(make_failure("vid1"))
        first.record(make_failure("vid2", failure_class="no_captions"))

        second = open_ledger(tmp_path, fetch_error_rate_limit=0.9)

        assert second.failed_ids() == frozenset({"vid1", "vid2"})
        assert second.failures() == (), "a new run starts with an empty failure list"

    def test_failed_ids_do_not_change_as_this_run_records(self, tmp_path: Path) -> None:
        first = open_ledger(tmp_path)
        first.record(make_failure("vid1"))

        second = open_ledger(tmp_path)
        second.record(make_failure("vid9"))

        assert second.failed_ids() == frozenset({"vid1"})

    def test_attempts_increment_for_a_video_that_fails_twice(self, tmp_path: Path) -> None:
        first = open_ledger(tmp_path)
        first.record(make_failure("vid1"))
        assert first.failures()[0].attempts == 1
        assert records_on_disk(tmp_path)[0]["attempts"] == 1

        second = open_ledger(tmp_path)
        second.record(make_failure("vid1"))

        assert second.failures()[0].attempts == 2
        assert records_on_disk(tmp_path)[0]["attempts"] == 2

        third = open_ledger(tmp_path)
        third.record(make_failure("vid1"))

        assert third.failures()[0].attempts == 3

    def test_a_video_that_has_not_failed_before_starts_at_one(self, tmp_path: Path) -> None:
        first = open_ledger(tmp_path)
        first.record(make_failure("vid1"))

        second = open_ledger(tmp_path)
        second.record(make_failure("brandNew"))

        assert second.failures()[0].attempts == 1

    def test_a_video_that_succeeds_this_run_drops_out_of_the_file(self, tmp_path: Path) -> None:
        first = open_ledger(tmp_path, fetch_error_rate_limit=0.9)
        first.record(make_failure("vid1"))
        first.record(make_failure("vid2"))
        assert {record["video_id"] for record in records_on_disk(tmp_path)} == {"vid1", "vid2"}

        # This run retries both: vid1 succeeds, vid2 fails again.
        second = open_ledger(tmp_path, fetch_error_rate_limit=0.9)
        second.record_success()
        second.record(make_failure("vid2"))

        assert [record["video_id"] for record in records_on_disk(tmp_path)] == ["vid2"]
        assert [failure.video_id for failure in second.failures()] == ["vid2"]
        assert records_on_disk(tmp_path)[0]["attempts"] == 2


class TestConsecutiveFetchErrorTrigger:
    def test_does_not_fire_one_below_the_limit(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=1000, consecutive_fetch_error_limit=3)
        ledger.record(make_failure("vid1"))
        ledger.record(make_failure("vid2"))

        assert ledger.check_triggers() is None

    def test_fires_at_the_limit(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=1000, consecutive_fetch_error_limit=3)
        for name in ("vid1", "vid2", "vid3"):
            ledger.record(make_failure(name))

        assert ledger.check_triggers() == "consecutive_fetch_errors"

    def test_the_limit_comes_from_config(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=1000, consecutive_fetch_error_limit=2)
        ledger.record(make_failure("vid1"))
        assert ledger.check_triggers() is None

        ledger.record(make_failure("vid2"))

        assert ledger.check_triggers() == "consecutive_fetch_errors"

    def test_a_success_resets_the_counter(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=1000, consecutive_fetch_error_limit=3)
        ledger.record(make_failure("vid1"))
        ledger.record(make_failure("vid2"))
        ledger.record_success()
        ledger.record(make_failure("vid3"))

        assert ledger.check_triggers() is None

    def test_a_no_captions_record_resets_the_counter(self, tmp_path: Path) -> None:
        # A definitive "this video has no captions" proves the network works,
        # so it breaks the run of fetch errors just as a success does.
        ledger = open_ledger(
            tmp_path,
            indexed_count=1000,
            consecutive_fetch_error_limit=3,
            missing_caption_rate_limit=0.9,
        )
        ledger.record(make_failure("vid1"))
        ledger.record(make_failure("vid2"))
        ledger.record(make_failure("gap", failure_class="no_captions"))
        ledger.record(make_failure("vid3"))

        assert ledger.check_triggers() is None

    def test_the_counter_resumes_after_a_reset(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=1000, consecutive_fetch_error_limit=3)
        ledger.record(make_failure("vid1"))
        ledger.record_success()
        for name in ("vid2", "vid3", "vid4"):
            ledger.record(make_failure(name))

        assert ledger.check_triggers() == "consecutive_fetch_errors"


class TestRateTriggers:
    def test_fetch_error_rate_does_not_fire_exactly_at_the_limit(self, tmp_path: Path) -> None:
        # Strictly greater: 3/100 == 0.03 is not above a 0.03 limit.
        ledger = open_ledger(
            tmp_path,
            indexed_count=100,
            consecutive_fetch_error_limit=1000,
            fetch_error_rate_limit=0.03,
        )
        for index in range(3):
            ledger.record(make_failure(f"vid{index}"))

        assert ledger.check_triggers() is None

    def test_fetch_error_rate_fires_above_the_limit(self, tmp_path: Path) -> None:
        ledger = open_ledger(
            tmp_path,
            indexed_count=100,
            consecutive_fetch_error_limit=1000,
            fetch_error_rate_limit=0.03,
        )
        for index in range(4):
            ledger.record(make_failure(f"vid{index}"))

        assert ledger.check_triggers() == "fetch_error_rate"

    def test_missing_caption_rate_does_not_fire_exactly_at_the_limit(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=100, missing_caption_rate_limit=0.05)
        for index in range(5):
            ledger.record(make_failure(f"vid{index}", failure_class="no_captions"))

        assert ledger.check_triggers() is None

    def test_missing_caption_rate_fires_above_the_limit(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=100, missing_caption_rate_limit=0.05)
        for index in range(6):
            ledger.record(make_failure(f"vid{index}", failure_class="no_captions"))

        assert ledger.check_triggers() == "missing_caption_rate"

    def test_the_two_rates_are_counted_separately(self, tmp_path: Path) -> None:
        # Five no-captions and three fetch errors: neither class is over its own
        # limit, even though eight failures out of a hundred would be over both.
        ledger = open_ledger(
            tmp_path,
            indexed_count=100,
            consecutive_fetch_error_limit=1000,
            fetch_error_rate_limit=0.03,
            missing_caption_rate_limit=0.05,
        )
        for index in range(5):
            ledger.record(make_failure(f"gap{index}", failure_class="no_captions"))
        for index in range(3):
            ledger.record(make_failure(f"vid{index}"))

        assert ledger.check_triggers() is None

    def test_zero_indexed_count_never_fires_a_rate_trigger(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=0, consecutive_fetch_error_limit=1000)
        for index in range(20):
            ledger.record(make_failure(f"vid{index}"))
            ledger.record(make_failure(f"gap{index}", failure_class="no_captions"))

        assert ledger.check_triggers() is None

    def test_the_consecutive_trigger_is_checked_first(self, tmp_path: Path) -> None:
        # Both would fire; the contract fixes the order they are checked in, so
        # the owner is told about the network before the rate.
        ledger = open_ledger(
            tmp_path, indexed_count=10, consecutive_fetch_error_limit=3, fetch_error_rate_limit=0.03
        )
        for index in range(4):
            ledger.record(make_failure(f"vid{index}"))

        assert ledger.check_triggers() == "consecutive_fetch_errors"

    def test_check_triggers_does_not_consume_the_state(self, tmp_path: Path) -> None:
        ledger = open_ledger(tmp_path, indexed_count=1000, consecutive_fetch_error_limit=2)
        ledger.record(make_failure("vid1"))
        ledger.record(make_failure("vid2"))

        assert ledger.check_triggers() == "consecutive_fetch_errors"
        assert ledger.check_triggers() == "consecutive_fetch_errors"


class TestHaltTriggered:
    def test_carries_the_trigger_and_the_ledger_it_halted_on(self) -> None:
        failures = (make_failure("vid1"), make_failure("vid2"))

        error = HaltTriggered("fetch_error_rate", failures)

        assert error.trigger == "fetch_error_rate"
        assert tuple(error.ledger) == failures
        assert isinstance(error, Exception), "a halt must be raisable"

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(HaltTriggered) as caught:
            raise HaltTriggered("missing_caption_rate", ())

        assert caught.value.trigger == "missing_caption_rate"
