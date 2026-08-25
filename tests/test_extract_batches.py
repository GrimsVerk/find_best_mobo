"""Tests for run-scripts slice 2's `extract` loop — how many batches, and where it stops.

Written blind from `docs/plans/run-scripts.md` (slice 2), R7, R26, R27 and §3's
non-goals, while the implementation is authored in parallel — so a missing
`pending_batches` or `--batches` is the expected state until assembly. The
helpers are reached as attributes of the command module rather than imported by
name, so an absent one fails the tests that need it instead of the whole file.

**No test here invokes a model or a reader**, by the same two guards
`tests/test_extract_command.py` and `tests/test_spend.py` use: `extract_bundle`
and `take_reading` are patched on every module that exposes the name, and
`never_shell_out` is autouse so a seam this file missed shows up as a loud
assertion rather than a real `claude -p` that spends against the very limit
under test (R19, R20).

The three properties a plausible-looking loop gets wrong, and which every test
below is shaped to discriminate:

- **ONE batch is the default.** Not all. The owner starts with unfamiliar
  numbers, and defaulting to `all` would make the FIRST run the largest one —
  the opposite of what the calibration batch exists for.
- **`--batch N` and `--batches N` are different arguments.** `--batch 3` names
  ONE batch and refuses a stored one; `--batches 3` says how many PENDING ones
  to work through and passes over a stored one without comment. An
  implementation that made them aliases satisfies neither half of
  `TestNamingABatchIsNotSayingHowMany`.
- **The ceiling stops the LOOP.** A run halted by R26 does not go on to the next
  batch; it says which batches landed, which remain and what the meter read, and
  exits non-zero. A run that merely finished the count it was given exits ZERO —
  stopping because you asked for one batch is a normal continuation point, not a
  failure, and it must not read as one (R7, S2).

Batch numbers 7 and 9 appear in the reporting tests on purpose: the fake's token
counts, percentages and bundle ids are all built from other digits, so a bare `7`
in the output can only have come from the run naming batch 7. `report` drops the
lines that quote a filesystem path first, because a `tmp_path` carries digits of
its own and would otherwise answer for the run.

Deliberately NOT asserted, because the plan does not rule them: what `--batches`
does with a value that is neither `all` nor a number, the exit code of a run
that finds nothing pending at all, and where in a batch the part-way reading
falls (`tests/test_extract_command.py` pins that already, and this file inherits
it rather than restating it).
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo import extract as extract_module
from find_best_mobo import spend
from find_best_mobo.bundle import Bundle, write_bundles
from find_best_mobo.claims import Claim
from find_best_mobo.claimstore import append_claims, read_claims
from find_best_mobo.commands import extract as extract_command
from find_best_mobo.config import Config
from find_best_mobo.excerpt import Excerpt
from find_best_mobo.extract import ExtractionResult
from find_best_mobo.spend import WEEKLY_LABEL, Reading

TAKEN_AT = "2026-08-25T12:00:00+00:00"

# Well above R26's 10%, for the reason `tests/test_spend.py` records: the ceiling
# is measured FROM the baseline, so a run beginning here stops at 0.53 and is not
# refused for beginning at 0.43.
BASELINE = 0.43

# A reading past that ceiling, taken part-way through the first batch.
CROSSING = 0.55

# Every number the fake reports is built from these digits, so that a `7` or a
# `9` standing alone in the run's output can only be a batch number it named.
INPUT_TOKENS = 1200
OUTPUT_TOKENS = 300
CACHE_CREATION_TOKENS = 20000
CACHE_READ_TOKENS = 130000


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
        calibration_batch_size=12,
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

    Copied from `tests/test_extract_command.py` rather than shared, so this file
    stands alone: if a seam were missed, the command would reach the real reader,
    fail, and fall back to `claude -p "/usage"` — which starts a session and
    spends. `extract_bundle` would invoke a model outright.
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


def write_batches(
    config: Config, batches: Sequence[int], per_batch: int = 2
) -> dict[int, tuple[str, ...]]:
    """Lay down real bundle files for each batch, numbered without repeating.

    Written through `bundle.write_bundles` so the layout the loop has to discover
    is exactly the layout `estimate` produces. Bundle ids run in one sequence
    across the batches rather than restarting per batch, so "which batch was this
    bundle in" is answerable from the id alone.
    """
    laid: dict[int, tuple[str, ...]] = {}
    number = 1
    for batch in batches:
        bundles = []
        for _ in range(per_batch):
            bundles.append(
                Bundle(
                    bundle_id=f"bundle-{number:03d}",
                    batch=batch,
                    excerpts=(excerpt(number),),
                    projected_tokens=1500,
                )
            )
            number += 1
        write_bundles(bundles, config)
        laid[batch] = tuple(bundle.bundle_id for bundle in bundles)
    return laid


def empty_batch_directory(config: Config, batch: int) -> Path:
    """A batch directory holding no bundles — a real state, and not a pending batch."""
    directory = config.data_dir / "bundles" / f"batch-{batch}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store_batch(config: Config, batch: int) -> None:
    """Put a batch in the append-only store, the way a previous run would have."""
    append_claims(
        [
            Claim(
                board="ASRock X670E Taichi",
                video_id=f"stored-batch-{batch}",
                video_title="X670E VRM breakdown",
                timestamp_seconds=62.25,
                snippet="the VRM is genuinely overbuilt for anything you can socket",
                category="tested",
                subject="vrm_capacity",
                polarity="positive",
                batch=batch,
            )
        ],
        config,
    )


def claims_json(bundle_id: str) -> str:
    """One valid claim carrying its bundle's id where the store can be searched for it."""
    return (
        '[{"board": "ASRock X670E Taichi", '
        f'"video_id": "{bundle_id}", '
        '"video_title": "X670E VRM breakdown", '
        '"timestamp_seconds": 62.25, '
        '"snippet": "the VRM is genuinely overbuilt for anything you can socket", '
        '"category": "tested", "subject": "vrm_capacity", "polarity": "positive"}]'
    )


class FakeExtraction:
    """The two seams the loop drives, and a log of every batch they were asked for.

    `percents` is the meter's answers in order, the last one repeating once the
    list runs out — so a loop that keeps going after a crossing keeps reading the
    crossing value, and the bundles it extracts afterwards are recorded here for
    the test to find.
    """

    def __init__(self, config: Config, *, percents: tuple[float, ...] = (BASELINE,)) -> None:
        self.config = config
        self.percents = percents
        self.readings: list[float] = []
        self.calls: list[tuple[int, str]] = []
        self.attempts: dict[str, int] = {}

    # -- the seams -------------------------------------------------------

    def take_reading(self, config: Config) -> Reading:
        percent = self.percents[min(len(self.readings), len(self.percents) - 1)]
        self.readings.append(percent)
        return Reading(
            label=WEEKLY_LABEL, percent=percent, taken_at=TAKEN_AT, source="omarchy (fake)"
        )

    def extract_bundle(self, bundle_path: Path, batch: int, config: Config) -> ExtractionResult:
        bundle_id = Path(bundle_path).stem
        self.attempts[bundle_id] = self.attempts.get(bundle_id, 0) + 1
        self.calls.append((batch, bundle_id))

        directory = config.data_dir / "claims" / f"batch-{batch}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{bundle_id}-{self.attempts[bundle_id]}.json"
        path.write_text(claims_json(bundle_id), encoding="utf-8")

        # The four components, separately and never summed (R8 as amended).
        return ExtractionResult(
            bundle_id=bundle_id,
            claims_path=path,
            input_tokens=INPUT_TOKENS,
            output_tokens=OUTPUT_TOKENS,
            cache_creation_tokens=CACHE_CREATION_TOKENS,
            cache_read_tokens=CACHE_READ_TOKENS,
        )

    # -- what the log is for ---------------------------------------------

    @property
    def batches_extracted(self) -> list[int]:
        """Every batch a model call was made for, in order, without repeats."""
        seen: list[int] = []
        for batch, _ in self.calls:
            if batch not in seen:
                seen.append(batch)
        return seen

    def bundles_of(self, batch: int) -> list[str]:
        return [bundle_id for called, bundle_id in self.calls if called == batch]


def install(monkeypatch: pytest.MonkeyPatch, fake: FakeExtraction) -> FakeExtraction:
    """Patch both seams wherever the implementation bound them."""
    for name, replacement in (
        ("take_reading", fake.take_reading),
        ("extract_bundle", fake.extract_bundle),
    ):
        targets = [
            module for module in (spend, extract_module, extract_command) if hasattr(module, name)
        ]
        assert targets, f"no module exposes `{name}`, so the seam cannot be faked"
        for module in targets:
            monkeypatch.setattr(module, name, replacement)
    return fake


def run(config: Config, argv: Sequence[str] = ()) -> int:
    """The command as the CLI reaches it: its own parser, then its own `run`."""
    return extract_command.run(config, extract_command.parse_args(list(argv)))


def stored(config: Config) -> list[Claim]:
    return list(read_claims(config))


def stored_bundles(config: Config) -> set[str]:
    return {claim.video_id for claim in stored(config)}


def report(config: Config, capsys: pytest.CaptureFixture[str]) -> str:
    """What the run printed, with everything that carries a digit of its own removed.

    The assertions below ask whether a BATCH NUMBER was reported, so anything
    else in the output that could answer for one is taken out first. Two things
    can: a `tmp_path` — `pytest-of-loke/pytest-97` — so the lines quoting
    `data_dir` go, and the meter's label, `Weekly (7-day)`, which would otherwise
    report batch 7 on every run ever made.
    """
    printed = capsys.readouterr().out.replace(WEEKLY_LABEL, "the weekly limit")
    root = str(config.data_dir)
    return "\n".join(line for line in printed.splitlines() if root not in line)


def names_batch(text: str, batch: int) -> bool:
    """Whether `batch` appears as a number of its own, rather than inside another."""
    return re.search(rf"\b{batch}\b", text) is not None


class TestWhichBatchesArePending:
    """`pending_batches` reads the store against the batches `data/bundles/` holds."""

    def test_a_batch_with_bundles_in_it_is_pending(self, config: Config) -> None:
        write_batches(config, [1, 2])

        assert extract_command.pending_batches(config) == (1, 2)

    def test_a_batch_directory_holding_no_bundles_is_not_pending(self, config: Config) -> None:
        """The batch exists and holds nothing, which is a real value and not work."""
        write_batches(config, [1, 2])
        empty_batch_directory(config, 3)

        assert extract_command.pending_batches(config) == (1, 2)

    def test_a_batch_already_in_the_store_is_not_pending(self, config: Config) -> None:
        write_batches(config, [1, 2, 3])
        store_batch(config, 1)

        assert extract_command.pending_batches(config) == (2, 3)

    def test_every_stored_batch_drops_out(self, config: Config) -> None:
        write_batches(config, [1, 2])
        store_batch(config, 1)
        store_batch(config, 2)

        assert extract_command.pending_batches(config) == ()

    def test_a_batch_in_the_store_that_has_no_bundles_left_is_not_invented(
        self, config: Config
    ) -> None:
        """Pending is what `data/bundles/` holds, never what the store remembers."""
        write_batches(config, [2])
        store_batch(config, 1)

        assert extract_command.pending_batches(config) == (2,)

    def test_nothing_is_pending_before_estimate_has_written_anything(self, config: Config) -> None:
        assert extract_command.pending_batches(config) == ()


class TestHowManyBatchesARunDoes:
    """`batches_to_run` turns the argument into the list, and one is the default."""

    def test_one_batch_is_the_default(self, config: Config) -> None:
        """R7 and §3: the number is an argument, and the number it defaults to is ONE.

        Defaulting to `all` would make the first run the largest one, which is
        the opposite of what the calibration batch exists for.
        """
        write_batches(config, [1, 2, 3])

        assert extract_command.batches_to_run(None, config) == (1,)

    def test_all_means_every_pending_batch(self, config: Config) -> None:
        write_batches(config, [1, 2, 3])

        assert extract_command.batches_to_run("all", config) == (1, 2, 3)

    def test_a_number_says_how_many_pending_batches_to_work_through(self, config: Config) -> None:
        write_batches(config, [1, 2, 3])

        assert extract_command.batches_to_run("2", config) == (1, 2)

    def test_a_stored_batch_is_passed_over_rather_than_counted(self, config: Config) -> None:
        """`--batches` counts PENDING batches, so a stored one is not one of them."""
        write_batches(config, [1, 2, 3])
        store_batch(config, 1)

        assert extract_command.batches_to_run(None, config) == (2,)
        assert extract_command.batches_to_run("2", config) == (2, 3)
        assert extract_command.batches_to_run("all", config) == (2, 3)

    def test_asking_for_more_than_remain_yields_what_remains(self, config: Config) -> None:
        write_batches(config, [1, 2])

        assert extract_command.batches_to_run("5", config) == (1, 2)

    def test_nothing_pending_is_nothing_to_run(self, config: Config) -> None:
        assert extract_command.batches_to_run("all", config) == ()
        assert extract_command.batches_to_run(None, config) == ()


class TestTheArguments:
    """`--batch` and `--batches` both exist, and neither is required."""

    def test_neither_argument_is_required(self, config: Config) -> None:
        """The bare command is the default run, not the usage error it used to be."""
        args = extract_command.parse_args([])

        assert getattr(args, "batch", None) is None
        assert getattr(args, "batches", None) is None

    def test_the_named_batch_argument_stays(self) -> None:
        assert extract_command.parse_args(["--batch", "3"]).batch == 3

    def test_how_many_can_be_a_count(self) -> None:
        assert str(extract_command.parse_args(["--batches", "3"]).batches) == "3"

    def test_how_many_can_be_all(self) -> None:
        """`all` is a value of the same argument, which is why it is not an int."""
        assert extract_command.parse_args(["--batches", "all"]).batches == "all"

    @pytest.mark.parametrize("how_many", ["1", "2", "all"])
    def test_giving_both_is_an_error_rather_than_a_precedence_rule(
        self, config: Config, monkeypatch: pytest.MonkeyPatch, how_many: str
    ) -> None:
        """A precedence rule is a thing readers guess at, so there is not one.

        Refused wherever the implementation refuses it — argparse or the run —
        but refused, and without spending: a run that quietly picked one of the
        two arguments would spend on a batch nobody asked for.
        """
        write_batches(config, [1, 2, 3])
        fake = install(monkeypatch, FakeExtraction(config))

        try:
            args = extract_command.parse_args(["--batch", "1", "--batches", how_many])
        except SystemExit as error:
            assert error.code != 0
        else:
            assert extract_command.run(config, args) != 0, (
                "giving both arguments was resolved by a precedence rule instead of refused"
            )
        assert fake.calls == [], "a refused command still spent on a batch"


class TestOneBatchByDefault:
    """The bare `extract`, with three batches waiting."""

    @pytest.fixture
    def laid(self, config: Config) -> dict[int, tuple[str, ...]]:
        return write_batches(config, [1, 7, 9])

    @pytest.fixture
    def fake(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeExtraction:
        return install(monkeypatch, FakeExtraction(config, percents=(BASELINE, 0.45)))

    def test_exactly_one_batch_runs(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        run(config)

        assert fake.batches_extracted == [1], (
            "a bare `extract` did not do exactly one batch; the default is one, "
            "because the first run is the one whose numbers are least familiar"
        )

    def test_the_batch_it_does_is_the_first_pending_one(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        run(config)

        assert fake.bundles_of(1) == list(laid[1])
        assert fake.bundles_of(7) == []
        assert fake.bundles_of(9) == []

    def test_a_run_that_completed_its_count_exits_zero(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        """Stopping because you asked for one batch is not a failure (R7, S2).

        The next run is a normal continuation, not a recovery, and an exit code
        is the only signal a caller reads without parsing the output.
        """
        assert run(config) == 0

    def test_the_output_says_which_batches_remain(
        self,
        config: Config,
        laid: dict[int, tuple[str, ...]],
        fake: FakeExtraction,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run(config)

        printed = report(config, capsys)
        assert names_batch(printed, 7), f"batch 7 is still pending and is not reported: {printed!r}"
        assert names_batch(printed, 9), f"batch 9 is still pending and is not reported: {printed!r}"

    def test_only_the_batch_that_ran_reaches_the_store(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        run(config)

        assert {claim.batch for claim in stored(config)} == {1}
        assert stored_bundles(config) == set(laid[1])


class TestWorkingThroughEveryPendingBatch:
    """`--batches all`, and `--batches N`, over three batches."""

    @pytest.fixture
    def laid(self, config: Config) -> dict[int, tuple[str, ...]]:
        return write_batches(config, [1, 2, 3])

    @pytest.fixture
    def fake(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeExtraction:
        return install(monkeypatch, FakeExtraction(config, percents=(BASELINE, 0.45, 0.47)))

    def test_all_works_through_every_one_of_them(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        code = run(config, ["--batches", "all"])

        assert fake.batches_extracted == [1, 2, 3]
        assert code == 0

    def test_a_count_stops_after_that_many(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        code = run(config, ["--batches", "2"])

        assert fake.batches_extracted == [1, 2]
        assert code == 0

    def test_each_batchs_claims_are_stored_under_its_own_batch_number(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        """R10: the store is tagged by batch, and a loop must not blur the tags."""
        run(config, ["--batches", "all"])

        for claim in stored(config):
            assert claim.video_id in laid[claim.batch], (
                f"{claim.video_id} was stored as batch {claim.batch}, which is not its batch"
            )
        assert {claim.batch for claim in stored(config)} == {1, 2, 3}

    def test_a_stored_batch_is_skipped_and_the_run_still_succeeds(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skipping a stored batch while working through the pending ones is not a fault."""
        laid = write_batches(config, [1, 2, 3])
        store_batch(config, 1)
        fake = install(monkeypatch, FakeExtraction(config, percents=(BASELINE, 0.45)))

        code = run(config, ["--batches", "all"])

        assert fake.batches_extracted == [2, 3]
        assert fake.bundles_of(1) == [], "a stored batch was extracted again"
        assert code == 0, "passing over a stored batch was reported as a failure"
        assert stored_bundles(config) >= set(laid[2]) | set(laid[3])

    def test_a_run_with_nothing_pending_spends_nothing(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_batches(config, [1])
        store_batch(config, 1)
        fake = install(monkeypatch, FakeExtraction(config))

        run(config, ["--batches", "all"])

        assert fake.calls == [], "a run with nothing pending still paid for a bundle"


class TestNamingABatchIsNotSayingHowMany:
    """`--batch N` and `--batches N` are different arguments, and both stay.

    The two halves of the difference are asserted separately and both must hold:
    naming a stored batch is a mistake worth reporting, and working through the
    pending ones past a stored one is not. An implementation that made the two
    arguments aliases fails whichever half it chose against.
    """

    def test_naming_a_stored_batch_is_refused_before_anything_is_spent(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_batches(config, [1, 2, 3])
        store_batch(config, 1)
        fake = install(monkeypatch, FakeExtraction(config))

        code = run(config, ["--batch", "1"])

        assert code != 0, "`--batch 1` named a batch the store already holds and did not refuse"
        assert fake.calls == [], "a refused batch still cost a model call"

    def test_asking_for_one_batch_passes_over_the_stored_one_instead(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same store, the same count, the other argument — and the opposite outcome."""
        write_batches(config, [1, 2, 3])
        store_batch(config, 1)
        fake = install(monkeypatch, FakeExtraction(config, percents=(BASELINE, 0.45)))

        code = run(config, ["--batches", "1"])

        assert fake.batches_extracted == [2], (
            "`--batches 1` refused or re-ran the stored batch instead of doing the "
            "first PENDING one; it says how many, not which"
        )
        assert code == 0

    def test_naming_a_batch_runs_that_batch_and_no_other(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--batch 2` is the second batch, not the first two of them."""
        laid = write_batches(config, [1, 2, 3])
        fake = install(monkeypatch, FakeExtraction(config, percents=(BASELINE, 0.45)))

        code = run(config, ["--batch", "2"])

        assert fake.batches_extracted == [2]
        assert fake.bundles_of(2) == list(laid[2])
        assert code == 0

    def test_naming_a_batch_with_no_bundle_directory_is_still_an_error(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R1005/OD-9: an absent upstream artifact is an error, not an empty run."""
        write_batches(config, [1])
        fake = install(monkeypatch, FakeExtraction(config))

        code = run(config, ["--batch", "4"])

        assert code != 0
        assert fake.calls == []


class TestTheCeilingStopsTheLoop:
    """0.43 baseline, 0.53 ceiling, and a reading of 0.55 part-way through batch 1.

    Batch 7 is pending behind it and holds bundles of its own. A loop that
    treated the ceiling as a per-batch stop would take a fresh baseline of 0.55,
    compute a fresh ceiling of 0.65, and carry on spending — which is the exact
    failure R26 is written against, one level up from the one slice 3 pinned.
    """

    @pytest.fixture
    def laid(self, config: Config) -> dict[int, tuple[str, ...]]:
        return write_batches(config, [1, 7], per_batch=4)

    @pytest.fixture
    def fake(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> FakeExtraction:
        return install(monkeypatch, FakeExtraction(config, percents=(BASELINE, CROSSING)))

    def test_the_next_batch_is_never_started(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        run(config, ["--batches", "all"])

        assert fake.bundles_of(7) == [], (
            "the run crossed the ceiling and went on to the next batch: the ceiling "
            "stops the LOOP, not just the batch it fired in"
        )

    def test_the_batch_it_stopped_in_did_not_finish_either(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        run(config, ["--batches", "all"])

        assert 0 < len(fake.bundles_of(1)) < len(laid[1]), fake.calls

    def test_the_exit_code_is_non_zero(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        """A run halted by the ceiling did not do what it was asked (R27)."""
        assert run(config, ["--batches", "all"]) != 0

    def test_the_output_says_which_batch_still_needs_doing(
        self,
        config: Config,
        laid: dict[int, tuple[str, ...]],
        fake: FakeExtraction,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run(config, ["--batches", "all"])

        printed = report(config, capsys)
        assert names_batch(printed, 7), (
            f"the run stopped with batch 7 pending and never named it: {printed!r}"
        )

    def test_the_output_says_which_bundles_landed(
        self,
        config: Config,
        laid: dict[int, tuple[str, ...]],
        fake: FakeExtraction,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run(config, ["--batches", "all"])

        printed = report(config, capsys)
        for bundle_id in fake.bundles_of(1):
            assert bundle_id in printed, f"{bundle_id} was extracted and is not reported"

    def test_the_output_says_what_the_meter_read(
        self,
        config: Config,
        laid: dict[int, tuple[str, ...]],
        fake: FakeExtraction,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run(config, ["--batches", "all"])

        printed = report(config, capsys)
        assert f"{round(CROSSING * 100)}" in printed, (
            f"the stop does not say what the meter read: {printed!r}"
        )

    def test_a_stop_is_not_a_rollback(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        """R27: every claim already ingested stays ingested."""
        run(config, ["--batches", "all"])

        assert stored_bundles(config) == set(fake.bundles_of(1)), (
            "the stop discarded work that had already been paid for"
        )

    def test_a_count_of_one_is_stopped_by_the_ceiling_the_same_way(
        self, config: Config, laid: dict[int, tuple[str, ...]], fake: FakeExtraction
    ) -> None:
        """R26's ceiling stops the run earlier whatever the number was (R7)."""
        assert run(config) != 0, "a default run halted by the ceiling reported success"
