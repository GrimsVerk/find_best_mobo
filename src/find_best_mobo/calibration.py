"""What a batch was projected to cost, what it actually cost, and where that is kept.

R8 requires two quantities after the calibration batch and requires them KEPT
APART. **Tokens against tokens** correct the chars-per-token factor, because both
sides are tokens. **Points against points** say what the batch took out of the
weekly subscription limit. Neither is derived from the other, and the conversion
between them is recorded beside them as a labelled ESTIMATE with every
assumption written out — `conversion_assumptions` is that list, and nothing in
this project reads it as an input. An estimate whose assumptions are not stored
beside it cannot be corrected, only replaced.

**The record is a committed file, not console output** (R1011). Before it, the
projected-versus-actual comparison existed only in one session's terminal, which
is why `docs/DESIGN.md` §13 could call S3 mechanically checkable while nothing
mechanical could check it. `acceptance/S3.sh` reads these files on every pull
request.

**One tracked file per batch, at `calibration/batch-<n>.json`.** The owner ruled
this on 2026-08-25, settling the contradiction the plan's first uncertainty
names: R1011 requires the record OUTSIDE the gitignored corpus directory, and
BL-26's earlier ruling had named `data/calibration.json`, which is inside it. So
R1011 governs the LOCATION and BL-26's ruling governs the SEMANTICS — the factor
is measured, `estimate` prefers it over `config.chars_per_token`, it says which
source it used and whether the number is a measurement or a guess, and the
configuration key is never rewritten by a stage. There is deliberately no
`data/` copy: R1011's own words are that "a restated number elsewhere is never a
second source", and a copy under a gitignored tree is not evidence anyone else
can read.

**The record names the model.** A factor measured against one model does not
transfer to another, so a record that cannot say which model it measured is not
evidence of anything.

**The four token components stay apart here too** (`TokenActual`), for the
reason R8 gives: on the owner's machine cache reads outnumber fresh input by
more than four orders of magnitude, so a summed total is dominated by the
cheapest tokens in it and says nothing about what a batch cost.

Nothing here invokes a model or reads a meter. The record is assembled by the
command that spent the money, because only that run knows which calls were its
own; this module is the shape it is written in and the way it is read back.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from find_best_mobo.spend import Reading

# Where the records live: one directory at the repository root, tracked in git.
#
# Relative to the working directory, like `data_dir` and `alias_table_path`
# before it, and for the same reason — `./scripts/run.sh` runs every stage from
# the repository root, so every path this project reads is anchored there. A
# module-level name rather than a literal inside `record_path` so that the one
# place the location is decided is also the one place a test can move it.
RECORD_DIR = Path("calibration")

_FIELDS = (
    "batch",
    "model",
    "projected_tokens",
    "actual",
    "measured_chars_per_token",
    "points_before",
    "points_after",
    "points_delta",
    "tokens_per_point",
    "conversion_assumptions",
    "recorded_at",
)
_TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens")
_READING_FIELDS = ("label", "percent", "taken_at", "source")


@dataclass(frozen=True)
class TokenActual:
    """What the batch's own calls reported, in four counts that never become one.

    Summed over THE BATCH'S OWN CALLS — retries included, because a call that
    produced a malformed file was still paid for — and never taken from a usage
    tool's daily figure. Measured on 2026-08-25: `todayTotalTokens` is a running
    total for the day covering every session on the machine, so attributing it
    to one batch would be wrong by whatever else the owner did that day.
    """

    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


@dataclass(frozen=True)
class CalibrationRecord:
    """One batch's two quantities, kept apart, with the conversion labelled.

    `points_delta` is in the units `Reading.percent` is in — a fraction of the
    weekly limit, so one percentage point is 0.01. `tokens_per_point` is per
    whole PERCENTAGE POINT, because that is the unit the meter is read in.

    `tokens_per_point` is `None` when the meter did not move, and **that is a
    result, not a failure**. The reader returns whole percentages, so a batch
    consuming less than one full point reads identically before and after. The
    owner kept the calibration batch at 12 bundles knowing this (2026-08-25):
    the factor correction does not need the meter at all, and "unmeasurable at
    this batch size" is a finding worth committing rather than a failure worth
    spending more of the weekly limit to avoid.
    """

    batch: int
    model: str
    projected_tokens: int
    actual: TokenActual
    measured_chars_per_token: float
    points_before: Reading
    points_after: Reading
    points_delta: float
    tokens_per_point: float | None
    conversion_assumptions: tuple[str, ...]
    recorded_at: str


def record_path(batch: int) -> Path:
    """`calibration/batch-<n>.json`. The batch number is the key, not the date.

    Keyed by batch (R1011) rather than by timestamp because the batch is what
    the record describes and what a reader looks it up by. A re-extracted batch
    overwrites its own record rather than accumulating a second one beside it —
    see `write_record`.
    """
    return RECORD_DIR / f"batch-{batch}.json"


def write_record(record: CalibrationRecord) -> Path:
    """Write one record and return where it landed.

    JSON with two-space indent and sorted keys: this file is read in a pull
    request diff by a person deciding whether a spend was reasonable, and a
    single dense line is not read at all. Sorted keys also make two records of
    the same run byte-identical, which is the property that lets a re-run be
    compared with a diff (R23).

    An existing record for the same batch is REPLACED, unlike the claim store,
    which refuses a batch it already holds. The store's refusal exists because a
    doubled batch is invisible once appended; a rewritten record is a diff on a
    tracked file, so git is already the thing that notices. Re-extracting a
    batch after moving the store aside should correct its record, not leave the
    superseded measurement standing as though it still described the run.

    Flushed and fsynced for the reason `claimstore` does it: the run this
    belongs to is one a spend guard may stop mid-batch, and evidence of money
    already spent must survive the stop (R27).
    """
    path = record_path(record.batch)
    payload = json.dumps(asdict(record), indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def load_latest() -> CalibrationRecord | None:
    """The highest-numbered batch's record, or None when none has been written.

    None is a real answer and the ordinary one until the calibration batch has
    run: nothing has been measured yet, so the projection has only its guess to
    go on. It is not an error, and callers say which of the two they used
    (BL-26) rather than printing a number whose provenance the reader has to
    infer.

    Highest BATCH, not most recent file. Batches are ordered and later ones are
    larger, so the latest batch is the best-founded measurement; modification
    times would order by whenever the files happened to be checked out.

    A record that does not parse RAISES rather than being skipped. This is
    committed evidence of a spend that already happened, and a loader that
    quietly fell back to the configured guess would print "estimate" over a
    measurement that exists and is broken.
    """
    latest: tuple[int, Path] | None = None
    for path in RECORD_DIR.glob("batch-*.json"):
        number = path.stem.removeprefix("batch-")
        # A name that is not exactly `batch-<digits>.json` is not a record this
        # module wrote — `batch-1-superseded.json`, say, parked there by hand.
        # The name is the key, so a file that does not carry one is not indexed
        # by it and is left alone rather than refused.
        if not number.isdigit():
            continue
        if latest is None or int(number) > latest[0]:
            latest = (int(number), path)
    if latest is None:
        return None
    return _read(latest[1])


def measured_factor(record: CalibrationRecord) -> float:
    """The measured characters-per-token factor, refused if it is not a factor.

    The one way the preference in `estimate` reaches the number, so the check
    that it is usable arithmetic happens once. A factor of zero or less, or an
    infinity, would not make a projection wrong in a visible way — it would make
    every token figure zero or absurd while the line above still read
    "measurement", which is worse than the guess it replaced.
    """
    factor = record.measured_chars_per_token
    if not math.isfinite(factor) or factor <= 0.0:
        raise ValueError(
            f"{record_path(record.batch)} records a measured factor of {factor}, which is not a "
            "characters-per-token factor. A projection cannot be stated in it."
        )
    return factor


def _read(path: Path) -> CalibrationRecord:
    """One record file, refused with what is wrong with it rather than repaired.

    Strict about unknown keys for the reason `claims.py` is: a key nothing reads
    is a number somebody recorded and believed was being used. Here it would
    most likely be a hand-edited record, and the edit deserves to be noticed at
    the moment it stops meaning what its author thought.
    """
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} is not a readable calibration record: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path} holds {type(payload).__name__}, expected one record object")

    _require_keys(payload, _FIELDS, path)
    record = CalibrationRecord(
        batch=_whole(payload["batch"], "batch", path),
        model=_text(payload["model"], "model", path),
        projected_tokens=_whole(payload["projected_tokens"], "projected_tokens", path),
        actual=_token_actual(payload["actual"], path),
        measured_chars_per_token=_number(
            payload["measured_chars_per_token"], "measured_chars_per_token", path
        ),
        points_before=_reading(payload["points_before"], "points_before", path),
        points_after=_reading(payload["points_after"], "points_after", path),
        points_delta=_number(payload["points_delta"], "points_delta", path),
        tokens_per_point=_optional_number(payload["tokens_per_point"], "tokens_per_point", path),
        conversion_assumptions=_assumptions(payload["conversion_assumptions"], path),
        recorded_at=_text(payload["recorded_at"], "recorded_at", path),
    )
    if record_path(record.batch) != path:
        # The filename is how `load_latest` picks the newest measurement, so a
        # record filed under another batch's name would be returned as evidence
        # about a batch it does not describe.
        raise ValueError(
            f"{path} records batch {record.batch}, which belongs at {record_path(record.batch)}"
        )
    return record


def _token_actual(value: Any, path: Path) -> TokenActual:
    """The four counts, each required — an absent one is not a zero."""
    if not isinstance(value, dict):
        raise ValueError(f"{path}: actual is {type(value).__name__}, expected four token counts")
    _require_keys(value, _TOKEN_FIELDS, path)
    return TokenActual(
        input_tokens=_whole(value["input_tokens"], "actual.input_tokens", path),
        output_tokens=_whole(value["output_tokens"], "actual.output_tokens", path),
        cache_creation_tokens=_whole(
            value["cache_creation_tokens"], "actual.cache_creation_tokens", path
        ),
        cache_read_tokens=_whole(value["cache_read_tokens"], "actual.cache_read_tokens", path),
    )


def _reading(value: Any, field: str, path: Path) -> Reading:
    """One meter reading, with the reader that gave it.

    `source` is required rather than defaulted: a reading taken by the fallback
    started a session and so moved the meter it reported, and a record that
    dropped that could not be told apart afterwards from one that did not.
    """
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {field} is {type(value).__name__}, expected a reading")
    _require_keys(value, _READING_FIELDS, path)
    return Reading(
        label=_text(value["label"], f"{field}.label", path),
        percent=_number(value["percent"], f"{field}.percent", path),
        taken_at=_text(value["taken_at"], f"{field}.taken_at", path),
        source=_text(value["source"], f"{field}.source", path),
    )


def _assumptions(value: Any, path: Path) -> tuple[str, ...]:
    """The assumptions behind the conversion, empty list included.

    R8 requires every assumption written out rather than implied, and an empty
    list was refused here at first — a conversion presented with nothing behind
    it reads as a measurement. Two things make that wrong. **A record with no
    conversion has no assumptions to state**: when the meter did not move,
    `tokens_per_point` is None and there is nothing to have assumed. And
    refusing on READ while accepting on WRITE let this module produce a file it
    could not read back, which is a worse failure than the one it prevented.
    The blind tests caught it, on the round trip rather than on the rule.

    What R8 actually needs is enforced where the record is BUILT, in
    `commands/extract.py`, which states its assumptions whenever it states a
    conversion. A reader's job is to read what was written.
    """
    if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
        raise ValueError(f"{path}: conversion_assumptions is not a list of statements")
    return tuple(value)


def _require_keys(payload: dict[str, Any], names: tuple[str, ...], path: Path) -> None:
    """Every expected key present and no others, reported all at once."""
    missing = sorted(set(names) - set(payload))
    unknown = sorted(set(payload) - set(names))
    faults = []
    if missing:
        faults.append(f"missing {', '.join(missing)}")
    if unknown:
        faults.append(f"unknown {', '.join(unknown)}")
    if faults:
        raise ValueError(f"{path} is not a calibration record: {'; '.join(faults)}")


def _whole(value: Any, field: str, path: Path) -> int:
    """A count. `bool` is excluded because it is an `int` and `True` is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}: {field} is {type(value).__name__}, expected a whole number")
    return value


def _number(value: Any, field: str, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: {field} is {type(value).__name__}, expected a number")
    return float(value)


def _optional_number(value: Any, field: str, path: Path) -> float | None:
    """A number, or null where the meter did not move. Null is a measurement."""
    return None if value is None else _number(value, field, path)


def _text(value: Any, field: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: {field} is missing or empty")
    return value
