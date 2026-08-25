"""The claim schema, and the refusal that keeps a model honest.

A claim is the atom of evidence: one board, one thing said about it, in one
category, about one subject, with the verbatim snippet and the timestamp that
makes it findable again (`docs/DESIGN.md` §9). Stage B's agent produces these by
reading a bundle, and **the agent is never trusted to self-check** — BL-23 says
so outright, and this module is what does the checking instead.

The refusals here are shaped by what a model actually gets wrong rather than by
what a schema library would flag: a field left out, a null where a string
belongs, a category capitalised, a timestamp quoted as a string, an empty
snippet standing in for "nothing quotable", and a field the prompt never asked
for. That last one is the reason unknown keys are a FAULT rather than something
to drop: a model inventing `confidence` has misunderstood the contract, and
silently discarding the field hides the misunderstanding until it matters.

Nothing here touches the disk and nothing here invokes a model.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The vocabularies, verbatim from `docs/DESIGN.md` §9. Tuples rather than sets
# so the order is the order an error message lists them in, and the same order
# twice (R23).
CATEGORIES: tuple[str, ...] = ("tested", "reasoned", "secondhand", "warning")
SUBJECTS: tuple[str, ...] = (
    "vrm_capacity",
    "voltage_firmware_safety",
    "memory",
    "features",
    "value",
)
POLARITIES: tuple[str, ...] = ("positive", "negative", "mixed")

_TEXT_FIELDS = ("board", "video_id", "video_title", "snippet")
_VOCABULARIES = {"category": CATEGORIES, "subject": SUBJECTS, "polarity": POLARITIES}
_FIELDS = frozenset(_TEXT_FIELDS) | frozenset(_VOCABULARIES) | {"timestamp_seconds"}
_CLAIM_FIELDS = (*_TEXT_FIELDS, *_VOCABULARIES, "timestamp_seconds")


class InvalidClaims(ValueError):
    """A claims file that does not meet the schema, carrying EVERY fault.

    Not the first fault. A file with four bad rows produces four faults in one
    message, because reporting them one at a time turns a malformed batch into
    four round trips and every round trip is paid for (BL-23, R9).
    """

    def __init__(self, path: Path, faults: Sequence[str]) -> None:
        self.path = path
        self.faults = tuple(faults)
        super().__init__(self.message())

    def message(self) -> str:
        lines = [f"{self.path} is not a valid claims file:"]
        lines.extend(f"  {fault}" for fault in self.faults)
        lines.append("Nothing was appended, and the bundle stays unconsumed.")
        return "\n".join(lines)


@dataclass(frozen=True)
class Claim:
    board: str
    video_id: str
    video_title: str
    timestamp_seconds: float
    snippet: str
    category: str
    subject: str
    polarity: str
    batch: int


def parse_claims(raw: str, path: Path, batch: int) -> tuple[Claim, ...]:
    """Every claim in `raw`, or `InvalidClaims` naming every fault in it.

    `batch` is supplied by the caller and stamped on each claim rather than read
    from the file. The batch is a fact about the RUN, and a file that could
    declare its own batch could declare someone else's — which is the one thing
    the append-only store cannot detect after the fact.
    """
    faults: list[str] = []
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise InvalidClaims(path, [f"not JSON: {error}"]) from error

    if not isinstance(payload, list):
        raise InvalidClaims(path, [f"top level is {type(payload).__name__}, expected a list"])

    claims: list[Claim] = []
    for index, entry in enumerate(payload):
        claim = _parse_entry(entry, index, faults)
        if claim is not None:
            claims.append(_stamped(claim, batch))

    _report_duplicates(claims, faults)
    if faults:
        raise InvalidClaims(path, faults)
    return tuple(claims)


def _parse_entry(entry: Any, index: int, faults: list[str]) -> dict[str, Any] | None:
    """One entry's fields, or None with every fault it carries appended."""
    where = f"claim {index}"
    if not isinstance(entry, dict):
        faults.append(f"{where}: is {type(entry).__name__}, expected an object")
        return None

    before = len(faults)
    unknown = sorted(set(entry) - _FIELDS)
    if unknown:
        # A model that invents a field has misunderstood the contract. Dropping
        # the field would hide that until something downstream needed it.
        faults.append(f"{where}: unknown field(s) {', '.join(unknown)}")
    for field in _TEXT_FIELDS:
        _check_text(entry, field, where, faults)
    for field, vocabulary in _VOCABULARIES.items():
        _check_vocabulary(entry, field, vocabulary, where, faults)
    _check_timestamp(entry, where, faults)
    return None if len(faults) > before else dict(entry)


def _check_text(entry: dict[str, Any], field: str, where: str, faults: list[str]) -> None:
    """A required, non-empty string. Empty is a fault, not an absence of news."""
    if field not in entry:
        faults.append(f"{where}: missing {field}")
        return
    value = entry[field]
    if not isinstance(value, str):
        faults.append(f"{where}: {field} is {type(value).__name__}, expected a string")
    elif not value.strip():
        faults.append(f"{where}: {field} is empty")


def _check_vocabulary(
    entry: dict[str, Any], field: str, vocabulary: tuple[str, ...], where: str, faults: list[str]
) -> None:
    """One of the declared values, exactly. Case is part of the value."""
    if field not in entry:
        faults.append(f"{where}: missing {field}")
        return
    value = entry[field]
    if value not in vocabulary:
        shown = value if isinstance(value, str) else type(value).__name__
        faults.append(f"{where}: {field} {shown!r} is not one of {', '.join(vocabulary)}")


def _check_timestamp(entry: dict[str, Any], where: str, faults: list[str]) -> None:
    """A real number, not a string that looks like one.

    Coercing `"12.5"` would accept a model that ignored the type and would make
    the same file valid or invalid depending on how it was serialised.
    `bool` is excluded explicitly because it is an `int` in Python and `True`
    would otherwise pass as a timestamp of one second.
    """
    if "timestamp_seconds" not in entry:
        faults.append(f"{where}: missing timestamp_seconds")
        return
    value = entry["timestamp_seconds"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        faults.append(f"{where}: timestamp_seconds is {type(value).__name__}, expected a number")
    elif value < 0:
        faults.append(f"{where}: timestamp_seconds is negative")


def _report_duplicates(claims: Sequence[Claim], faults: list[str]) -> None:
    """The same claim twice in one file is a fault, reported once per repeat.

    A model repeating itself is cheap to make and expensive to notice later: the
    store is append-only, so a duplicate that lands is permanent evidence of
    something said once.
    """
    seen: set[tuple[Any, ...]] = set()
    for index, claim in enumerate(claims):
        # EVERY field, not a chosen subset. Two rows quoting the same words at
        # the same second can still be different claims — the same sentence can
        # be positive about a board's VRM and negative about its price — so a
        # key that ignored category, subject or polarity would refuse evidence
        # the model was right to record twice.
        key = tuple(getattr(claim, field) for field in _CLAIM_FIELDS)
        if key in seen:
            faults.append(f"claim {index}: duplicates an earlier claim in the same file")
        seen.add(key)


def _stamped(fields: dict[str, Any], batch: int) -> Claim:
    return Claim(
        board=fields["board"],
        video_id=fields["video_id"],
        video_title=fields["video_title"],
        timestamp_seconds=float(fields["timestamp_seconds"]),
        snippet=fields["snippet"],
        category=fields["category"],
        subject=fields["subject"],
        polarity=fields["polarity"],
        batch=batch,
    )
