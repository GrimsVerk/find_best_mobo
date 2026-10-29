"""S3 and R1011: every committed calibration record has the shape S3 names.

This was `acceptance/S3.sh` before the move to template v2. It reads the
committed files under `calibration/` directly and parses the JSON itself rather
than importing the project's loader, so a record and the code that writes it
cannot agree with each other about a shape neither has. With no record
committed there is nothing to check, and the test says so by skipping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS = sorted((REPO_ROOT / "calibration").glob("batch-*.json"))

FIELDS: dict[str, type] = {
    "batch": int,
    "model": str,
    "projected_tokens": int,
    "actual": dict,
    "measured_chars_per_token": float,
    "points_before": dict,
    "points_after": dict,
    "points_delta": float,
    "conversion_assumptions": list,
    "recorded_at": str,
}
# Kept apart, never one total: a cache read is not billed as fresh input (R8).
COMPONENTS = ("input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens")
READING = ("label", "percent", "taken_at", "source")


def _faults(record: dict[str, Any]) -> list[str]:
    faults = []
    for name, kind in FIELDS.items():
        if name not in record:
            faults.append(f"missing {name}")
            continue
        value = record[name]
        if not (isinstance(value, kind) or (kind is float and isinstance(value, int))):
            faults.append(f"{name} is {type(value).__name__}, expected {kind.__name__}")
    if "tokens_per_point" not in record:
        faults.append("missing tokens_per_point")
    if faults:
        return faults

    # The tokens: the projection against what the batch's own calls reported.
    for component in COMPONENTS:
        if not isinstance(record["actual"].get(component), int):
            faults.append(f"actual.{component} is not a token count")
    if record["projected_tokens"] <= 0:
        faults.append("projected_tokens is not a projection")
    if record["measured_chars_per_token"] <= 0:
        faults.append("the corrected factor is not a factor")
    if not record["model"].strip():
        faults.append("the record does not name the model")

    # The points: a separate quantity, never derived from the tokens.
    for side in ("points_before", "points_after"):
        faults += [f"{side} has no {f}" for f in READING if f not in record[side]]
    if not faults:
        delta = record["points_after"]["percent"] - record["points_before"]["percent"]
        if abs(record["points_delta"] - delta) >= 1e-6:
            faults.append("points_delta is not the difference of the readings")

    # The conversion: a labelled estimate, null only when the meter did not move.
    per_point = record["tokens_per_point"]
    if not (per_point is None or (isinstance(per_point, int | float) and per_point > 0)):
        faults.append("tokens_per_point is neither a rate nor null")
    if per_point is None and record["points_delta"] > 0:
        faults.append("the meter moved, so tokens_per_point may not be null")
    if not all(isinstance(line, str) and line.strip() for line in record["conversion_assumptions"]):
        faults.append("conversion_assumptions must be written out, not implied")
    return faults


@pytest.mark.skipif(not RECORDS, reason="no calibration record committed yet")
@pytest.mark.parametrize("path", RECORDS, ids=lambda path: path.name)
def test_committed_record_has_the_shape_s3_requires(path: Path) -> None:
    record = json.loads(path.read_text(encoding="utf-8"))
    assert _faults(record) == []
    assert path.name == f"batch-{record['batch']}.json"


def test_a_record_missing_its_token_split_is_refused() -> None:
    """The check itself must be able to fail, or a green run proves nothing."""
    record = json.loads(RECORDS[0].read_text(encoding="utf-8")) if RECORDS else {}
    record = {**record, "actual": {"total_tokens": 1}}
    assert any("actual." in fault or "missing" in fault for fault in _faults(record))
