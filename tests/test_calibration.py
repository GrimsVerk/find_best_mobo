"""Tests for Stage B slice 4 — the calibration batch, measured and committed.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 4), R8 and S3
as they were rewritten on 2026-08-25, R1011, R23 and the owner's rulings of
2026-08-24 and 2026-08-25, while the implementation is authored in parallel — so
failing imports are the expected state until assembly.

**Nothing here invokes a model or a usage reader.** The two seams slice 3 already
has — `extract.extract_bundle` and `spend.take_reading` — are faked exactly as
`tests/test_extract_command.py` fakes them, and that file's autouse
`never_shell_out` fixture is imported rather than re-written, so a seam this file
missed cannot quietly become a real `claude -p` that spends against the very
limit under test.

Three conventions this file assumes, each taken from something the repository
already does:

- **The record's JSON keys are the field names of `CalibrationRecord`**, nested
  dataclasses included, exactly as `tests/test_claims.py` assumes for a claims
  file. R1011 makes this file evidence rather than a log line, and evidence is
  read months later by a person with a text editor and no imports.
- **`record_path` takes a batch and nothing else**, so the directory it writes to
  is anchored in the module. That is what lets `records` redirect it into
  `tmp_path` instead of writing into the repository's own `calibration/`, and it
  is also the point of the owner's ruling: the location cannot depend on
  `config.data_dir`, because `data/` is gitignored and R1011 wants the record
  committed.
- **`estimate` reaches the record through `load_latest`**, so the projection's
  preference can be exercised by replacing that one name — on whichever module
  binds it — rather than by planting files under the repository root.

The numbers are chosen so that a defect is visible rather than merely possible.
The four token components differ by orders of magnitude the way the owner's own
machine reports them, and no two of them sum to any third, to any other pair, or
to anything else the record carries — so a run that summed them, or swapped two
of them, cannot produce a record this file accepts.

What this file deliberately does NOT pin, because the plan does not rule it: which
token components the corrected factor is divided by (only that the result is
characters per token and not its inverse), the numerator of the
`tokens_per_point` conversion (only that it is absent when the meter did not
move), and whether a batch stopped by the R26 ceiling records anything at all.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as in
# tests/test_claims.py and tests/test_extract_command.py: `find_best_mobo.calibration`
# does not exist yet, so the isort rule classifies it as third-party and would
# demand a different grouping from the one it demands once it lands. The block is
# written in its post-assembly order, which is the stable one.
from __future__ import annotations

import inspect
import itertools
import json
from dataclasses import asdict, fields
from datetime import date
from pathlib import Path

import pytest

import find_best_mobo
from find_best_mobo import calibration
from find_best_mobo import estimate as estimate_module
from find_best_mobo import extract as extract_module
from find_best_mobo import spend
from find_best_mobo.bundle import Bundle, write_bundles
from find_best_mobo.calibration import (
    CalibrationRecord,
    TokenActual,
    load_latest,
    measured_factor,
    record_path,
    write_record,
)
from find_best_mobo.commands import extract as extract_command
from find_best_mobo.config import Config
from find_best_mobo.estimate import Projection, project, render_projection
from find_best_mobo.excerpt import Excerpt
from find_best_mobo.extract import ExtractionResult
from find_best_mobo.spend import WEEKLY_LABEL, Reading

# The one fixture this file borrows rather than copies: no test in it may start a
# real process, and the reason is the same one it was written for.
from test_extract_command import never_shell_out  # noqa: F401

REPO_ROOT = Path(find_best_mobo.__file__).resolve().parents[2]

# A model name that is plainly a name and not a default, because there is no
# default in code: `config.extraction_model` is unset until `config.toml` says
# otherwise, and a record that cannot name its model is not evidence.
MODEL = "claude-opus-5-1m"

# The owner's real week sits well above the cap, which is why the readings start
# here rather than at zero (R26 caps the effort, not the account).
BEFORE_PERCENT = 0.43
AFTER_PERCENT = 0.47
POINTS_DELTA = 0.04

TAKEN_BEFORE = "2026-08-25T09:00:00+00:00"
TAKEN_AFTER = "2026-08-25T09:41:00+00:00"
PRIMARY_READER = "omarchy-agent-usage-claude --limits-only --force"

# The plan's calibration batch, at the size the owner ruled on 2026-08-25.
CALIBRATION_SIZE = 12

# One call's four components, in the proportions the owner measured: cache reads
# outnumber fresh input by orders of magnitude, which is exactly why a summed
# total says nothing. Over a 12-bundle batch these come to
# (9600, 2400, 18000, 480000) — four numbers no two of which sum to a third, and
# none of which can be mistaken for another if a pair is swapped.
PER_CALL_INPUT = 800
PER_CALL_OUTPUT = 200
PER_CALL_CACHE_CREATION = 1500
PER_CALL_CACHE_READ = 40000

# Long enough that characters per token lands in the region a real corpus lands
# in: 4000 characters a bundle over twelve bundles is 48,000 characters against
# 9,600 fresh input tokens, so a factor computed the right way round is about 5
# and a factor computed upside down is about 0.2.
BUNDLE_CHARACTERS = 4000

ASSUMPTIONS = (
    "The token figure is summed over this batch's own calls, never a usage tool's daily total.",
    "The points figure is the Weekly (7-day) reading, reported in whole percentage points.",
    "The conversion between the two is an ESTIMATE; nothing in the pipeline reads it as an input.",
)


# --- building records by hand -------------------------------------------------


def reading(percent: float, taken_at: str = TAKEN_BEFORE, source: str = PRIMARY_READER) -> Reading:
    return Reading(label=WEEKLY_LABEL, percent=percent, taken_at=taken_at, source=source)


def make_record(**overrides: object) -> CalibrationRecord:
    """A complete record, every field carrying something recognisable.

    `measured_chars_per_token` is hand-computed and not taken from anything the
    implementation does: 240,000 characters of bundle text divided by 50,000
    tokens the calls reported is 4.8 characters per token.
    """
    base: dict[str, object] = {
        "batch": 1,
        "model": MODEL,
        "projected_tokens": 12_600,
        "actual": TokenActual(
            input_tokens=9_600,
            output_tokens=2_400,
            cache_creation_tokens=18_000,
            cache_read_tokens=480_000,
        ),
        "measured_chars_per_token": 240_000 / 50_000,
        "points_before": reading(BEFORE_PERCENT, TAKEN_BEFORE),
        "points_after": reading(AFTER_PERCENT, TAKEN_AFTER),
        "points_delta": POINTS_DELTA,
        "tokens_per_point": 315_000.0,
        "conversion_assumptions": ASSUMPTIONS,
        "recorded_at": "2026-08-25T09:41:07+00:00",
    }
    return CalibrationRecord(**(base | overrides))  # type: ignore[arg-type]


def components_of(record: CalibrationRecord) -> tuple[int, int, int, int]:
    return (
        record.actual.input_tokens,
        record.actual.output_tokens,
        record.actual.cache_creation_tokens,
        record.actual.cache_read_tokens,
    )


def every_partial_sum(components: tuple[int, ...]) -> set[float]:
    """Every number a run that summed the components could have written down."""
    sums: set[float] = set()
    for size in (2, 3, 4):
        for combination in itertools.combinations(components, size):
            sums.add(float(sum(combination)))
    return sums


def numbers_in(payload: object) -> list[float]:
    """Every number anywhere in a record, however deeply it is nested."""
    if isinstance(payload, bool) or payload is None:
        return []
    if isinstance(payload, (int, float)):
        return [float(payload)]
    if isinstance(payload, dict):
        return [number for value in payload.values() for number in numbers_in(value)]
    if isinstance(payload, (list, tuple)):
        return [number for value in payload for number in numbers_in(value)]
    return []


def repo_relative(path: Path) -> tuple[str, ...]:
    """Where a path sits inside the repository, however it is anchored.

    A record git can track is a record inside the checkout; anything else fails
    here rather than in the acceptance script months later.
    """
    resolved = (path if path.is_absolute() else REPO_ROOT / path).resolve()
    assert resolved.is_relative_to(REPO_ROOT), (
        f"the calibration record at {resolved} is outside the repository at {REPO_ROOT}, "
        "so git cannot track it and R1011's committed evidence does not exist"
    )
    return resolved.relative_to(REPO_ROOT).parts


# --- redirecting the tracked directory ----------------------------------------


def redirect(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    """Point the calibration module's record directory into `root`.

    The module anchors its own directory — `record_path` takes only a batch — so
    every module-level `Path` it holds is redirected and the module is asked
    afterwards where it would now write. A test suite that wrote real records
    into `calibration/` would leave the repository dirty and, worse, would make
    the next `estimate` prefer a factor measured by a fixture.
    """
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(root)
    for name, value in list(vars(calibration).items()):
        if isinstance(value, Path):
            monkeypatch.setattr(calibration, name, root)
    written = record_path(1)
    assert written.is_relative_to(root), (
        f"`record_path` still points at {written} after every module-level Path in "
        f"`find_best_mobo.calibration` was redirected to {root}. The record directory has to be "
        "reachable as a module-level constant, or a test run writes into the repository's own "
        "tracked `calibration/`."
    )
    return written.parent


@pytest.fixture
def records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The redirected record directory, empty and not yet created."""
    return redirect(monkeypatch, tmp_path / "repo")


# --- driving one whole batch --------------------------------------------------


def make_config(data_dir: Path, chars_per_token: float = 4.0) -> Config:
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
        chars_per_token=chars_per_token,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
        extraction_model=MODEL,
    )


def write_calibration_batch(config: Config, count: int = CALIBRATION_SIZE) -> None:
    """Lay down a real batch of bundles where Stage A puts them."""
    bundles = tuple(
        Bundle(
            bundle_id=f"bundle-{number:03d}",
            batch=1,
            excerpts=(
                Excerpt(
                    video_id=f"vid{number:08d}abc",
                    video_title=f"X670E VRM breakdown, part {number}",
                    start_seconds=0.0,
                    end_seconds=600.0,
                    text="the VRM on this one is genuinely overbuilt. " * (BUNDLE_CHARACTERS // 43),
                    canonicals=("ASRock X670E Taichi",),
                ),
            ),
            projected_tokens=BUNDLE_CHARACTERS // 4,
        )
        for number in range(1, count + 1)
    )
    write_bundles(bundles, config)


def valid_claims(bundle_id: str) -> str:
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


class FakeBatch:
    """The meter and the model, faked — and a log of what each was asked.

    `percents` is what the meter answers, in order; the last answer repeats once
    the list runs out, so a run that takes four readings and a run that takes
    three both end on the same closing figure.
    """

    def __init__(
        self,
        percents: tuple[float, ...] = (BEFORE_PERCENT, AFTER_PERCENT),
        scale: int = 1,
    ) -> None:
        self.percents = percents
        self.scale = scale
        self.readings: list[float] = []
        self.calls: list[str] = []

    def take_reading(self, config: Config) -> Reading:
        percent = self.percents[min(len(self.readings), len(self.percents) - 1)]
        self.readings.append(percent)
        return Reading(
            label=WEEKLY_LABEL,
            percent=percent,
            taken_at=TAKEN_BEFORE if len(self.readings) == 1 else TAKEN_AFTER,
            source=PRIMARY_READER,
        )

    def extract_bundle(self, bundle_path: Path, batch: int, config: Config) -> ExtractionResult:
        bundle_id = Path(bundle_path).stem
        self.calls.append(bundle_id)
        directory = config.data_dir / "claims" / f"batch-{batch}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{bundle_id}.json"
        path.write_text(valid_claims(bundle_id), encoding="utf-8")
        return ExtractionResult(
            bundle_id=bundle_id,
            claims_path=path,
            input_tokens=PER_CALL_INPUT * self.scale,
            output_tokens=PER_CALL_OUTPUT * self.scale,
            cache_creation_tokens=PER_CALL_CACHE_CREATION * self.scale,
            cache_read_tokens=PER_CALL_CACHE_READ * self.scale,
        )


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


def measure(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    percents: tuple[float, ...] = (BEFORE_PERCENT, AFTER_PERCENT),
    scale: int = 1,
    chars_per_token: float = 4.0,
) -> CalibrationRecord:
    """Run one whole calibration batch and hand back the record it committed."""
    config = make_config(root / "data", chars_per_token=chars_per_token)
    write_calibration_batch(config)
    redirect(monkeypatch, root / "repo")
    install(monkeypatch, FakeBatch(percents=percents, scale=scale))

    code = extract_command.run(config, extract_command.parse_args(["--batch", "1"]))
    assert code == 0, "the calibration batch did not run to completion"

    record = load_latest()
    assert record is not None, (
        f"the batch ran and nothing was committed to {record_path(1)}. R1011 makes the "
        "measurement evidence rather than console output, so a run that measures and does not "
        "write has produced nothing S3 can read."
    )
    return record


# --- installing a record under `estimate` -------------------------------------


def install_record(monkeypatch: pytest.MonkeyPatch, record: CalibrationRecord | None) -> None:
    """Make `load_latest` answer with `record`, on whichever module binds it."""
    targets = [
        module for module in (calibration, estimate_module) if hasattr(module, "load_latest")
    ]
    assert targets, (
        "neither `find_best_mobo.calibration` nor `find_best_mobo.estimate` exposes "
        "`load_latest`, so the projection cannot be shown a record"
    )
    for module in targets:
        monkeypatch.setattr(module, "load_latest", lambda: record)


def projection_over_nothing(tmp_path: Path) -> Projection:
    """A projection over an empty but present corpus, so only the factor varies."""
    config = make_config(tmp_path / "data")
    config.data_dir.mkdir(parents=True, exist_ok=True)
    (config.data_dir / "index.jsonl").write_text("", encoding="utf-8")
    return project((), (), (), config)


# --- where the record lives ---------------------------------------------------


class TestWhereTheRecordLives:
    """The owner's ruling of 2026-08-25: one tracked file, and no `data/` copy.

    This is the whole point of the ruling and the reason it was HIGH risk. `data/`
    is gitignored (R21), and R1011 requires committed evidence — so a record under
    `config.data_dir` is a record that never reaches a pull request, and
    `acceptance/S3.sh` would read a file that exists only on the machine that
    wrote it.
    """

    def test_the_record_is_named_for_its_batch(self) -> None:
        assert record_path(1).name == "batch-1.json"
        assert record_path(7).name == "batch-7.json"

    def test_the_record_sits_in_the_tracked_calibration_directory(self) -> None:
        assert repo_relative(record_path(1)) == ("calibration", "batch-1.json")

    def test_two_batches_do_not_share_a_file(self) -> None:
        assert record_path(1) != record_path(2)

    def test_the_location_cannot_depend_on_the_gitignored_corpus_directory(self) -> None:
        """`record_path` takes a batch and nothing else — no `Config`, so no `data_dir`."""
        parameters = tuple(inspect.signature(record_path).parameters)
        assert parameters == ("batch",), (
            f"`record_path` takes {parameters}. The owner ruled the record lives at "
            "calibration/batch-<n>.json, which no configuration decides."
        )

    def test_the_record_is_not_inside_the_corpus_directory(self) -> None:
        assert repo_relative(record_path(1))[0] != "data"

    def test_git_does_not_ignore_the_record(self) -> None:
        """R1011: committed evidence. An ignored record is a console line with a filename."""
        parts = repo_relative(record_path(1))
        ignored = {
            line.strip().strip("/")
            for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        assert not ignored & set(parts), (
            f"`.gitignore` ignores part of {'/'.join(parts)}, so the record can never be committed"
        )

    def test_no_second_copy_is_written_under_the_corpus_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BL-26 named `data/calibration.json`; R1011 moved it and left no copy behind.

        "A restated number elsewhere is never a second source" — R1011's own words,
        and the reason the ruling names ONE file.
        """
        record = measure(tmp_path, monkeypatch)
        assert record.batch == 1
        data_dir = tmp_path / "data"
        strays = [
            path
            for path in data_dir.rglob("*")
            if path.is_file() and "calibration" in path.name.lower()
        ]
        assert strays == [], f"a second copy of the record was written under {data_dir}: {strays}"


class TestTheAcceptanceScriptLandsWithTheRecord:
    """R1011: `acceptance/S3.sh` lands in the same change as the first real record.

    Never before it, so no pull request is red for a record that cannot yet exist —
    and never after it either, because a committed record nothing checks is back to
    being a number nobody reads.
    """

    def test_the_script_and_the_first_record_arrive_together(self) -> None:
        script = REPO_ROOT / "acceptance" / "S3.sh"
        first_record = record_path(1)
        assert script.exists() == first_record.exists(), (
            f"{script} exists: {script.exists()}, {first_record} exists: "
            f"{first_record.exists()} — S3.sh lands with the first real record, never apart "
            "from it (R1011)."
        )

    def test_the_script_reads_the_tracked_record_and_not_a_corpus_copy(self) -> None:
        script = REPO_ROOT / "acceptance" / "S3.sh"
        if not script.exists():
            pytest.skip("no S3.sh yet, which is correct until the first record is committed")
        text = script.read_text(encoding="utf-8")
        assert "calibration/batch-" in text, "S3.sh must read the tracked calibration record"
        assert "data/calibration.json" not in text, (
            "S3.sh reads `data/calibration.json`, which the owner's 2026-08-25 ruling replaced: "
            "`data/` is gitignored, so that file is never evidence"
        )


# --- the record as evidence ---------------------------------------------------


class TestTheRecordRoundTrips:
    """R1011: a reading that scrolled away is not evidence, and neither is one
    nobody can read back."""

    def test_writing_returns_the_path_the_record_belongs_at(self, records: Path) -> None:
        assert write_record(make_record(batch=3)) == record_path(3)

    def test_the_written_file_exists(self, records: Path) -> None:
        assert write_record(make_record()).is_file()

    def test_the_file_is_json(self, records: Path) -> None:
        path = write_record(make_record())
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_loading_returns_the_record_that_was_written(self, records: Path) -> None:
        record = make_record()
        write_record(record)
        assert load_latest() == record

    def test_every_field_survives_the_round_trip(self, records: Path) -> None:
        record = make_record()
        write_record(record)
        loaded = load_latest()
        assert loaded is not None
        for field in fields(record):
            assert getattr(loaded, field.name) == getattr(record, field.name), (
                f"`{field.name}` did not survive being written and read back"
            )

    def test_the_readings_survive_whole_and_not_just_their_percentages(self, records: Path) -> None:
        """Which reader answered is part of the evidence (R26, BL-24's ruling)."""
        write_record(make_record())
        loaded = load_latest()
        assert loaded is not None
        assert loaded.points_before == reading(BEFORE_PERCENT, TAKEN_BEFORE)
        assert loaded.points_after == reading(AFTER_PERCENT, TAKEN_AFTER)

    def test_the_conversion_assumptions_survive_in_order(self, records: Path) -> None:
        """R8: an estimate whose assumptions are not stored beside it can only be replaced."""
        write_record(make_record())
        loaded = load_latest()
        assert loaded is not None
        assert tuple(loaded.conversion_assumptions) == ASSUMPTIONS

    def test_a_record_with_no_assumptions_at_all_is_still_read_back_as_none(
        self, records: Path
    ) -> None:
        write_record(make_record(conversion_assumptions=()))
        loaded = load_latest()
        assert loaded is not None
        assert tuple(loaded.conversion_assumptions) == ()

    def test_the_measured_factor_survives_to_its_last_digit(self, records: Path) -> None:
        """A factor rounded on the way to disk is a different correction."""
        write_record(make_record(measured_chars_per_token=3.742987132))
        loaded = load_latest()
        assert loaded is not None
        assert loaded.measured_chars_per_token == 3.742987132

    def test_nothing_written_at_all_reads_back_as_nothing(self, records: Path) -> None:
        assert load_latest() is None

    def test_an_empty_directory_reads_back_as_nothing(self, records: Path) -> None:
        record_path(1).parent.mkdir(parents=True, exist_ok=True)
        assert load_latest() is None

    def test_the_latest_record_is_the_latest_batch(self, records: Path) -> None:
        write_record(make_record(batch=1, measured_chars_per_token=4.0))
        write_record(make_record(batch=2, measured_chars_per_token=3.1))
        loaded = load_latest()
        assert loaded is not None
        assert loaded.batch == 2
        assert loaded.measured_chars_per_token == 3.1

    def test_the_latest_record_is_not_merely_the_last_file_written(self, records: Path) -> None:
        """Batches are numbered; the order someone happened to write them is not evidence."""
        write_record(make_record(batch=2, measured_chars_per_token=3.1))
        write_record(make_record(batch=1, measured_chars_per_token=4.0))
        loaded = load_latest()
        assert loaded is not None
        assert loaded.batch == 2

    def test_an_earlier_record_is_not_overwritten_by_a_later_one(self, records: Path) -> None:
        write_record(make_record(batch=1))
        write_record(make_record(batch=2))
        assert record_path(1).is_file()
        assert record_path(2).is_file()


class TestWhatTheFileItselfSays:
    """Read months later, by a person with a text editor and no imports."""

    @pytest.fixture
    def payload(self, records: Path) -> dict[str, object]:
        path = write_record(make_record())
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)
        return loaded

    def test_every_field_of_the_record_is_named_in_the_file(
        self, payload: dict[str, object]
    ) -> None:
        expected = {field.name for field in fields(make_record())}
        assert expected <= set(payload), (
            f"the record's file is missing {sorted(expected - set(payload))}"
        )

    def test_the_file_names_the_model_it_measured(self, payload: dict[str, object]) -> None:
        """A factor measured against one model does not transfer to another."""
        assert payload["model"] == MODEL

    def test_the_file_names_the_batch_it_measured(self, payload: dict[str, object]) -> None:
        assert payload["batch"] == 1

    def test_the_file_says_when_it_was_measured(self, payload: dict[str, object]) -> None:
        assert payload["recorded_at"] == "2026-08-25T09:41:07+00:00"

    def test_the_four_components_are_four_separate_numbers_in_the_file(
        self, payload: dict[str, object]
    ) -> None:
        actual = payload["actual"]
        assert isinstance(actual, dict)
        assert actual["input_tokens"] == 9_600
        assert actual["output_tokens"] == 2_400
        assert actual["cache_creation_tokens"] == 18_000
        assert actual["cache_read_tokens"] == 480_000

    def test_the_file_carries_the_readings_that_bracket_the_batch(
        self, payload: dict[str, object]
    ) -> None:
        before, after = payload["points_before"], payload["points_after"]
        assert isinstance(before, dict) and isinstance(after, dict)
        assert before["percent"] == BEFORE_PERCENT
        assert after["percent"] == AFTER_PERCENT
        assert before["label"] == WEEKLY_LABEL
        assert before["source"] == PRIMARY_READER

    def test_the_file_carries_the_assumptions_as_text(self, payload: dict[str, object]) -> None:
        assumptions = payload["conversion_assumptions"]
        assert isinstance(assumptions, list)
        assert assumptions == list(ASSUMPTIONS)


class TestTheRecordRendersTheSameBytesTwice:
    """R23. Two runs over the same measurement must be a no-op diff, or a
    committed record becomes noise in every later pull request."""

    def test_writing_the_same_record_twice_produces_the_same_bytes(self, records: Path) -> None:
        record = make_record()
        first = write_record(record).read_bytes()
        second = write_record(record).read_bytes()
        assert first == second

    def test_two_equal_records_produce_the_same_bytes(self, records: Path) -> None:
        first = write_record(make_record()).read_bytes()
        second = write_record(make_record()).read_bytes()
        assert first == second

    def test_the_time_written_down_is_the_records_own_and_not_the_clocks(
        self, records: Path
    ) -> None:
        """`recorded_at` is a field. A writer that stamped its own clock instead
        would make every rewrite a diff, and R23 unfalsifiable."""
        first = write_record(make_record(recorded_at="2026-01-01T00:00:00+00:00")).read_bytes()
        second = write_record(make_record(recorded_at="2026-02-02T00:00:00+00:00")).read_bytes()
        assert first != second
        assert b"2026-02-02T00:00:00+00:00" in second

    def test_two_different_records_do_not_produce_the_same_bytes(self, records: Path) -> None:
        first = write_record(make_record()).read_bytes()
        second = write_record(make_record(measured_chars_per_token=2.5)).read_bytes()
        assert first != second


# --- the two quantities -------------------------------------------------------


class TestTheFourComponentsAreNeverSummed:
    """R8 as amended: a cache read is not billed as fresh input, and on the
    owner's machine cache reads outnumber fresh input by more than four orders of
    magnitude — so a summed figure is dominated by the cheapest tokens in it."""

    def test_the_four_components_are_each_present_and_distinct(self) -> None:
        components = components_of(make_record())
        assert len(set(components)) == 4, "the fixture's own components must be tellable apart"

    def test_no_number_on_the_record_is_a_sum_of_the_components(self) -> None:
        record = make_record()
        forbidden = every_partial_sum(components_of(record))
        found = forbidden & set(numbers_in(asdict(record)))
        assert not found, (
            f"the record carries {sorted(found)}, which is a sum of the token components. "
            "R8 as amended forbids the four ever becoming one number."
        )

    def test_no_number_in_the_written_file_is_a_sum_of_the_components(self, records: Path) -> None:
        record = make_record()
        path = write_record(record)
        forbidden = every_partial_sum(components_of(record))
        found = forbidden & set(numbers_in(json.loads(path.read_text(encoding="utf-8"))))
        assert not found, f"the committed file carries the summed figure {sorted(found)}"

    def test_the_components_survive_a_round_trip_unswapped(self, records: Path) -> None:
        write_record(make_record())
        loaded = load_latest()
        assert loaded is not None
        assert components_of(loaded) == (9_600, 2_400, 18_000, 480_000)


class TestTokensPerPointIsAResultAndNotAFailure:
    """The reader returns whole percentages, so a batch consuming less than one
    full point reads identically before and after. The owner kept the batch at 12
    knowing this (2026-08-25): "unmeasurable at this batch size" is a finding."""

    def test_a_meter_that_did_not_move_records_none(self, records: Path) -> None:
        record = make_record(
            points_after=reading(BEFORE_PERCENT, TAKEN_AFTER),
            points_delta=0.0,
            tokens_per_point=None,
        )
        write_record(record)
        loaded = load_latest()
        assert loaded is not None
        assert loaded.tokens_per_point is None

    def test_none_is_not_read_back_as_zero(self, records: Path) -> None:
        write_record(make_record(points_delta=0.0, tokens_per_point=None))
        loaded = load_latest()
        assert loaded is not None
        assert loaded.tokens_per_point != 0, (
            "a conversion that could not be measured was written down as zero tokens per "
            "point, which is a measurement nobody made"
        )

    def test_the_field_is_present_in_the_file_rather_than_omitted(self, records: Path) -> None:
        """An absent key and an unmeasurable conversion are different facts."""
        path = write_record(make_record(points_delta=0.0, tokens_per_point=None))
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "tokens_per_point" in payload
        assert payload["tokens_per_point"] is None

    def test_a_measurable_conversion_survives_as_a_number(self, records: Path) -> None:
        write_record(make_record(tokens_per_point=315_000.0))
        loaded = load_latest()
        assert loaded is not None
        assert loaded.tokens_per_point == 315_000.0

    def test_an_unmeasurable_conversion_does_not_stop_the_factor_being_recorded(
        self, records: Path
    ) -> None:
        write_record(make_record(points_delta=0.0, tokens_per_point=None))
        loaded = load_latest()
        assert loaded is not None
        assert measured_factor(loaded) == 4.8


class TestMeasuredFactor:
    """Characters divided by tokens — the correction that makes the next
    projection right."""

    def test_it_is_the_measurement_the_record_carries(self) -> None:
        record = make_record(measured_chars_per_token=240_000 / 50_000)
        assert measured_factor(record) == pytest.approx(4.8)

    def test_it_is_characters_per_token_and_not_its_inverse(self) -> None:
        """50,000 tokens for 240,000 characters is 4.8, not 0.208."""
        record = make_record(measured_chars_per_token=240_000 / 50_000)
        assert measured_factor(record) == pytest.approx(240_000 / 50_000)
        assert measured_factor(record) != pytest.approx(50_000 / 240_000)

    def test_a_batch_that_cost_more_tokens_than_projected_corrects_the_factor_down(self) -> None:
        """Twice the tokens for the same characters is half the characters per token."""
        record = make_record(measured_chars_per_token=240_000 / 100_000)
        assert measured_factor(record) == pytest.approx(2.4)
        assert measured_factor(record) < 4.0

    def test_it_ignores_the_conversion_assumptions_beside_it(self) -> None:
        """R8: the assumptions are recorded, and nothing reads them as an input."""
        plain = make_record(conversion_assumptions=())
        annotated = make_record(conversion_assumptions=("anything at all",))
        assert measured_factor(plain) == measured_factor(annotated)

    def test_it_ignores_the_points_readings_entirely(self) -> None:
        """Neither quantity is derived from the other (R8)."""
        quiet = make_record(
            points_after=reading(BEFORE_PERCENT, TAKEN_AFTER),
            points_delta=0.0,
            tokens_per_point=None,
        )
        moved = make_record()
        assert measured_factor(quiet) == measured_factor(moved)


# --- the batch, measured ------------------------------------------------------


class TestTheCalibrationBatchIsMeasuredAndCommitted:
    """One real run of the batch, with the model and the meter faked, and the
    record it leaves behind."""

    @pytest.fixture
    def record(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CalibrationRecord:
        return measure(tmp_path, monkeypatch)

    def test_the_record_is_written_where_the_owner_ruled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        measure(tmp_path, monkeypatch)
        assert record_path(1).is_file()

    def test_it_names_the_batch_it_measured(self, record: CalibrationRecord) -> None:
        assert record.batch == 1

    def test_it_names_the_model_it_measured(self, record: CalibrationRecord) -> None:
        """A record that does not say which model it measured is not evidence."""
        assert record.model == MODEL

    def test_the_model_is_not_left_blank(self, record: CalibrationRecord) -> None:
        assert record.model.strip(), (
            "the record does not name a model, so nothing in it transfers to the next batch"
        )

    def test_the_token_actual_is_summed_over_the_batchs_own_calls(
        self, record: CalibrationRecord
    ) -> None:
        """Never a usage tool's daily total, which includes every other session."""
        assert record.actual.input_tokens == PER_CALL_INPUT * CALIBRATION_SIZE
        assert record.actual.output_tokens == PER_CALL_OUTPUT * CALIBRATION_SIZE
        assert record.actual.cache_creation_tokens == PER_CALL_CACHE_CREATION * CALIBRATION_SIZE
        assert record.actual.cache_read_tokens == PER_CALL_CACHE_READ * CALIBRATION_SIZE

    def test_the_four_components_are_not_summed_anywhere_on_the_record(
        self, record: CalibrationRecord
    ) -> None:
        forbidden = every_partial_sum(components_of(record))
        found = forbidden & set(numbers_in(asdict(record)))
        assert not found, f"the run wrote down the summed figure {sorted(found)} (R8 forbids it)"

    def test_the_points_readings_bracket_the_batch(self, record: CalibrationRecord) -> None:
        assert record.points_before.percent == BEFORE_PERCENT
        assert record.points_after.percent == AFTER_PERCENT
        assert record.points_before.label == WEEKLY_LABEL
        assert record.points_after.label == WEEKLY_LABEL

    def test_the_points_delta_is_the_difference_between_them(
        self, record: CalibrationRecord
    ) -> None:
        assert record.points_delta == pytest.approx(POINTS_DELTA)

    def test_the_reading_records_which_reader_answered(self, record: CalibrationRecord) -> None:
        assert record.points_before.source == PRIMARY_READER

    def test_the_projection_is_a_token_figure_of_its_own(self, record: CalibrationRecord) -> None:
        assert record.projected_tokens > 0

    def test_the_corrected_factor_is_characters_per_token(self, record: CalibrationRecord) -> None:
        """48,000 characters of bundle text against 9,600 fresh input tokens.

        The exact divisor is the implementation's to choose — fresh input, or
        fresh input and cache creation together — so what is pinned here is the
        direction: a chars-per-token factor is greater than one, and an inverted
        one, or one taken over the four components summed, is far below it.
        """
        assert 1.0 < record.measured_chars_per_token < 20.0, (
            f"a corrected factor of {record.measured_chars_per_token} is not characters per "
            "token: either the division is inverted, or the four components were summed"
        )

    def test_the_record_says_what_the_conversion_assumed(self, record: CalibrationRecord) -> None:
        """R8: every assumption written out rather than implied."""
        assumptions = tuple(record.conversion_assumptions)
        assert assumptions, (
            "the token-to-points conversion was recorded with no assumptions beside it. "
            "An estimate whose assumptions are not stored cannot be corrected, only replaced."
        )
        joined = " ".join(assumptions).lower()
        assert "token" in joined and "point" in joined, (
            f"the assumptions do not mention both quantities they convert between: {assumptions}"
        )


class TestNeitherQuantityIsDerivedFromTheOther:
    """R8's central rule, and the one a plausible implementation gets wrong by
    computing the points cost from the tokens or the factor from the points."""

    def test_ten_times_the_tokens_does_not_move_the_meter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        modest = measure(tmp_path / "modest", monkeypatch, scale=1)
        lavish = measure(tmp_path / "lavish", monkeypatch, scale=10)

        assert lavish.actual.input_tokens == modest.actual.input_tokens * 10
        assert lavish.points_delta == pytest.approx(modest.points_delta), (
            "ten times the tokens changed what the batch cost the weekly limit, so the points "
            "were derived from the tokens rather than read from the meter (R8)"
        )
        assert lavish.points_after.percent == modest.points_after.percent

    def test_a_meter_that_moved_further_does_not_change_the_token_counts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Both stay under the R26 ceiling this batch fixed at 53%, so what differs
        # between the two runs is the meter and nothing else.
        quiet = measure(tmp_path / "quiet", monkeypatch, percents=(0.43, 0.44))
        loud = measure(tmp_path / "loud", monkeypatch, percents=(0.43, 0.52))

        assert quiet.points_delta != pytest.approx(loud.points_delta)
        assert components_of(quiet) == components_of(loud), (
            "a different meter reading changed the token counts, so the tokens were derived "
            "from the points rather than from the run's own calls (R8)"
        )
        assert quiet.measured_chars_per_token == pytest.approx(loud.measured_chars_per_token), (
            "the corrected factor moved with the meter. Tokens correct the factor because both "
            "sides are tokens; points say what the batch cost the weekly limit (R8)."
        )

    def test_a_meter_that_did_not_move_still_corrects_the_factor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The owner's 2026-08-25 ruling: the factor correction does not need the meter."""
        record = measure(tmp_path, monkeypatch, percents=(BEFORE_PERCENT,))

        assert record.points_delta == pytest.approx(0.0)
        assert record.tokens_per_point is None, (
            "the meter did not move and the conversion was written down anyway. Below one whole "
            "percentage point the conversion is unmeasurable, and that is the finding."
        )
        assert 1.0 < record.measured_chars_per_token < 20.0
        assert record.actual.input_tokens == PER_CALL_INPUT * CALIBRATION_SIZE

    def test_an_unmeasurable_conversion_is_not_a_failed_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        measure(tmp_path, monkeypatch, percents=(BEFORE_PERCENT,))
        assert record_path(1).is_file()

    def test_the_projection_is_the_configured_factors_and_the_measurement_is_not(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Doubling the guess halves the projection and leaves the measurement alone.

        The projected figure is what the configuration predicted; the corrected
        factor is characters over the tokens the calls actually reported, and the
        guess cannot appear in it.
        """
        guessed = measure(tmp_path / "guessed", monkeypatch, chars_per_token=4.0)
        doubled = measure(tmp_path / "doubled", monkeypatch, chars_per_token=8.0)

        assert doubled.projected_tokens == pytest.approx(guessed.projected_tokens / 2, rel=0.02)
        assert doubled.measured_chars_per_token == pytest.approx(
            guessed.measured_chars_per_token, rel=0.02
        ), "the corrected factor moved with the guess it exists to replace"


# --- what estimate does with it -----------------------------------------------


class TestEstimatePrefersTheMeasurement:
    """BL-26's ruling, which the owner's 2026-08-25 ruling kept whole: the
    measured factor is preferred, the source is printed, and the configuration key
    stays the fallback."""

    def test_without_a_record_the_projection_uses_the_configured_guess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_record(monkeypatch, None)
        projection = projection_over_nothing(tmp_path)
        assert projection.chars_per_token == 4.0

    def test_without_a_record_the_factor_is_named_as_a_guess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_record(monkeypatch, None)
        text = render_projection(projection_over_nothing(tmp_path)).lower()
        assert "estimate" in text or "guess" in text, (
            "the projection presented an unmeasured factor without saying it was unmeasured"
        )

    def test_with_a_record_the_projection_uses_the_measured_factor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_record(monkeypatch, make_record(batch=2, measured_chars_per_token=3.2))
        projection = projection_over_nothing(tmp_path)
        assert projection.chars_per_token == pytest.approx(3.2), (
            "the projection kept the configured guess although a measurement was committed"
        )

    def test_the_measured_factor_is_the_one_printed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_record(monkeypatch, make_record(batch=2, measured_chars_per_token=3.2))
        text = render_projection(projection_over_nothing(tmp_path))
        assert "3.2" in text

    def test_the_projection_names_the_record_it_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Printing a corrected number without saying where it came from leaves the
        reader unable to tell a measurement from a changed default."""
        install_record(monkeypatch, make_record(batch=2, measured_chars_per_token=3.2))
        text = render_projection(projection_over_nothing(tmp_path))
        assert record_path(2).name in text, (
            f"the projection used the measured factor without naming {record_path(2)}"
        )

    def test_the_projection_says_the_number_is_a_measurement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_record(monkeypatch, make_record(batch=2, measured_chars_per_token=3.2))
        text = render_projection(projection_over_nothing(tmp_path)).lower()
        assert "measur" in text
        assert "not a measurement" not in text, (
            "the projection used a measured factor and went on calling it an estimate"
        )

    def test_the_configuration_key_is_not_rewritten_by_the_projection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stage that edits its own configuration makes R23's "same cache and
        configuration" unfalsifiable."""
        install_record(monkeypatch, make_record(batch=2, measured_chars_per_token=3.2))
        config = make_config(tmp_path / "data")
        config.data_dir.mkdir(parents=True, exist_ok=True)
        (config.data_dir / "index.jsonl").write_text("", encoding="utf-8")

        render_projection(project((), (), (), config))

        assert config.chars_per_token == 4.0

    def test_the_projection_writes_nothing_at_all(self) -> None:
        source = (REPO_ROOT / "src" / "find_best_mobo" / "estimate.py").read_text(encoding="utf-8")
        for forbidden in ("write_text", "write_bytes", "tomli_w", "tomlkit"):
            assert forbidden not in source, (
                f"`estimate.py` contains `{forbidden}`. The projection reads the measurement and "
                "corrects nothing on disk; the configuration key is never rewritten by a stage."
            )

    def test_a_run_of_the_batch_does_not_rewrite_the_configuration_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = tmp_path / "repo" / "config.toml"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('chars_per_token = 4.0\nextraction_model = "x"\n', encoding="utf-8")
        before = settings.read_bytes()

        measure(tmp_path, monkeypatch)

        assert settings.read_bytes() == before, (
            "the calibration run rewrote config.toml. The measured factor lives in the "
            "committed record; the configuration key stays the fallback (BL-26's ruling)."
        )


class TestNothingHereSpends:
    """The suite runs offline, free, and identically on a machine with no
    subscription at all (R19, R20, S9)."""

    def test_the_calibration_module_starts_no_processes(self) -> None:
        source = (REPO_ROOT / "src" / "find_best_mobo" / "calibration.py").read_text(
            encoding="utf-8"
        )
        assert "subprocess" not in source, (
            "`calibration.py` reaches for a subprocess. The record is written from the "
            "`ExtractionResult`s the batch already produced, never from a usage tool's total."
        )

    def test_writing_and_reading_a_record_touches_nothing_but_its_own_file(
        self, records: Path
    ) -> None:
        write_record(make_record())
        assert load_latest() is not None
        written = sorted(path.name for path in records.rglob("*") if path.is_file())
        assert written == ["batch-1.json"]
