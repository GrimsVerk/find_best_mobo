"""The alias table, and the single pass that finds its entities in text.

An entity is one canonical name — a chipset, a vendor, a board family, a CPU —
plus every surface form a transcript might spell it as. The table is data, not
code, because it is the part of the pipeline the owner will keep extending as
the corpus shows what it misses — and it is hand-authored INPUT rather than
cached corpus, so its path comes from configuration (`alias_table_path`) and no
loader here builds one (OD-11, R1007).

Two things here are deliberate. First, every surface form is `normalize`d before
it enters the pattern, so the table lives in the same space as the caption text
and a mangled spelling in either one folds onto the other. Second, the whole
table compiles to ONE regex with a group per surface form, so a two-hour
transcript is scanned once rather than once per entity — the difference between
a table that can grow and a table that cannot.

Third, a `kind = "chipset"` alias also contributes its ITX form — every declared
surface form plus a trailing `i`, so `b850i` finds B850 (OD-7, R1003). It is
DERIVED in code rather than listed in the table, so a spelling added later gets
its variant for free; it applies to chipsets only, because a vendor deriving
`asrocki` would be inventing a word; and an explicitly declared form always wins,
because declared forms are enumerated before any derived one and the
de-duplication below is first-declared-wins.

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
# The single character an ITX board's name appends to its chipset — `b850i`,
# `x870i`, `b650i` (OD-7, R1003). Named rather than inlined because `itx_forms`
# both appends it and tests for it, and the two must never drift.
ITX_SUFFIX = "i"

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
    # Declared forms first, ALL of them, before any derived one. That ordering
    # is what makes "explicit beats derived" fall out of the existing
    # first-declared-wins de-duplication: a hand-added `b850i` claims the form
    # and the derived one drops out silently (OD-7, R1003).
    for alias in aliases:
        for form in alias.surface_forms:
            normalized = normalize(form)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            forms.append((normalized, alias.canonical))
    for alias in aliases:
        for derived in itx_forms(alias):
            if derived in seen:
                continue
            seen.add(derived)
            forms.append((derived, alias.canonical))
    if not forms:
        return _MATCHES_NOTHING

    # A stable sort on negated length keeps file order among equal-length forms,
    # so the pattern is byte-identical for a given table (R23).
    forms.sort(key=lambda pair: -len(pair[0]))
    alternatives = "|".join(
        f"(?P<{_group_name(canonical, position)}>{alias_pattern(form)})"
        for position, (form, canonical) in enumerate(forms)
    )
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])")


def itx_forms(alias: Alias) -> tuple[str, ...]:
    """A chipset's ITX spellings, derived from every form it declares (R1003).

    ITX boards are named `<chipset>I` — `b850i`, `x870i`, `b650i` — and the
    right-boundary rule means the chipset alias cannot see them. BL-9 measured
    the cost as total: a 33-minute review of the MSI MPG B850I Edge TI matched
    `B850` zero times, in title and body both, so even the automatic title
    include missed it. Every ITX review in the corpus is affected, and ITX is
    where one-DIMM-per-channel memory behaviour lives.

    Derived from each DECLARED form rather than from the canonical alone, so a
    spelling the owner adds later gets its ITX variant with no code change —
    the self-maintaining property OD-7 rejected hand-listed entries for.

    Chipsets only: R1003 names the chipset, and a vendor deriving `asrocki`
    would be inventing a word. A form already ending in `i` derives nothing.
    The boundary itself is untouched, which is why `b850ix` and `theb850i` still
    match nothing.
    """
    if alias.kind != "chipset":
        return ()
    derived: list[str] = []
    for form in alias.surface_forms:
        normalized = normalize(form)
        if not normalized or normalized.endswith(ITX_SUFFIX):
            continue
        candidate = f"{normalized}{ITX_SUFFIX}"
        # Distinct spellings, in declaration order. Two declared forms can
        # normalize to one string — `b650` and `b 650` both fold to `b650` —
        # and a list of spellings that repeats itself is not a list of
        # spellings. `compile_matcher`'s global de-duplication would drop the
        # repeat anyway; this keeps the function's own contract honest.
        if candidate not in derived:
            derived.append(candidate)
    return tuple(derived)


def alias_pattern(form: str) -> str:
    """Regex source for one already-normalized surface form, split-tolerant (R1002).

    Auto-captions break product names mid-word: BL-8 measured `toma hawk` for
    `tomahawk`, `aor us master` for `aorus master`, `air us elite` for `aorus
    elite`. The first two are a name split at an arbitrary point, and this is
    what recovers them.

    Between every pair of adjacent characters INSIDE one word of the form, an
    optional single space. Where the form itself has a space, a REQUIRED single
    space. That asymmetry is the whole safety property: `aorus master` cannot
    match `aorusmaster`, because the alias's own space needs a real token
    boundary to land on, so a match always starts at a token start and ends at a
    token end (with `compile_matcher`'s boundary lookarounds). `air us` for
    `aorus` is a mishearing no join recovers and stays the alias table's job.

    Returns source only — no group wrapper and no lookarounds, both of which are
    `compile_matcher`'s. Raises `ValueError` on an empty form: an empty pattern
    matches at every position, which is worth naming rather than emitting.
    """
    if not form:
        raise ValueError("an empty surface form would match at every position")
    parts: list[str] = []
    for index, character in enumerate(form):
        if index:
            previous = form[index - 1]
            if character == " " or previous == " ":
                # The form's own space, emitted once by the space character
                # itself; never also as an optional one beside it.
                pass
            else:
                parts.append(" ?")
        parts.append(" " if character == " " else re.escape(character))
    return "".join(parts)


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


def count_cross_cue_candidates(transcript: Transcript, matcher: re.Pattern[str]) -> int:
    """How many alias matches exist ONLY across an adjacent-cue join (R1010).

    Auto-captions break mid-phrase — the shipped VTT fixture has `...Taichi
    board` ending one cue and `has a twelve phase...` beginning the next — so a
    board name can land half in each. OD-15 ruled that R1002's join applies
    WITHIN one cue and that a cross-cue split is **counted, never matched**: no
    mention is synthesized here, nothing is emitted, and no `start_seconds` is
    invented, because a mention spanning two cues has no single cue start and R5
    cuts every excerpt window from that field.

    This is the counter that turns the scoped-out case from an assumption into a
    measurement. It is a FLOOR, not a certified total: the scan is one
    left-to-right non-overlapping pass, so a match lying wholly inside the first
    cue can consume characters a crossing match would have used. R1010 asks for
    an observable that tells a zero from a material number, and "at least N"
    does that; a certified total would cost an overlapping scan for no decision
    it would change.

    Pure and offline. Adjacency is list order — a silent gap between two cues
    does not disqualify a pair, because R1010 says adjacent cues and nothing
    about time.
    """
    total = 0
    cues = transcript.cues
    for first, second in zip(cues, cues[1:], strict=False):
        left, right = normalize(first.text), normalize(second.text)
        if not left or not right:
            continue
        boundary = len(left)
        for match in matcher.finditer(f"{left} {right}"):
            # Wholly inside the first cue, or wholly inside the second: both are
            # already the matcher's own business. Only a match straddling the
            # inserted separator is new information.
            if match.start() < boundary and match.end() > boundary + 1:
                total += 1
    return total


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
