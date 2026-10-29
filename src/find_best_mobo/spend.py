"""The R26 guard: what the meter says, read before the line is crossed.

R26 caps the extraction effort at 10% of the owner's weekly subscription limit
and requires the cap be enforced "against real readings rather than the
projection". This module is the reading. Nothing here consults a projection —
the projection is the thing Stage B exists to correct, so a guard built on one
would be checking an estimate against itself and would report healthy for
exactly as long as the estimate was wrong.

**`Weekly (7-day)` governs**, by the owner's ruling of 2026-08-25
(`docs/DECISIONS.md`), and not the model-scoped limit printed beside it. The
model-scoped figure ignores spend on every other model; the account-wide one
comes from Anthropic's own usage endpoint, so it counts every session on the
subscription — other machines, web sessions and spawned workers included. That
property, measured on 2026-08-25, is the only reason the cap means anything: a
figure that saw only this terminal could be held under 10% while the account ran
out.

Two readers, in order (R26 as amended, BL-24's ruling).
`omarchy-agent-usage-claude --limits-only --force` is an ordinary command that
returns the limits as JSON without starting a session. `claude -p "/usage"` is
the FALLBACK, and it is a fallback rather than the default because it starts a
session and so spends against the very limit it is reading. `Reading.source`
records which one answered: a reading that perturbed the meter is a different
kind of evidence from one that did not, and a record that does not say which it
was cannot be told apart afterwards.

**One seam — `take_reading` — for the reason `ytdlp.py` has one.** No test may
invoke a reader: the fallback would spend real subscription budget on any
machine with `claude` installed, so a suite that reached it would be neither
offline nor free (R20). Everything the guard actually decides — `ceiling` and
`check` — is pure arithmetic over readings a caller can construct.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from find_best_mobo.config import Config

WEEKLY_LABEL = "Weekly (7-day)"

# R26's 10%, as a fraction of the whole weekly limit. A constant and not a
# configuration key, deliberately: R17 makes the levers that decide what a run
# COSTS configurable, and this is not one of them — it is the bound the run is
# allowed to spend within, and a run that could raise its own ceiling is not a
# guard.
CAP_FRACTION = 0.10

_PRIMARY_READER = ("omarchy-agent-usage-claude", "--limits-only", "--force")
_FALLBACK_READER = ("claude", "-p", "/usage")

# Long enough that a slow usage endpoint is not mistaken for a broken reader,
# short enough that a wedged one cannot hold a batch open indefinitely. The
# fallback answers through a model, which is why this is minutes rather than
# seconds.
_READER_TIMEOUT_SECONDS = 120


class UsageUnreadable(RuntimeError):
    """Neither reader answered, so the run is about to spend blind.

    Raised rather than defaulted to a safe-looking number. A guard that invented
    a reading when it could not take one would let the batch run with the meter
    unwatched while printing a percentage that came from nowhere, which is worse
    than refusing: the refusal is visible and the invention is not.
    """

    def __init__(self, faults: Sequence[str]) -> None:
        self.faults = tuple(faults)
        super().__init__(self.message())

    def message(self) -> str:
        lines = [f"Could not read the {WEEKLY_LABEL} limit. Both readers were tried:"]
        lines.extend(f"  {fault}" for fault in self.faults)
        lines.append(
            "R26 enforces the cap against real readings, so the run stops here rather "
            "than spending against a limit it cannot see."
        )
        return "\n".join(lines)


class CapExceeded(RuntimeError):
    """The run stopped BEFORE crossing the line, and says what it read.

    Not an overrun report. R26's whole point is that the stop happens instead of
    the crossing, so this is raised while the reading is still under the account
    limit and the work already done is still intact (R27).
    """

    def __init__(self, reading: Reading, ceiling: float) -> None:
        self.reading = reading
        self.ceiling = ceiling
        super().__init__(self.message())

    def message(self) -> str:
        return (
            f"Stopping: {self.reading.label} reads {_as_points(self.reading.percent)} and this "
            f"extraction effort's ceiling is {_as_points(self.ceiling)} "
            f"(R26: 10% of the weekly limit, measured from where the batch began). "
            f"Read at {self.reading.taken_at} via `{self.reading.source}`. "
            "Nothing is rolled back: every bundle already extracted stays extracted and "
            "every claim already ingested stays ingested."
        )


@dataclass(frozen=True)
class Reading:
    label: str
    percent: float
    taken_at: str
    source: str


def take_reading(config: Config) -> Reading:
    """The current `Weekly (7-day)` percentage, and which reader gave it.

    The primary reader is tried first and the session-starting fallback only if
    it does not answer, for the reason in the module docstring. A reader that
    exits non-zero, times out, is not installed, or answers with something this
    module cannot read is a reader that did not answer — the next one is tried,
    and every failure is carried into `UsageUnreadable` so the owner sees why
    both fell through rather than only the last.
    """
    # `config` is unused: both reader commands are named by R26 itself, not by
    # this project's configuration, and there is no lever to read. Kept because
    # the plan declares it, so the seam the tests fake stays the seam the plan
    # declares — the same reason `ytdlp.fetch_video` keeps its own.
    del config
    faults: list[str] = []
    for command in (_PRIMARY_READER, _FALLBACK_READER):
        reading, fault = _try_reader(command)
        if reading is not None:
            return reading
        faults.append(f"`{' '.join(command)}` {fault}")
    raise UsageUnreadable(faults)


def ceiling(baseline: Reading, config: Config) -> float:
    """Ten points above where this batch began, never above the whole limit.

    **R26 caps the extraction EFFORT, not the account.** A run that starts at 43%
    stops at 53% rather than refusing outright, because the 10% is what Stage B
    is allowed to spend and not a health threshold for the subscription. Reading
    it the other way would make the cap depend on what the owner did earlier in
    the week, which is not what it is measuring.

    Clamped at 1.0 so the ceiling is never a percentage that cannot be reached.
    An account already at the limit therefore yields a ceiling equal to its own
    reading, and `check` refuses on it — which is right: there is no headroom to
    spend, and the alternative is a ceiling of 105% that nothing could ever trip.
    """
    # `config` is unused for the same reason `CAP_FRACTION` is a constant: the
    # fraction is R26's, not a lever, and there is nothing else here to read.
    del config
    return min(baseline.percent + CAP_FRACTION, 1.0)


def check(reading: Reading, ceiling: float) -> None:
    """Raise `CapExceeded` if this reading is at or past the ceiling.

    At the ceiling counts as past it. The readings arrive in whole percentage
    points (R26), so landing exactly on the line is the ordinary case rather
    than a corner, and the effort has by then spent the whole 10% it was given —
    the next bundle would cross. Stopping before the line is the requirement;
    stopping on it is the only way to keep it.
    """
    if reading.percent >= ceiling:
        raise CapExceeded(reading, ceiling)


def _try_reader(command: tuple[str, ...]) -> tuple[Reading | None, str]:
    """One reader's answer, or the reason it did not give one."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_READER_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return None, "is not installed"
    except subprocess.TimeoutExpired:
        return None, f"gave no answer within {_READER_TIMEOUT_SECONDS}s"
    except OSError as error:
        return None, f"could not be run: {error}"

    if completed.returncode != 0:
        return None, f"exited {completed.returncode}: {_first_line(completed)}"
    try:
        return _reading_from(completed.stdout, " ".join(command)), ""
    except ValueError as error:
        return None, f"answered but {error}"


def _first_line(completed: subprocess.CompletedProcess[str]) -> str:
    """The one line of a failed reader's output worth putting in a message."""
    for stream in (completed.stderr, completed.stdout):
        for line in (stream or "").splitlines():
            if line.strip():
                return line.strip()
    return "with no output"


def _reading_from(stdout: str, source: str) -> Reading:
    """The `Weekly (7-day)` entry of a reader's JSON, as a `Reading`.

    Only that label. The model-scoped limits ride in the same array and are
    ignored on purpose (the owner's ruling of 2026-08-25); picking the first
    entry, or the largest, would silently make the cap mean something else on
    the day Anthropic reorders the list.
    """
    payload = _json_object(stdout)
    limits = payload.get("limits")
    if not isinstance(limits, list):
        raise ValueError("its JSON carries no `limits` array")
    labels: list[str] = []
    for entry in limits:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        labels.append(str(label))
        if label == WEEKLY_LABEL:
            return Reading(
                label=WEEKLY_LABEL,
                percent=_percent(entry.get("percent")),
                taken_at=datetime.now(UTC).isoformat(timespec="seconds"),
                source=source,
            )
    reported = ", ".join(labels) if labels else "nothing"
    raise ValueError(f"reported no {WEEKLY_LABEL!r} limit (it reported: {reported})")


def _percent(value: Any) -> float:
    """The fraction 0.0–1.0 the reader reports, refused if it is not one.

    A reader that ever answered `43` for 43% would be read here as 4300%, and
    the guard would refuse every run; answered the other way round, a fraction
    read as a percentage would put the ceiling out of reach and the guard would
    never fire at all. Neither is worth guessing a scale for, so a value outside
    the range is a reader this module does not understand.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"gave a {type(value).__name__} percent, expected a number")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"gave a percent of {value}, expected a fraction between 0.0 and 1.0")
    return float(value)


def _json_object(text: str) -> dict[str, Any]:
    """The JSON object in a reader's output, wrapped in prose or not.

    The primary reader emits bare JSON. The fallback answers through a model, so
    its reply can arrive fenced or with a sentence around it — taking the
    outermost braces recovers the payload without this module having to learn
    the shape of an explanation.
    """
    payload: Any
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("its output is not JSON") from None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError(f"its output is not JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"its output is a {type(payload).__name__}, expected an object")
    return payload


def _as_points(fraction: float) -> str:
    """A fraction rendered as the percentage points the meter is read in."""
    return f"{fraction * 100:g}%"
