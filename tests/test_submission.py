"""Tests for slice 1 of R28/R1008 — routing a saturated video, and splitting it.

Written blind from `docs/plans/oracle/capped-whole-transcript-path.md` alone, in
a worktree at a commit where `find_best_mobo.submission` does not exist, so
failing imports are the expected state until assembly. Nothing is faked:
`excerpt_ratio`, `split_whole` and `choose_submission` are pure functions over
plain records, and this slice touches no network at all.

The plan the file is built from is the one that supersedes R1001 (OD-13): the
whole-transcript path is UNCAPPED. Size decides how many blocks a transcript is
delivered in and never whether it is delivered whole, so every routing assertion
here is about the ratio and nothing else, and `TestSizeIsNeverConsulted` is what
fails if a cap check comes back.

Every fixture is sized so the arithmetic is checkable by eye. `chars_per_token`
is 1.0 almost everywhere, which makes `estimate_tokens` the character count, and
the cue texts are short blocks of one repeated letter, so a joined part can be
read straight off the page.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as it is in
# tests/test_excerpt.py and tests/test_json3_captions.py: `find_best_mobo.submission`
# does not exist yet, so the isort rule classifies it as third-party and would
# demand a different grouping from the one it demands once it does. The block is
# written in its post-assembly order, which is the stable one.
from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.bundle import estimate_tokens
from find_best_mobo.config import Config
from find_best_mobo.excerpt import (
    Excerpt,
    cut_windows,
    transcript_characters,
    transcript_text,
)
from find_best_mobo.aliases import Mention
from find_best_mobo.index import Video
from find_best_mobo.transcripts import Cue, Transcript
from find_best_mobo.submission import (
    EXCERPTS,
    WHOLE,
    WHOLE_TRANSCRIPT_RATIO,
    VideoSubmission,
    choose_submission,
    excerpt_ratio,
    split_whole,
)

# Five four-character cues ten seconds apart. Joined they are
# "aaaa bbbb cccc dddd eeee" — 24 characters, four of them separators — and
# every split fixture below is a cap chosen against that one string.
FIVE_CUES: tuple[tuple[float, str], ...] = (
    (0.0, "aaaa"),
    (10.0, "bbbb"),
    (20.0, "cccc"),
    (30.0, "dddd"),
    (40.0, "eeee"),
)
FIVE_CUE_TEXT = "aaaa bbbb cccc dddd eeee"


def make_config(
    data_dir: Path = Path("data"),
    *,
    window_before_seconds: int = 120,
    window_after_seconds: int = 300,
    per_video_excerpt_cap: int = 10,
    bundle_token_cap: int = 24000,
    calibration_batch_size: int = 12,
    batch_count: int = 3,
    chars_per_token: float = 1.0,
) -> Config:
    """A config whose token factor is one character per token unless asked otherwise.

    `estimate_tokens` is then the character count, which is what lets every cap
    in this file be read as "this many characters of joined cue text".
    """
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=date(2023, 1, 1),
        data_dir=data_dir,
        shorts_max_seconds=120,
        mention_threshold=3,
        window_before_seconds=window_before_seconds,
        window_after_seconds=window_after_seconds,
        per_video_excerpt_cap=per_video_excerpt_cap,
        bundle_token_cap=bundle_token_cap,
        calibration_batch_size=calibration_batch_size,
        batch_count=batch_count,
        chars_per_token=chars_per_token,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


def make_video(
    video_id: str = "v1",
    title: str = "Board roundup",
    *,
    upload_date: date = date(2024, 6, 15),
) -> Video:
    return Video(
        video_id=video_id,
        title=title,
        upload_date=upload_date,
        duration_seconds=3600,
        was_live=False,
        classification="regular",
        inclusion="pending",
    )


def make_transcript(video_id: str, *cues: tuple[float, str]) -> Transcript:
    return Transcript(
        video_id=video_id,
        cues=tuple(Cue(start_seconds=start, text=text) for start, text in cues),
    )


def make_excerpt(
    text: str,
    *,
    video_id: str = "v1",
    start: float = 0.0,
    end: float = 100.0,
    canonicals: tuple[str, ...] = ("B650E",),
    title: str = "Board roundup",
) -> Excerpt:
    return Excerpt(
        video_id=video_id,
        video_title=title,
        start_seconds=start,
        end_seconds=end,
        text=text,
        canonicals=canonicals,
    )


def make_mention(canonical: str, start: float, video_id: str = "v1") -> Mention:
    return Mention(
        video_id=video_id,
        canonical=canonical,
        start_seconds=start,
        matched_form=canonical.lower(),
    )


def transcript_of_length(video_id: str, total: int) -> Transcript:
    """Two cues whose single-space join is exactly `total` characters."""
    first = (total - 1) // 2
    second = total - 1 - first
    return make_transcript(video_id, (0.0, "a" * first), (10.0, "b" * second))


def random_transcript(seed: int, cue_count: int = 40) -> Transcript:
    """Cues of varied length, deterministic per seed, for the property sweeps."""
    rng = random.Random(seed)
    cues: list[tuple[float, str]] = []
    for index in range(cue_count):
        length = rng.randint(1, 30)
        cues.append((float(index * 5), chr(ord("a") + index % 26) * length))
    return make_transcript("v1", *cues)


def part_texts(blocks: Sequence[Excerpt]) -> list[str]:
    return [block.text for block in blocks]


class TestTranscriptText:
    """One definition of the transcript's text, and `transcript_characters` on it."""

    def test_it_is_the_single_space_join_of_every_cue(self) -> None:
        assert transcript_text(make_transcript("v1", *FIVE_CUES)) == FIVE_CUE_TEXT

    def test_zero_cues_is_the_empty_string(self) -> None:
        assert transcript_text(make_transcript("v1")) == ""

    def test_one_cue_carries_no_separator(self) -> None:
        assert transcript_text(make_transcript("v1", (3.0, "alone"))) == "alone"

    def test_the_join_follows_cue_order_not_timestamp_order(self) -> None:
        out_of_order = make_transcript("v1", (90.0, "late"), (1.0, "early"))

        assert transcript_text(out_of_order) == "late early"

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_transcript_characters_is_exactly_its_length(self, seed: int) -> None:
        transcript = random_transcript(seed)

        assert transcript_characters(transcript) == len(transcript_text(transcript))

    def test_transcript_characters_is_its_length_on_the_empty_transcript_too(self) -> None:
        empty = make_transcript("v1")

        assert transcript_characters(empty) == len(transcript_text(empty)) == 0

    def test_it_agrees_with_a_window_covering_every_cue(self) -> None:
        """The denominator and the whole-path text are the same join (R1000, R28)."""
        transcript = make_transcript("v1", *FIVE_CUES)
        config = make_config(window_before_seconds=1000, window_after_seconds=1000)
        windows = cut_windows(transcript, (make_mention("B650E", 20.0),), make_video(), config)

        assert windows[0].text == transcript_text(transcript)


class TestExcerptGainsThreeDefaultedFields:
    def test_an_excerpt_built_the_old_way_is_an_excerpt_part_one_of_one(self) -> None:
        excerpt = make_excerpt("some text")

        assert excerpt.form == "excerpts"
        assert excerpt.part == 1
        assert excerpt.part_count == 1

    def test_the_default_form_is_the_excerpts_constant(self) -> None:
        assert make_excerpt("some text").form == EXCERPTS

    def test_the_two_path_constants_are_the_two_form_values(self) -> None:
        assert EXCERPTS == "excerpts"
        assert WHOLE == "whole"

    def test_the_fields_can_be_set_explicitly(self) -> None:
        block = Excerpt(
            video_id="v1",
            video_title="Board roundup",
            start_seconds=0.0,
            end_seconds=40.0,
            text="whatever",
            canonicals=("B650E",),
            form=WHOLE,
            part=2,
            part_count=4,
        )

        assert (block.form, block.part, block.part_count) == (WHOLE, 2, 4)


class TestExcerptRatio:
    def test_it_is_the_excerpt_characters_over_the_transcript_characters(self) -> None:
        transcript = transcript_of_length("v1", 100)

        assert excerpt_ratio((make_excerpt("x" * 25),), transcript) == pytest.approx(0.25)

    def test_several_excerpts_are_summed(self) -> None:
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 10), make_excerpt("y" * 20), make_excerpt("z" * 5))

        assert excerpt_ratio(excerpts, transcript) == pytest.approx(0.35)

    def test_no_excerpts_is_zero(self) -> None:
        assert excerpt_ratio((), transcript_of_length("v1", 100)) == 0.0

    def test_a_transcript_with_no_cues_is_zero_rather_than_a_division_error(self) -> None:
        assert excerpt_ratio((make_excerpt("anything"),), make_transcript("v1")) == 0.0

    def test_a_transcript_whose_text_is_empty_is_zero(self) -> None:
        empty_speech = make_transcript("v1", (0.0, ""))

        assert excerpt_ratio((make_excerpt("anything"),), empty_speech) == 0.0

    def test_the_denominator_counts_the_separators_between_cues(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)

        assert excerpt_ratio((make_excerpt(FIVE_CUE_TEXT),), transcript) == 1.0

    def test_it_reads_the_texts_and_not_the_spans(self) -> None:
        transcript = transcript_of_length("v1", 100)
        wide_span = make_excerpt("x" * 10, start=0.0, end=99999.0)

        assert excerpt_ratio((wide_span,), transcript) == pytest.approx(0.10)

    def test_overlapping_excerpts_can_exceed_one(self) -> None:
        """Which is why the ratio is measured after the merge, never before it."""
        transcript = transcript_of_length("v1", 100)
        doubled = (make_excerpt("x" * 90), make_excerpt("x" * 90))

        assert excerpt_ratio(doubled, transcript) > 1.0


class TestTheRoutingThreshold:
    """Just below, exactly at, and just above R28's 80%."""

    def test_the_constant_is_eighty_percent(self) -> None:
        assert WHOLE_TRANSCRIPT_RATIO == 0.80

    def test_just_below_the_threshold_takes_the_excerpt_path(self) -> None:
        transcript = transcript_of_length("v1", 100)
        submission = choose_submission(
            make_video(), transcript, (make_excerpt("x" * 79),), make_config()
        )

        assert submission.path == EXCERPTS

    def test_exactly_at_the_threshold_takes_the_whole_path(self) -> None:
        """R28 says "80% or more", so the boundary belongs to the whole path."""
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 80),)
        assert excerpt_ratio(excerpts, transcript) == WHOLE_TRANSCRIPT_RATIO

        submission = choose_submission(make_video(), transcript, excerpts, make_config())

        assert submission.path == WHOLE

    def test_just_above_the_threshold_takes_the_whole_path(self) -> None:
        transcript = transcript_of_length("v1", 100)
        submission = choose_submission(
            make_video(), transcript, (make_excerpt("x" * 81),), make_config()
        )

        assert submission.path == WHOLE

    def test_exactly_at_the_threshold_on_a_larger_scale_too(self) -> None:
        transcript = transcript_of_length("v1", 500)
        excerpts = (make_excerpt("x" * 200), make_excerpt("y" * 200))
        assert excerpt_ratio(excerpts, transcript) == WHOLE_TRANSCRIPT_RATIO

        assert choose_submission(make_video(), transcript, excerpts, make_config()).path == WHOLE

    def test_one_character_short_of_the_boundary_is_still_excerpts(self) -> None:
        transcript = transcript_of_length("v1", 500)
        excerpts = (make_excerpt("x" * 399),)

        assert choose_submission(make_video(), transcript, excerpts, make_config()).path == EXCERPTS

    def test_a_fully_covered_transcript_goes_whole(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        excerpts = (make_excerpt(FIVE_CUE_TEXT),)

        assert choose_submission(make_video(), transcript, excerpts, make_config()).path == WHOLE


class TestSizeIsNeverConsulted:
    """OD-13's whole point: the router compares the ratio and nothing else."""

    def test_a_saturated_transcript_far_larger_than_the_cap_still_goes_whole(self) -> None:
        cues = tuple((float(index * 5), "word" * 20) for index in range(200))
        transcript = make_transcript("v1", *cues)
        config = make_config(bundle_token_cap=100)
        excerpts = (make_excerpt(transcript_text(transcript)),)

        submission = choose_submission(make_video(), transcript, excerpts, config)

        assert submission.path == WHOLE
        assert submission.projected_tokens > config.bundle_token_cap

    def test_the_path_does_not_change_with_the_bundle_cap(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        excerpts = (make_excerpt("x" * 20),)
        tiny = choose_submission(
            make_video(), transcript, excerpts, make_config(bundle_token_cap=4)
        )
        huge = choose_submission(
            make_video(), transcript, excerpts, make_config(bundle_token_cap=1_000_000)
        )

        assert tiny.path == huge.path == WHOLE

    def test_only_the_number_of_blocks_changes_with_the_cap(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        excerpts = (make_excerpt("x" * 20),)
        tiny = choose_submission(
            make_video(), transcript, excerpts, make_config(bundle_token_cap=4)
        )
        huge = choose_submission(
            make_video(), transcript, excerpts, make_config(bundle_token_cap=1_000_000)
        )

        assert len(tiny.blocks) == 5
        assert len(huge.blocks) == 1

    def test_a_video_below_the_threshold_stays_on_excerpts_however_small_it_is(self) -> None:
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 10),)

        assert choose_submission(make_video(), transcript, excerpts, make_config()).path == EXCERPTS


class TestSplitWholeParts:
    def test_a_transcript_that_fits_one_bundle_is_one_part(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=1000),
        )

        assert len(blocks) == 1
        assert blocks[0].part == 1
        assert blocks[0].part_count == 1
        assert blocks[0].text == FIVE_CUE_TEXT

    def test_the_parts_are_numbered_from_one_in_cue_order(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=10),
        )

        assert [block.part for block in blocks] == [1, 2, 3]

    def test_every_part_carries_the_same_part_count(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=10),
        )

        assert {block.part_count for block in blocks} == {len(blocks)}

    def test_the_split_is_greedy_in_cue_order(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=10),
        )

        assert part_texts(blocks) == ["aaaa bbbb", "cccc dddd", "eeee"]

    def test_a_cue_that_takes_the_part_exactly_to_the_cap_stays_in_it(self) -> None:
        """The rule is `<= cap`, so nine tokens under a cap of nine still fit."""
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=9),
        )

        assert part_texts(blocks) == ["aaaa bbbb", "cccc dddd", "eeee"]

    def test_one_token_less_of_cap_puts_every_cue_in_its_own_part(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=8),
        )

        assert part_texts(blocks) == ["aaaa", "bbbb", "cccc", "dddd", "eeee"]

    def test_the_whole_transcript_in_one_part_when_the_cap_is_its_exact_size(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("B650E",),
            make_config(bundle_token_cap=len(FIVE_CUE_TEXT)),
        )

        assert part_texts(blocks) == [FIVE_CUE_TEXT]

    @pytest.mark.parametrize("cap", [9, 10, 13, 19, 24, 1000])
    def test_no_part_exceeds_the_cap_when_no_single_cue_does(self, cap: int) -> None:
        config = make_config(bundle_token_cap=cap)
        blocks = split_whole(make_video(), make_transcript("v1", *FIVE_CUES), (), config)

        assert all(estimate_tokens(block.text, config) <= cap for block in blocks)

    def test_the_split_uses_the_same_estimator_the_packer_does(self) -> None:
        """A four-characters-per-token factor makes a 40-character cue ten tokens."""
        config = make_config(bundle_token_cap=25, chars_per_token=4.0)
        cues = tuple((float(index * 5), "z" * 40) for index in range(4))
        blocks = split_whole(make_video(), make_transcript("v1", *cues), (), config)

        assert [estimate_tokens(block.text, config) for block in blocks] == [21, 21]


class TestSplitWholeConservesEverySpokenCharacter:
    def test_the_parts_rejoin_into_the_whole_transcript(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=10))

        assert " ".join(block.text for block in blocks) == transcript_text(transcript)

    @pytest.mark.parametrize("cap", [4, 8, 9, 10, 13, 19, 24, 1000])
    def test_the_character_arithmetic_is_exact(self, cap: int) -> None:
        """The assertion the plan states: one joining space is consumed per split."""
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=cap))
        part_count = blocks[0].part_count

        assert sum(len(block.text) for block in blocks) == transcript_characters(transcript) - (
            part_count - 1
        )

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
    @pytest.mark.parametrize("cap", [12, 40, 200])
    def test_the_arithmetic_holds_over_generated_transcripts(self, seed: int, cap: int) -> None:
        transcript = random_transcript(seed)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=cap))
        part_count = blocks[0].part_count

        assert sum(len(block.text) for block in blocks) == transcript_characters(transcript) - (
            part_count - 1
        )
        assert " ".join(block.text for block in blocks) == transcript_text(transcript)

    def test_a_one_part_split_loses_nothing_at_all(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=10_000))

        assert sum(len(block.text) for block in blocks) == transcript_characters(transcript)

    @pytest.mark.parametrize("cap", [4, 8, 9, 10, 13, 19, 24])
    def test_no_cue_is_ever_split(self, cap: int) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=cap))
        rejoined = " ".join(block.text for block in blocks)

        assert rejoined.split(" ") == [cue.text for cue in transcript.cues]

    def test_no_cue_text_appears_in_two_parts(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=10))

        for cue in transcript.cues:
            assert sum(block.text.count(cue.text) for block in blocks) == 1

    def test_the_last_part_is_never_dropped(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=10))

        assert blocks[-1].text.endswith("eeee")
        assert blocks[-1].part == blocks[-1].part_count


class TestSplitWholeNeverSplitsACue:
    """A cue over the cap becomes a part on its own and exceeds it (the packer's rule)."""

    def test_a_transcript_of_one_giant_cue_is_part_one_of_one(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", (0.0, "g" * 500))
        blocks = split_whole(make_video(), transcript, (), config)

        assert len(blocks) == 1
        assert blocks[0].part == 1
        assert blocks[0].part_count == 1
        assert blocks[0].text == "g" * 500

    def test_the_over_cap_part_really_does_exceed_the_cap(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", (0.0, "g" * 500))
        blocks = split_whole(make_video(), transcript, (), config)

        assert estimate_tokens(blocks[0].text, config) > config.bundle_token_cap

    def test_a_giant_cue_between_ordinary_ones_stands_alone(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", (0.0, "aaaa"), (10.0, "G" * 50), (20.0, "bbbb"))
        blocks = split_whole(make_video(), transcript, (), config)

        assert part_texts(blocks) == ["aaaa", "G" * 50, "bbbb"]
        assert [block.part for block in blocks] == [1, 2, 3]

    def test_the_arithmetic_still_holds_around_a_giant_cue(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", (0.0, "aaaa"), (10.0, "G" * 50), (20.0, "bbbb"))
        blocks = split_whole(make_video(), transcript, (), config)

        assert sum(len(block.text) for block in blocks) == transcript_characters(transcript) - 2

    def test_a_cue_over_the_cap_is_not_cut_to_fit(self) -> None:
        config = make_config(bundle_token_cap=3)
        transcript = make_transcript("v1", *FIVE_CUES)
        blocks = split_whole(make_video(), transcript, (), config)

        assert part_texts(blocks) == ["aaaa", "bbbb", "cccc", "dddd", "eeee"]


class TestSplitWholeProvenance:
    def test_the_video_id_and_title_come_from_the_video(self) -> None:
        video = make_video("abc123", "X670E boards, ranked")
        blocks = split_whole(
            video, make_transcript("abc123", *FIVE_CUES), (), make_config(bundle_token_cap=10)
        )

        assert {block.video_id for block in blocks} == {"abc123"}
        assert {block.video_title for block in blocks} == {"X670E boards, ranked"}

    def test_every_part_is_marked_whole(self) -> None:
        blocks = split_whole(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config(bundle_token_cap=10)
        )

        assert {block.form for block in blocks} == {WHOLE}

    def test_canonicals_are_the_distinct_sorted_union_on_every_part(self) -> None:
        blocks = split_whole(
            make_video(),
            make_transcript("v1", *FIVE_CUES),
            ("X670E", "B650E", "X670E", "A620"),
            make_config(bundle_token_cap=10),
        )

        assert len(blocks) == 3
        for block in blocks:
            assert block.canonicals == ("A620", "B650E", "X670E")

    def test_no_canonicals_at_all_is_an_empty_tuple(self) -> None:
        blocks = split_whole(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config(bundle_token_cap=10)
        )

        assert all(block.canonicals == () for block in blocks)

    def test_the_blocks_are_a_tuple_of_excerpts(self) -> None:
        blocks = split_whole(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config(bundle_token_cap=10)
        )

        assert isinstance(blocks, tuple)
        assert all(isinstance(block, Excerpt) for block in blocks)


class TestSplitWholeSpans:
    """A part runs from its first cue's start to its LAST CUE'S START."""

    def test_a_parts_span_ends_at_its_last_cues_start(self) -> None:
        blocks = split_whole(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config(bundle_token_cap=10)
        )

        assert [(block.start_seconds, block.end_seconds) for block in blocks] == [
            (0.0, 10.0),
            (20.0, 30.0),
            (40.0, 40.0),
        ]

    def test_a_one_cue_part_starts_and_ends_at_that_cue(self) -> None:
        blocks = split_whole(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config(bundle_token_cap=8)
        )

        assert [(block.start_seconds, block.end_seconds) for block in blocks] == [
            (0.0, 0.0),
            (10.0, 10.0),
            (20.0, 20.0),
            (30.0, 30.0),
            (40.0, 40.0),
        ]

    def test_a_single_part_spans_the_first_cue_to_the_last_cues_start(self) -> None:
        blocks = split_whole(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config(bundle_token_cap=1000)
        )

        assert (blocks[0].start_seconds, blocks[0].end_seconds) == (0.0, 40.0)

    def test_the_span_never_runs_past_the_last_cue_it_holds(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        starts = [cue.start_seconds for cue in transcript.cues]
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=10))

        for block in blocks:
            assert block.end_seconds in starts
            assert block.end_seconds <= max(starts)

    def test_the_spans_are_ascending_and_do_not_overlap(self) -> None:
        transcript = random_transcript(7)
        blocks = split_whole(make_video(), transcript, (), make_config(bundle_token_cap=40))

        for earlier, later in zip(blocks, blocks[1:], strict=False):
            assert earlier.end_seconds < later.start_seconds


class TestChooseSubmissionOnTheWholePath:
    def test_the_blocks_are_exactly_what_split_whole_produces(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", *FIVE_CUES)
        video = make_video()
        excerpts = (make_excerpt("x" * 20, canonicals=("B650E",)),)

        submission = choose_submission(video, transcript, excerpts, config)

        assert submission.blocks == split_whole(video, transcript, ("B650E",), config)

    def test_the_canonicals_are_the_union_of_the_videos_excerpts(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", *FIVE_CUES)
        excerpts = (
            make_excerpt("x" * 12, canonicals=("X670E", "A620")),
            make_excerpt("y" * 12, canonicals=("B650E", "X670E")),
        )

        submission = choose_submission(make_video(), transcript, excerpts, config)

        assert submission.path == WHOLE
        for block in submission.blocks:
            assert block.canonicals == ("A620", "B650E", "X670E")

    def test_the_video_identity_is_carried_onto_the_submission(self) -> None:
        video = make_video("abc123", "X670E boards, ranked")
        transcript = make_transcript("abc123", *FIVE_CUES)
        submission = choose_submission(video, transcript, (make_excerpt("x" * 20),), make_config())

        assert submission.video_id == "abc123"
        assert submission.video_title == "X670E boards, ranked"

    def test_transcript_characters_is_the_whole_transcripts(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)
        submission = choose_submission(
            make_video(), transcript, (make_excerpt("x" * 20),), make_config()
        )

        assert submission.transcript_characters == transcript_characters(transcript)

    def test_a_multi_part_submission_keeps_every_character(self) -> None:
        transcript = random_transcript(11)
        excerpts = (make_excerpt(transcript_text(transcript)),)
        submission = choose_submission(
            make_video(), transcript, excerpts, make_config(bundle_token_cap=50)
        )
        part_count = submission.blocks[0].part_count

        assert submission.path == WHOLE
        assert part_count > 1
        assert sum(len(block.text) for block in submission.blocks) == transcript_characters(
            transcript
        ) - (part_count - 1)


class TestChooseSubmissionOnTheExcerptPath:
    def test_the_excerpts_are_contributed_unchanged(self) -> None:
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 10), make_excerpt("y" * 20))

        submission = choose_submission(make_video(), transcript, excerpts, make_config())

        assert submission.path == EXCERPTS
        assert submission.blocks == excerpts

    def test_the_blocks_keep_the_default_form_and_part_fields(self) -> None:
        transcript = transcript_of_length("v1", 100)
        submission = choose_submission(
            make_video(), transcript, (make_excerpt("x" * 10),), make_config()
        )

        assert [(b.form, b.part, b.part_count) for b in submission.blocks] == [(EXCERPTS, 1, 1)]

    def test_the_blocks_are_a_tuple(self) -> None:
        transcript = transcript_of_length("v1", 100)
        submission = choose_submission(
            make_video(), transcript, [make_excerpt("x" * 10)], make_config()
        )

        assert isinstance(submission.blocks, tuple)

    def test_a_video_with_no_excerpts_contributes_nothing(self) -> None:
        submission = choose_submission(
            make_video(), make_transcript("v1", *FIVE_CUES), (), make_config()
        )

        assert submission.path == EXCERPTS
        assert submission.blocks == ()
        assert submission.excerpt_characters == 0
        assert submission.projected_tokens == 0

    def test_a_video_with_no_excerpts_has_ratio_zero(self) -> None:
        transcript = make_transcript("v1", *FIVE_CUES)

        assert excerpt_ratio((), transcript) == 0.0

    def test_a_transcript_with_no_cues_takes_the_excerpt_path(self) -> None:
        """Rather than dividing by zero, and rather than sending an empty whole block."""
        excerpts = (make_excerpt("x" * 40),)
        submission = choose_submission(make_video(), make_transcript("v1"), excerpts, make_config())

        assert submission.path == EXCERPTS
        assert submission.blocks == excerpts
        assert submission.transcript_characters == 0

    def test_a_transcript_whose_text_is_empty_takes_the_excerpt_path(self) -> None:
        empty_speech = make_transcript("v1", (0.0, ""))
        excerpts = (make_excerpt("x" * 40),)

        submission = choose_submission(make_video(), empty_speech, excerpts, make_config())

        assert submission.path == EXCERPTS
        assert submission.blocks == excerpts

    def test_an_empty_transcript_and_no_excerpts_is_still_the_excerpt_path(self) -> None:
        submission = choose_submission(make_video(), make_transcript("v1"), (), make_config())

        assert submission.path == EXCERPTS
        assert submission.blocks == ()


class TestProjectedTokens:
    def test_it_sums_estimate_tokens_over_the_blocks_on_the_excerpt_path(self) -> None:
        config = make_config()
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 10), make_excerpt("y" * 20))

        submission = choose_submission(make_video(), transcript, excerpts, config)

        assert submission.projected_tokens == 30

    def test_it_sums_the_parts_on_the_whole_path(self) -> None:
        config = make_config(bundle_token_cap=10)
        transcript = make_transcript("v1", *FIVE_CUES)
        submission = choose_submission(make_video(), transcript, (make_excerpt("x" * 20),), config)

        assert submission.projected_tokens == 9 + 9 + 4

    def test_it_is_the_per_block_estimate_and_not_the_estimate_of_the_joined_text(self) -> None:
        """Each block is rounded up on its own, exactly as the packer rounds it."""
        config = make_config(chars_per_token=4.0)
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 5), make_excerpt("y" * 5))

        submission = choose_submission(make_video(), transcript, excerpts, config)

        assert submission.projected_tokens == 4
        assert estimate_tokens("x" * 5 + " " + "y" * 5, config) == 3

    def test_it_counts_the_blocks_the_submission_contributes_not_the_excerpts_it_discarded(
        self,
    ) -> None:
        config = make_config(bundle_token_cap=1000)
        transcript = make_transcript("v1", *FIVE_CUES)
        excerpts = (make_excerpt("x" * 20), make_excerpt("y" * 20))

        submission = choose_submission(make_video(), transcript, excerpts, config)

        assert submission.path == WHOLE
        assert submission.projected_tokens == len(FIVE_CUE_TEXT)


class TestSubmissionCharacterFields:
    def test_transcript_characters_is_the_transcripts_on_the_excerpt_path(self) -> None:
        transcript = transcript_of_length("v1", 100)
        submission = choose_submission(
            make_video(), transcript, (make_excerpt("x" * 10),), make_config()
        )

        assert submission.transcript_characters == 100

    def test_excerpt_characters_is_the_summed_excerpt_text(self) -> None:
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 10), make_excerpt("y" * 20))

        submission = choose_submission(make_video(), transcript, excerpts, make_config())

        assert submission.excerpt_characters == 30

    def test_the_two_fields_reproduce_the_ratio_the_routing_read(self) -> None:
        """The pair is what lets a reader check one video's routing by hand."""
        transcript = transcript_of_length("v1", 100)
        excerpts = (make_excerpt("x" * 85),)

        submission = choose_submission(make_video(), transcript, excerpts, make_config())

        assert submission.path == WHOLE
        assert submission.excerpt_characters / submission.transcript_characters == excerpt_ratio(
            excerpts, transcript
        )

    def test_it_is_a_frozen_record(self) -> None:
        submission = choose_submission(
            make_video(), transcript_of_length("v1", 100), (make_excerpt("x"),), make_config()
        )

        assert isinstance(submission, VideoSubmission)
        with pytest.raises(FrozenInstanceError):
            submission.path = WHOLE  # type: ignore[misc]


class TestDeterminism:
    @pytest.mark.parametrize("cap", [10, 24, 1000])
    def test_two_runs_over_the_same_input_agree(self, cap: int) -> None:
        config = make_config(bundle_token_cap=cap)
        transcript = make_transcript("v1", *FIVE_CUES)
        excerpts = (make_excerpt("x" * 20, canonicals=("X670E", "A620")),)
        video = make_video()

        first = choose_submission(video, transcript, excerpts, config)
        second = choose_submission(video, transcript, excerpts, config)

        assert first == second
