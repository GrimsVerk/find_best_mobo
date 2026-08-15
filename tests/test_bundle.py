"""Tests for slice 5 — token estimates, bundle packing, batches and XML.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. Nothing under test is faked; the only I/O is real files
under `tmp_path`, and this slice touches no network at all.

Most of the packing tests run with `chars_per_token = 1.0`, which makes a token
a character and every cap arithmetic checkable by counting letters. One test
deliberately uses a different factor, so that a packer which hard-coded the
four-characters-per-token default is caught rather than flattered.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-5 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import xml.etree.ElementTree as ET
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
from find_best_mobo.excerpt import Excerpt


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


EXPECTED_XML = (
    '<bundle id="bundle-003" batch="1">\n'
    '  <excerpt video_id="abc123" start="1042" end="1462">\n'
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
