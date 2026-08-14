"""Tests for slice 3 — normalization of caption text and titles.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. `normalize` is pure, total and has no boundaries, so
nothing here is faked at all.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-3 module
# below does not exist yet, so the isort rule classifies it as third-party and
# would demand a different grouping from the one it demands once it does — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import pytest

from find_best_mobo.normalize import normalize

# Every character the contract requires to be stripped out of part numbers.
# The hyphen is deliberately absent: it is load-bearing in `x670e-plus`.
STRIPPED_PUNCTUATION = [".", ",", "!", "?", ":", ";", '"', "'", "(", ")", "[", "]"]


class TestLowercasing:
    def test_lowercases(self) -> None:
        assert normalize("X670E TAICHI") == "x670e taichi"

    def test_mixed_case_prose_lowercases(self) -> None:
        assert normalize("The VRM Is Fine") == "the vrm is fine"

    def test_already_lowercase_text_is_unchanged(self) -> None:
        assert normalize("the vrm is fine") == "the vrm is fine"


class TestWhitespace:
    def test_runs_of_spaces_collapse_to_one(self) -> None:
        assert normalize("the     board     is     good") == "the board is good"

    def test_tabs_and_newlines_collapse_to_one_space(self) -> None:
        assert normalize("the\tboard\nis\r\ngood") == "the board is good"

    def test_ends_are_stripped(self) -> None:
        assert normalize("   \t the board \n  ") == "the board"

    def test_whitespace_only_input_becomes_empty(self) -> None:
        assert normalize("  \t\n ") == ""


class TestPunctuation:
    @pytest.mark.parametrize("mark", STRIPPED_PUNCTUATION)
    def test_each_listed_mark_is_stripped(self, mark: str) -> None:
        assert normalize(f"x670e{mark} board") == "x670e board"

    @pytest.mark.parametrize("mark", STRIPPED_PUNCTUATION)
    def test_each_listed_mark_is_stripped_at_the_end(self, mark: str) -> None:
        assert normalize(f"the board{mark}") == "the board"

    def test_wrapping_brackets_and_parens_vanish(self) -> None:
        assert normalize("(x670e) [taichi]") == "x670e taichi"

    def test_quotes_around_a_phrase_vanish(self) -> None:
        assert normalize('"the best board", he said') == "the best board he said"

    def test_hyphen_survives_as_a_character(self) -> None:
        assert "-" in normalize("the x670e-plus board")

    def test_hyphenated_model_name_is_left_intact(self) -> None:
        assert normalize("The X670E-PLUS board") == "the x670e-plus board"


class TestSpacingDamage:
    def test_spaced_out_part_number_is_joined(self) -> None:
        assert normalize("x 670 e") == "x670e"

    def test_hyphenated_part_number_is_joined(self) -> None:
        assert normalize("x-670-e") == "x670e"

    def test_split_digits_are_joined(self) -> None:
        assert normalize("x 6 70 e") == "x670e"

    def test_every_mangling_lands_on_one_string(self) -> None:
        variants = ["x 670 e", "x-670-e", "X670E", "x 6 70 e", "X 670 E"]

        assert {normalize(variant) for variant in variants} == {"x670e"}

    def test_folding_happens_inside_a_sentence(self) -> None:
        assert normalize("so the x 670 e board is good") == "so the x670e board is good"

    def test_folding_survives_punctuation_in_the_middle(self) -> None:
        assert normalize("the x 670 e, honestly, rules") == "the x670e honestly rules"

    def test_a_trailing_letter_group_folds_too(self) -> None:
        assert normalize("b 650 e") == "b650e"


class TestOrdinaryTextSurvives:
    def test_a_plain_sentence_survives_apart_from_case_and_punctuation(self) -> None:
        assert normalize("The VRM is, honestly, quite good!") == "the vrm is honestly quite good"

    def test_an_already_joined_part_number_keeps_its_neighbours_apart(self) -> None:
        # If the folding rule swallowed ordinary word boundaries here, `b650`
        # could never be matched as a token again.
        assert normalize("the b650 board") == "the b650 board"

    def test_a_number_between_two_words_does_not_glue_the_sentence(self) -> None:
        assert normalize("it costs 300 dollars") == "it costs 300 dollars"

    def test_a_bare_number_is_left_alone(self) -> None:
        assert normalize("300") == "300"


class TestTotality:
    def test_empty_string_returns_empty_string(self) -> None:
        assert normalize("") == ""

    @pytest.mark.parametrize(
        "text",
        [
            "",
            " ",
            "---",
            "!!!",
            "x",
            "9",
            "x-",
            "-e",
            "()[]",
            "x 670 e-plus, and the b 650 e too!",
            "éçho",
        ],
    )
    def test_never_raises_and_always_returns_a_string(self, text: str) -> None:
        result = normalize(text)

        assert isinstance(result, str)
        assert result == result.strip()

    def test_is_idempotent(self) -> None:
        once = normalize("So the X 670 E Taichi board, honestly?")

        assert normalize(once) == once
