"""Tests for Stage B slice 1's claim store — append-only, tagged by batch.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 1) and the
shared contract while the implementation is authored in parallel, so failing
imports are the expected state until assembly.

Nothing here is faked: the store is bookkeeping over a file, so these tests run
the real thing against a real `tmp_path`, exactly as `tests/test_ledger.py`
does. The schema's side of the slice lives in `tests/test_claims.py`.

The store's on-disk FORMAT is deliberately not asserted anywhere — the file is
found through `store_path` and compared with itself. What is asserted is what
R10 and R27 promise about it: earlier bytes are never rewritten, a batch already
stored is refused rather than merged, a file's claims land all together or not
at all, and the same claims produce the same bytes twice (R23).
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-1 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.claims import Claim
from find_best_mobo.claimstore import append_claims, batches_stored, read_claims, store_path
from find_best_mobo.config import Config


def make_config(data_dir: Path) -> Config:
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
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


def make_claim(
    board: str = "ASRock X670E Taichi",
    *,
    batch: int = 1,
    video_id: str = "dQw4w9WgXcQ",
    video_title: str = "X670E VRM breakdown",
    timestamp_seconds: float = 62.25,
    snippet: str = "the VRM is genuinely overbuilt for anything you can socket",
    category: str = "tested",
    subject: str = "vrm_capacity",
    polarity: str = "positive",
) -> Claim:
    return Claim(
        board=board,
        video_id=video_id,
        video_title=video_title,
        timestamp_seconds=timestamp_seconds,
        snippet=snippet,
        category=category,
        subject=subject,
        polarity=polarity,
        batch=batch,
    )


def make_batch(batch: int, count: int = 3) -> tuple[Claim, ...]:
    """`count` distinct claims, all tagged `batch` — one file's worth.

    The board names run DOWNWARDS on purpose, so a store that sorts or
    otherwise reorders what it was handed reads back differently from what went
    in. A file's claims are evidence in the order the agent found them.
    """
    return tuple(
        make_claim(
            f"board-{batch}-{count - index}",
            batch=batch,
            timestamp_seconds=float(index * 30),
            snippet=f"claim {index} of batch {batch}",
        )
        for index in range(count)
    )


def store_bytes(config: Config) -> bytes:
    """What is on disk, or `b""` before anything has been appended."""
    path = store_path(config)
    return path.read_bytes() if path.exists() else b""


def refuse(claims: Sequence[Claim], config: Config, *, why: str) -> Exception:
    """Call `append_claims` where it must refuse, and hand back the refusal.

    The plan names no exception class for a refused re-ingest — only that it is
    refused — so this catches broadly rather than pinning a type the contract
    does not fix. What the tests then assert is the consequence: nothing landed.
    """
    try:
        append_claims(claims, config)
    except Exception as error:
        return error
    pytest.fail(f"append_claims must refuse: {why}")


class UnwritableValue:
    """A value no serializer can write, for probing per-file atomicity.

    `str`, `repr` and `json.dumps` all fail on it, so a store raises partway
    through whichever way it writes a claim out.
    """

    def __str__(self) -> str:
        raise RuntimeError("this claim cannot be serialized")

    def __repr__(self) -> str:
        raise RuntimeError("this claim cannot be serialized")


def poisoned(claim: Claim) -> Claim:
    """`claim` with an unwritable board, bypassing the frozen dataclass."""
    object.__setattr__(claim, "board", UnwritableValue())
    return claim


class TestStorePath:
    def test_lives_under_the_configured_data_dir(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "corpus")

        assert config.data_dir in store_path(config).parents

    def test_is_the_same_path_every_time(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        assert store_path(config) == store_path(config)

    def test_follows_the_data_dir(self, tmp_path: Path) -> None:
        first = make_config(tmp_path / "one")
        second = make_config(tmp_path / "two")

        assert store_path(first) != store_path(second)

    def test_asking_for_the_path_does_not_create_the_store(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "corpus")

        assert not store_path(config).exists()


class TestEmptyStore:
    def test_reads_as_empty_before_anything_is_appended(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "corpus")

        assert list(read_claims(config)) == []

    def test_no_batches_are_stored(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "corpus")

        assert batches_stored(config) == frozenset()

    def test_batches_stored_is_a_frozenset(self, tmp_path: Path) -> None:
        assert isinstance(batches_stored(make_config(tmp_path)), frozenset)


class TestAppending:
    def test_returns_how_many_claims_landed(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        assert append_claims(make_batch(1, count=3), config) == 3

    def test_creates_the_store_and_any_directory_it_needs(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "not" / "yet" / "there")

        append_claims(make_batch(1), config)

        assert store_path(config).is_file()

    def test_every_claim_reads_back_exactly_as_it_went_in(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        claims = make_batch(1, count=4)

        append_claims(claims, config)

        assert tuple(read_claims(config)) == claims

    def test_a_claim_keeps_every_field_across_the_round_trip(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        claim = make_claim(
            "Gigabyte B650 Aorus Elite AX",
            batch=4,
            video_id="9bZkp7q19f0",
            video_title="Two hours on B650 memory training — 中文字幕",
            timestamp_seconds=7384.5,
            snippet='he said "it\'s fine", then walked it back',
            category="warning",
            subject="voltage_firmware_safety",
            polarity="negative",
        )

        append_claims([claim], config)

        assert tuple(read_claims(config)) == (claim,)

    def test_the_batch_tag_survives_the_round_trip(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        append_claims(make_batch(9), config)

        assert {claim.batch for claim in read_claims(config)} == {9}
        assert batches_stored(config) == frozenset({9})

    def test_a_second_batch_lands_after_the_first(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        first = make_batch(1, count=2)
        second = make_batch(2, count=3)

        append_claims(first, config)
        append_claims(second, config)

        assert [claim.batch for claim in read_claims(config)] == [1, 1, 2, 2, 2]
        assert tuple(read_claims(config)) == first + second, "in the order appended"
        assert batches_stored(config) == frozenset({1, 2})

    def test_batches_may_arrive_out_of_order(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)

        append_claims(make_batch(3), config)
        append_claims(make_batch(1), config)

        assert batches_stored(config) == frozenset({1, 3})

    def test_the_store_is_on_disk_not_in_memory(self, tmp_path: Path) -> None:
        # A fresh Config over the same directory — the next run — sees it all.
        append_claims(make_batch(1, count=2), make_config(tmp_path))

        later = make_config(tmp_path)

        assert len(list(read_claims(later))) == 2
        assert batches_stored(later) == frozenset({1})

    def test_reading_twice_gives_the_same_claims(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=3), config)

        assert tuple(read_claims(config)) == tuple(read_claims(config))


class TestAppendOnly:
    def test_a_later_batch_does_not_rewrite_the_bytes_already_stored(self, tmp_path: Path) -> None:
        # R10 and R27 together: work already paid for is never rewritten, so
        # what is on disk after batch 2 begins with what was there after batch 1.
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=2), config)
        before = store_bytes(config)

        append_claims(make_batch(2, count=2), config)

        after = store_bytes(config)
        assert before
        assert after.startswith(before)
        assert len(after) > len(before)

    def test_the_first_batch_still_reads_back_unchanged(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        first = make_batch(1, count=3)
        append_claims(first, config)

        append_claims(make_batch(2, count=3), config)

        assert tuple(read_claims(config))[: len(first)] == first


class TestDeterminism:
    def test_the_same_claims_give_byte_identical_stores(self, tmp_path: Path) -> None:
        # R23: nothing timestamped, nothing ordered by a set's iteration order.
        for name in ("one", "two"):
            config = make_config(tmp_path / name)
            append_claims(make_batch(1, count=3), config)
            append_claims(make_batch(2, count=2), config)

        first = store_bytes(make_config(tmp_path / "one"))
        second = store_bytes(make_config(tmp_path / "two"))
        assert first
        assert first == second

    def test_a_second_identical_run_is_stable_over_a_refusal(self, tmp_path: Path) -> None:
        # Re-running `ingest` on a batch already stored must leave the store
        # byte-for-byte as it was, not merely equivalent.
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=3), config)
        before = store_bytes(config)

        refuse(make_batch(1, count=3), config, why="batch 1 is already stored")

        assert store_bytes(config) == before


class TestReIngestIsRefused:
    def test_appending_a_stored_batch_again_is_refused(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=3), config)

        refuse(make_batch(1, count=3), config, why="batch 1 is already stored")

        assert len(list(read_claims(config))) == 3, "nothing may be duplicated"

    def test_a_refused_re_ingest_appends_nothing(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=2), config)

        # Different claims, same batch: an agent re-run that produced other
        # text. Still refused — the batch is the unit R10 tags, and merging
        # would silently rewrite work already paid for (R27).
        refuse(
            (make_claim("something else", batch=1),),
            config,
            why="batch 1 is already stored, whatever the claims say",
        )

        assert [claim.board for claim in read_claims(config)] == ["board-1-2", "board-1-1"]
        assert batches_stored(config) == frozenset({1})

    def test_the_refusal_says_which_batch_it_refused(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        append_claims(make_batch(4), config)

        error = refuse(make_batch(4), config, why="batch 4 is already stored")

        assert "4" in str(error)

    def test_a_batch_holding_one_stored_batch_is_refused_whole(self, tmp_path: Path) -> None:
        # The atomicity rule and the refusal rule meet here: claims of a new
        # batch travelling with a stored one must not slip in behind it.
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=2), config)

        refuse(
            make_batch(1, count=1) + make_batch(2, count=2),
            config,
            why="batch 1 is already stored",
        )

        assert batches_stored(config) == frozenset({1})
        assert len(list(read_claims(config))) == 2

    def test_another_batch_still_lands_after_a_refusal(self, tmp_path: Path) -> None:
        # A refusal is not a poisoned store: the run continues with the rest.
        config = make_config(tmp_path)
        append_claims(make_batch(1, count=2), config)
        refuse(make_batch(1, count=2), config, why="batch 1 is already stored")

        assert append_claims(make_batch(2, count=2), config) == 2
        assert batches_stored(config) == frozenset({1, 2})
        assert len(list(read_claims(config))) == 4


class TestAtomicPerFile:
    """Either every claim in a file lands or none does — never half a bundle."""

    def test_a_failure_partway_leaves_the_earlier_claims_out(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        claims = list(make_batch(1, count=3))
        claims[2] = poisoned(claims[2])

        refuse(claims, config, why="the third claim cannot be written")

        assert list(read_claims(config)) == []
        assert batches_stored(config) == frozenset()
        assert store_bytes(config) == b"", "a half-written file is not a store"

    def test_a_failure_partway_leaves_an_existing_store_untouched(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        stored = make_batch(1, count=2)
        append_claims(stored, config)
        before = store_bytes(config)

        claims = list(make_batch(2, count=3))
        claims[1] = poisoned(claims[1])
        refuse(claims, config, why="the second claim cannot be written")

        assert store_bytes(config) == before
        assert tuple(read_claims(config)) == stored
        assert batches_stored(config) == frozenset({1})

    def test_the_batch_is_not_recorded_when_its_file_fails(self, tmp_path: Path) -> None:
        # If the batch were tagged as stored anyway, the retry R9 allows would
        # be refused as a duplicate and the bundle would be lost outright.
        config = make_config(tmp_path)
        claims = list(make_batch(5, count=2))
        claims[0] = poisoned(claims[0])

        refuse(claims, config, why="the first claim cannot be written")

        assert 5 not in batches_stored(config)
        assert append_claims(make_batch(5, count=2), config) == 2
