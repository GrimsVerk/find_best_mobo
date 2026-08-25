#!/usr/bin/env bash
# S3 — after the calibration batch, the token projection, the token actual the
# run's own calls reported, their delta and the corrected factor are recorded
# together, and the R26 points readings taken around the batch are recorded
# beside them as a separate quantity, with the token-to-points conversion and
# its assumptions.
#
# It reads the committed records under calibration/, which is where R1011 puts
# them: "a restated number elsewhere is never a second source", so this script
# reads the same one file `estimate` prefers its factor from. It parses the JSON
# itself rather than importing the project's loader, so a record and the code
# that writes it cannot agree with each other about a shape neither has.
#
# THIS SCRIPT LANDS WITH THE FIRST REAL RECORD AND NEVER BEFORE IT (R1011), so
# no pull request is red for a record that cannot yet exist.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

shopt -s nullglob
records=(calibration/batch-*.json)

if [[ ${#records[@]} -eq 0 ]]; then
  echo "no calibration record: calibration/batch-<n>.json does not exist"
  echo "S3 is met by running the calibration batch — ./scripts/run.sh extract --batch 1 —"
  echo "which writes the record at the end of the batch and commits it as evidence (R1011)."
  exit 1
fi

echo "calibration records: ${records[*]}"

uv run python - "${records[@]}" <<'PY'
"""Every committed record, checked for the shape S3 names. Faults are collected
and printed together: a record with three things wrong should cost one run, not
three."""
import json
import sys

FIELDS = {
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
# The four token components, recorded separately and never as one total: a cache
# read is not billed as fresh input, and on this machine cache reads outnumber
# fresh input by more than four orders of magnitude (R8).
COMPONENTS = ("input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens")
READING = ("label", "percent", "taken_at", "source")

faults = []


def check(condition, message):
    if not condition:
        faults.append(message)
    return condition


for path in sys.argv[1:]:
    # Every record is read, whatever the ones before it did. A batch whose
    # record is malformed must not hide the state of the five batches after it:
    # the point of collecting faults is that one run tells you everything that
    # is wrong, and an early exit here would have made that true only of the
    # first bad file.
    faults_before_this_record = len(faults)

    with open(path, encoding="utf-8") as handle:
        try:
            record = json.load(handle)
        except json.JSONDecodeError as error:
            faults.append(f"{path}: not JSON ({error})")
            continue

    for name, kind in FIELDS.items():
        if not check(name in record, f"{path}: missing {name}"):
            continue
        value = record[name]
        ok = isinstance(value, kind) or (kind is float and isinstance(value, int))
        check(ok, f"{path}: {name} is {type(value).__name__}, expected {kind.__name__}")
    check("tokens_per_point" in record, f"{path}: missing tokens_per_point")
    # The checks below index into fields the block above proved are there. If
    # any of them is missing or the wrong type, go on to the NEXT RECORD rather
    # than out of the script: reading `record["actual"]["input_tokens"]` on a
    # record that has no `actual` raises, and a traceback says less than the
    # faults already collected.
    if len(faults) > faults_before_this_record:
        continue

    # The tokens: the projection against what the batch's own calls reported,
    # four components kept apart, and the factor their comparison corrected.
    for component in COMPONENTS:
        check(
            isinstance(record["actual"].get(component), int),
            f"{path}: actual.{component} is not a token count",
        )
    check(record["projected_tokens"] > 0, f"{path}: projected_tokens is not a projection")
    check(record["measured_chars_per_token"] > 0, f"{path}: the corrected factor is not a factor")
    check(bool(record["model"].strip()), f"{path}: the record does not name the model")

    # The points: a separate quantity, read around the batch, never derived from
    # the tokens above.
    for side in ("points_before", "points_after"):
        for field in READING:
            check(field in record[side], f"{path}: {side} has no {field}")
    delta = record["points_after"]["percent"] - record["points_before"]["percent"]
    check(
        abs(record["points_delta"] - delta) < 1e-6,
        f"{path}: points_delta {record['points_delta']} is not the difference of the readings",
    )

    # The conversion between them: an estimate, labelled, with its assumptions
    # written out — and absent when the meter did not move, which is a result
    # and not a gap (the reader returns whole percentage points).
    per_point = record["tokens_per_point"]
    check(
        per_point is None or (isinstance(per_point, (int, float)) and per_point > 0),
        f"{path}: tokens_per_point is neither a rate nor null",
    )
    check(
        per_point is not None or record["points_delta"] <= 0,
        f"{path}: the meter moved, so tokens_per_point may not be null",
    )
    check(
        all(isinstance(line, str) and line.strip() for line in record["conversion_assumptions"]),
        f"{path}: conversion_assumptions must be written out, not implied",
    )

    actual = record["actual"]
    print(f"{path}: batch {record['batch']}, model {record['model']}")
    print(f"    projected {record['projected_tokens']} tokens")
    print(
        "    actual: {input_tokens} fresh input, {output_tokens} output, "
        "{cache_creation_tokens} cache creation, {cache_read_tokens} cache read".format(**actual)
    )
    print(f"    corrected factor: {record['measured_chars_per_token']} characters per token")
    print(
        f"    points: {record['points_before']['percent']} before, "
        f"{record['points_after']['percent']} after, delta {record['points_delta']}"
    )
    print(
        f"    tokens per point: {per_point} (estimate) — "
        f"{len(record['conversion_assumptions'])} assumptions recorded"
    )

if faults:
    print("\n".join(faults))
    raise SystemExit(1)
PY
rc=$?
[[ "$rc" -eq 0 ]] || { echo "S3: a committed calibration record is not what S3 requires"; exit "$rc"; }
