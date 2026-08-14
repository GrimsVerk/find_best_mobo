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
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import (
    Alias,
    Mention,
    compile_matcher,
    find_mentions,
    find_title_hits,
    load_aliases,
)
from find_best_mobo.commands.aliases import run
from find_best_mobo.config import Config
from find_best_mobo.index import Video, write_index
from find_best_mobo.normalize import normalize
from find_best_mobo.transcripts import Cue, Transcript, cache_path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_TABLE = REPO_ROOT / "data" / "aliases.toml"

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


def matcher_for(entries: Sequence[Mapping[str, object]], tmp_path: Path) -> re.Pattern[str]:
    table = write_aliases(tmp_path / "aliases.toml", entries)
    return compile_matcher(load_aliases(table))


def line_with(output: str, token: str) -> str:
    """The first output line mentioning `token`, for asserting on a report row."""
    for line in output.splitlines():
        if token in line:
            return line
    raise AssertionError(f"no line of the report mentions {token!r}:\n{output}")


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

    def test_empty_transcript_cache_returns_one_naming_what_to_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml", STANDARD_TABLE)
        write_index([make_video("vid1")], config.data_dir / "index.jsonl")

        assert run(config, Namespace(check=True)) == 1

        out = capsys.readouterr().out
        assert "fetch" in out.lower(), f"the message must name the fetch command: {out!r}"
        assert "Traceback" not in out

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
