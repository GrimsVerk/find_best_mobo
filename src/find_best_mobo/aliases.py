"""The alias table, and the single pass that finds its entities in text.

An entity is one canonical name — a chipset, a vendor, a board family, a CPU —
plus every surface form a transcript might spell it as. The table is data
(`data/aliases.toml`), not code, because it is the part of the pipeline the
owner will keep extending as the corpus shows what it misses.

Two things here are deliberate. First, every surface form is `normalize`d before
it enters the pattern, so the table lives in the same space as the caption text
and a mangled spelling in either one folds onto the other. Second, the whole
table compiles to ONE regex with a group per surface form, so a two-hour
transcript is scanned once rather than once per entity — the difference between
a table that can grow and a table that cannot.

De-duplication is global: if two canonicals claim the same normalized form, the
one declared first wins and the other never fires. That is not hidden — it
surfaces as a zero-match canonical in `find-best-mobo aliases --check`, which is
exactly the defect that report exists to make visible.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from find_best_mobo.index import Video
from find_best_mobo.normalize import normalize
from find_best_mobo.transcripts import Transcript

KINDS = ("board", "family", "chipset", "cpu", "vendor")

# Group names must be valid Python identifiers, and canonicals are not
# (`ROG Crosshair` has a space; `7800X3D` starts with a digit). Hex of the
# UTF-8 bytes is reversible, collision-free by construction, and needs no state
# outside the pattern itself — `find_mentions` only ever receives the compiled
# pattern, so the canonical has to be recoverable from the group name alone.
_GROUP_PREFIX = "c"

# Nothing matches this, at any position: the pattern for an empty alias table.
_MATCHES_NOTHING = re.compile(r"(?!)")


@dataclass(frozen=True)
class Alias:
    canonical: str
    kind: str  # "board" | "family" | "chipset" | "cpu" | "vendor"
    surface_forms: tuple[str, ...]


@dataclass(frozen=True)
class Mention:
    video_id: str
    canonical: str
    start_seconds: float
    matched_form: str


def load_aliases(path: Path) -> tuple[Alias, ...]:
    """Read the alias table, in file order.

    Every structural problem raises `ValueError` naming the offending entry,
    because the failure this slice exists to prevent is a malformed table
    quietly deciding which videos make it into the corpus. A missing file
    raises `FileNotFoundError` — that is a different mistake and deserves its
    own name.
    """
    with path.open("rb") as handle:
        document: dict[str, Any] = tomllib.load(handle)
    entries = document.get("alias", [])
    if not isinstance(entries, list):
        raise ValueError(f"{path}: `alias` must be an array of tables")

    aliases: list[Alias] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"alias #{index} is not a table")
        canonical = entry.get("canonical")
        if not isinstance(canonical, str) or not canonical:
            raise ValueError(f"alias #{index} has no `canonical`")
        kind = entry.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"alias {canonical!r} has no `kind`")
        if kind not in KINDS:
            raise ValueError(f"alias {canonical!r} has unknown kind {kind!r}: expected {KINDS}")
        forms = entry.get("surface_forms")
        if not isinstance(forms, list) or not all(isinstance(form, str) for form in forms):
            raise ValueError(f"alias {canonical!r} has no `surface_forms`")
        aliases.append(Alias(canonical=canonical, kind=kind, surface_forms=tuple(forms)))
    return tuple(aliases)


def compile_matcher(aliases: Sequence[Alias]) -> re.Pattern[str]:
    """Compile the whole table into one pattern over normalized text.

    Callers must pass `normalize`d text: the surface forms were normalized on
    the way in, so raw text would be compared against a vocabulary it does not
    share.

    Longer forms are tried first so `x670e` wins over `670e` where both could
    start at the same position. Matches are bounded with alphanumeric
    lookaround rather than `\\b`, which places a boundary between a letter and a
    digit and would happily match `650` inside `b650e`.
    """
    seen: set[str] = set()
    forms: list[tuple[str, str]] = []
    for alias in aliases:
        for form in alias.surface_forms:
            normalized = normalize(form)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            forms.append((normalized, alias.canonical))
    if not forms:
        return _MATCHES_NOTHING

    # A stable sort on negated length keeps file order among equal-length forms,
    # so the pattern is byte-identical for a given table (R23).
    forms.sort(key=lambda pair: -len(pair[0]))
    alternatives = "|".join(
        f"(?P<{_group_name(canonical, position)}>{re.escape(form)})"
        for position, (form, canonical) in enumerate(forms)
    )
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])")


def find_mentions(transcript: Transcript, matcher: re.Pattern[str]) -> tuple[Mention, ...]:
    """Every match in every cue, in cue order and then in position order.

    The same canonical matching twice in one cue yields two mentions: this
    function reports what the text says, and de-duplicating is the caller's
    decision — slice 4 counts distinct canonicals, slice 5 wants every position.
    """
    mentions: list[Mention] = []
    for cue in transcript.cues:
        for match in matcher.finditer(normalize(cue.text)):
            group = match.lastgroup
            if group is None:  # pragma: no cover - every alternative is a group
                continue
            mentions.append(
                Mention(
                    video_id=transcript.video_id,
                    canonical=_canonical_of(group),
                    start_seconds=cue.start_seconds,
                    matched_form=match.group(0),
                )
            )
    return tuple(mentions)


def find_title_hits(video: Video, matcher: re.Pattern[str]) -> frozenset[str]:
    """The canonicals named in the video's title, if any.

    A title hit is stronger evidence than a body mention — a video called
    "X870E boards are a mess" is about X870E — so slice 4 admits on it alone.
    """
    return frozenset(
        _canonical_of(match.lastgroup)
        for match in matcher.finditer(normalize(video.title))
        if match.lastgroup is not None
    )


def _group_name(canonical: str, position: int) -> str:
    """A valid, unique, reversible identifier for one surface form's group.

    The position suffix is what lets a canonical own several alternatives while
    the group names stay unique; the hex body is what lets `find_mentions`
    recover the canonical from a pattern it was handed with nothing else.
    """
    return f"{_GROUP_PREFIX}{canonical.encode('utf-8').hex()}_{position}"


def _canonical_of(group: str) -> str:
    """Invert `_group_name`."""
    return bytes.fromhex(group[len(_GROUP_PREFIX) : group.index("_")]).decode("utf-8")
