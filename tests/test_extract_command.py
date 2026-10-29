"""Tests for Stage B slice 3's `extract` command — one batch, stopped before the line.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 3), R26, R27,
R9 and BL-23 items 5 and 6, while the implementation is authored in parallel — so
failing imports are the expected state until assembly.

**No test here invokes a model or a reader.** Two seams are faked, both the way
`ytdlp.py`'s boundary is faked in `tests/test_ytdlp_client_reuse.py`: the
model-invoking `extract_bundle` from slice 2, and `take_reading` from
`find_best_mobo.spend`. Each is patched on every module that exposes the name,
because whether the command wrote `from ... import take_reading` or reached it
through the module is an implementation choice a blind test may not know. On top
of that, `never_shell_out` is autouse and fails any test that starts a real
process, so a seam this file missed cannot quietly become a real `claude -p`
that spends against the limit under test.

What is asserted is the ORDER OF EVENTS, not the internals. The fakes append to
one event log — `("read", percent)` and `("extract", bundle_id)` — and the log is
what proves the part-way reading is a guard rather than a receipt: a run that
read only before and after would satisfy every count-based test and is exactly
the failure the plan names.

Three deliberate non-assertions, because the plan does not rule them: how many
bundles must sit between the part-way reading and the ends (only that at least
one reading falls strictly between the first and last extraction), the exit code
of a run that merely set a bundle aside, and whether a reading exactly equal to
the ceiling stops the run.

One thing this file asserts as an OUTCOME rather than a mechanism, on purpose:
"every claim already ingested stays ingested" is checked by reading the store
after the run, never by counting appends. `claimstore.append_claims` refuses a
batch it already holds, so a command appending once per bundle and a command
appending once per batch cannot both be written against the same assertion — and
which one slice 3 chose is not something a blind test can know.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as in
# tests/test_claims.py: the slice-3 modules below do not exist yet, so the isort
# rule classifies them as third-party and would demand a different grouping from
# the one it demands once they land. The block is written in its post-assembly
# order, which is the stable one.
from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo import spend
from find_best_mobo.bundle import Bundle, write_bundles
from find_best_mobo.claims import Claim
from find_best_mobo.claimstore import read_claims
from find_best_mobo.commands import extract as extract_command
from find_best_mobo.config import Config
from find_best_mobo.excerpt import Excerpt
from find_best_mobo import extract as extract_module
from find_best_mobo.extract import ExtractionResult
from find_best_mobo.spend import WEEKLY_LABEL, Reading

TAKEN_AT = "2026-08-25T12:00:00+00:00"

# The owner's real week sits well above the 10% cap, which is the whole point:
# the ceiling is measured FROM this, so a run beginning here stops at 0.53 and
# is not refused for being at 0.43 (R26 caps the effort, not the account).
BASELINE = 0.43

# A batch the plan's own calibration size, so the part-way reading is plainly
# warranted. A two-bundle batch would let a before-and-after implementation pass.
CALIBRATION_SIZE = 12


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
        calibration_batch_size=CALIBRATION_SIZE,
        batch_count=3,
        chars_per_token=4.0,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return make_config(tmp_path / "data")


@pytest.fixture(autouse=True)
def never_shell_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test in this file may start a real process.

    If a seam were missed, the command would reach the real reader, fail, and
    fall back to `claude -p "/usage"` — which starts a session and spends. And
    `extract_bundle` would invoke a model outright. Both must be impossible
    rather than merely unlikely (R19, R20).
    """

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            f"a test started a real process: {args!r}. A seam was not patched, and "
            "the command spends real subscription budget when it is not."
        )

    for name in ("run", "check_output", "check_call", "call", "Popen"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def excerpt(number: int) -> Excerpt:
    return Excerpt(
        video_id=f"vid{number:08d}abc",
        video_title=f"X670E VRM breakdown, part {number}",
        start_seconds=0.0,
        end_seconds=120.0,
        text="the VRM on this one is genuinely overbuilt for anything you can socket",
        canonicals=("ASRock X670E Taichi",),
    )


def write_batch(config: Config, batch: int, count: int) -> tuple[str, ...]:
    """Lay down `count` real bundle files where Stage A puts them.

    Written through `bundle.write_bundles` rather than by hand, so the layout
    the command has to discover is exactly the layout `estimate` produces.
    """
    bundles = tuple(
        Bundle(
            bundle_id=f"bundle-{number:03d}",
            batch=batch,
            excerpts=(excerpt(number),),
            projected_tokens=1500,
        )
        for number in range(1, count + 1)
    )
    write_bundles(bundles, config)
    return tuple(bundle.bundle_id for bundle in bundles)


def valid_claims(bundle_id: str) -> str:
    """One claim, carrying its bundle's id where the store can be searched for it.

    `video_id` is the marker: it survives into `data/claims.jsonl` untouched, so
    "which bundles' claims landed" is answerable from the store alone.
    """
    return json.dumps(
        [
            {
                "board": "ASRock X670E Taichi",
                "video_id": bundle_id,
                "video_title": "X670E VRM breakdown",
                "timestamp_seconds": 62.25,
                "snippet": "the VRM is genuinely overbuilt for anything you can socket",
                "category": "tested",
                "subject": "vrm_capacity",
                "polarity": "positive",
            }
        ]
    )


# A model that misunderstood the contract: an invented field, and most of the
# required ones missing. `parse_claims` refuses it with several faults.
BROKEN_CLAIMS = json.dumps([{"board": "ASRock X670E Taichi", "confidence": 0.9}])

ALWAYS = 99


class FakeBatch:
    """The two seams slice 3 drives, and one log of everything they were asked.

    `percents` is the meter's answers in order; the last one repeats once the
    list runs out. `broken` maps a bundle id to how many of its extractions
    produce a claims file that fails validation — `ALWAYS` for a bundle that
    never comes back valid.
    """

    def __init__(
        self,
        config: Config,
        *,
        percents: tuple[float, ...] = (BASELINE,),
        broken: dict[str, int] | None = None,
    ) -> None:
        self.config = config
        self.percents = percents
        self.broken = dict(broken or {})
        self.events: list[tuple[str, str]] = []
        self.attempts: Counter[str] = Counter()
        self.readings: list[float] = []
        self.claims_paths: dict[str, Path] = {}

    # -- the seams -------------------------------------------------------

    def take_reading(self, config: Config) -> Reading:
        percent = self.percents[min(len(self.readings), len(self.percents) - 1)]
        self.readings.append(percent)
        self.events.append(("read", f"{percent}"))
        return Reading(
            label=WEEKLY_LABEL, percent=percent, taken_at=TAKEN_AT, source="omarchy (fake)"
        )

    def extract_bundle(self, bundle_path: Path, batch: int, config: Config) -> ExtractionResult:
        bundle_id = Path(bundle_path).stem
        self.attempts[bundle_id] += 1
        self.events.append(("extract", bundle_id))

        directory = config.data_dir / "claims" / f"batch-{batch}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{bundle_id}-{self.attempts[bundle_id]}.json"
        failing = self.attempts[bundle_id] <= self.broken.get(bundle_id, 0)
        path.write_text(BROKEN_CLAIMS if failing else valid_claims(bundle_id), encoding="utf-8")
        self.claims_paths[bundle_id] = path

        # The four components, separately and never summed (R8 as amended).
        return ExtractionResult(
            bundle_id=bundle_id,
            claims_path=path,
            input_tokens=1200,
            output_tokens=340,
            cache_creation_tokens=8000,
            cache_read_tokens=980000,
        )

    # -- what the log is for ---------------------------------------------

    @property
    def extracted(self) -> list[str]:
        """Every bundle id handed to the model, in order, retries included."""
        return [value for kind, value in self.events if kind == "extract"]

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.events]


def install(monkeypatch: pytest.MonkeyPatch, batch: FakeBatch) -> FakeBatch:
    """Patch both seams wherever the implementation bound them."""
    for name, replacement in (
        ("take_reading", batch.take_reading),
        ("extract_bundle", batch.extract_bundle),
    ):
        targets = [
            module for module in (spend, extract_module, extract_command) if hasattr(module, name)
        ]
        assert targets, f"no module exposes `{name}`, so the seam cannot be faked"
        for module in targets:
            monkeypatch.setattr(module, name, replacement)
    return batch


def run_extract(config: Config, batch: int = 1) -> int:
    return extract_command.run(config, extract_command.parse_args(["--batch", str(batch)]))


def stored(config: Config) -> list[Claim]:
    return list(read_claims(config))


def stored_bundles(config: Config) -> set[str]:
    """Which bundles' claims are in the append-only store, by their marker."""
    return {claim.video_id for claim in stored(config)}


def digits(value: float) -> str:
    """`0.55` as `55`, the substring every plausible rendering of it contains."""
    return f"{round(value * 100)}"


class TestTheCommandIsTheContinueCommandR7Promises:
    def test_the_batch_is_named_on_the_command_line(self) -> None:
        assert extract_command.parse_args(["--batch", "3"]).batch == 3

    def test_a_batch_with_no_bundles_is_refused_before_anything_is_spent(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R1005/OD-9: an absent upstream artifact is an error, not an empty run."""
        batch = install(monkeypatch, FakeBatch(config))

        code = run_extract(config, batch=4)

        assert code != 0
        assert batch.extracted == [], "a missing batch cost a model call"


class TestABatchThatStaysUnderTheLine:
    @pytest.fixture
    def batch(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeBatch:
        write_batch(config, 1, CALIBRATION_SIZE)
        # 0.43 to 0.49: real movement, never reaching the 0.53 ceiling.
        return install(
            monkeypatch,
            FakeBatch(config, percents=(BASELINE, 0.45, 0.47, 0.49)),
        )

    def test_a_run_beginning_above_ten_percent_is_not_refused_outright(
        self, config: Config, batch: FakeBatch
    ) -> None:
        """The failure this pins is the whole point of R26's wording.

        A guard reading the cap as an absolute 10% of the weekly limit would
        refuse this run before extracting anything — the account is at 43% — and
        would do so on the owner's machine every week of the year.
        """
        code = run_extract(config)

        assert code == 0, "a run starting at 43% was refused for starting at 43%"
        assert batch.extracted, "nothing was extracted at all"

    def test_every_bundle_in_the_batch_is_extracted_exactly_once(
        self, config: Config, batch: FakeBatch
    ) -> None:
        expected = [f"bundle-{number:03d}" for number in range(1, CALIBRATION_SIZE + 1)]

        run_extract(config)

        assert sorted(batch.extracted) == sorted(expected)

    def test_every_bundles_claims_are_stored(self, config: Config, batch: FakeBatch) -> None:
        run_extract(config)

        assert stored_bundles(config) == {
            f"bundle-{number:03d}" for number in range(1, CALIBRATION_SIZE + 1)
        }

    def test_the_stored_claims_are_tagged_with_the_batch(
        self, config: Config, batch: FakeBatch
    ) -> None:
        """R10: the store is tagged by batch, so a stop between batches loses nothing."""
        run_extract(config)

        assert {claim.batch for claim in stored(config)} == {1}

    def test_only_the_named_batch_is_extracted(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One batch at a time (BL-23 item 5). Batch 2 exists and is left alone."""
        write_batch(config, 1, 3)
        write_batch(config, 2, 3)
        fake = install(monkeypatch, FakeBatch(config, percents=(BASELINE,)))

        run_extract(config, batch=1)

        assert sorted(fake.extracted) == ["bundle-001", "bundle-002", "bundle-003"]
        assert {claim.batch for claim in stored(config)} == {1}


class TestTheReadingIsTakenThreeTimes:
    """Before, part-way, and after — and the part-way one is what makes it a guard.

    Asserted structurally rather than as a count of exactly three: the plan's own
    ordering ("read, extract one bundle, ingest it, read again if the batch is
    long enough to warrant it") permits more than three on a long batch, and a
    guard that looks MORE often is not the failure this file is hunting. What is
    pinned is that a reading falls strictly between the first and last extraction
    — which a before-and-after implementation cannot satisfy.
    """

    @pytest.fixture
    def batch(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeBatch:
        write_batch(config, 1, CALIBRATION_SIZE)
        return install(monkeypatch, FakeBatch(config, percents=(BASELINE, 0.45, 0.47, 0.49)))

    def test_at_least_three_readings_are_taken(self, config: Config, batch: FakeBatch) -> None:
        run_extract(config)

        assert batch.kinds.count("read") >= 3, (
            f"the meter was read {batch.kinds.count('read')} times: {batch.events}"
        )

    def test_the_first_reading_comes_before_any_bundle_is_extracted(
        self, config: Config, batch: FakeBatch
    ) -> None:
        run_extract(config)

        assert batch.kinds[0] == "read", batch.events

    def test_the_last_reading_comes_after_the_last_bundle(
        self, config: Config, batch: FakeBatch
    ) -> None:
        run_extract(config)

        assert batch.kinds[-1] == "read", batch.events

    def test_a_reading_is_taken_part_way_through_the_batch(
        self, config: Config, batch: FakeBatch
    ) -> None:
        """The reading that would have to happen for a stop to be possible at all.

        A run that reads only before and after discovers an overrun once it has
        already been paid for, which is the receipt R26 was written to replace.
        """
        run_extract(config)

        kinds = batch.kinds
        first_extract = kinds.index("extract")
        last_extract = len(kinds) - 1 - kinds[::-1].index("extract")
        part_way = [
            position
            for position, kind in enumerate(kinds)
            if kind == "read" and first_extract < position < last_extract
        ]

        assert part_way, (
            "no reading was taken while bundles remained; a guard that reads only "
            f"before and after is a receipt, not a guard: {batch.events}"
        )


class TestStoppingBeforeTheLine:
    """0.43 baseline, 0.53 ceiling, and a part-way reading of 0.55."""

    CROSSING = 0.55

    @pytest.fixture
    def batch(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeBatch:
        write_batch(config, 1, CALIBRATION_SIZE)
        return install(monkeypatch, FakeBatch(config, percents=(BASELINE, self.CROSSING)))

    def test_the_batch_does_not_finish(self, config: Config, batch: FakeBatch) -> None:
        run_extract(config)

        assert len(set(batch.extracted)) < CALIBRATION_SIZE, (
            "every bundle was extracted despite the meter crossing the ceiling: "
            "the ceiling was checked after the batch rather than before crossing it"
        )

    def test_some_of_the_batch_did_run(self, config: Config, batch: FakeBatch) -> None:
        """A stop is not a refusal of the whole run: the baseline is under the line."""
        run_extract(config)

        assert batch.extracted, batch.events

    def test_nothing_is_extracted_after_the_reading_that_crossed(
        self, config: Config, batch: FakeBatch
    ) -> None:
        run_extract(config)

        crossed = [
            position
            for position, (kind, value) in enumerate(batch.events)
            if kind == "read" and value == str(self.CROSSING)
        ]
        assert crossed, f"the crossing reading was never taken: {batch.events}"
        after = [kind for kind, _ in batch.events[crossed[0] + 1 :]]
        assert "extract" not in after, f"the run crossed the line and kept spending: {batch.events}"

    def test_the_exit_code_is_non_zero(self, config: Config, batch: FakeBatch) -> None:
        """So nothing downstream mistakes a partial batch for a whole one."""
        assert run_extract(config) != 0

    def test_a_stop_is_not_a_rollback_of_the_claims(self, config: Config, batch: FakeBatch) -> None:
        """R27: every claim already ingested stays ingested."""
        run_extract(config)

        assert stored_bundles(config) == set(batch.extracted), (
            "the stop discarded work that had already been paid for"
        )

    def test_a_stop_is_not_a_rollback_of_the_model_output(
        self, config: Config, batch: FakeBatch
    ) -> None:
        """R27: a model output already written stays written."""
        run_extract(config)

        for bundle_id in batch.extracted:
            assert batch.claims_paths[bundle_id].is_file(), bundle_id

    def test_the_output_names_the_bundles_that_are_done(
        self, config: Config, batch: FakeBatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run_extract(config)

        printed = capsys.readouterr().out
        for bundle_id in set(batch.extracted):
            assert bundle_id in printed, f"{bundle_id} was extracted and is not reported"

    def test_the_output_names_the_bundles_that_remain(
        self, config: Config, batch: FakeBatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run_extract(config)

        printed = capsys.readouterr().out
        done = set(batch.extracted)
        remaining = [
            f"bundle-{number:03d}"
            for number in range(1, CALIBRATION_SIZE + 1)
            if f"bundle-{number:03d}" not in done
        ]
        assert remaining, "this fixture must leave something unextracted"
        for bundle_id in remaining:
            assert bundle_id in printed, f"{bundle_id} still needs doing and is not reported"

    def test_the_output_says_what_the_meter_read(
        self, config: Config, batch: FakeBatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run_extract(config)

        printed = capsys.readouterr().out
        assert digits(self.CROSSING) in printed, f"the stop does not say what it read: {printed!r}"


class TestAClaimsFileThatFailsValidation:
    """One retry, then set aside — and the batch continues (R9, the plan's ruling).

    A batch that halted on one malformed file would strand the eleven bundles
    already paid for, which is the waste R27 exists to prevent.
    """

    BUNDLES = 4
    BAD = "bundle-002"

    @pytest.fixture
    def batch(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeBatch:
        write_batch(config, 1, self.BUNDLES)
        return install(
            monkeypatch,
            FakeBatch(config, percents=(BASELINE,), broken={self.BAD: ALWAYS}),
        )

    def test_the_bundle_is_retried_exactly_once(self, config: Config, batch: FakeBatch) -> None:
        run_extract(config)

        assert batch.attempts[self.BAD] == 2, (
            f"{self.BAD} was extracted {batch.attempts[self.BAD]} times; R9 asks for "
            "one retry, and then for the bundle to be set aside"
        )

    def test_the_bundles_claims_never_reach_the_store(
        self, config: Config, batch: FakeBatch
    ) -> None:
        run_extract(config)

        assert self.BAD not in stored_bundles(config)

    def test_the_batch_continues_past_it(self, config: Config, batch: FakeBatch) -> None:
        """The eleven bundles already paid for are not stranded by the twelfth."""
        run_extract(config)

        assert "bundle-003" in batch.extracted, batch.events
        assert "bundle-004" in batch.extracted, batch.events

    def test_every_other_bundle_is_still_stored(self, config: Config, batch: FakeBatch) -> None:
        run_extract(config)

        assert stored_bundles(config) == {"bundle-001", "bundle-003", "bundle-004"}

    def test_the_set_aside_bundle_is_named_in_the_output(
        self, config: Config, batch: FakeBatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R9: never silently dropped."""
        run_extract(config)

        printed = capsys.readouterr().out
        assert self.BAD in printed, f"a bundle was set aside without saying so: {printed!r}"

    def test_the_output_that_failed_is_kept_on_disk(self, config: Config, batch: FakeBatch) -> None:
        """R27: the file is evidence of a spend that already happened."""
        run_extract(config)

        assert batch.claims_paths[self.BAD].is_file()

    def test_a_retry_that_succeeds_is_the_end_of_it(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_batch(config, 1, 3)
        fake = install(
            monkeypatch,
            FakeBatch(config, percents=(BASELINE,), broken={"bundle-002": 1}),
        )

        code = run_extract(config)

        assert fake.attempts["bundle-002"] == 2, "the retry never happened"
        assert stored_bundles(config) == {"bundle-001", "bundle-002", "bundle-003"}
        assert code == 0, "a batch that recovered on the retry is not a failed batch"

    def test_the_meter_is_still_watched_while_bundles_are_being_set_aside(
        self, config: Config, batch: FakeBatch
    ) -> None:
        """A set-aside is not an escape hatch out of the guard."""
        run_extract(config)

        assert batch.kinds[0] == "read"
        assert batch.kinds[-1] == "read"
