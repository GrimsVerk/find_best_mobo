"""Tests for slice 3 — the alias table, the matcher, and `aliases --check`.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so failing imports are the expected
state until assembly. Nothing under test is faked: the alias tables are real
TOML files written into `tmp_path`, the transcripts are real cache files in the
documented slice-2 shape, and this slice touches no network at all.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-3 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import (
    ITX_SUFFIX,
    count_cross_cue_candidates,
    Alias,
    itx_forms,
    Mention,
    alias_pattern,
    compile_matcher,
    find_description_hits,
    find_mentions,
    find_title_hits,
    load_aliases,
)
from find_best_mobo.commands.aliases import run
from find_best_mobo.config import DEFAULT_ALIAS_TABLE, Config
from find_best_mobo.index import Video, write_index
from find_best_mobo.normalize import normalize
from find_best_mobo.transcripts import Cue, Transcript, cache_path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_TABLE = REPO_ROOT / DEFAULT_ALIAS_TABLE

VALID_KINDS = frozenset({"board", "family", "chipset", "cpu", "vendor"})

# The table most tests run against. Small, but it carries the shapes that
# matter: a mangled surface form, a short form that a longer one must beat, and
# a canonical that nothing will ever match.
STANDARD_TABLE: tuple[Mapping[str, object], ...] = (
    {"canonical": "X670E", "kind": "chipset", "surface_forms": ["x670e", "x 670 e", "670e"]},
    {"canonical": "B650E", "kind": "chipset", "surface_forms": ["b650e", "b 650 e"]},
    {"canonical": "A620", "kind": "chipset", "surface_forms": ["a620", "a 620"]},
    {"canonical": "Taichi", "kind": "family", "surface_forms": ["taichi"]},
)


# The table the R1002 cases are stated over. The canonicals and their forms are
# spelled as the shipped table spells them, so a case here reads the same as the
# same case run against `data/aliases.toml` — but the table is local, so nothing
# here moves when the shipped table is extended.
SPLIT_TABLE: tuple[Mapping[str, object], ...] = (
    {
        "canonical": "MAG Tomahawk",
        "kind": "family",
        "surface_forms": ["mag tomahawk", "tomahawk"],
    },
    {"canonical": "Aorus Master", "kind": "family", "surface_forms": ["aorus master"]},
    {"canonical": "Steel Legend", "kind": "family", "surface_forms": ["steel legend"]},
    {"canonical": "X870E", "kind": "chipset", "surface_forms": ["x870e"]},
    {"canonical": "B650E", "kind": "chipset", "surface_forms": ["b650e"]},
    {"canonical": "B650", "kind": "chipset", "surface_forms": ["b650"]},
)

# R1002's reject set: in each of these the alias would have to start or end
# inside a fused token, or land its own space where there is no boundary. None
# of them may produce a mention at all — not merely not the obvious one.
# Named apart from the fixture's `never_match` list below: this one is the
# inline reject set for the PATTERN rule (R1002 slice 2), the other is the
# reconstructed variant fixture's (slice 3). Two blind authors wrote them
# independently and both are wanted.
REJECT_SET = (
    "theb650",
    "xb650e",
    "b650ex",
    "x870ese",
    "verb 650",
    "verb 650 watts",
    "aorusmaster",
    "steellegend",
)


def one_space_splits(form: str) -> list[str]:
    """Every way one space can fall INSIDE a word of `form`.

    A caption splits a name at an arbitrary point, so the rule is stated over
    all of them rather than over the one split that was observed. Positions
    beside a space the form already has are skipped: those are not new splits.
    """
    return [
        f"{form[:index]} {form[index:]}"
        for index in range(1, len(form))
        if form[index - 1] != " " and form[index] != " "
    ]


def write_aliases(path: Path, entries: Sequence[Mapping[str, object]]) -> Path:
    """Write an alias table as TOML. JSON scalars are valid TOML for this data."""
    blocks = []
    for entry in entries:
        lines = ["[[alias]]"]
        lines += [f"{key} = {json.dumps(value)}" for key, value in entry.items()]
        blocks.append("\n".join(lines))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def make_alias(canonical: str, *forms: str, kind: str = "chipset") -> Alias:
    return Alias(canonical=canonical, kind=kind, surface_forms=tuple(forms))


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
        bundle_token_cap=24000,
        calibration_batch_size=12,
        batch_count=3,
        chars_per_token=4.0,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
        # Set explicitly rather than defaulted: `alias_table_path` no longer
        # follows `data_dir` (R1007), so these suites now exercise a configured,
        # non-default path throughout — which is the clause of R1007 they are
        # best placed to pin.
        alias_table_path=data_dir / "aliases.toml",
    )


def make_video(video_id: str, title: str = "Deep dive", *, inclusion: str = "pending") -> Video:
    return Video(
        video_id=video_id,
        title=title,
        upload_date=date(2023, 6, 15),
        duration_seconds=3600,
        was_live=False,
        classification="regular",
        inclusion=inclusion,
    )


def make_transcript(video_id: str, *cues: tuple[float, str]) -> Transcript:
    return Transcript(
        video_id=video_id,
        cues=tuple(Cue(start_seconds=start, text=text) for start, text in cues),
    )


def write_transcript(config: Config, transcript: Transcript) -> None:
    """Write the cache file in the shape slice 2 documents for `load_cached`."""
    path = cache_path(transcript.video_id, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "video_id": transcript.video_id,
                "cues": [
                    {"start_seconds": cue.start_seconds, "text": cue.text}
                    for cue in transcript.cues
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


# The standard table plus the chipset BL-11 measured, for the description tests.
# `#AMD`, `#ryzen`, `#MSI` and `#ITX` deliberately have no forms here: the
# measured hashtag line must hit on B850 and on nothing else, or the test would
# pass on a signal that is not the one under examination.
DESCRIPTION_TABLE: tuple[Mapping[str, object], ...] = STANDARD_TABLE + (
    {"canonical": "B850", "kind": "chipset", "surface_forms": ["b850"]},
)


def matcher_for(entries: Sequence[Mapping[str, object]], tmp_path: Path) -> re.Pattern[str]:
    table = write_aliases(tmp_path / "aliases.toml", entries)
    return compile_matcher(load_aliases(table))


def line_with(output: str, token: str) -> str:
    """The first output line mentioning `token`, for asserting on a report row."""
    for line in output.splitlines():
        if token in line:
            return line
    raise AssertionError(f"no line of the report mentions {token!r}:\n{output}")


CAPTION_VARIANTS_PATH = Path(__file__).resolve().parent / "fixtures" / "caption_variants.json"


def _load_caption_variants() -> tuple[str, list[dict[str, str]], list[str]]:
    """The fixture, unpacked into the three things the suite reads."""
    document = json.loads(CAPTION_VARIANTS_PATH.read_text(encoding="utf-8"))
    note: str = document["note"]
    variants: list[dict[str, str]] = document["variants"]
    never_match: list[str] = document["never_match"]
    return note, variants, never_match


FIXTURE_NOTE, CAPTION_VARIANTS, NEVER_MATCH = _load_caption_variants()

VARIANT_CASES = [
    pytest.param(variant["text"], variant["canonical"], id=variant["text"])
    for variant in CAPTION_VARIANTS
]
NEVER_MATCH_CASES = [pytest.param(text, id=text) for text in NEVER_MATCH]


CARRIER = "the {text} board"

MARKED_FAILURES = (
    "toma hawk",
    "aor us master",
    "air us elite",
    "steel-legend",
    "as-rock",
)

VALID_DAMAGE = frozenset(
    {"spacing", "digit-split", "hyphen", "split", "spelled-out", "mishearing", "plural", "partial"}
)


@pytest.fixture(scope="module")
def shipped_matcher() -> re.Pattern[str]:
    """The matcher this repository ships, compiled once for the whole module.

    The recall set is measured against the REAL table, not a fixture table: a
    variant that only matches a table written for the test measures the test.
    """
    return compile_matcher(load_aliases(SHIPPED_TABLE))


# A RECONSTRUCTED title. `MSI MPG B850I Edge TI` is verbatim from BL-9 and is
# the only wording here with measured provenance; everything around it is
# invented, is asserted on nowhere, and carries no form the pre-R1003 matcher
# resolves to B850. See `TestShippedTable.test_the_reconstructed_itx_title_hits
# _its_chipset` for the full provenance statement (BL-18, OD-17).
RECONSTRUCTED_B850I_TITLE = "Taking a look at the MSI MPG B850I Edge TI and how it runs"

ITX_TOKENS: tuple[tuple[str, str], ...] = (
    ("b850i", "B850"),
    ("x870i", "X870"),
    ("b650i", "B650"),
    ("a620i", "A620"),
    ("x670ei", "X670E"),
)

ITX_TABLE: tuple[Mapping[str, object], ...] = (
    {"canonical": "B850", "kind": "chipset", "surface_forms": ["b850", "b 850"]},
    {"canonical": "X870", "kind": "chipset", "surface_forms": ["x870", "x 870"]},
    {"canonical": "B650", "kind": "chipset", "surface_forms": ["b650", "b 650"]},
    {"canonical": "A620", "kind": "chipset", "surface_forms": ["a620", "a 620"]},
    {"canonical": "X670E", "kind": "chipset", "surface_forms": ["x670e", "x 670 e"]},
    {"canonical": "ASRock", "kind": "vendor", "surface_forms": ["asrock"]},
    {"canonical": "Taichi", "kind": "family", "surface_forms": ["taichi"]},
    {"canonical": "9950X3D", "kind": "cpu", "surface_forms": ["9950x3d"]},
    {"canonical": "Pro RS", "kind": "board", "surface_forms": ["pro rs"]},
)


class TestLoadAliases:
    def test_returns_entries_in_file_order(self, tmp_path: Path) -> None:
        path = write_aliases(tmp_path / "aliases.toml", STANDARD_TABLE)

        aliases = load_aliases(path)

        assert [alias.canonical for alias in aliases] == ["X670E", "B650E", "A620", "Taichi"]

    def test_reversing_the_file_reverses_the_result(self, tmp_path: Path) -> None:
        path = write_aliases(tmp_path / "aliases.toml", tuple(reversed(STANDARD_TABLE)))

        assert [alias.canonical for alias in load_aliases(path)] == [
            "Taichi",
            "A620",
            "B650E",
            "X670E",
        ]

    def test_carries_kind_and_surface_forms(self, tmp_path: Path) -> None:
        path = write_aliases(tmp_path / "aliases.toml", STANDARD_TABLE)

        first = load_aliases(path)[0]

        assert first == Alias(
            canonical="X670E", kind="chipset", surface_forms=("x670e", "x 670 e", "670e")
        )

    def test_returns_a_tuple(self, tmp_path: Path) -> None:
        path = write_aliases(tmp_path / "aliases.toml", STANDARD_TABLE)

        assert isinstance(load_aliases(path), tuple)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_aliases(tmp_path / "nowhere" / "aliases.toml")

    def test_missing_kind_raises_value_error_naming_the_canonical(self, tmp_path: Path) -> None:
        path = write_aliases(
            tmp_path / "aliases.toml",
            [{"canonical": "B650E", "surface_forms": ["b650e"]}],
        )

        with pytest.raises(ValueError, match="B650E"):
            load_aliases(path)

    def test_missing_surface_forms_raises_value_error_naming_the_canonical(
        self, tmp_path: Path
    ) -> None:
        path = write_aliases(tmp_path / "aliases.toml", [{"canonical": "B650E", "kind": "chipset"}])

        with pytest.raises(ValueError, match="B650E"):
            load_aliases(path)

    def test_bad_kind_raises_value_error_naming_the_canonical(self, tmp_path: Path) -> None:
        path = write_aliases(
            tmp_path / "aliases.toml",
            [{"canonical": "B650E", "kind": "motherboard", "surface_forms": ["b650e"]}],
        )

        with pytest.raises(ValueError, match="B650E"):
            load_aliases(path)

    def test_missing_canonical_raises_value_error(self, tmp_path: Path) -> None:
        path = write_aliases(
            tmp_path / "aliases.toml",
            [{"kind": "chipset", "surface_forms": ["b650e"]}],
        )

        with pytest.raises(ValueError):
            load_aliases(path)

    def test_a_bad_entry_late_in_the_file_still_raises(self, tmp_path: Path) -> None:
        path = write_aliases(
            tmp_path / "aliases.toml",
            [
                {"canonical": "X670E", "kind": "chipset", "surface_forms": ["x670e"]},
                {"canonical": "Taichi", "kind": "brand", "surface_forms": ["taichi"]},
            ],
        )

        with pytest.raises(ValueError, match="Taichi"):
            load_aliases(path)

    @pytest.mark.parametrize("kind", sorted(VALID_KINDS))
    def test_every_documented_kind_is_accepted(self, tmp_path: Path, kind: str) -> None:
        path = write_aliases(
            tmp_path / "aliases.toml",
            [{"canonical": "Thing", "kind": kind, "surface_forms": ["thing"]}],
        )

        assert load_aliases(path)[0].kind == kind


class TestShippedTable:
    def test_the_shipped_table_exists_and_loads(self) -> None:
        aliases = load_aliases(SHIPPED_TABLE)

        assert len(aliases) > 0

    def test_every_kind_is_one_of_the_documented_values(self) -> None:
        bad = {alias.canonical: alias.kind for alias in load_aliases(SHIPPED_TABLE)}
        bad = {name: kind for name, kind in bad.items() if kind not in VALID_KINDS}

        assert bad == {}

    def test_no_two_entries_share_a_canonical(self) -> None:
        canonicals = [alias.canonical for alias in load_aliases(SHIPPED_TABLE)]

        duplicates = sorted({name for name in canonicals if canonicals.count(name) > 1})
        assert duplicates == []

    def test_every_entry_has_at_least_one_surface_form(self) -> None:
        empty = [
            alias.canonical for alias in load_aliases(SHIPPED_TABLE) if not alias.surface_forms
        ]

        assert empty == []

    def test_carries_the_am5_chipsets_the_slice_names(self) -> None:
        canonicals = {alias.canonical for alias in load_aliases(SHIPPED_TABLE)}

        assert {"X870E", "X670E", "B650E", "A620"} <= canonicals

    def test_mangled_caption_spacing_still_finds_a_chipset(self) -> None:
        matcher = compile_matcher(load_aliases(SHIPPED_TABLE))
        video = make_video("vid1", "so the x 670 e board is good")

        assert "X670E" in find_title_hits(video, matcher)

    @pytest.mark.parametrize(("text", "canonical"), ITX_TOKENS)
    def test_every_shipped_chipset_matches_its_itx_token(self, text: str, canonical: str) -> None:
        """R1003 against the table this repository actually ships."""
        matcher = compile_matcher(load_aliases(SHIPPED_TABLE))
        video = make_video("vid1", f"the {text} is a tiny board")

        assert find_title_hits(video, matcher) == frozenset({canonical})

    @pytest.mark.parametrize("text", ["theb850i", "xb850i", "b850ix", "b850ii", "asrocki"])
    def test_the_shipped_table_keeps_the_right_boundary(self, text: str) -> None:
        """R1003's other half: the boundary stays in force for everything else."""
        matcher = compile_matcher(load_aliases(SHIPPED_TABLE))

        assert matcher.search(text) is None, f"{text!r} must match nothing"

    def test_the_shipped_table_hand_lists_no_itx_form(self) -> None:
        """OD-7 rejected hand-listed `b850i` entries; the table must stay that way.

        The variant is derived in code, which is what makes it self-maintaining
        — a chipset added tomorrow brings its ITX spelling with it. A form
        written into the table would be the maintenance burden OD-7 declined,
        and would silently shadow the derived one.
        """
        aliases = load_aliases(SHIPPED_TABLE)
        declared = {normalize(form) for alias in aliases for form in alias.surface_forms}
        derived = {form for alias in aliases for form in itx_forms(alias)}

        assert declared & derived == set()

    def test_the_reconstructed_itx_title_hits_its_chipset(self) -> None:
        """R1003's regression, over a LABELLED RECONSTRUCTION of the title.

        The real B850I review's title is not recoverable from this repository:
        it is in no commit, no journal entry and no run record, and
        `data/index.jsonl`, the one artifact that would hold it, is gitignored
        and absent from a fresh clone. That is BL-18, ruled LOW and proceeded on
        under OD-17. Absent, note, not unknowable — the video is public, so
        recovering the measured string later is a supersession with logged
        evidence, never a silent swap of this constant.

        `MSI MPG B850I Edge TI` is verbatim from BL-9 and is the ONLY wording
        here with measured provenance. What BL-9 measured is the provenance of
        the CASE, not of the string: on a real 33-minute review of that board,
        `B850` matched ZERO times, in title and body both, so even the automatic
        title include missed it. The surrounding wording is invented, nothing
        asserts on it, and it carries no form the pre-R1003 matcher resolves to
        B850 — otherwise this test would be green before the fix and would
        demonstrate nothing.

        The reconstruction does NOT reproduce the real video's recorded
        invisibility to title matching, and must not be read as claiming to:
        `msi` is a vendor form in the shipped table, so this title hits MSI
        before and after R1003. It reproduces the one property the regression
        turns on — the chipset spelled only inside an unseparated `B850I` token.
        """
        matcher = compile_matcher(load_aliases(SHIPPED_TABLE))
        video = make_video("vid1", RECONSTRUCTED_B850I_TITLE)

        assert "B850" in find_title_hits(video, matcher)

    def test_the_reconstructed_itx_body_mentions_its_chipset_by_the_itx_form(self) -> None:
        """The body half of BL-9's measured zero, on the same reconstruction.

        Provenance and its limits are stated in full on
        `test_the_reconstructed_itx_title_hits_its_chipset`: only
        `MSI MPG B850I Edge TI` is measured wording (BL-9), the rest is invented
        and unasserted (BL-18, OD-17). The assertions here are the canonical and
        the matched form — `b850i`, the spelling the caption actually used, which
        is what has to survive into `selected.jsonl` and the recall report.
        """
        matcher = compile_matcher(load_aliases(SHIPPED_TABLE))
        transcript = make_transcript("vid1", (0.0, RECONSTRUCTED_B850I_TITLE))

        mentions = [m for m in find_mentions(transcript, matcher) if m.canonical == "B850"]

        assert [mention.matched_form for mention in mentions] == ["b850i"]


class TestCompileMatcher:
    def test_a_surface_form_matches(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert matcher.search("the x670e board") is not None

    def test_the_longer_form_wins_at_the_same_position(self, tmp_path: Path) -> None:
        # `x670e` and `670e` could both match at the same place; the longer one
        # must win, so the text yields exactly one match, for X670E.
        matcher = matcher_for(
            [
                {"canonical": "X670E", "kind": "chipset", "surface_forms": ["x670e"]},
                {"canonical": "670E", "kind": "chipset", "surface_forms": ["670e"]},
            ],
            tmp_path,
        )
        video = make_video("vid1", "x670e")

        assert find_title_hits(video, matcher) == frozenset({"X670E"})
        assert len(matcher.findall("x670e")) == 1

    def test_the_longer_form_wins_within_one_canonical(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "x670e"))

        mentions = find_mentions(transcript, matcher)

        assert [(m.canonical, m.matched_form) for m in mentions] == [("X670E", "x670e")]

    @pytest.mark.parametrize("text", ["9b650e", "b650e1", "xb650e", "b650ex", "ab650ez"])
    def test_no_match_inside_a_longer_word(self, tmp_path: Path, text: str) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert matcher.search(text) is None, f"{text!r} must not count as a B650E mention"

    def test_a_form_at_the_ends_of_the_text_still_matches(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert matcher.search("b650e") is not None
        assert matcher.search("b650e board") is not None
        assert matcher.search("the b650e") is not None

    def test_a_hyphen_neighbour_does_not_block_a_match(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert matcher.search("the b650e-plus board") is not None

    def test_an_empty_alias_sequence_matches_nothing(self) -> None:
        matcher = compile_matcher(())

        assert matcher.search("") is None
        assert matcher.search("the x670e taichi board is good") is None

    def test_an_empty_alias_sequence_yields_no_mentions(self) -> None:
        matcher = compile_matcher(())
        transcript = make_transcript("vid1", (0.0, "the x670e taichi board"))

        assert find_mentions(transcript, matcher) == ()
        assert find_title_hits(make_video("vid1", "x670e taichi"), matcher) == frozenset()

    def test_canonicals_that_would_collide_as_identifiers_stay_distinct(self) -> None:
        # Both names sanitize to the same Python identifier under any naive
        # scheme, so a colliding group name would silently merge two entities.
        matcher = compile_matcher(
            (
                make_alias("ROG Strix", "rog strix", kind="family"),
                make_alias("ROG-Strix", "rog strix x", kind="family"),
                make_alias("ROG.Strix", "rog strix y", kind="family"),
            )
        )

        assert find_title_hits(make_video("v", "rog strix"), matcher) == frozenset({"ROG Strix"})
        assert find_title_hits(make_video("v", "rog strix x"), matcher) == frozenset({"ROG-Strix"})
        assert find_title_hits(make_video("v", "rog strix y"), matcher) == frozenset({"ROG.Strix"})

    def test_surface_forms_are_normalized_into_the_pattern(self) -> None:
        # The table may hold a form written the human way; the pattern lives in
        # normalized space, so it must still match normalized text.
        matcher = compile_matcher((make_alias("X870E", "X 870 E", "X870E-Nova"),))

        assert find_title_hits(make_video("v", "the x870e board"), matcher) == frozenset({"X870E"})
        assert find_title_hits(make_video("v", "x870e-nova"), matcher) == frozenset({"X870E"})

    def test_accepts_a_plain_list_of_aliases(self) -> None:
        matcher = compile_matcher([make_alias("A620", "a620")])

        assert matcher.search("a620") is not None


class TestFindMentions:
    def test_one_mention_per_match_with_the_cue_start(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript(
            "vid1",
            (12.5, "so the x670e board"),
            (61.0, "and the taichi is fine"),
        )

        assert find_mentions(transcript, matcher) == (
            Mention(video_id="vid1", canonical="X670E", start_seconds=12.5, matched_form="x670e"),
            Mention(video_id="vid1", canonical="Taichi", start_seconds=61.0, matched_form="taichi"),
        )

    def test_cue_order_is_preserved(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript(
            "vid1",
            (30.0, "taichi"),
            (10.0, "b650e"),
            (20.0, "a620"),
        )

        mentions = find_mentions(transcript, matcher)

        assert [mention.canonical for mention in mentions] == ["Taichi", "B650E", "A620"]
        assert [mention.start_seconds for mention in mentions] == [30.0, 10.0, 20.0]

    def test_two_matches_in_one_cue_yield_two_mentions(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (5.0, "the b650e and the taichi"))

        mentions = find_mentions(transcript, matcher)

        assert [mention.canonical for mention in mentions] == ["B650E", "Taichi"]
        assert {mention.start_seconds for mention in mentions} == {5.0}

    def test_the_same_canonical_twice_in_one_cue_is_not_deduped(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (5.0, "x670e versus another x670e"))

        mentions = find_mentions(transcript, matcher)

        assert len(mentions) == 2
        assert {mention.canonical for mention in mentions} == {"X670E"}

    def test_a_mangled_form_matches_its_canonical(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (7.0, "So the X 670 E Taichi, honestly, rules"))

        mentions = find_mentions(transcript, matcher)

        assert [mention.canonical for mention in mentions] == ["X670E", "Taichi"]

    def test_matched_form_is_the_normalized_matched_text(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (7.0, "So the X 670 E board"))

        (mention,) = find_mentions(transcript, matcher)

        assert mention.matched_form == "x670e"
        assert mention.matched_form == normalize(mention.matched_form)

    def test_video_id_comes_from_the_transcript(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("someVideo", (0.0, "b650e"))

        assert find_mentions(transcript, matcher)[0].video_id == "someVideo"

    def test_no_matches_returns_an_empty_tuple(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "he talks about power supplies"))

        assert find_mentions(transcript, matcher) == ()

    def test_a_transcript_with_no_cues_returns_an_empty_tuple(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert find_mentions(Transcript(video_id="vid1", cues=()), matcher) == ()


class TestFindTitleHits:
    def test_returns_the_canonicals_in_the_title(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        video = make_video("vid1", "X670E Taichi VRM breakdown")

        assert find_title_hits(video, matcher) == frozenset({"X670E", "Taichi"})

    def test_a_mangled_title_still_hits(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        video = make_video("vid1", "The X-670-E boards, ranked!")

        assert find_title_hits(video, matcher) == frozenset({"X670E"})

    def test_repeated_hits_collapse_to_one_canonical(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        video = make_video("vid1", "x670e versus x670e")

        assert find_title_hits(video, matcher) == frozenset({"X670E"})

    def test_nothing_matching_returns_an_empty_frozenset(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        video = make_video("vid1", "Power supply teardown")

        result = find_title_hits(video, matcher)

        assert result == frozenset()
        assert isinstance(result, frozenset)

    def test_an_empty_title_returns_an_empty_frozenset(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert find_title_hits(make_video("vid1", ""), matcher) == frozenset()


class TestItxForms:
    """`itx_forms` — R1003's derivation as a unit, before any pattern exists."""

    def test_a_chipset_derives_its_form_with_a_trailing_i(self) -> None:
        assert itx_forms(make_alias("B850", "b850")) == ("b850i",)

    def test_the_derived_form_is_the_form_plus_the_single_suffix(self) -> None:
        assert ITX_SUFFIX == "i"
        assert itx_forms(make_alias("X870", "x870")) == ("x870" + ITX_SUFFIX,)

    def test_every_declared_form_derives_one_in_declaration_order(self) -> None:
        """Not the canonical alone: a spelling added later must derive too."""
        assert itx_forms(make_alias("X670E", "x670e", "670e")) == ("x670ei", "670ei")

    def test_forms_are_normalized_before_the_suffix(self) -> None:
        assert itx_forms(make_alias("X670E", "X 670 E")) == ("x670ei",)

    @pytest.mark.parametrize("kind", ["board", "family", "cpu", "vendor"])
    def test_no_other_kind_derives_anything(self, kind: str) -> None:
        """R1003 names the chipset. `asrocki` would be an invented word."""
        assert itx_forms(make_alias("ASRock", "asrock", kind=kind)) == ()

    def test_a_form_already_ending_in_the_suffix_derives_nothing(self) -> None:
        """`b850ii` is an alternative no text can reach."""
        assert itx_forms(make_alias("B650I", "b650i")) == ()

    def test_a_form_that_normalizes_onto_a_trailing_i_derives_nothing(self) -> None:
        assert itx_forms(make_alias("X870I", "x 870 i")) == ()

    def test_the_other_forms_still_derive_when_one_is_skipped(self) -> None:
        assert itx_forms(make_alias("B650", "b650", "b650i")) == ("b650i",)

    def test_a_form_that_normalizes_to_nothing_is_skipped(self) -> None:
        assert itx_forms(make_alias("B850", "...", "b850")) == ("b850i",)

    def test_forms_colliding_within_one_alias_derive_once(self) -> None:
        assert itx_forms(make_alias("B650", "b650", "b 650")) == ("b650i",)

    def test_an_alias_with_no_forms_derives_nothing(self) -> None:
        assert itx_forms(make_alias("B850")) == ()

    def test_returns_a_tuple(self) -> None:
        assert isinstance(itx_forms(make_alias("B850", "b850")), tuple)

    def test_is_pure_and_leaves_the_alias_alone(self) -> None:
        alias = make_alias("B850", "b850", "b 850")

        assert itx_forms(alias) == itx_forms(alias)
        assert alias.surface_forms == ("b850", "b 850")


class TestItxChipsetVariant:
    """R1003 through the compiled pattern: `<chipset>i` counts as the chipset."""

    @pytest.mark.parametrize(("text", "canonical"), ITX_TOKENS)
    def test_an_itx_token_is_a_title_hit_for_its_chipset(
        self, tmp_path: Path, text: str, canonical: str
    ) -> None:
        matcher = matcher_for(ITX_TABLE, tmp_path)

        assert find_title_hits(make_video("vid1", text), matcher) == frozenset({canonical})

    @pytest.mark.parametrize(("text", "canonical"), ITX_TOKENS)
    def test_an_itx_token_mid_title_is_a_title_hit(
        self, tmp_path: Path, text: str, canonical: str
    ) -> None:
        matcher = matcher_for(ITX_TABLE, tmp_path)
        video = make_video("vid1", f"the {text} is a tiny board")

        assert find_title_hits(video, matcher) == frozenset({canonical})

    @pytest.mark.parametrize(
        "text",
        [
            "b850i",
            "so the b850i is a tiny board",
            "b850i boards run hot",
            "he would rather have the b850i",
        ],
    )
    def test_an_itx_token_is_a_body_mention_wherever_it_sits(
        self, tmp_path: Path, text: str
    ) -> None:
        matcher = matcher_for(ITX_TABLE, tmp_path)

        mentions = find_mentions(make_transcript("vid1", (0.0, text)), matcher)

        assert [(m.canonical, m.matched_form) for m in mentions] == [("B850", "b850i")]

    def test_the_plain_chipset_form_is_untouched(self, tmp_path: Path) -> None:
        matcher = matcher_for(ITX_TABLE, tmp_path)

        mentions = find_mentions(make_transcript("vid1", (0.0, "the b850 board")), matcher)

        assert [(m.canonical, m.matched_form) for m in mentions] == [("B850", "b850")]

    @pytest.mark.parametrize(
        "text",
        [
            "theb850i",
            "xb850i",
            "b850ix",
            "b850i7",
            "b850ie",
            "b850ii",
            "asrocki",
            "taichii",
            "9950x3di",
            "pro rsi",
        ],
    )
    def test_the_right_boundary_stays_in_force(self, tmp_path: Path, text: str) -> None:
        """The derived form is a FORM, not a relaxed boundary.

        `theb850i` and `b850ix` still start or end inside a token; `b850ii` is
        derived by nothing; and `asrocki`, `taichii`, `9950x3di` and `pro rsi`
        are a vendor, a family, a CPU and a board, none of which derive.
        """
        matcher = matcher_for(ITX_TABLE, tmp_path)

        assert matcher.search(text) is None, f"{text!r} must match nothing"

    @pytest.mark.parametrize("text", ["theb650", "b650ex", "xb650e", "9b650", "b6501"])
    def test_the_negatives_the_suite_already_pinned_are_unchanged(
        self, tmp_path: Path, text: str
    ) -> None:
        matcher = matcher_for(ITX_TABLE, tmp_path)

        assert matcher.search(text) is None, f"{text!r} must match nothing"

    @pytest.mark.parametrize("explicit_first", [True, False])
    def test_an_explicitly_declared_itx_form_beats_the_derived_one(
        self, tmp_path: Path, explicit_first: bool
    ) -> None:
        """Explicit beats derived, in either declaration order.

        This is the existing first-declared-wins de-duplication doing its job
        over a second source of forms, not a new rule: every declared form is
        enumerated before any derived one, so the hand-written `b650i` claims
        the form and B650's derived one drops out silently — exactly as a
        duplicate declared form does today.
        """
        b650 = {"canonical": "B650", "kind": "chipset", "surface_forms": ["b650"]}
        b650i = {"canonical": "B650I", "kind": "chipset", "surface_forms": ["b650i"]}
        entries = [b650i, b650] if explicit_first else [b650, b650i]
        matcher = matcher_for(entries, tmp_path)

        assert find_title_hits(make_video("v", "b650i"), matcher) == frozenset({"B650I"})
        assert len(matcher.findall("b650i")) == 1
        assert find_title_hits(make_video("v", "b650"), matcher) == frozenset({"B650"})

    def test_the_pattern_is_identical_across_compilations(self, tmp_path: Path) -> None:
        """R23: the derived pass walks the same table in the same order."""
        aliases = load_aliases(write_aliases(tmp_path / "aliases.toml", ITX_TABLE))

        assert compile_matcher(aliases).pattern == compile_matcher(aliases).pattern

    def test_an_empty_table_still_matches_nothing(self) -> None:
        matcher = compile_matcher(())

        assert matcher.search("b850i") is None


class TestCaptionVariantFixture:
    """The measured recall set, pinned against the table this repository ships.

    **Provenance, and the reason it is stated here rather than assumed.** BL-8
    tested 52 mangled caption spellings against the shipped table and recorded
    that 49 matched; the three that did not (`toma hawk`, `aor us master`,
    `air us elite`) are named there, as is the related hyphen observation
    (`steel-legend`). The list itself is in no commit, no journal entry and no
    run record — BL-17 established that, and OD-16 ruled the honest response: a
    RECONSTRUCTION that declares itself. So the number 52 below is a floor taken
    from the backlog entry's history, never a claim that these 52 strings are
    the ones BL-8 measured. `tests/fixtures/caption_variants.json` says the same
    in its own `note`, which is where a reader who never opens this file will
    look.

    A later addition to the fixture is welcome and this floor still holds; a
    LOSS is a regression, which is exactly what the floor exists to catch —
    OD-16's point is that the class most exposed to a silent recall loss is the
    already-matching majority, not the three famous failures.
    """

    def test_the_fixture_declares_itself_a_reconstruction(self) -> None:
        """OD-16: the fixture may not wear measured provenance it does not have."""
        lowered = FIXTURE_NOTE.lower()

        assert "reconstruct" in lowered, FIXTURE_NOTE
        assert "bl-8" in lowered and "bl-17" in lowered, FIXTURE_NOTE

    def test_the_fixture_holds_at_least_the_fifty_two_bl_8_counted(self) -> None:
        """52 is BL-8's recorded count, and here it is a FLOOR, not a measurement.

        BL-8's arithmetic — 49 matched plus 3 failures — is where the number
        comes from. It sizes the reconstruction and nothing else in this suite
        rests on it.
        """
        assert len(CAPTION_VARIANTS) >= 52

    def test_every_variant_record_has_the_three_documented_fields(self) -> None:
        for variant in CAPTION_VARIANTS:
            assert set(variant) == {"text", "canonical", "damage"}, variant
            assert variant["text"], variant
            assert variant["canonical"], variant
            assert variant["damage"] in VALID_DAMAGE, variant

    def test_no_variant_is_listed_twice(self) -> None:
        texts = [variant["text"] for variant in CAPTION_VARIANTS]

        assert sorted(texts) == sorted(set(texts))

    def test_the_marked_failures_are_present_by_exact_text(self) -> None:
        """The cases the evidence was written about, kept verbatim.

        Three of these carry BL-8's measured provenance (`toma hawk`,
        `aor us master`, `air us elite`); `steel-legend` is BL-8's related
        parenthetical; `as-rock` is the reconstruction's own hyphen case and
        claims no provenance at all. All five were observed FAILING against the
        pre-fix matcher when this file was written, which is the
        demonstrated-or-labelled rule OD-16 applies to a failing-today mark.
        """
        texts = {variant["text"] for variant in CAPTION_VARIANTS}

        assert set(MARKED_FAILURES) <= texts

    def test_every_canonical_named_by_the_fixture_is_in_the_shipped_table(self) -> None:
        """A variant pointing at a canonical the table does not carry can never go green."""
        canonicals = {alias.canonical for alias in load_aliases(SHIPPED_TABLE)}
        wanted = {variant["canonical"] for variant in CAPTION_VARIANTS}

        assert wanted <= canonicals, sorted(wanted - canonicals)

    @pytest.mark.parametrize(("text", "canonical"), VARIANT_CASES)
    def test_a_variant_is_found_in_a_cue_bare_and_in_a_sentence(
        self, shipped_matcher: re.Pattern[str], text: str, canonical: str
    ) -> None:
        bare = find_mentions(make_transcript("vid1", (0.0, text)), shipped_matcher)
        carried = find_mentions(
            make_transcript("vid1", (0.0, CARRIER.format(text=text))), shipped_matcher
        )

        assert canonical in {mention.canonical for mention in bare}, f"bare: {text!r}"
        assert canonical in {mention.canonical for mention in carried}, f"in a sentence: {text!r}"

    @pytest.mark.parametrize(("text", "canonical"), VARIANT_CASES)
    def test_a_variant_is_found_in_a_title_bare_and_in_a_sentence(
        self, shipped_matcher: re.Pattern[str], text: str, canonical: str
    ) -> None:
        bare = find_title_hits(make_video("vid1", text), shipped_matcher)
        carried = find_title_hits(make_video("vid1", CARRIER.format(text=text)), shipped_matcher)

        assert canonical in bare, f"bare title: {text!r}"
        assert canonical in carried, f"title sentence: {text!r}"

    @pytest.mark.parametrize("text", NEVER_MATCH_CASES)
    def test_a_reject_yields_no_mention_at_all(
        self, shipped_matcher: re.Pattern[str], text: str
    ) -> None:
        """R1002's never-a-proper-substring clause: ANY mention here is the bug.

        Asserting "not the obvious canonical" would pass a matcher that found
        some other entity inside the fused token, which is the same defect one
        name over.
        """
        bare = find_mentions(make_transcript("vid1", (0.0, text)), shipped_matcher)
        carried = find_mentions(
            make_transcript("vid1", (0.0, CARRIER.format(text=text))), shipped_matcher
        )

        assert bare == (), f"bare: {text!r} produced {[m.canonical for m in bare]}"
        assert carried == (), f"in a sentence: {text!r} produced {[m.canonical for m in carried]}"

    @pytest.mark.parametrize("text", NEVER_MATCH_CASES)
    def test_a_reject_yields_no_title_hit_at_all(
        self, shipped_matcher: re.Pattern[str], text: str
    ) -> None:
        assert find_title_hits(make_video("vid1", text), shipped_matcher) == frozenset()
        assert (
            find_title_hits(make_video("vid1", CARRIER.format(text=text)), shipped_matcher)
            == frozenset()
        )


class TestShippedTableCaptionSplitEdits:
    """The two data edits slice 3 makes, and the guard that keeps the fold honest."""

    def shipped_forms(self) -> list[tuple[str, str]]:
        """Every `(canonical, surface_form)` the shipped table declares, in file order."""
        return [
            (alias.canonical, form)
            for alias in load_aliases(SHIPPED_TABLE)
            for form in alias.surface_forms
        ]

    def test_aorus_elite_carries_the_airus_mishearing(self) -> None:
        """`air us` for `aorus` is a mishearing no join rule can recover.

        R1002 leaves exactly that class to the table, and only the Elite
        spelling was ever heard — `airus master` is deliberately NOT added.
        """
        forms = {
            canonical: form for canonical, form in self.shipped_forms() if form == "airus elite"
        }

        assert forms == {"Aorus Elite": "airus elite"}

    def test_aorus_master_does_not_carry_the_airus_mishearing(self) -> None:
        """The table gains the OBSERVED spoken forms and no more (R1002)."""
        (master,) = [
            alias for alias in load_aliases(SHIPPED_TABLE) if alias.canonical == "Aorus Master"
        ]

        assert not any("airus" in form for form in master.surface_forms), master.surface_forms

    def test_the_airus_form_reaches_aorus_elite_however_the_caption_broke_it(
        self, shipped_matcher: re.Pattern[str]
    ) -> None:
        """One table line covers all three spellings, which is why one line is enough."""
        for text in ("air us elite", "airus elite", "air-us elite"):
            hits = find_title_hits(make_video("vid1", f"the {text} board"), shipped_matcher)
            assert "Aorus Elite" in hits, text

    def test_pro_rs_no_longer_carries_the_hyphenated_form(self) -> None:
        """It folds onto the `pro rs` beside it, so de-duplication drops it silently.

        A line the matcher can never use is worse than absent: it reads as
        coverage in `aliases --check` while carrying none.
        """
        (pro_rs,) = [alias for alias in load_aliases(SHIPPED_TABLE) if alias.canonical == "Pro RS"]

        assert "pro-rs" not in pro_rs.surface_forms
        assert "pro rs" in pro_rs.surface_forms

    def test_the_hyphenated_spelling_still_reaches_pro_rs(
        self, shipped_matcher: re.Pattern[str]
    ) -> None:
        """Removing the line removes no recall — that is the whole argument for it."""
        assert "Pro RS" in find_title_hits(make_video("vid1", "the pro-rs board"), shipped_matcher)

    def test_no_hyphenated_shipped_form_is_left_dead_by_the_fold(self) -> None:
        """Scoped to HYPHENATED forms, deliberately.

        The joining rule already makes many forms redundant — `x 870 e` folds
        onto `x870e` — and every one of those is kept on purpose: they are
        distinct normalized forms that still fire on their own, and deleting
        them would move `aliases --check`'s per-form counts for reasons nothing
        to do with this change. What the HYPHEN fold newly creates is different:
        a hyphenated form that now collides with a form beside it is dropped by
        global de-duplication and never fires again, silently.
        """
        forms = self.shipped_forms()
        collisions = {}
        for canonical, form in forms:
            if "-" not in form:
                continue
            twins = [
                (other_canonical, other)
                for other_canonical, other in forms
                if (other_canonical, other) != (canonical, form)
                and normalize(other) == normalize(form)
            ]
            if twins:
                collisions[f"{canonical}: {form}"] = twins

        assert collisions == {}, f"hyphenated forms the fold makes dead: {collisions}"


class TestCountCrossCueCandidates:
    """R1010's counter: a split across a cue boundary is COUNTED, never matched.

    OD-15 scoped cross-cue matching out and instrumented the boundary instead,
    because a loss no artifact would ever show could never be evaluated against
    evidence or superseded by it. Everything here is about a number; the
    load-bearing assertions are the ones saying nothing is emitted.
    """

    def crossing_transcript(self) -> Transcript:
        """The pair R1010 demands, spelled across two cues."""
        return make_transcript("vid1", (0.0, "the mag toma"), (3.0, "hawk has a twelve phase vrm"))

    def whole_transcript(self) -> Transcript:
        """The same words, in one cue."""
        return make_transcript("vid1", (0.0, "the mag toma hawk has a twelve phase vrm"))

    def test_a_split_across_the_boundary_is_counted(self, shipped_matcher: re.Pattern[str]) -> None:
        assert count_cross_cue_candidates(self.crossing_transcript(), shipped_matcher) == 1

    def test_a_split_across_the_boundary_yields_no_mention(
        self, shipped_matcher: re.Pattern[str]
    ) -> None:
        """THE load-bearing negative, asserted directly rather than implied.

        `find_mentions` is not touched by this slice: no `Mention` is
        constructed for a crossing match and no `start_seconds` is invented for
        one. A mention spanning two cues has no single cue start, and that field
        is what R5 cuts every excerpt window from and R14 builds every
        timestamped link on.
        """
        assert find_mentions(self.crossing_transcript(), shipped_matcher) == ()

    def test_the_same_split_inside_one_cue_is_a_mention_and_not_a_candidate(
        self, shipped_matcher: re.Pattern[str]
    ) -> None:
        transcript = self.whole_transcript()

        mentions = find_mentions(transcript, shipped_matcher)

        assert [mention.canonical for mention in mentions] == ["MAG Tomahawk"]
        assert mentions[0].start_seconds == 0.0
        assert count_cross_cue_candidates(transcript, shipped_matcher) == 0

    def test_the_counter_returns_a_plain_integer(self, shipped_matcher: re.Pattern[str]) -> None:
        """It is a count and nothing else — no mentions, no offsets, no cues."""
        count = count_cross_cue_candidates(self.crossing_transcript(), shipped_matcher)

        assert isinstance(count, int)
        assert not isinstance(count, bool)

    def test_a_transcript_with_no_cues_is_zero(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)

        assert count_cross_cue_candidates(Transcript(video_id="vid1", cues=()), matcher) == 0

    def test_a_transcript_with_one_cue_is_zero(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the x670e board is fine"))

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_a_match_wholly_inside_the_first_cue_is_not_counted(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript(
            "vid1", (0.0, "the x670e board"), (3.0, "has a twelve phase vrm")
        )

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_a_match_wholly_inside_the_second_cue_is_not_counted(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript(
            "vid1", (0.0, "it has a twelve phase vrm"), (3.0, "the x670e board")
        )

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_a_match_ending_exactly_at_the_boundary_is_not_counted(self, tmp_path: Path) -> None:
        """`match.end() > boundary + 1`, and the reason: it lies wholly in the first cue.

        `find_mentions` already found this one and gave it the first cue's
        start. Counting it here would report a loss that never happened.
        """
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the x670e"), (3.0, "board is fine"))

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_a_match_starting_after_the_separator_is_not_counted(self, tmp_path: Path) -> None:
        """`match.start() < boundary`: this one lies wholly in the second cue."""
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the board"), (3.0, "x670e is fine"))

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_spacing_damage_across_the_break_is_counted(self, tmp_path: Path) -> None:
        """The join is `normalize(a) + " " + normalize(b)`, which keeps the boundary known.

        `x 670` | `e board` becomes `the x670 e board`, where the alias really
        does start in the first cue's text and end in the second's.
        """
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the x 670"), (3.0, "e board"))

        assert count_cross_cue_candidates(transcript, matcher) == 1

    def test_no_mention_is_emitted_for_the_spacing_case_either(self, tmp_path: Path) -> None:
        """And the mentions that DO exist keep a real cue's start, never an invented one."""
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (10.0, "the x 670"), (20.0, "e board and the taichi"))

        mentions = find_mentions(transcript, matcher)

        assert [mention.canonical for mention in mentions] == ["Taichi"]
        assert [mention.start_seconds for mention in mentions] == [20.0]
        assert count_cross_cue_candidates(transcript, matcher) == 1

    @pytest.mark.parametrize("blank", ["", "   ", "..."])
    def test_a_pair_with_an_empty_side_is_skipped(self, tmp_path: Path, blank: str) -> None:
        """Both pairs here have a side that normalizes to nothing, so both are skipped.

        The candidate that a two-cue version of this transcript would report is
        not reported, which is the point: the rule is about ADJACENT cues, and
        an empty cue sits between these two.
        """
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the x 670"), (1.0, blank), (3.0, "e board"))

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_adjacency_is_list_order_and_a_silent_gap_does_not_disqualify_a_pair(
        self, tmp_path: Path
    ) -> None:
        """R1010 says adjacent cues and says nothing about time.

        An hour of silence between two cues is a fact about the audio, not about
        whether the matcher would have joined the text.
        """
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the x 670"), (3600.0, "e board"))

        assert count_cross_cue_candidates(transcript, matcher) == 1

    def test_cues_out_of_chronological_order_are_still_adjacent(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (90.0, "the x 670"), (5.0, "e board"))

        assert count_cross_cue_candidates(transcript, matcher) == 1

    def test_every_adjacent_pair_contributes_its_own_occurrences(self, tmp_path: Path) -> None:
        """The count is of MATCHES per adjacent pair — not distinct canonicals, not videos."""
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript(
            "vid1",
            (0.0, "the x 670"),
            (3.0, "e board and the b 650"),
            (6.0, "e is fine"),
        )

        assert count_cross_cue_candidates(transcript, matcher) == 2

    def test_a_canonical_found_elsewhere_in_the_video_does_not_suppress_the_count(
        self, tmp_path: Path
    ) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript(
            "vid1",
            (0.0, "the x670e board is great"),
            (3.0, "the x 670"),
            (6.0, "e board again"),
        )

        assert count_cross_cue_candidates(transcript, matcher) == 1

    def test_the_count_is_a_floor_not_a_certified_total(
        self, shipped_matcher: re.Pattern[str]
    ) -> None:
        """One left-to-right non-overlapping pass, and the docstring must say so.

        Both `aorus master` and `orus master` cross this boundary, and they
        overlap, so a single `finditer` reports one of them. R1010 asks for an
        observable that tells a zero from a material number; "at least N" does
        that, and a certified total would cost an overlapping scan for no
        decision it would change.
        """
        transcript = make_transcript("vid1", (0.0, "the aorus"), (3.0, "master board"))

        assert count_cross_cue_candidates(transcript, shipped_matcher) == 1

    def test_a_transcript_with_nothing_to_find_is_zero(self, tmp_path: Path) -> None:
        matcher = matcher_for(STANDARD_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "he talks about"), (3.0, "power supplies"))

        assert count_cross_cue_candidates(transcript, matcher) == 0

    def test_an_empty_alias_table_counts_nothing(self) -> None:
        matcher = compile_matcher(())

        assert count_cross_cue_candidates(self.crossing_transcript(), matcher) == 0

    def test_two_runs_over_one_transcript_agree(self, shipped_matcher: re.Pattern[str]) -> None:
        transcript = self.crossing_transcript()

        assert count_cross_cue_candidates(
            transcript, shipped_matcher
        ) == count_cross_cue_candidates(transcript, shipped_matcher)


class TestFindDescriptionHits:
    """`find_title_hits` over another string (OD-8, R1004).

    It takes a plain `str` rather than a `Transcript`, so every case here is a
    literal — no cache entry, no video record, no I/O.
    """

    def test_the_measured_hashtag_line_hits(self, tmp_path: Path) -> None:
        """BL-11's evidence, verbatim: `#B850` is the only signal on that video.

        The hashtag line is what BL-11 measured; the video it came from is not
        reconstructed here, because this function sees nothing but the string.
        `#` is not alphanumeric, so the matcher's boundary is satisfied with no
        hashtag-specific rule anywhere in the code.
        """
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        assert find_description_hits("#AMD #ryzen #MSI #B850 #ITX", matcher) == frozenset({"B850"})

    def test_a_plain_sentence_naming_a_board_hits(self, tmp_path: Path) -> None:
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        hits = find_description_hits("A full review of the B850 board, at last.", matcher)

        assert hits == frozenset({"B850"})

    def test_a_name_on_its_own_line_hits(self, tmp_path: Path) -> None:
        description = "Timestamps below.\n\nB850\n\nThanks for watching."

        hits = find_description_hits(description, matcher_for(DESCRIPTION_TABLE, tmp_path))

        assert hits == frozenset({"B850"})

    def test_every_canonical_named_comes_back(self, tmp_path: Path) -> None:
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        hits = find_description_hits("x670e versus b650e, with a taichi thrown in", matcher)

        assert hits == frozenset({"X670E", "B650E", "Taichi"})

    def test_repeated_hits_collapse_to_one_canonical(self, tmp_path: Path) -> None:
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        assert find_description_hits("#b850 #b850 b850", matcher) == frozenset({"B850"})

    def test_a_mangled_form_still_hits(self, tmp_path: Path) -> None:
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        assert find_description_hits("the X-670-E boards", matcher) == frozenset({"X670E"})

    def test_an_empty_description_returns_an_empty_frozenset(self, tmp_path: Path) -> None:
        result = find_description_hits("", matcher_for(DESCRIPTION_TABLE, tmp_path))

        assert result == frozenset()
        assert isinstance(result, frozenset)

    def test_nothing_matching_returns_an_empty_frozenset(self, tmp_path: Path) -> None:
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        result = find_description_hits("Subscribe for more power supply teardowns!", matcher)

        assert result == frozenset()
        assert isinstance(result, frozenset)

    def test_a_fused_token_yields_nothing(self, tmp_path: Path) -> None:
        """The boundary rule is not relaxed for descriptions."""
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)

        assert find_description_hits("theb850", matcher) == frozenset()
        assert find_description_hits("b850x", matcher) == frozenset()

    def test_boilerplate_and_links_are_matched_like_any_other_text(self, tmp_path: Path) -> None:
        """R1004 says "a normalized alias hit in the description", unqualified."""
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)
        description = (
            "Patreon: https://example.com/patreon\n"
            "Board bought here: https://example.com/b850-mobo?ref=1\n"
        )

        assert find_description_hits(description, matcher) == frozenset({"B850"})

    def test_an_empty_table_matches_nothing(self, tmp_path: Path) -> None:
        matcher = matcher_for((), tmp_path)

        assert find_description_hits("#B850 x670e taichi", matcher) == frozenset()

    def test_it_is_the_same_answer_as_a_title_carrying_the_same_words(self, tmp_path: Path) -> None:
        """Same matcher, same rules, another string — that is the whole function."""
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)
        text = "x670e and the b850, plus a taichi"

        assert find_description_hits(text, matcher) == find_title_hits(
            make_video("vid1", text), matcher
        )

    def test_it_reads_nothing_from_disk(self, tmp_path: Path) -> None:
        # Pure and total: given a compiled matcher it needs no file, and this
        # test hands it none — `tmp_path` holds only the table the matcher came
        # from, which is already compiled by the time the call happens.
        matcher = matcher_for(DESCRIPTION_TABLE, tmp_path)
        for entry in tmp_path.iterdir():
            entry.unlink()

        assert find_description_hits("#B850", matcher) == frozenset({"B850"})


class TestAliasesCommand:
    """`find-best-mobo aliases --check`.

    The corpus here is arranged so every reported number is checkable by hand:
    X670E is mentioned in three videos (two bodies and one title), B650E and
    A620 in one each — a deliberate tie, to pin the canonical-ascending
    tie-break — and Taichi in none at all.
    """

    def setup_corpus(self, tmp_path: Path) -> Config:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml", STANDARD_TABLE)
        videos = [
            make_video("vid1", "Deep dive number one"),
            make_video("vid2", "Deep dive number two"),
            make_video("vid3", "X670E rundown"),
        ]
        write_index(videos, config.data_dir / "index.jsonl")
        write_transcript(
            config,
            make_transcript(
                "vid1", (10.0, "so the x 670 e board"), (20.0, "and the b650e is fine")
            ),
        )
        write_transcript(
            config, make_transcript("vid2", (5.0, "x670e again"), (9.0, "and x670e twice"))
        )
        write_transcript(config, make_transcript("vid3", (1.0, "the a620 chipset")))
        return config

    def test_a_configured_table_outside_data_dir_is_found_and_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R1007: the loader reads the configured path and never builds one.

        The table is written where nothing else would guess — outside
        `data_dir`, and not named `aliases.toml` — so a loader that joined a
        directory to a filename could not find it. The report's first line names
        the file it read, which is how a run says out loud which table it used.
        """
        config = self.setup_corpus(tmp_path)
        elsewhere = tmp_path / "inputs" / "boards.toml"
        write_aliases(elsewhere, STANDARD_TABLE)
        (config.data_dir / "aliases.toml").unlink()
        config = replace(config, alias_table_path=elsewhere)

        assert run(config, Namespace(check=True)) == 0

        captured = capsys.readouterr()
        assert captured.out.splitlines()[0] == f"Alias table: {elsewhere}"

    def test_a_missing_configured_table_returns_one_naming_that_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal names the path that was configured, not a guessed one."""
        config = self.setup_corpus(tmp_path)
        absent = tmp_path / "inputs" / "boards.toml"
        config = replace(config, alias_table_path=absent)

        assert run(config, Namespace(check=True)) == 1

        captured = capsys.readouterr()
        assert str(absent) in captured.out
        assert "aliases.toml" not in captured.out.replace(str(absent), "")

    def test_missing_check_flag_prints_usage_and_returns_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=False)) == 2

        captured = capsys.readouterr()
        assert "--check" in captured.out + captured.err

    def test_missing_index_returns_one_naming_what_to_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml", STANDARD_TABLE)

        assert run(config, Namespace(check=True)) == 1

        out = capsys.readouterr().out
        assert "index" in out.lower(), f"the message must name the index command: {out!r}"
        assert "Traceback" not in out

    def test_an_absent_transcript_cache_returns_one_naming_what_to_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """RENAMED from `test_empty_transcript_cache_...`, and the name was the bug.

        It called this state "empty" and it is ABSENT: no `data/transcripts/`
        directory at all, which means `fetch` has not run. The assertion is
        unchanged and still passes; what changed is that the suite now has a
        separate test for the genuinely empty case below, which used to be
        indistinguishable and used to fail (R1005, OD-9).
        """
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml", STANDARD_TABLE)
        write_index([make_video("vid1")], config.data_dir / "index.jsonl")

        assert run(config, Namespace(check=True)) == 1

        out = capsys.readouterr().out
        assert "fetch" in out.lower(), f"the message must name the fetch command: {out!r}"
        assert "Traceback" not in out

    def test_an_empty_transcript_cache_reports_all_zeros_and_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`fetch` ran and cached nothing. That is a result, not a precondition failure.

        The report is useless in this state, and that is not a reason to hide
        it: R1005's point is that it is not a LIE. Every canonical reads
        `videos=0`, which says plainly that nothing was scanned — where the old
        exit-1 told the owner to re-run a stage that had already run.
        """
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml", STANDARD_TABLE)
        write_index([make_video("vid1")], config.data_dir / "index.jsonl")
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        assert "Traceback" not in out
        for canonical in ("X670E", "B650E", "A620", "Taichi"):
            line = line_with(out, canonical)
            assert "videos=0" in line and "mentions=0" in line, line
            assert "NEVER MATCHED" in line, line
        assert "4 of 4 canonicals never matched anything" in out

    def test_normal_run_returns_zero_and_reports_video_counts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        assert "Traceback" not in out
        assert re.search(r"\b3\b", line_with(out, "X670E")), (
            f"X670E is mentioned in three videos: {out!r}"
        )
        assert re.search(r"\b1\b", line_with(out, "B650E")), (
            f"B650E is mentioned in one video: {out!r}"
        )

    def test_the_matched_surface_forms_are_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        assert "x670e" in line_with(out, "X670E"), (
            f"the form that actually matched must be shown: {out!r}"
        )
        assert "b650e" in line_with(out, "B650E")

    def test_a_canonical_nothing_matched_is_listed_visibly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        assert "Taichi" in out, f"a zero-match alias must never be invisible: {out!r}"
        assert re.search(r"\b0\b", line_with(out, "Taichi")), (
            f"the zero-match alias must show its zero: {out!r}"
        )

    def test_report_order_is_video_count_descending_then_canonical_ascending(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        # X670E (3 videos) then the tie at one video, A620 before B650E, then
        # Taichi at zero.
        positions = [out.index(name) for name in ("X670E", "A620", "B650E", "Taichi")]
        assert positions == sorted(positions), f"report is out of order: {out!r}"

    def test_two_runs_over_the_same_cache_print_identically(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0
        first = capsys.readouterr().out
        assert run(config, Namespace(check=True)) == 0
        second = capsys.readouterr().out

        assert first == second
        assert first.strip() != ""

    def test_a_video_with_no_cached_transcript_does_not_stop_the_report(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)
        videos = [
            make_video("vid1", "Deep dive number one"),
            make_video("vid2", "Deep dive number two"),
            make_video("vid3", "X670E rundown"),
            make_video("vid4", "Deep dive number four"),
        ]
        write_index(videos, config.data_dir / "index.jsonl")

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        assert "Traceback" not in out
        assert re.search(r"\b3\b", line_with(out, "X670E"))

    def test_an_itx_token_counts_for_its_chipset_and_is_named_as_the_form(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """OD-7's stated measurement: the ITX spelling reaches `aliases --check`.

        A fourth video says `a620i` and nothing else, so A620 goes from one
        video to two. The report must also NAME the spelling that fired — the
        recall report is what tells the owner which forms carried the weight,
        and it measures nothing about R1003 if the derived form vanishes from it.
        A620 is deliberately the canonical here rather than B850: this class runs
        against `STANDARD_TABLE`, so the assertion is about the report, not about
        the shipped table.
        """
        config = self.setup_corpus(tmp_path)
        videos = [
            make_video("vid1", "Deep dive number one"),
            make_video("vid2", "Deep dive number two"),
            make_video("vid3", "X670E rundown"),
            make_video("vid4", "Deep dive number four"),
        ]
        write_index(videos, config.data_dir / "index.jsonl")
        write_transcript(config, make_transcript("vid4", (3.0, "the a620i is a tiny board")))

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        line = line_with(out, "A620")
        assert "videos=2" in line, f"the ITX video must be counted for A620: {out!r}"
        assert "a620i" in line, f"the form that actually fired must be shown: {out!r}"


class TestAliasPattern:
    """`alias_pattern` — the join rule for ONE already-normalized surface form.

    OD-6/R1002, slice 2. Every test here compiles the source and matches with
    it; none of them compares the source to a string. What the function returns
    is an implementation detail and the language it accepts is the contract, so
    a rewrite that changes the spelling of the pattern and not its language must
    stay green.
    """

    @pytest.mark.parametrize(
        "form",
        ["x670e", "b650", "tomahawk", "mag tomahawk", "aorus master", "steel legend", "x"],
    )
    def test_the_form_itself_matches(self, form: str) -> None:
        assert re.fullmatch(alias_pattern(form), form) is not None

    @pytest.mark.parametrize("text", one_space_splits("tomahawk"))
    def test_a_split_anywhere_inside_a_word_matches(self, text: str) -> None:
        """A caption breaks a word wherever it likes, so every break must land."""
        assert re.fullmatch(alias_pattern("tomahawk"), text) is not None

    @pytest.mark.parametrize("text", one_space_splits("aorus master"))
    def test_a_split_inside_either_word_of_a_two_word_form_matches(self, text: str) -> None:
        assert re.fullmatch(alias_pattern("aorus master"), text) is not None

    @pytest.mark.parametrize("text", ["toma hawk", "tom a hawk", "t o m a h a w k"])
    def test_several_splits_at_once_still_match(self, text: str) -> None:
        # The space is optional between EVERY adjacent pair, so more than one
        # break in a word is the same rule applied more than once.
        assert re.fullmatch(alias_pattern("tomahawk"), text) is not None

    @pytest.mark.parametrize(
        ("form", "text"),
        [
            ("aorus master", "aor us master"),
            ("steel legend", "steel leg end"),
            ("tomahawk", "toma hawk"),
            ("b650", "b 650"),
            ("b650", "b6 50"),
            ("x670e", "x 670 e"),
        ],
    )
    def test_the_split_spellings_r1002_names_match(self, form: str, text: str) -> None:
        assert re.fullmatch(alias_pattern(form), text) is not None

    @pytest.mark.parametrize(
        ("form", "text"),
        [
            ("aorus master", "aorusmaster"),
            ("steel legend", "steellegend"),
            ("mag tomahawk", "magtomahawk"),
        ],
    )
    def test_the_forms_own_space_is_required(self, form: str, text: str) -> None:
        """The space in the form is where a real token boundary has to be.

        This is the half of the rule that keeps it safe rather than merely wide:
        an optional space everywhere would make `aorus master` a substring of
        the fused token `aorusmaster`, which is exactly what R1002 forbids.
        """
        assert re.fullmatch(alias_pattern(form), text) is None

    def test_an_optional_space_is_a_single_space(self) -> None:
        # Normalized text has no runs, so the pattern needs no `+` and gains
        # none — one fewer thing that can drift between two runs (R23).
        assert re.fullmatch(alias_pattern("tomahawk"), "toma  hawk") is None

    def test_a_required_space_is_a_single_space(self) -> None:
        assert re.fullmatch(alias_pattern("aorus master"), "aorus  master") is None

    @pytest.mark.parametrize("text", ["toma\thawk", "toma\nhawk"])
    def test_the_optional_space_is_a_space_and_not_any_whitespace(self, text: str) -> None:
        assert re.fullmatch(alias_pattern("tomahawk"), text) is None

    def test_a_split_is_never_required(self) -> None:
        assert re.fullmatch(alias_pattern("tomahawk"), "tomahawk") is not None

    def test_it_carries_no_boundary_of_its_own(self) -> None:
        """No lookarounds: the boundaries are `compile_matcher`'s, not this one's.

        `theb650` is a case the matcher must never match, and this asserts the
        opposite deliberately — for one form on its own there is nothing to stop
        it. Which is the point: the anchoring lives in exactly one place, so
        `compile_matcher` is where a reader looks for it and where OD-7's later
        boundary work has to happen.
        """
        assert re.search(alias_pattern("b650"), "theb650") is not None
        assert re.search(alias_pattern("b650"), "verb 650") is not None

    def test_it_adds_no_capturing_group(self) -> None:
        # `compile_matcher` dispatches on named groups; a stray capturing group
        # from here would shift every group index it owns.
        assert re.compile(alias_pattern("mag tomahawk")).groups == 0
        assert re.compile(alias_pattern("x670e")).groups == 0

    def test_it_returns_a_string(self) -> None:
        assert isinstance(alias_pattern("x670e"), str)

    def test_it_is_deterministic_for_one_form(self) -> None:
        # R23: the same table compiles to the same bytes on every run.
        assert alias_pattern("mag tomahawk") == alias_pattern("mag tomahawk")

    def test_an_empty_form_raises_value_error(self) -> None:
        """An empty pattern matches at every position; that is the failure to name.

        `compile_matcher` drops forms that normalize to empty, so this is
        unreachable from there — which is why it is asserted here.
        """
        with pytest.raises(ValueError):
            alias_pattern("")


class TestSplitFormsMatch:
    """R1002 over normalized text, through the compiled matcher."""

    @pytest.mark.parametrize(
        ("text", "canonical"),
        [
            ("toma hawk", "MAG Tomahawk"),
            ("tom a hawk", "MAG Tomahawk"),
            ("t omahawk", "MAG Tomahawk"),
            ("tomahaw k", "MAG Tomahawk"),
            ("mag toma hawk", "MAG Tomahawk"),
            ("aor us master", "Aorus Master"),
            ("a orus master", "Aorus Master"),
            ("aorus mast er", "Aorus Master"),
            ("steel leg end", "Steel Legend"),
            ("st eel legend", "Steel Legend"),
            ("b 650", "B650"),
            ("x 870 e", "X870E"),
        ],
    )
    def test_a_split_spelling_reaches_its_canonical(
        self, tmp_path: Path, text: str, canonical: str
    ) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, text))

        assert canonical in {mention.canonical for mention in find_mentions(transcript, matcher)}

    @pytest.mark.parametrize(
        ("text", "canonical"),
        [
            ("toma hawk", "MAG Tomahawk"),
            ("aor us master", "Aorus Master"),
            ("steel leg end", "Steel Legend"),
        ],
    )
    def test_a_split_spelling_matches_mid_sentence_too(
        self, tmp_path: Path, text: str, canonical: str
    ) -> None:
        # A match at the ends of the text and a match with a word either side
        # are different positions for the boundary rule, so both are covered.
        matcher = matcher_for(SPLIT_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, f"the {text} board"))

        assert canonical in {mention.canonical for mention in find_mentions(transcript, matcher)}

    @pytest.mark.parametrize("text", one_space_splits("aorus master"))
    def test_a_split_anywhere_inside_a_word_reaches_the_canonical(
        self, tmp_path: Path, text: str
    ) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert find_title_hits(make_video("v", f"the {text} board"), matcher) == frozenset(
            {"Aorus Master"}
        )

    def test_a_hyphenated_family_name_matches_through_the_fold(self, tmp_path: Path) -> None:
        """Slice 1 and slice 2 meet here: `steel-legend` is BL-8's own example.

        The hyphen folds to a space (R1002) and the form's required space lands
        on the boundary the fold created, so the caption's spelling and the
        table's spelling finally meet.
        """
        matcher = matcher_for(SPLIT_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the ASRock B650E Steel-Legend, honestly"))

        canonicals = {mention.canonical for mention in find_mentions(transcript, matcher)}
        assert "Steel Legend" in canonicals
        assert "B650E" in canonicals

    def test_a_title_inherits_the_rule(self, tmp_path: Path) -> None:
        # Title hits go through the same matcher, so nothing here is a second
        # rule that could drift from the first.
        matcher = matcher_for(SPLIT_TABLE, tmp_path)
        video = make_video("vid1", "MSI MAG toma hawk MAX WIFI review")

        assert "MAG Tomahawk" in find_title_hits(video, matcher)

    def test_a_title_hyphenated_form_hits(self, tmp_path: Path) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert find_title_hits(make_video("vid1", "The Steel-Legend, ranked!"), matcher) == (
            frozenset({"Steel Legend"})
        )

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("the mag tomahawk board", {"MAG Tomahawk"}),
            ("the tomahawk board", {"MAG Tomahawk"}),
            ("the aorus master board", {"Aorus Master"}),
            ("the steel legend board", {"Steel Legend"}),
            ("the x870e board", {"X870E"}),
            ("the b650e board", {"B650E"}),
            ("the b650 board", {"B650"}),
            ("b650", {"B650"}),
            ("the b650e-plus board", {"B650E"}),
            ("power supply teardown", set()),
        ],
    )
    def test_everything_that_matched_before_still_matches(
        self, tmp_path: Path, text: str, expected: set[str]
    ) -> None:
        """The rule widens what matches; it may not move what already did."""
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert find_title_hits(make_video("v", text), matcher) == frozenset(expected)


class TestFusedTokensAreStillNeverMatched:
    """R1002's reject set — the half of the rule that makes it safe, not wide."""

    @pytest.mark.parametrize("text", REJECT_SET)
    def test_nothing_in_the_reject_set_yields_a_mention(self, tmp_path: Path, text: str) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, text))

        assert find_mentions(transcript, matcher) == (), f"{text!r} must produce no mention at all"

    @pytest.mark.parametrize("text", REJECT_SET)
    def test_nothing_in_the_reject_set_yields_a_title_hit(self, tmp_path: Path, text: str) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert find_title_hits(make_video("v", text), matcher) == frozenset()
        assert find_title_hits(make_video("v", f"the {text} board"), matcher) == frozenset()

    @pytest.mark.parametrize("text", REJECT_SET)
    def test_the_compiled_matcher_finds_nothing_in_the_reject_set(
        self, tmp_path: Path, text: str
    ) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert matcher.search(normalize(text)) is None

    def test_the_optional_space_does_not_reach_across_a_word_boundary(self, tmp_path: Path) -> None:
        """`verb 650` is `b650` starting inside a token, split-rule or not.

        The optional space makes `b 650` a spelling of `b650`; the left boundary
        is what stops that spelling being read out of the middle of `verb`.
        """
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert matcher.search("the amp draw is verb 650 watts") is None

    def test_a_split_spelling_may_not_end_inside_a_token_either(self, tmp_path: Path) -> None:
        """The right boundary applies to the split spelling, not just the fused one.

        `x870e` can be spelled `x 870 e`, and `x 870 ese` is that spelling
        running into a token it does not own — the same rejection as `x870ese`,
        reached the other way round.
        """
        matcher = matcher_for(SPLIT_TABLE, tmp_path)

        assert find_title_hits(make_video("v", "x 870 ese"), matcher) == frozenset()
        assert find_title_hits(make_video("v", "aor us masters"), matcher) == frozenset()


class TestLongestFormFirstIsUnchanged:
    """R23 and the ordering rule, restated over patterns that are no longer literals."""

    def test_the_longer_form_wins_at_the_same_position_when_split(self, tmp_path: Path) -> None:
        matcher = matcher_for(SPLIT_TABLE, tmp_path)
        transcript = make_transcript("vid1", (0.0, "the mag toma hawk vrm"))

        mentions = find_mentions(transcript, matcher)

        assert [mention.canonical for mention in mentions] == ["MAG Tomahawk"]
        assert mentions[0].matched_form == "mag toma hawk"

    def test_the_order_is_by_normalized_form_length_not_by_pattern_length(
        self, tmp_path: Path
    ) -> None:
        """Two forms that sort one way by form and the other way by pattern.

        `aa bb cc dd` is the longer FORM (11 characters against 10). `aabbccddee`
        compiles to the longer PATTERN, because a pattern grows by an optional
        space between every adjacent pair inside a word and this one is all one
        word. Both can match at position 0 of the text below, so whichever sort
        the implementation uses decides which canonical is reported — and R1002
        says the sort is on the form.
        """
        matcher = matcher_for(
            [
                {"canonical": "Fused", "kind": "family", "surface_forms": ["aabbccddee"]},
                {"canonical": "Spaced", "kind": "family", "surface_forms": ["aa bb cc dd"]},
            ],
            tmp_path,
        )

        assert find_title_hits(make_video("v", "aa bb cc dd ee"), matcher) == frozenset({"Spaced"})

    def test_two_canonicals_claiming_one_form_still_resolve_to_the_first(
        self, tmp_path: Path
    ) -> None:
        # Global de-duplication is unchanged: a stable sort on negated form
        # length keeps file order among equals, so the first declared wins and
        # the loser stays a visible zero in the report.
        matcher = matcher_for(
            [
                {"canonical": "First", "kind": "family", "surface_forms": ["tomahawk"]},
                {"canonical": "Second", "kind": "family", "surface_forms": ["tomahawk"]},
            ],
            tmp_path / "a",
        )

        assert find_title_hits(make_video("v", "toma hawk"), matcher) == frozenset({"First"})

    def test_the_compiled_pattern_is_byte_identical_for_a_given_table(self, tmp_path: Path) -> None:
        # R23: two runs over one table produce the same bytes, so a diff of two
        # run reports is a diff of the corpus and never of the compiler.
        first = matcher_for(SPLIT_TABLE, tmp_path / "a")
        second = matcher_for(SPLIT_TABLE, tmp_path / "b")

        assert first.pattern == second.pattern

    def test_the_shipped_table_compiles_and_finds_a_split_form(self) -> None:
        matcher = compile_matcher(load_aliases(SHIPPED_TABLE))

        assert "MAG Tomahawk" in find_title_hits(make_video("v", "the toma hawk board"), matcher)
        assert "Aorus Master" in find_title_hits(make_video("v", "aor us master"), matcher)
        assert find_title_hits(make_video("v", "theb650"), matcher) == frozenset()


class TestSplitSpellingsReachTheRecallReport:
    """R1002's stated measurement: `aliases --check` names the form that fired.

    The report only measures the change if the split spelling survives into it,
    so `matched_form` staying `match.group(0)` — the text as the caption spelled
    it — is asserted here at the report, not only at the matcher.
    """

    def setup_corpus(self, tmp_path: Path) -> Config:
        config = make_config(tmp_path / "data")
        write_aliases(config.alias_table_path, SPLIT_TABLE)
        write_index([make_video("vid1", "Deep dive")], config.data_dir / "index.jsonl")
        write_transcript(
            config,
            make_transcript(
                "vid1",
                (10.0, "so the mag toma hawk board"),
                (20.0, "and the aor us master, honestly"),
                (30.0, "the steel-legend is fine"),
            ),
        )
        return config

    def test_matched_form_is_the_split_text_the_caption_spelled(self, tmp_path: Path) -> None:
        config = self.setup_corpus(tmp_path)
        matcher = compile_matcher(load_aliases(config.alias_table_path))
        transcript = make_transcript("vid1", (7.0, "So the AOR US Master, honestly, rules"))

        (mention,) = find_mentions(transcript, matcher)

        assert mention.matched_form == "aor us master"
        assert mention.matched_form == normalize(mention.matched_form)

    def test_the_report_names_the_split_spelling_that_fired(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        assert "Traceback" not in out
        assert "mag toma hawk" in line_with(out, "MAG Tomahawk"), out
        assert "aor us master" in line_with(out, "Aorus Master"), out

    def test_a_canonical_found_only_by_a_split_spelling_is_no_longer_a_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Before R1002 all three of these read NEVER MATCHED. That was the loss."""
        config = self.setup_corpus(tmp_path)

        assert run(config, Namespace(check=True)) == 0

        out = capsys.readouterr().out
        for canonical in ("MAG Tomahawk", "Aorus Master", "Steel Legend"):
            assert "NEVER MATCHED" not in line_with(out, canonical), out
