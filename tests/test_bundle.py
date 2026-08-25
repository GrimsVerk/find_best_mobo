"""Tests for slice 5 — token estimates, bundle packing, batches and XML.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. Nothing under test is faked; the only I/O is real files
under `tmp_path`, and this slice touches no network at all.

Most of the packing tests run with `chars_per_token = 1.0`, which makes a token
a character and every cap arithmetic checkable by counting letters. One test
deliberately uses a different factor, so that a packer which hard-coded the
four-characters-per-token default is caught rather than flattered.

**Slice 2 of R28/R1008 was added blind on top of that**, from
`docs/plans/oracle/capped-whole-transcript-path.md` alone: the `<excerpt>`
element gains `form`, `part` and `parts`, always present, and a whole
transcript's parts land one per bundle in strictly ascending bundles. The
sequencing tests do not construct their parts by hand — they build a real
transcript, route it through slice 1's `choose_submission`, and pack what comes
out, because the plan asks for that ordering to be ASSERTED as a property of the
existing packer rather than engineered into a fixture.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-5 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.bundle import (
    Bundle,
    assign_batches,
    estimate_tokens,
    pack_bundles,
    render_bundle,
    write_bundles,
)
from find_best_mobo.config import Config
from find_best_mobo.excerpt import Excerpt, cut_windows, merge_overlapping, transcript_text
from find_best_mobo.aliases import Mention
from find_best_mobo.index import Video
from find_best_mobo.transcripts import Cue, Transcript
from find_best_mobo.submission import EXCERPTS, WHOLE, VideoSubmission, choose_submission


def make_config(
    data_dir: Path = Path("data"),
    *,
    bundle_token_cap: int = 24000,
    calibration_batch_size: int = 12,
    batch_count: int = 3,
    chars_per_token: float = 4.0,
) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=date(2023, 1, 1),
        data_dir=data_dir,
        shorts_max_seconds=120,
        mention_threshold=3,
        window_before_seconds=120,
        window_after_seconds=300,
        per_video_excerpt_cap=10,
        bundle_token_cap=bundle_token_cap,
        calibration_batch_size=calibration_batch_size,
        batch_count=batch_count,
        chars_per_token=chars_per_token,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


def make_excerpt(
    text: str,
    *,
    video_id: str = "v1",
    title: str = "Board roundup",
    start: float = 100.0,
    end: float = 200.0,
    canonicals: tuple[str, ...] = ("B650E",),
) -> Excerpt:
    return Excerpt(
        video_id=video_id,
        video_title=title,
        start_seconds=start,
        end_seconds=end,
        text=text,
        canonicals=canonicals,
    )


def sized_excerpt(length: int, marker: str = "x", video_id: str = "v1") -> Excerpt:
    """An excerpt whose text is exactly `length` characters long."""
    assert length >= 1
    return make_excerpt(marker * length, video_id=video_id)


def make_bundle(bundle_id: str, *, batch: int = 0, tokens: int = 10) -> Bundle:
    return Bundle(
        bundle_id=bundle_id,
        batch=batch,
        excerpts=(sized_excerpt(tokens, marker="q"),),
        projected_tokens=tokens,
    )


def make_bundles(count: int) -> tuple[Bundle, ...]:
    return tuple(make_bundle(f"bundle-{n:03d}") for n in range(1, count + 1))


def batches_of(bundles: tuple[Bundle, ...]) -> list[int]:
    return [bundle.batch for bundle in bundles]


def counts_per_batch(bundles: tuple[Bundle, ...], batch_count: int) -> list[int]:
    """How many bundles landed in batch 1, 2, ... 1 + batch_count."""
    return [
        sum(1 for bundle in bundles if bundle.batch == number)
        for number in range(1, batch_count + 2)
    ]


class TestEstimateTokens:
    @pytest.mark.parametrize(
        ("length", "expected"),
        [(1, 1), (3, 1), (4, 1), (5, 2), (8, 2), (9, 3), (100, 25)],
    )
    def test_the_default_factor_rounds_up(self, length: int, expected: int) -> None:
        assert estimate_tokens("z" * length, make_config(chars_per_token=4.0)) == expected

    def test_the_factor_comes_from_config(self) -> None:
        config = make_config(chars_per_token=2.5)

        assert estimate_tokens("z" * 10, config) == 4
        assert estimate_tokens("z" * 11, config) == 5
        assert estimate_tokens("z" * 5, config) == 2

    def test_a_factor_of_one_makes_a_token_a_character(self) -> None:
        assert estimate_tokens("hello world", make_config(chars_per_token=1.0)) == 11

    def test_a_larger_factor_gives_fewer_tokens_for_the_same_text(self) -> None:
        text = "z" * 120

        assert estimate_tokens(text, make_config(chars_per_token=3.0)) == 40
        assert estimate_tokens(text, make_config(chars_per_token=6.0)) == 20

    def test_the_empty_string_is_zero(self) -> None:
        assert estimate_tokens("", make_config(chars_per_token=4.0)) == 0
        assert estimate_tokens("", make_config(chars_per_token=1.0)) == 0

    def test_the_count_is_of_characters_not_words(self) -> None:
        # Eleven characters, two words: the factor is a character factor.
        assert estimate_tokens("hello world", make_config(chars_per_token=4.0)) == 3


class TestPackBundles:
    def test_excerpts_fill_a_bundle_up_to_the_cap(self) -> None:
        config = make_config(bundle_token_cap=25, chars_per_token=1.0)
        excerpts = [sized_excerpt(10, "a"), sized_excerpt(10, "b"), sized_excerpt(5, "c")]

        bundles = pack_bundles(excerpts, config)

        assert len(bundles) == 1
        assert bundles[0].projected_tokens == 25
        assert [e.text[0] for e in bundles[0].excerpts] == ["a", "b", "c"]

    def test_a_bundle_closes_when_the_next_excerpt_would_exceed_the_cap(self) -> None:
        config = make_config(bundle_token_cap=25, chars_per_token=1.0)
        excerpts = [sized_excerpt(10, "a"), sized_excerpt(10, "b"), sized_excerpt(10, "c")]

        bundles = pack_bundles(excerpts, config)

        assert [b.bundle_id for b in bundles] == ["bundle-001", "bundle-002"]
        assert [len(b.excerpts) for b in bundles] == [2, 1]
        assert [b.projected_tokens for b in bundles] == [20, 10]

    def test_packing_is_first_fit_in_the_order_given_and_never_reorders(self) -> None:
        config = make_config(bundle_token_cap=20, chars_per_token=1.0)
        # A greedy first-fit packer cannot rescue the 5 into the first bundle by
        # looking ahead; order is the caller's, and it is preserved.
        excerpts = [sized_excerpt(15, "a"), sized_excerpt(10, "b"), sized_excerpt(5, "c")]

        bundles = pack_bundles(excerpts, config)

        assert [[e.text[0] for e in b.excerpts] for b in bundles] == [["a"], ["b", "c"]]

    def test_an_excerpt_larger_than_the_cap_gets_a_bundle_of_its_own(self) -> None:
        config = make_config(bundle_token_cap=25, chars_per_token=1.0)
        excerpts = [sized_excerpt(10, "a"), sized_excerpt(100, "b"), sized_excerpt(10, "c")]

        bundles = pack_bundles(excerpts, config)

        assert [b.bundle_id for b in bundles] == ["bundle-001", "bundle-002", "bundle-003"]
        assert [[e.text[0] for e in b.excerpts] for b in bundles] == [["a"], ["b"], ["c"]]
        assert bundles[1].projected_tokens == 100

    def test_an_oversized_excerpt_is_neither_dropped_nor_split(self) -> None:
        config = make_config(bundle_token_cap=10, chars_per_token=1.0)
        giant = sized_excerpt(500, "g")

        bundles = pack_bundles([giant], config)

        assert len(bundles) == 1
        assert bundles[0].excerpts == (giant,)
        assert bundles[0].excerpts[0].text == giant.text

    def test_every_excerpt_given_appears_exactly_once(self) -> None:
        config = make_config(bundle_token_cap=17, chars_per_token=1.0)
        excerpts = [sized_excerpt(n, chr(ord("a") + n)) for n in range(1, 12)]

        bundles = pack_bundles(excerpts, config)

        packed = [excerpt for bundle in bundles for excerpt in bundle.excerpts]
        assert packed == excerpts

    def test_ids_count_from_one_in_packing_order(self) -> None:
        config = make_config(bundle_token_cap=10, chars_per_token=1.0)
        excerpts = [sized_excerpt(10, chr(ord("a") + n)) for n in range(4)]

        bundles = pack_bundles(excerpts, config)

        assert [b.bundle_id for b in bundles] == [
            "bundle-001",
            "bundle-002",
            "bundle-003",
            "bundle-004",
        ]

    def test_projected_tokens_is_the_sum_of_its_excerpts_estimates(self) -> None:
        config = make_config(bundle_token_cap=1000, chars_per_token=3.0)
        excerpts = [sized_excerpt(10, "a"), sized_excerpt(20, "b"), sized_excerpt(7, "c")]

        (bundle,) = pack_bundles(excerpts, config)

        assert bundle.projected_tokens == sum(estimate_tokens(e.text, config) for e in excerpts)
        # ceil(10/3) + ceil(20/3) + ceil(7/3) = 4 + 7 + 3
        assert bundle.projected_tokens == 14

    def test_the_cap_is_read_in_tokens_not_characters(self) -> None:
        config = make_config(bundle_token_cap=10, chars_per_token=4.0)
        # 20 characters is 5 tokens, so two of them fit under a 10-token cap.
        excerpts = [sized_excerpt(20, "a"), sized_excerpt(20, "b")]

        bundles = pack_bundles(excerpts, config)

        assert len(bundles) == 1
        assert bundles[0].projected_tokens == 10

    def test_batch_is_zero_before_assignment(self) -> None:
        config = make_config(bundle_token_cap=10, chars_per_token=1.0)
        excerpts = [sized_excerpt(10, "a"), sized_excerpt(10, "b")]

        bundles = pack_bundles(excerpts, config)

        assert [b.batch for b in bundles] == [0, 0]

    def test_empty_input_gives_an_empty_tuple(self) -> None:
        assert pack_bundles([], make_config(bundle_token_cap=25)) == ()

    def test_two_runs_over_the_same_input_agree(self) -> None:
        config = make_config(bundle_token_cap=25, chars_per_token=1.0)
        excerpts = [sized_excerpt(10, "a"), sized_excerpt(10, "b"), sized_excerpt(10, "c")]

        assert pack_bundles(excerpts, config) == pack_bundles(excerpts, config)


class TestAssignBatches:
    def test_batch_one_takes_at_most_the_calibration_size(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        assigned = assign_batches(make_bundles(11), config)

        assert sum(1 for bundle in assigned if bundle.batch == 1) == 2
        assert batches_of(assigned)[:2] == [1, 1]

    def test_the_rest_split_as_evenly_as_possible(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        assigned = assign_batches(make_bundles(11), config)

        assert counts_per_batch(assigned, 3) == [2, 3, 3, 3]

    def test_a_remainder_goes_to_the_earlier_batches(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        # 10 bundles: 2 calibration, 8 across three batches — 3, 3, 2.
        assigned = assign_batches(make_bundles(10), config)

        assert counts_per_batch(assigned, 3) == [2, 3, 3, 2]

    def test_no_earlier_batch_is_smaller_than_a_later_one(self) -> None:
        config = make_config(calibration_batch_size=1, batch_count=3)

        for total in range(1, 25):
            assigned = assign_batches(make_bundles(total), config)
            counts = counts_per_batch(assigned, 3)[1:]
            assert counts == sorted(counts, reverse=True), f"{total} bundles gave {counts}"
            assert sum(counts_per_batch(assigned, 3)) == total

    def test_batches_are_numbered_from_two_after_the_calibration_batch(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        assigned = assign_batches(make_bundles(11), config)

        assert sorted({bundle.batch for bundle in assigned}) == [1, 2, 3, 4]
        assert all(1 <= bundle.batch <= 4 for bundle in assigned)

    def test_the_given_order_is_preserved_and_not_re_sorted(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)
        # Ids deliberately out of lexical order: recency ordering is the
        # caller's, and this function must not impose one of its own.
        given = (
            make_bundle("bundle-007"),
            make_bundle("bundle-001"),
            make_bundle("bundle-004"),
            make_bundle("bundle-002"),
            make_bundle("bundle-009"),
        )

        assigned = assign_batches(given, config)

        assert [b.bundle_id for b in assigned] == [
            "bundle-007",
            "bundle-001",
            "bundle-004",
            "bundle-002",
            "bundle-009",
        ]

    def test_batch_numbers_run_in_the_order_the_bundles_were_given(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        assigned = assign_batches(make_bundles(11), config)

        assert batches_of(assigned) == sorted(batches_of(assigned))
        assert batches_of(assigned) == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]

    def test_fewer_bundles_than_the_calibration_size_all_land_in_batch_one(self) -> None:
        config = make_config(calibration_batch_size=5, batch_count=3)

        assigned = assign_batches(make_bundles(3), config)

        assert batches_of(assigned) == [1, 1, 1]
        assert counts_per_batch(assigned, 3) == [3, 0, 0, 0]

    def test_exactly_the_calibration_size_leaves_the_later_batches_empty(self) -> None:
        config = make_config(calibration_batch_size=4, batch_count=3)

        assigned = assign_batches(make_bundles(4), config)

        assert counts_per_batch(assigned, 3) == [4, 0, 0, 0]

    def test_fewer_remaining_bundles_than_batches_fills_the_earlier_ones(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        assigned = assign_batches(make_bundles(4), config)

        assert counts_per_batch(assigned, 3) == [2, 1, 1, 0]

    def test_one_bundle_lands_in_the_calibration_batch(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)

        assigned = assign_batches(make_bundles(1), config)

        assert batches_of(assigned) == [1]

    def test_nothing_else_about_a_bundle_changes(self) -> None:
        config = make_config(calibration_batch_size=1, batch_count=3)
        given = make_bundles(4)

        assigned = assign_batches(given, config)

        for before, after in zip(given, assigned, strict=True):
            assert after.bundle_id == before.bundle_id
            assert after.excerpts == before.excerpts
            assert after.projected_tokens == before.projected_tokens

    def test_empty_input_gives_an_empty_tuple(self) -> None:
        assert assign_batches([], make_config(calibration_batch_size=2, batch_count=3)) == ()

    def test_two_runs_over_the_same_input_agree(self) -> None:
        config = make_config(calibration_batch_size=2, batch_count=3)
        given = make_bundles(9)

        assert assign_batches(given, config) == assign_batches(given, config)


# R1008 slice 2 changes this string, and it is the only edit this file's blind
# slice-2 pass makes to work written for slice 5. The plan
# (`docs/plans/oracle/capped-whole-transcript-path.md`, "Slice 2") says the
# `<excerpt>` element GAINS `form`, `part` and `parts` and that the XML does not
# otherwise change shape — so the contract rendering is the slice-5 one with
# three attributes appended, defaults included. See
# `TestExcerptFormAttributes.test_the_attributes_are_appended_after_the_existing_ones`
# for the assumption about where they sit; the plan names the attributes but not
# their position.
EXPECTED_XML = (
    '<bundle id="bundle-003" batch="1">\n'
    '  <excerpt video_id="abc123" start="1042" end="1462" form="excerpts" part="1" parts="1">\n'
    "    <video_title>Some title</video_title>\n"
    "    <boards>B650E, X670E</boards>\n"
    "    <transcript>...the text...</transcript>\n"
    "  </excerpt>\n"
    "</bundle>\n"
)


def contract_bundle() -> Bundle:
    """The bundle whose rendering the contract spells out character by character."""
    excerpt = Excerpt(
        video_id="abc123",
        video_title="Some title",
        start_seconds=1042.0,
        end_seconds=1462.0,
        text="...the text...",
        canonicals=("B650E", "X670E"),
    )
    return Bundle(bundle_id="bundle-003", batch=1, excerpts=(excerpt,), projected_tokens=4)


class TestRenderBundle:
    def test_the_exact_shape_the_contract_specifies(self) -> None:
        assert render_bundle(contract_bundle()) == EXPECTED_XML

    def test_it_ends_with_a_single_trailing_newline(self) -> None:
        rendered = render_bundle(contract_bundle())

        assert rendered.endswith("</bundle>\n")
        assert not rendered.endswith("\n\n")

    def test_whole_seconds_are_rounded_down(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=2,
            excerpts=(make_excerpt("some words", start=1042.9, end=1462.999),),
            projected_tokens=3,
        )

        excerpt = ET.fromstring(render_bundle(bundle))[0]

        assert excerpt.get("start") == "1042"
        assert excerpt.get("end") == "1462"

    def test_a_zero_start_is_rendered_as_zero(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt("some words", start=0.0, end=300.0),),
            projected_tokens=3,
        )

        excerpt = ET.fromstring(render_bundle(bundle))[0]

        assert excerpt.get("start") == "0"
        assert excerpt.get("end") == "300"

    def test_the_bundle_id_and_batch_are_carried_on_the_root(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-042",
            batch=3,
            excerpts=(make_excerpt("some words"),),
            projected_tokens=3,
        )

        root = ET.fromstring(render_bundle(bundle))

        assert root.tag == "bundle"
        assert root.get("id") == "bundle-042"
        assert root.get("batch") == "3"

    def test_boards_are_comma_space_separated_in_sorted_order(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt("words", canonicals=("A620", "B650E", "X670E Taichi")),),
            projected_tokens=2,
        )

        boards = ET.fromstring(render_bundle(bundle))[0].find("boards")

        assert boards is not None
        assert boards.text == "A620, B650E, X670E Taichi"

    def test_an_excerpt_with_no_boards_renders_an_empty_element(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt("words", canonicals=()),),
            projected_tokens=1,
        )

        boards = ET.fromstring(render_bundle(bundle))[0].find("boards")

        assert boards is not None
        assert (boards.text or "") == ""

    def test_the_title_and_transcript_are_carried_verbatim(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt("he says the b650e is fine", title="X670E boards, ranked"),),
            projected_tokens=7,
        )

        excerpt = ET.fromstring(render_bundle(bundle))[0]
        title = excerpt.find("video_title")
        transcript = excerpt.find("transcript")

        assert title is not None
        assert transcript is not None
        assert title.text == "X670E boards, ranked"
        assert transcript.text == "he says the b650e is fine"

    def test_one_block_per_excerpt_in_order(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(
                make_excerpt("first", video_id="aaa", start=0.0, end=10.0),
                make_excerpt("second", video_id="bbb", start=20.0, end=30.0),
                make_excerpt("third", video_id="ccc", start=40.0, end=50.0),
            ),
            projected_tokens=5,
        )

        root = ET.fromstring(render_bundle(bundle))

        assert [child.tag for child in root] == ["excerpt"] * 3
        assert [child.get("video_id") for child in root] == ["aaa", "bbb", "ccc"]

    def test_an_empty_bundle_still_renders_valid_xml(self) -> None:
        bundle = Bundle(bundle_id="bundle-001", batch=1, excerpts=(), projected_tokens=0)

        root = ET.fromstring(render_bundle(bundle))

        assert root.tag == "bundle"
        assert list(root) == []

    def test_two_space_indentation(self) -> None:
        lines = render_bundle(contract_bundle()).splitlines()

        assert lines[0].startswith("<bundle")
        assert lines[1].startswith("  <excerpt ")
        assert lines[2].startswith("    <video_title>")
        assert lines[5] == "  </excerpt>"
        assert lines[6] == "</bundle>"

    def test_rendering_twice_is_identical(self) -> None:
        assert render_bundle(contract_bundle()) == render_bundle(contract_bundle())


class TestRenderBundleEscaping:
    def test_angle_brackets_and_ampersands_in_the_transcript_stay_valid_xml(self) -> None:
        raw = "he says 5 < 6 & 7 > 6 <c>markup</c>"
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt(raw),),
            projected_tokens=9,
        )

        rendered = render_bundle(bundle)
        transcript = ET.fromstring(rendered)[0].find("transcript")

        assert transcript is not None
        assert transcript.text == raw
        assert "&lt;" in rendered and "&amp;" in rendered

    def test_a_title_with_markup_characters_stays_valid_xml(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt("body", title="AM5 <boards> & chipsets"),),
            projected_tokens=1,
        )

        title = ET.fromstring(render_bundle(bundle))[0].find("video_title")

        assert title is not None
        assert title.text == "AM5 <boards> & chipsets"

    def test_a_board_name_with_markup_characters_stays_valid_xml(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt("body", canonicals=("A<620", "B&650E")),),
            projected_tokens=1,
        )

        boards = ET.fromstring(render_bundle(bundle))[0].find("boards")

        assert boards is not None
        assert boards.text == "A<620, B&650E"

    def test_a_raw_closing_tag_in_the_text_does_not_close_the_element(self) -> None:
        # The nightmare case: auto-caption text that happens to spell the tag
        # this excerpt is sitting inside.
        raw = "and then </transcript></excerpt> he said"
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(make_excerpt(raw), make_excerpt("second", video_id="bbb")),
            projected_tokens=9,
        )

        root = ET.fromstring(render_bundle(bundle))

        assert len(root) == 2
        first = root[0].find("transcript")
        assert first is not None
        assert first.text == raw


class TestWriteBundles:
    def test_files_land_under_the_batch_directory(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        bundles = (
            Bundle("bundle-001", 1, (make_excerpt("first"),), 2),
            Bundle("bundle-002", 2, (make_excerpt("second"),), 2),
        )

        write_bundles(bundles, config)

        assert (config.data_dir / "bundles" / "batch-1" / "bundle-001.xml").is_file()
        assert (config.data_dir / "bundles" / "batch-2" / "bundle-002.xml").is_file()

    def test_directories_are_created(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "nothing" / "here" / "data")

        write_bundles([Bundle("bundle-001", 4, (make_excerpt("only"),), 1)], config)

        assert (config.data_dir / "bundles" / "batch-4" / "bundle-001.xml").is_file()

    def test_the_file_holds_exactly_the_rendered_bundle(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        bundle = contract_bundle()

        write_bundles([bundle], config)

        path = config.data_dir / "bundles" / "batch-1" / "bundle-003.xml"
        assert path.read_text(encoding="utf-8") == render_bundle(bundle)
        assert path.read_text(encoding="utf-8") == EXPECTED_XML

    def test_the_return_value_is_the_count_written(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        bundles = [Bundle(f"bundle-{n:03d}", 1, (make_excerpt("t"),), 1) for n in range(1, 6)]

        assert write_bundles(bundles, config) == 5

    def test_writing_nothing_returns_zero(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")

        assert write_bundles([], config) == 0

    def test_accepts_an_iterator_of_bundles(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        bundles = [Bundle(f"bundle-{n:03d}", 2, (make_excerpt("t"),), 1) for n in range(1, 4)]

        assert write_bundles(iter(bundles), config) == 3

    def test_the_bytes_are_utf8_with_newline_line_endings(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        bundle = Bundle("bundle-001", 1, (make_excerpt("he calls it “fine” — really"),), 7)

        write_bundles([bundle], config)

        raw = (config.data_dir / "bundles" / "batch-1" / "bundle-001.xml").read_bytes()
        assert b"\r\n" not in raw
        assert "“fine” — really" in raw.decode("utf-8")

    def test_writing_twice_is_byte_identical(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        bundle = contract_bundle()
        path = config.data_dir / "bundles" / "batch-1" / "bundle-003.xml"

        write_bundles([bundle], config)
        first = path.read_bytes()
        write_bundles([bundle], config)

        assert path.read_bytes() == first
        assert first != b""

    def test_the_whole_tree_is_byte_identical_across_two_runs(self, tmp_path: Path) -> None:
        config_a = make_config(tmp_path / "a")
        config_b = make_config(tmp_path / "b")
        bundles = (
            Bundle("bundle-001", 1, (make_excerpt("first", video_id="aaa"),), 2),
            Bundle("bundle-002", 2, (make_excerpt("second", video_id="bbb"),), 2),
            Bundle("bundle-003", 2, (make_excerpt("third", video_id="ccc"),), 2),
        )

        assert write_bundles(bundles, config_a) == 3
        assert write_bundles(bundles, config_b) == 3

        def tree(root: Path) -> dict[str, bytes]:
            return {
                str(path.relative_to(root)): path.read_bytes()
                for path in sorted(root.rglob("*.xml"))
            }

        assert tree(config_a.data_dir) == tree(config_b.data_dir)
        assert len(tree(config_a.data_dir)) == 3


# --------------------------------------------------------------------------
# Slice 2 of R28/R1008 — the bundle says which form each block is, and which
# part. Everything below this line was written blind against
# `docs/plans/oracle/capped-whole-transcript-path.md`, "Slice 2".
# --------------------------------------------------------------------------


def whole_block(
    text: str,
    *,
    part: int,
    part_count: int,
    video_id: str = "v1",
    title: str = "Board roundup",
    start: float = 0.0,
    end: float = 900.0,
    canonicals: tuple[str, ...] = ("B650E",),
) -> Excerpt:
    """One part of a whole transcript, as `submission.split_whole` builds it."""
    return replace(
        make_excerpt(
            text, video_id=video_id, title=title, start=start, end=end, canonicals=canonicals
        ),
        form="whole",
        part=part,
        part_count=part_count,
    )


def one_block_bundle(excerpt: Excerpt, *, bundle_id: str = "bundle-001", batch: int = 1) -> Bundle:
    return Bundle(
        bundle_id=bundle_id,
        batch=batch,
        excerpts=(excerpt,),
        projected_tokens=len(excerpt.text),
    )


def rendered_excerpt(excerpt: Excerpt) -> ET.Element:
    """The parsed `<excerpt>` element for a bundle holding just this block."""
    return ET.fromstring(render_bundle(one_block_bundle(excerpt)))[0]


def make_video(video_id: str = "v1", title: str = "Board roundup") -> Video:
    return Video(
        video_id=video_id,
        title=title,
        upload_date=date(2024, 5, 1),
        duration_seconds=1800,
        was_live=False,
        classification="regular",
        inclusion="pending",
    )


def make_transcript(
    video_id: str = "v1", *, cue_count: int = 60, cue_length: int = 40, spacing: float = 5.0
) -> Transcript:
    """A transcript of `cue_count` equal-length cues, `spacing` seconds apart.

    The cue texts are distinct so that a part which repeated or dropped speech
    would show up as a different string, not merely a different length.
    """
    return Transcript(
        video_id=video_id,
        cues=tuple(
            Cue(start_seconds=index * spacing, text=f"cue{index:03d}".ljust(cue_length, "x"))
            for index in range(cue_count)
        ),
    )


def saturated_submission(
    config: Config, *, video_id: str = "v1", cue_count: int = 60
) -> tuple[Video, Transcript, VideoSubmission]:
    """Route a video whose windows cover it, exactly as `estimate` would.

    Windows are cut around real mentions and merged, so the 80% ratio is
    measured on the blocks that would actually be sent rather than on a number
    written into the fixture. Nothing here chooses the whole path directly.
    """
    video = make_video(video_id)
    transcript = make_transcript(video_id, cue_count=cue_count)
    mentions = (
        Mention(
            video_id=video_id,
            canonical="B650E",
            start_seconds=cue.start_seconds,
            matched_form="b650e",
        )
        for cue in transcript.cues[::10]
    )
    windows = cut_windows(transcript, tuple(mentions), video, config)
    excerpts = merge_overlapping(windows, transcript)
    return video, transcript, choose_submission(video, transcript, excerpts, config)


def parts_in_bundles(bundles: tuple[Bundle, ...], video_id: str) -> list[tuple[int, Excerpt]]:
    """Every whole-form block of `video_id`, paired with the bundle index holding it."""
    return [
        (index, block)
        for index, bundle in enumerate(bundles)
        for block in bundle.excerpts
        if block.video_id == video_id and block.form == "whole"
    ]


WHOLE_PART_XML = (
    '<bundle id="bundle-007" batch="2">\n'
    '  <excerpt video_id="xyz789" start="0" end="1200" form="whole" part="2" parts="4">\n'
    "    <video_title>Three hours of B650E</video_title>\n"
    "    <boards>B650E, X670E</boards>\n"
    "    <transcript>part two of the speech</transcript>\n"
    "  </excerpt>\n"
    "</bundle>\n"
)


def whole_part_bundle() -> Bundle:
    """A bundle holding part 2 of 4 of a whole transcript."""
    excerpt = Excerpt(
        video_id="xyz789",
        video_title="Three hours of B650E",
        start_seconds=0.0,
        end_seconds=1200.0,
        text="part two of the speech",
        canonicals=("B650E", "X670E"),
        form="whole",
        part=2,
        part_count=4,
    )
    return Bundle(bundle_id="bundle-007", batch=2, excerpts=(excerpt,), projected_tokens=6)


class TestExcerptFormAttributes:
    def test_a_whole_part_renders_the_exact_shape_the_plan_specifies(self) -> None:
        assert render_bundle(whole_part_bundle()) == WHOLE_PART_XML

    def test_the_attributes_are_appended_after_the_existing_ones(self) -> None:
        # The plan names `form`, `part` and `parts` but not where they sit. This
        # pins the reading that they are APPENDED — "the `<excerpt>` element
        # GAINS" them and "the XML does not change shape" — and it is the one
        # test to look at first if the implementation ordered them differently.
        line = render_bundle(whole_part_bundle()).splitlines()[1]

        assert line == (
            '  <excerpt video_id="xyz789" start="0" end="1200" form="whole" part="2" parts="4">'
        )

    def test_a_default_excerpt_block_still_states_all_three(self) -> None:
        # The whole point: a reader never infers meaning from an absent
        # attribute, so the excerpt path spells out its defaults too.
        excerpt = rendered_excerpt(make_excerpt("some words"))

        assert excerpt.get("form") == "excerpts"
        assert excerpt.get("part") == "1"
        assert excerpt.get("parts") == "1"

    def test_the_defaults_are_spelled_out_in_the_bytes_not_only_in_the_tree(self) -> None:
        rendered = render_bundle(one_block_bundle(make_excerpt("some words")))

        assert 'form="excerpts"' in rendered
        assert 'part="1"' in rendered
        assert 'parts="1"' in rendered

    @pytest.mark.parametrize(
        ("part", "part_count"),
        [(1, 1), (1, 2), (2, 2), (1, 7), (4, 7), (7, 7), (2, 13), (13, 13)],
    )
    def test_part_and_parts_are_rendered_from_the_fields(self, part: int, part_count: int) -> None:
        excerpt = rendered_excerpt(whole_block("text", part=part, part_count=part_count))

        assert excerpt.get("part") == str(part)
        assert excerpt.get("parts") == str(part_count)

    def test_parts_is_part_count_and_part_is_part(self) -> None:
        # Two distinct values, so an implementation that swapped the two fields
        # cannot pass by accident.
        excerpt = rendered_excerpt(whole_block("text", part=2, part_count=5))

        assert excerpt.get("part") == "2"
        assert excerpt.get("parts") == "5"

    def test_part_numbering_is_rendered_one_based(self) -> None:
        # `part` runs 1..part_count; the first part is "1", never "0".
        excerpt = rendered_excerpt(whole_block("text", part=1, part_count=4))

        assert excerpt.get("part") == "1"

    def test_the_field_is_part_count_but_the_attribute_is_parts(self) -> None:
        rendered = render_bundle(one_block_bundle(whole_block("text", part=1, part_count=3)))

        assert 'parts="3"' in rendered
        assert "part_count" not in rendered

    def test_form_is_rendered_from_the_field(self) -> None:
        assert rendered_excerpt(make_excerpt("t")).get("form") == "excerpts"
        assert rendered_excerpt(whole_block("t", part=1, part_count=1)).get("form") == "whole"

    def test_a_whole_transcript_that_fits_one_bundle_is_part_one_of_one(self) -> None:
        excerpt = rendered_excerpt(whole_block("the whole thing", part=1, part_count=1))

        assert (excerpt.get("form"), excerpt.get("part"), excerpt.get("parts")) == (
            "whole",
            "1",
            "1",
        )

    def test_every_block_in_a_mixed_bundle_carries_all_three(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(
                make_excerpt("a window", video_id="aaa"),
                whole_block("part one", part=1, part_count=2, video_id="bbb"),
                whole_block("part two", part=2, part_count=2, video_id="bbb"),
                make_excerpt("another window", video_id="ccc"),
            ),
            projected_tokens=30,
        )

        root = ET.fromstring(render_bundle(bundle))

        assert [child.get("form") for child in root] == ["excerpts", "whole", "whole", "excerpts"]
        assert [child.get("part") for child in root] == ["1", "1", "2", "1"]
        assert [child.get("parts") for child in root] == ["1", "2", "2", "1"]
        assert all(
            child.get(name) is not None for child in root for name in ("form", "part", "parts")
        )

    def test_the_element_is_not_renamed(self) -> None:
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(
                make_excerpt("a window", video_id="aaa"),
                whole_block("part one", part=1, part_count=2, video_id="bbb"),
            ),
            projected_tokens=20,
        )

        root = ET.fromstring(render_bundle(bundle))

        assert root.tag == "bundle"
        assert [child.tag for child in root] == ["excerpt", "excerpt"]

    def test_the_xml_does_not_change_shape(self) -> None:
        # Same children, same order, same indentation, same five lines per block
        # as slice 5 rendered — only the open tag grew.
        rendered = render_bundle(one_block_bundle(whole_block("body", part=3, part_count=4)))
        lines = rendered.splitlines()
        excerpt = ET.fromstring(rendered)[0]

        assert [child.tag for child in excerpt] == ["video_title", "boards", "transcript"]
        assert len(lines) == 7
        assert lines[1].startswith("  <excerpt ")
        assert lines[2].startswith("    <video_title>")
        assert lines[5] == "  </excerpt>"
        assert lines[6] == "</bundle>"

    def test_the_existing_attributes_are_untouched(self) -> None:
        excerpt = rendered_excerpt(
            whole_block("body", part=2, part_count=3, video_id="abc123", start=1042.9, end=1462.9)
        )

        assert excerpt.get("video_id") == "abc123"
        assert excerpt.get("start") == "1042"
        assert excerpt.get("end") == "1462"

    def test_the_bundle_element_gains_nothing(self) -> None:
        root = ET.fromstring(
            render_bundle(one_block_bundle(whole_block("b", part=1, part_count=2)))
        )

        assert sorted(root.keys()) == ["batch", "id"]

    def test_the_excerpt_element_carries_exactly_six_attributes(self) -> None:
        excerpt = rendered_excerpt(whole_block("b", part=1, part_count=2))

        assert sorted(excerpt.keys()) == ["end", "form", "part", "parts", "start", "video_id"]


class TestFormAttributeEscaping:
    def test_a_form_with_a_quote_stays_valid_xml(self) -> None:
        # `form` is a plain string field, so it is escaped like every other
        # attribute value rather than trusted because today's values are tame.
        raw = 'he said "5 < 6" & left'
        rendered = render_bundle(one_block_bundle(replace(make_excerpt("body"), form=raw)))

        assert "&quot;" in rendered
        assert ET.fromstring(rendered)[0].get("form") == raw

    def test_a_form_spelling_a_closing_tag_does_not_break_out(self) -> None:
        raw = '"><script>'
        bundle = Bundle(
            bundle_id="bundle-001",
            batch=1,
            excerpts=(
                replace(make_excerpt("first"), form=raw),
                make_excerpt("second", video_id="bbb"),
            ),
            projected_tokens=11,
        )

        root = ET.fromstring(render_bundle(bundle))

        assert [child.tag for child in root] == ["excerpt", "excerpt"]
        assert root[0].get("form") == raw

    def test_the_video_id_is_still_escaped_alongside_the_new_attributes(self) -> None:
        excerpt = rendered_excerpt(whole_block("body", part=1, part_count=2, video_id='a"b&c<d'))

        assert excerpt.get("video_id") == 'a"b&c<d'
        assert excerpt.get("form") == "whole"


_RENDER_SCRIPT = """
import sys

from find_best_mobo.bundle import Bundle, render_bundle
from find_best_mobo.excerpt import Excerpt

blocks = tuple(
    Excerpt(
        video_id="abc123",
        video_title="Some title",
        start_seconds=1042.0,
        end_seconds=1462.0,
        text="...the text...",
        canonicals=("B650E", "X670E"),
        form=form,
        part=part,
        part_count=parts,
    )
    for form, part, parts in (("whole", 1, 3), ("whole", 2, 3), ("excerpts", 1, 1))
)
sys.stdout.write(render_bundle(Bundle("bundle-003", 1, blocks, 12)))
"""


class TestRenderDeterminism:
    def test_the_same_blocks_render_the_same_bytes(self) -> None:
        # Two independently built but equal submissions, so a renderer keying
        # off object identity or insertion history is caught.
        first = render_bundle(whole_part_bundle())
        second = render_bundle(whole_part_bundle())

        assert first == second

    def test_the_attributes_are_derived_from_the_fields_alone(self) -> None:
        block = whole_block("body", part=2, part_count=4)
        renders = {render_bundle(one_block_bundle(block)) for _ in range(20)}

        assert len(renders) == 1

    def test_rendering_is_identical_under_a_different_hash_seed(self) -> None:
        # R23 is about two RUNS, not two calls. A renderer that built its
        # attributes from a set or a dict keyed on interned strings can be
        # stable within one process and unstable across two, and only a fresh
        # interpreter with a different `PYTHONHASHSEED` shows it.
        outputs = set()
        for seed in ("0", "1", "524287"):
            environment = dict(os.environ, PYTHONHASHSEED=seed)
            result = subprocess.run(
                [sys.executable, "-c", _RENDER_SCRIPT],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            outputs.add(result.stdout)

        assert len(outputs) == 1
        assert 'form="whole" part="1" parts="3"' in outputs.pop()

    def test_two_runs_write_the_same_bytes_for_a_whole_transcript(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", bundle_token_cap=400, chars_per_token=1.0)
        _, _, submission = saturated_submission(config)
        bundles = assign_batches(pack_bundles(submission.blocks, config), config)

        write_bundles(bundles, make_config(tmp_path / "a", chars_per_token=1.0))
        write_bundles(bundles, make_config(tmp_path / "b", chars_per_token=1.0))

        def tree(root: Path) -> dict[str, bytes]:
            return {
                str(path.relative_to(root)): path.read_bytes()
                for path in sorted(root.rglob("*.xml"))
            }

        assert tree(tmp_path / "a") == tree(tmp_path / "b")
        assert len(tree(tmp_path / "a")) == len(bundles) > 1


class TestPartsAcrossBundles:
    """The sequencing property, asserted on real slice-1 output rather than staged.

    Slice 1 closes a part only when the NEXT cue would carry it over the cap, so
    two consecutive parts can never fit in one bundle. Nothing in slice 2 makes
    that true; these tests are the check that it is.
    """

    def test_a_saturated_video_really_does_take_the_whole_path(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)

        _, transcript, submission = saturated_submission(config)

        assert submission.path == WHOLE
        assert len(submission.blocks) > 3
        assert {block.form for block in submission.blocks} == {"whole"}
        assert transcript_text(transcript) != ""

    def test_consecutive_parts_can_never_share_a_bundle(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        _, _, submission = saturated_submission(config)

        blocks = submission.blocks
        for earlier, later in zip(blocks, blocks[1:], strict=False):
            pair = estimate_tokens(earlier.text, config) + estimate_tokens(later.text, config)
            assert pair > config.bundle_token_cap

    def test_the_parts_land_one_per_bundle_in_strictly_ascending_bundles(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        _, _, submission = saturated_submission(config)

        bundles = pack_bundles(submission.blocks, config)
        placed = parts_in_bundles(bundles, "v1")

        assert [block.part for _, block in placed] == list(range(1, len(submission.blocks) + 1))
        indices = [index for index, _ in placed]
        assert indices == sorted(indices)
        assert len(set(indices)) == len(indices)
        assert {block.part_count for _, block in placed} == {len(submission.blocks)}
        assert len(bundles) > 1

    def test_greedy_packing_puts_nothing_between_two_parts(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        _, _, submission = saturated_submission(config)

        bundles = pack_bundles(submission.blocks, config)
        indices = [index for index, _ in parts_in_bundles(bundles, "v1")]

        assert indices == list(range(indices[0], indices[0] + len(indices)))

    def test_the_property_holds_with_other_videos_packed_around_them(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        _, _, submission = saturated_submission(config)
        before = make_excerpt("b" * 30, video_id="before")
        after = make_excerpt("a" * 30, video_id="after")

        bundles = pack_bundles((before, *submission.blocks, after), config)
        placed = parts_in_bundles(bundles, "v1")
        indices = [index for index, _ in placed]

        assert [block.part for _, block in placed] == list(range(1, len(submission.blocks) + 1))
        assert indices == sorted(set(indices))
        assert len(indices) == len(submission.blocks)
        for bundle in bundles:
            whole_here = [b for b in bundle.excerpts if b.video_id == "v1" and b.form == "whole"]
            assert len(whole_here) <= 1

    def test_the_rendered_bundles_read_as_part_k_of_n_in_order(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        _, _, submission = saturated_submission(config)
        bundles = pack_bundles(submission.blocks, config)
        total = len(submission.blocks)

        seen: list[tuple[str, str, str]] = []
        for bundle in bundles:
            for element in ET.fromstring(render_bundle(bundle)):
                if element.get("video_id") == "v1":
                    seen.append(
                        (
                            element.get("form") or "",
                            element.get("part") or "",
                            element.get("parts") or "",
                        )
                    )

        assert seen == [("whole", str(n), str(total)) for n in range(1, total + 1)]

    def test_no_speech_is_lost_or_repeated_across_the_bundles(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        _, transcript, submission = saturated_submission(config)

        bundles = pack_bundles(submission.blocks, config)
        rejoined = " ".join(block.text for _, block in parts_in_bundles(bundles, "v1"))

        assert rejoined == transcript_text(transcript)

    def test_a_smaller_cap_makes_more_parts_and_more_bundles(self) -> None:
        wide = make_config(bundle_token_cap=800, chars_per_token=1.0)
        narrow = make_config(bundle_token_cap=200, chars_per_token=1.0)

        _, _, wide_submission = saturated_submission(wide)
        _, _, narrow_submission = saturated_submission(narrow)

        assert len(narrow_submission.blocks) > len(wide_submission.blocks) > 1
        assert len(pack_bundles(narrow_submission.blocks, narrow)) == len(narrow_submission.blocks)
        assert len(pack_bundles(wide_submission.blocks, wide)) == len(wide_submission.blocks)

    def test_an_excerpt_path_video_is_unaffected_by_any_of_this(self) -> None:
        config = make_config(bundle_token_cap=400, chars_per_token=1.0)
        video = make_video("plain")
        transcript = make_transcript("plain", cue_count=60)
        excerpts = cut_windows(
            transcript,
            (
                Mention(
                    video_id="plain",
                    canonical="B650E",
                    start_seconds=0.0,
                    matched_form="b650e",
                ),
            ),
            video,
            replace(config, window_before_seconds=0, window_after_seconds=10),
        )

        submission = choose_submission(video, transcript, excerpts, config)
        bundles = pack_bundles(submission.blocks, config)
        elements = [e for b in bundles for e in ET.fromstring(render_bundle(b))]

        assert submission.path == EXCERPTS
        assert [e.get("form") for e in elements] == ["excerpts"] * len(elements)
        assert [e.get("part") for e in elements] == ["1"] * len(elements)
        assert [e.get("parts") for e in elements] == ["1"] * len(elements)


class TestOverCapBlocksKeepTheirOwnBundle:
    """The over-cap branch survives an uncapped whole path, asserted as an OUTCOME.

    The plan says the branch "is not removed". These tests cannot check for a
    branch, only for what it produces — and deliberately so: an over-cap block
    that is dropped, truncated or split is the defect the branch exists to rule
    out, and each of those is caught here. `cap_per_video` bounds how MANY
    excerpts a video keeps and never how big one is, so an over-cap excerpt-form
    block is still reachable; an over-cap whole-form part is slice 1's
    single-giant-cue case.
    """

    def test_an_over_cap_excerpt_block_still_gets_a_bundle_to_itself(self) -> None:
        # `cap_per_video` bounds how MANY excerpts a video keeps, never how big
        # one is, so this case survives the uncapped whole path.
        config = make_config(bundle_token_cap=50, chars_per_token=1.0)
        giant = make_excerpt("g" * 500, video_id="big")
        excerpts = [
            make_excerpt("a" * 20, video_id="one"),
            giant,
            make_excerpt("c" * 20, video_id="two"),
        ]

        bundles = pack_bundles(excerpts, config)

        assert [[e.video_id for e in b.excerpts] for b in bundles] == [["one"], ["big"], ["two"]]
        assert bundles[1].excerpts[0].text == giant.text
        assert bundles[1].projected_tokens == 500

    def test_an_over_cap_whole_part_gets_a_bundle_to_itself(self) -> None:
        config = make_config(bundle_token_cap=100, chars_per_token=1.0)
        blocks = (
            whole_block("s" * 50, part=1, part_count=3, video_id="giant"),
            whole_block("g" * 1000, part=2, part_count=3, video_id="giant"),
            whole_block("e" * 50, part=3, part_count=3, video_id="giant"),
        )

        bundles = pack_bundles(blocks, config)
        placed = parts_in_bundles(bundles, "giant")

        assert [len(b.excerpts) for b in bundles] == [1, 1, 1]
        assert [block.part for _, block in placed] == [1, 2, 3]
        assert [index for index, _ in placed] == [0, 1, 2]
        assert bundles[1].projected_tokens == 1000

    def test_the_over_cap_block_renders_its_attributes_like_any_other(self) -> None:
        config = make_config(bundle_token_cap=10, chars_per_token=1.0)
        giant = whole_block("g" * 500, part=2, part_count=2)

        (bundle,) = pack_bundles([giant], config)
        excerpt = ET.fromstring(render_bundle(bundle))[0]

        assert excerpt.get("form") == "whole"
        assert excerpt.get("part") == "2"
        assert excerpt.get("parts") == "2"
        transcript = excerpt.find("transcript")
        assert transcript is not None
        assert transcript.text == giant.text

    def test_an_oversized_block_is_still_neither_dropped_nor_split(self) -> None:
        config = make_config(bundle_token_cap=10, chars_per_token=1.0)
        giant = whole_block("g" * 500, part=1, part_count=1)

        bundles = pack_bundles([giant], config)

        assert len(bundles) == 1
        assert bundles[0].excerpts == (giant,)
