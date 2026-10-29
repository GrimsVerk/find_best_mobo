"""Tests for slice 5 — excerpt windows cut around mentions.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. Nothing under test is faked: `cut_windows`,
`merge_overlapping` and `cap_per_video` are pure functions over plain records,
and this slice touches no network at all.

The windows here are deliberately small and the cue texts deliberately short, so
that every asserted span and every joined string is checkable by eye rather than
by re-deriving the implementation's arithmetic.

`TestMergeOverlapping` was rewritten for **R1000** (OD-4): `merge_overlapping`
now takes the video's transcript and RE-CUTS each merged span from the cues
instead of gluing two window texts together, so the speech in an overlap is paid
for once. Each rewritten test says in its docstring what it used to assert and
why that behaviour was retired. Two consequences have classes of their own —
`TestMergeRefusesAForeignVideo`, which replaces the old cross-video grouping
tests, and `TestTheBound`, which asserts the property R1000 states rather than
sampling it.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-5 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import Mention
from find_best_mobo.config import Config
from find_best_mobo.excerpt import (
    Excerpt,
    cap_per_video,
    cut_windows,
    merge_overlapping,
    transcript_characters,
)
from find_best_mobo.index import Video
from find_best_mobo.transcripts import Cue, Transcript


def make_config(
    data_dir: Path = Path("data"),
    *,
    window_before_seconds: int = 120,
    window_after_seconds: int = 300,
    per_video_excerpt_cap: int = 10,
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


def make_mention(canonical: str, start: float, video_id: str = "v1") -> Mention:
    return Mention(
        video_id=video_id,
        canonical=canonical,
        start_seconds=start,
        matched_form=canonical.lower(),
    )


def make_excerpt(
    video_id: str,
    start: float,
    end: float,
    text: str = "text",
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


def spans(excerpts: tuple[Excerpt, ...]) -> list[tuple[str, float, float]]:
    return [(e.video_id, e.start_seconds, e.end_seconds) for e in excerpts]


def marker(index: int) -> str:
    """The unique, ZERO-PADDED tag carried by cue `index`.

    Padded on purpose: with `"cue 1"` and `"cue 10"` the first is a substring of
    the second, and every "does this cue's text appear twice?" assertion below
    would then pass or fail for a reason that has nothing to do with merging.
    """
    return f"cue {index:03d}"


def marked_transcript(cue_count: int, *, video_id: str = "v1", spacing: float = 10.0) -> Transcript:
    """A transcript whose every cue is individually identifiable in a joined text."""
    return Transcript(
        video_id=video_id,
        cues=tuple(
            Cue(
                start_seconds=index * spacing,
                text=f"{marker(index)} the vrm on this board holds up ok!",
            )
            for index in range(cue_count)
        ),
    )


def text_between(transcript: Transcript, start: float, end: float) -> str:
    """The cutting rule as the design states it, restated here to assert against.

    Every cue whose START falls inside `[start, end]`, in cue order, joined by
    exactly one space. This is what a merged excerpt's text must be — and the
    same join `transcript_characters` counts.
    """
    return " ".join(cue.text for cue in transcript.cues if start <= cue.start_seconds <= end)


def window(
    transcript: Transcript,
    start: float,
    end: float,
    canonicals: tuple[str, ...] = ("B650E",),
    *,
    title: str = "Board roundup",
) -> Excerpt:
    """One window as `cut_windows` would have produced it over this transcript."""
    return Excerpt(
        video_id=transcript.video_id,
        video_title=title,
        start_seconds=start,
        end_seconds=end,
        text=text_between(transcript, start, end),
        canonicals=canonicals,
    )


def no_cue_appears_twice(excerpts: Sequence[Excerpt], transcript: Transcript) -> bool:
    """No cue's text is carried by more than one of these excerpts, or twice by one."""
    return all(
        sum(excerpt.text.count(marker(index)) for excerpt in excerpts) <= 1
        for index in range(len(transcript.cues))
    )


_WINDOW_WIDTHS = ((0, 15), (5, 10), (30, 60), (120, 300))
_CANONICALS = ("A620", "B650E", "X670E", "Taichi")


def generated_case(seed: int) -> tuple[Transcript, tuple[Excerpt, ...], Config]:
    """One reproducible (transcript, merged excerpts, config) case for the bound.

    Seeded rather than random-per-run: a property that fails must fail the same
    way on the next run, which is the same reason R23 pins the pipeline's own
    ordering. Mentions land inside the transcript, so every case has something to
    excerpt and the bound is never satisfied by an empty result.
    """
    rng = random.Random(seed)
    transcript = marked_transcript(rng.randint(20, 200), spacing=3.0)
    before, after = _WINDOW_WIDTHS[seed % len(_WINDOW_WIDTHS)]
    config = make_config(
        window_before_seconds=before,
        window_after_seconds=after,
        per_video_excerpt_cap=3,
    )
    last_cue = transcript.cues[-1].start_seconds
    mentions = [
        make_mention(rng.choice(_CANONICALS), round(rng.uniform(0.0, last_cue), 1))
        for _ in range(rng.randint(1, 12))
    ]
    windows = cut_windows(transcript, mentions, make_video(), config)
    return transcript, merge_overlapping(windows, transcript), config


class TestCutWindowsSpan:
    def test_the_window_is_asymmetric_around_the_mention(self) -> None:
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        transcript = make_transcript("v1", (200.0, "the b650e"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 200.0)], make_video(), config)

        assert excerpt.start_seconds == 80.0
        assert excerpt.end_seconds == 500.0

    def test_the_window_widths_come_from_config(self) -> None:
        config = make_config(window_before_seconds=10, window_after_seconds=45)
        transcript = make_transcript("v1", (200.0, "the b650e"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 200.0)], make_video(), config)

        assert excerpt.start_seconds == 190.0
        assert excerpt.end_seconds == 245.0

    def test_the_start_is_clamped_at_zero_and_never_negative(self) -> None:
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        transcript = make_transcript("v1", (30.0, "the b650e"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 30.0)], make_video(), config)

        assert excerpt.start_seconds == 0.0
        assert excerpt.end_seconds == 330.0

    def test_a_mention_at_zero_still_gives_a_window_starting_at_zero(self) -> None:
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        transcript = make_transcript("v1", (0.0, "the b650e right away"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 0.0)], make_video(), config)

        assert excerpt.start_seconds == 0.0
        assert excerpt.text == "the b650e right away"

    def test_the_end_is_not_clamped_to_the_transcript_length(self) -> None:
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        # The transcript stops at 400s; the window runs to 600s regardless.
        transcript = make_transcript("v1", (300.0, "the b650e"), (400.0, "last cue"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 300.0)], make_video(), config)

        assert excerpt.end_seconds == 600.0
        assert excerpt.text == "the b650e last cue"


class TestCutWindowsText:
    def test_only_cues_inside_the_span_are_collected(self) -> None:
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        transcript = make_transcript(
            "v1",
            (79.0, "just before"),
            (80.0, "at the start"),
            (200.0, "the b650e"),
            (500.0, "at the end"),
            (501.0, "just after"),
        )

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 200.0)], make_video(), config)

        assert excerpt.text == "at the start the b650e at the end"

    def test_cues_are_joined_with_exactly_one_space(self) -> None:
        config = make_config(window_before_seconds=10, window_after_seconds=10)
        transcript = make_transcript("v1", (95.0, "one"), (100.0, "two"), (105.0, "three"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 100.0)], make_video(), config)

        assert excerpt.text == "one two three"
        assert "  " not in excerpt.text

    def test_the_text_follows_cue_order_not_timestamp_order(self) -> None:
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        # A caption file whose cues are not in chronological order: the contract
        # says cue order, which is the order the transcript holds them in.
        transcript = make_transcript("v1", (250.0, "later"), (150.0, "earlier"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 200.0)], make_video(), config)

        assert excerpt.text == "later earlier"

    def test_a_window_with_no_cues_at_all_has_empty_text(self) -> None:
        config = make_config(window_before_seconds=1, window_after_seconds=1)
        transcript = make_transcript("v1", (500.0, "far away"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 100.0)], make_video(), config)

        assert excerpt.text == ""
        assert excerpt.start_seconds == 99.0


class TestCutWindowsProvenance:
    def test_the_video_id_and_title_come_from_the_video(self) -> None:
        config = make_config()
        video = make_video("abc123", "X670E boards, ranked")
        transcript = make_transcript("abc123", (200.0, "the b650e"))

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 200.0)], video, config)

        assert excerpt.video_id == "abc123"
        assert excerpt.video_title == "X670E boards, ranked"

    def test_the_window_carries_its_mention_canonical(self) -> None:
        config = make_config()
        transcript = make_transcript("v1", (200.0, "the taichi"))

        (excerpt,) = cut_windows(transcript, [make_mention("Taichi", 200.0)], make_video(), config)

        assert excerpt.canonicals == ("Taichi",)

    def test_canonicals_are_distinct_and_sorted_on_every_window(self) -> None:
        config = make_config()
        transcript = make_transcript("v1", (200.0, "x670e b650e a620"))
        mentions = [
            make_mention("X670E", 200.0),
            make_mention("B650E", 200.5),
            make_mention("A620", 201.0),
        ]

        excerpts = cut_windows(transcript, mentions, make_video(), config)

        for excerpt in excerpts:
            assert tuple(sorted(set(excerpt.canonicals))) == excerpt.canonicals
            assert excerpt.canonicals != ()


class TestCutWindowsPerMention:
    def test_one_window_per_mention_in_the_order_given(self) -> None:
        config = make_config(window_before_seconds=10, window_after_seconds=10)
        transcript = make_transcript("v1", (100.0, "a"), (500.0, "b"), (900.0, "c"))
        mentions = [
            make_mention("B650E", 900.0),
            make_mention("X670E", 100.0),
            make_mention("A620", 500.0),
        ]

        excerpts = cut_windows(transcript, mentions, make_video(), config)

        assert len(excerpts) == 3
        assert [e.start_seconds for e in excerpts] == [890.0, 90.0, 490.0]
        assert [e.canonicals for e in excerpts] == [("B650E",), ("X670E",), ("A620",)]

    def test_two_mentions_close_together_are_not_merged_here(self) -> None:
        # Merging is merge_overlapping's job; this stage emits one per mention
        # even when the windows plainly overlap.
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        transcript = make_transcript("v1", (200.0, "x670e"), (210.0, "b650e"))
        mentions = [make_mention("X670E", 200.0), make_mention("B650E", 210.0)]

        excerpts = cut_windows(transcript, mentions, make_video(), config)

        assert len(excerpts) == 2

    def test_no_mentions_gives_an_empty_tuple(self) -> None:
        config = make_config()
        transcript = make_transcript("v1", (10.0, "nothing relevant here"))

        assert cut_windows(transcript, [], make_video(), config) == ()

    def test_no_mentions_over_an_empty_transcript_gives_an_empty_tuple(self) -> None:
        assert cut_windows(Transcript("v1", ()), [], make_video(), make_config()) == ()

    def test_two_runs_over_the_same_input_agree(self) -> None:
        config = make_config()
        transcript = make_transcript("v1", (200.0, "x670e"), (260.0, "b650e"))
        mentions = [make_mention("X670E", 200.0), make_mention("B650E", 260.0)]

        first = cut_windows(transcript, mentions, make_video(), config)
        second = cut_windows(transcript, mentions, make_video(), config)

        assert first == second


class TestMergeOverlapping:
    """R1000: a merged span is RE-CUT from the cues, never glued together.

    Every test in this class used to assert the concatenating merge — two window
    texts joined with a space, so `"early"` and `"late"` came back as
    `"early late"` and every character of the overlap was paid for once per
    window. OD-4 retired that behaviour on BL-10's evidence: on a real 33-minute
    video a 28,438-character transcript produced a single 137,246-character
    excerpt, and the cost projection, which is the one number the checkpoint
    exists to produce, was wrong by 4.8x. The merged text is now the transcript's
    own speech across the merged span, so the overlap is counted exactly once.
    """

    def test_two_overlapping_windows_are_recut_rather_than_concatenated(self) -> None:
        """Was: the merged text was `f"{earlier.text} {later.text}"` — "early late".

        OD-4 retired it because the speech in the overlap was then counted once
        per window instead of once. The span here covers every cue, so the merged
        text is exactly the transcript's own text.
        """
        transcript = marked_transcript(16)
        earlier = window(transcript, 0.0, 100.0)
        later = window(transcript, 50.0, 150.0)

        merged = merge_overlapping([earlier, later], transcript)

        assert spans(merged) == [("v1", 0.0, 150.0)]
        assert merged[0].text == text_between(transcript, 0.0, 150.0)
        assert merged[0].text != f"{earlier.text} {later.text}"
        assert len(merged[0].text) < len(f"{earlier.text} {later.text}")

    def test_a_cue_in_the_overlap_is_counted_exactly_once(self) -> None:
        """Was: an overlap cue appeared in both window texts and so twice in the merge.

        That double count is precisely the defect R1000 removes.
        """
        transcript = marked_transcript(16)
        earlier = window(transcript, 0.0, 100.0)
        later = window(transcript, 50.0, 150.0)
        # Cue 007 starts at 70s, inside both windows.
        assert marker(7) in earlier.text
        assert marker(7) in later.text

        merged = merge_overlapping([earlier, later], transcript)

        assert merged[0].text.count(marker(7)) == 1

    def test_a_merged_span_covering_every_cue_is_the_whole_transcript_and_no_more(self) -> None:
        """Was: this shape produced ~2x the transcript, and with 33 windows ~4.8x.

        The bound is tight, not slack: when the merged span covers every cue the
        excerpt is the transcript's characters exactly.
        """
        transcript = marked_transcript(16)

        merged = merge_overlapping(
            [window(transcript, 0.0, 100.0), window(transcript, 50.0, 150.0)], transcript
        )

        assert len(merged[0].text) == transcript_characters(transcript)

    def test_exactly_touching_windows_merge_into_one_recut_span(self) -> None:
        """Was: touching windows merged and their texts were concatenated.

        Merging ON TOUCH survives R1000 untouched — `start <= previous_end` is
        what makes the surviving spans strictly disjoint, and disjointness plus
        start-only cue membership is the whole proof of the bound. What OD-4
        retired is only the gluing: the shared cue at 100s is now counted once.
        """
        transcript = marked_transcript(21)
        earlier = window(transcript, 0.0, 100.0)
        later = window(transcript, 100.0, 200.0)

        merged = merge_overlapping([earlier, later], transcript)

        assert len(merged) == 1
        assert spans(merged) == [("v1", 0.0, 200.0)]
        assert merged[0].text == text_between(transcript, 0.0, 200.0)
        # Cue 010 starts at exactly 100s and is a member of BOTH windows.
        assert marker(10) in earlier.text
        assert marker(10) in later.text
        assert merged[0].text.count(marker(10)) == 1

    def test_a_chain_of_exactly_touching_windows_collapses_into_one(self) -> None:
        """Was: three touching windows concatenated into one triple-counted text.

        Kept as a touch test rather than dropped: relaxing the merge rule to a
        strict `<` would leave three excerpts here whose spans share endpoints,
        and shared endpoints are exactly what the bound's disjointness argument
        forbids.
        """
        transcript = marked_transcript(31)

        merged = merge_overlapping(
            [
                window(transcript, 0.0, 100.0),
                window(transcript, 100.0, 200.0),
                window(transcript, 200.0, 300.0),
            ],
            transcript,
        )

        assert len(merged) == 1
        assert spans(merged) == [("v1", 0.0, 300.0)]
        assert merged[0].text == text_between(transcript, 0.0, 300.0)

    def test_a_one_second_gap_does_not_merge_and_neither_span_is_recut_wider(self) -> None:
        """Was: the same split, but each surviving text came from its window.

        Unchanged in outcome, restated under R1000: disjoint windows stay
        separate excerpts and each one's text is its own span, re-cut.
        """
        transcript = marked_transcript(21)

        merged = merge_overlapping(
            [window(transcript, 0.0, 100.0), window(transcript, 101.0, 200.0)], transcript
        )

        assert spans(merged) == [("v1", 0.0, 100.0), ("v1", 101.0, 200.0)]
        assert [e.text for e in merged] == [
            text_between(transcript, 0.0, 100.0),
            text_between(transcript, 101.0, 200.0),
        ]
        assert no_cue_appears_twice(merged, transcript)

    def test_a_wholly_contained_window_adds_nothing_to_the_span(self) -> None:
        """Was: the contained case was special-cased to keep the earlier text.

        The special case is gone — re-cutting the outer span gives the same
        answer without needing to know which text to discard.
        """
        transcript = marked_transcript(21)
        outer = window(transcript, 0.0, 200.0)

        merged = merge_overlapping([outer, window(transcript, 50.0, 100.0)], transcript)

        assert spans(merged) == [("v1", 0.0, 200.0)]
        assert merged[0].text == outer.text
        assert merged[0].text == text_between(transcript, 0.0, 200.0)

    def test_two_identical_spans_merge_to_one_copy_of_the_text(self) -> None:
        """Was: identical spans were detected as containment to avoid doubling.

        Now it needs no detection: two mentions of different boards in the same
        window produce one excerpt carrying both canonicals and one copy of the
        speech.
        """
        transcript = marked_transcript(21)

        merged = merge_overlapping(
            [
                window(transcript, 0.0, 200.0, ("B650E",)),
                window(transcript, 0.0, 200.0, ("X670E",)),
            ],
            transcript,
        )

        assert spans(merged) == [("v1", 0.0, 200.0)]
        assert merged[0].text == text_between(transcript, 0.0, 200.0)
        assert merged[0].canonicals == ("B650E", "X670E")

    def test_a_partial_overlap_given_later_first_still_recuts_one_span(self) -> None:
        """Was: `test_a_partial_overlap_concatenates_earlier_then_later`.

        There is no longer an "earlier then later" to get right — the text is a
        function of the merged span, so the input order cannot affect it.
        """
        transcript = marked_transcript(16)

        merged = merge_overlapping(
            [window(transcript, 50.0, 150.0), window(transcript, 0.0, 100.0)], transcript
        )

        assert spans(merged) == [("v1", 0.0, 150.0)]
        assert merged[0].text == text_between(transcript, 0.0, 150.0)

    def test_three_chained_windows_collapse_into_one_recut_span(self) -> None:
        """Was: the merged text was "a b c" — the three window texts glued up.

        Chained overlaps are where the old defect compounded: each link paid for
        its overlap again, which is how BL-10's 33 windows reached 4.8x.
        """
        transcript = marked_transcript(31)

        merged = merge_overlapping(
            [
                window(transcript, 0.0, 100.0, ("A620",)),
                window(transcript, 90.0, 200.0, ("B650E",)),
                window(transcript, 150.0, 300.0, ("X670E",)),
            ],
            transcript,
        )

        assert spans(merged) == [("v1", 0.0, 300.0)]
        assert merged[0].text == text_between(transcript, 0.0, 300.0)
        assert merged[0].canonicals == ("A620", "B650E", "X670E")
        assert no_cue_appears_twice(merged, transcript)

    def test_canonicals_are_unioned_distinct_and_resorted(self) -> None:
        """R23 provenance, unchanged by the re-cut: only the TEXT rule moved."""
        transcript = marked_transcript(16)

        merged = merge_overlapping(
            [
                window(transcript, 0.0, 100.0, ("X670E", "taichi")),
                window(transcript, 50.0, 150.0, ("B650E", "X670E")),
            ],
            transcript,
        )

        assert merged[0].canonicals == ("B650E", "X670E", "taichi")

    def test_the_provenance_survives_a_merge(self) -> None:
        """The video title is kept and the ids are the transcript's."""
        transcript = marked_transcript(16)

        merged = merge_overlapping(
            [
                window(transcript, 0.0, 100.0, title="X670E boards, ranked"),
                window(transcript, 50.0, 150.0, title="X670E boards, ranked"),
            ],
            transcript,
        )

        assert merged[0].video_id == "v1"
        assert merged[0].video_title == "X670E boards, ranked"

    def test_unsorted_input_is_handled(self) -> None:
        """Was: the same spans, with texts assembled in sorted order.

        The spans are unchanged; each surviving text is now its span re-cut.
        """
        transcript = marked_transcript(51)

        merged = merge_overlapping(
            [
                window(transcript, 300.0, 400.0),
                window(transcript, 0.0, 100.0),
                window(transcript, 350.0, 500.0),
                window(transcript, 150.0, 200.0),
            ],
            transcript,
        )

        assert spans(merged) == [
            ("v1", 0.0, 100.0),
            ("v1", 150.0, 200.0),
            ("v1", 300.0, 500.0),
        ]
        assert [e.text for e in merged] == [
            text_between(transcript, 0.0, 100.0),
            text_between(transcript, 150.0, 200.0),
            text_between(transcript, 300.0, 500.0),
        ]
        assert no_cue_appears_twice(merged, transcript)

    def test_ordering_stays_chronological(self) -> None:
        """R23: the same input renders the same bundle, so order is pinned."""
        transcript = marked_transcript(51)

        merged = merge_overlapping(
            [
                window(transcript, 300.0, 400.0),
                window(transcript, 0.0, 100.0),
                window(transcript, 150.0, 200.0),
            ],
            transcript,
        )

        assert [e.start_seconds for e in merged] == sorted(e.start_seconds for e in merged)

    def test_a_single_excerpt_comes_back_unchanged(self) -> None:
        """One window is its own span, and re-cutting it changes nothing."""
        transcript = marked_transcript(21)
        only = window(transcript, 10.0, 120.0, ("A620",))

        assert merge_overlapping([only], transcript) == (only,)

    def test_empty_input_gives_an_empty_tuple(self) -> None:
        assert merge_overlapping([], marked_transcript(5)) == ()

    def test_a_transcript_with_no_cues_gives_empty_text(self) -> None:
        """A window over silence is an empty excerpt, not a missing one."""
        transcript = Transcript("v1", ())

        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, ""),
                make_excerpt("v1", 50.0, 150.0, ""),
            ],
            transcript,
        )

        assert spans(merged) == [("v1", 0.0, 150.0)]
        assert merged[0].text == ""

    def test_two_runs_over_the_same_input_agree(self) -> None:
        """R23: byte-identical reruns, which the re-cut must not disturb."""
        transcript = marked_transcript(21)
        excerpts = [
            window(transcript, 0.0, 100.0, ("A620",)),
            window(transcript, 30.0, 60.0, ("B650E",)),
            window(transcript, 140.0, 200.0, ("X670E",)),
        ]

        assert merge_overlapping(excerpts, transcript) == merge_overlapping(excerpts, transcript)


class TestMergeRefusesAForeignVideo:
    """R1000/OD-4: one video's windows, one video's transcript, or a `ValueError`.

    This class replaces the retired cross-video merge tests
    (`test_different_videos_never_merge_however_close_the_timestamps` and
    `test_different_videos_interleaved_in_time_stay_separate`), which asserted
    that `merge_overlapping` grouped a mixed bag of videos and merged within each
    group. There is no grouping left to assert: the function takes exactly one
    video's transcript, the sole caller already holds exactly one (R22), and a
    foreign excerpt is now a programming error rather than a case to handle.
    """

    def test_an_excerpt_from_another_video_raises_value_error(self) -> None:
        transcript = marked_transcript(16, video_id="abc123")
        foreign = make_excerpt("zzz999", 50.0, 150.0, "someone else's speech")

        with pytest.raises(ValueError):
            merge_overlapping([window(transcript, 0.0, 100.0), foreign], transcript)

    def test_the_error_names_both_video_ids(self) -> None:
        transcript = marked_transcript(16, video_id="abc123")
        foreign = make_excerpt("zzz999", 50.0, 150.0, "someone else's speech")

        with pytest.raises(ValueError) as raised:
            merge_overlapping([window(transcript, 0.0, 100.0), foreign], transcript)

        message = str(raised.value)
        assert "abc123" in message, message
        assert "zzz999" in message, message

    def test_a_lone_foreign_excerpt_raises_rather_than_passing_through(self) -> None:
        """Silence here would be the worst outcome: the text would be re-cut from
        a transcript that is not the excerpt's, so the excerpt would silently
        acquire another video's speech.
        """
        transcript = marked_transcript(16, video_id="abc123")

        with pytest.raises(ValueError):
            merge_overlapping([make_excerpt("zzz999", 0.0, 100.0, "elsewhere")], transcript)

    def test_a_foreign_excerpt_that_could_never_merge_still_raises(self) -> None:
        """The timestamps are not comparable across videos, so "it did not overlap
        anything" is not a reason to let it through.
        """
        transcript = marked_transcript(16, video_id="abc123")

        with pytest.raises(ValueError):
            merge_overlapping(
                [window(transcript, 0.0, 100.0), make_excerpt("zzz999", 9000.0, 9100.0, "far")],
                transcript,
            )


class TestTranscriptCharacters:
    """R1000's denominator: the SAME single-space join an excerpt's text uses."""

    def test_it_is_the_single_space_join_of_every_cue(self) -> None:
        transcript = make_transcript("v1", (0.0, "one"), (10.0, "two"), (20.0, "three"))

        assert transcript_characters(transcript) == len("one two three")

    def test_the_separators_are_counted(self) -> None:
        """A denominator omitting the separators would make R1000's bound FALSE.

        An excerpt's own text carries a space between each pair of cues, so a
        count of raw cue text alone is smaller than the excerpt that covers the
        whole transcript — and the property the plan states would not hold.
        """
        transcript = make_transcript("v1", (0.0, "ab"), (10.0, "cd"), (20.0, "ef"))

        assert transcript_characters(transcript) == 8
        assert transcript_characters(transcript) != len("ab") + len("cd") + len("ef")

    def test_zero_cues_is_zero_characters(self) -> None:
        assert transcript_characters(Transcript("v1", ())) == 0

    def test_one_cue_is_its_own_length_with_no_separator(self) -> None:
        transcript = make_transcript("v1", (0.0, "just the one cue"))

        assert transcript_characters(transcript) == len("just the one cue")

    def test_it_agrees_with_a_window_covering_every_cue(self) -> None:
        """The two definitions must not drift: the numerator of the R28 ratio is
        cut with the same join as its denominator.
        """
        config = make_config(window_before_seconds=10, window_after_seconds=10_000)
        transcript = marked_transcript(40)

        (excerpt,) = cut_windows(transcript, [make_mention("B650E", 0.0)], make_video(), config)

        assert len(excerpt.text) == transcript_characters(transcript)

    def test_it_does_not_depend_on_the_cue_timings(self) -> None:
        early = make_transcript("v1", (0.0, "one"), (10.0, "two"))
        late = make_transcript("v1", (900.0, "one"), (9000.0, "two"))

        assert transcript_characters(early) == transcript_characters(late)


class TestTheBound:
    """R1000 as a property: a video's excerpts never out-run its transcript.

    Not an estimate and not a spot check — the merged spans are disjoint and cue
    membership is decided on the cue's start alone, so each cue's text lands in
    at most one excerpt. The cases below are generated from a fixed seed so a
    failure is reproducible (R23), and they are checked both before and after
    `cap_per_video`, which only ever drops excerpts.
    """

    def test_the_markers_cannot_collide_by_substring(self) -> None:
        """Guards every duplication assertion below.

        With unpadded markers `"cue 1"` is a substring of `"cue 10"`, and a
        counting assertion built on them passes or fails for the wrong reason.
        """
        transcript = marked_transcript(200)
        joined = " ".join(cue.text for cue in transcript.cues)

        for index in range(200):
            assert joined.count(marker(index)) == 1

    @pytest.mark.parametrize("seed", range(1, 17))
    def test_summed_excerpt_characters_never_exceed_the_transcripts(self, seed: int) -> None:
        transcript, merged, config = generated_case(seed)

        total = sum(len(excerpt.text) for excerpt in merged)

        assert total <= transcript_characters(transcript), (
            f"seed {seed}: {total} excerpt characters against "
            f"{transcript_characters(transcript)} in the transcript"
        )

    @pytest.mark.parametrize("seed", range(1, 17))
    def test_the_bound_is_not_met_by_emitting_nothing(self, seed: int) -> None:
        transcript, merged, config = generated_case(seed)

        assert sum(len(excerpt.text) for excerpt in merged) > 0

    @pytest.mark.parametrize("seed", range(1, 17))
    def test_the_bound_survives_the_per_video_cap(self, seed: int) -> None:
        transcript, merged, config = generated_case(seed)

        kept = cap_per_video(merged, config)
        total = sum(len(excerpt.text) for excerpt in kept)

        assert 0 < total <= transcript_characters(transcript)
        assert total <= sum(len(excerpt.text) for excerpt in merged)

    @pytest.mark.parametrize("seed", range(1, 17))
    def test_no_cue_text_appears_twice_across_the_excerpts(self, seed: int) -> None:
        transcript, merged, config = generated_case(seed)

        assert no_cue_appears_twice(merged, transcript)
        assert no_cue_appears_twice(cap_per_video(merged, config), transcript)

    def test_windows_dense_enough_to_cover_the_video_stay_at_its_size(self) -> None:
        """The saturated shape in miniature — BL-10's case is the regression in
        `tests/test_estimate.py`, and this is the same geometry small enough to
        read: a mention every 60s, windows of 120 before and 300 after, so every
        window overlaps its neighbours and one span covers the lot.
        """
        config = make_config(window_before_seconds=120, window_after_seconds=300)
        transcript = marked_transcript(200)
        mentions = [make_mention("B650E", float(start)) for start in range(0, 600, 60)]

        windows = cut_windows(transcript, mentions, make_video(), config)
        merged = merge_overlapping(windows, transcript)

        assert len(merged) == 1
        assert sum(len(e.text) for e in merged) <= transcript_characters(transcript)
        assert sum(len(e.text) for e in merged) > 0
        assert no_cue_appears_twice(merged, transcript)
        # The old merge glued 10 windows of ~140 cues each into one excerpt.
        assert sum(len(e.text) for e in windows) > transcript_characters(transcript)

    def test_two_runs_over_a_generated_case_agree(self) -> None:
        first = generated_case(3)[1]
        second = generated_case(3)[1]

        assert first == second


class TestCapPerVideo:
    def test_the_densest_excerpts_are_kept(self) -> None:
        config = make_config(per_video_excerpt_cap=2)
        excerpts = [
            make_excerpt("v1", 0.0, 10.0, "one board", ("A620",)),
            make_excerpt("v1", 50.0, 60.0, "two boards", ("A620", "B650E")),
            make_excerpt("v1", 100.0, 110.0, "three boards", ("A620", "B650E", "X670E")),
            make_excerpt("v1", 200.0, 210.0, "three more", ("A620", "B650E", "Taichi")),
        ]

        kept = cap_per_video(excerpts, config)

        assert [e.start_seconds for e in kept] == [100.0, 200.0]

    def test_an_earlier_sparse_excerpt_loses_to_a_later_dense_one(self) -> None:
        # The ranking is by density, not by time: the excerpt at 50s is dropped
        # even though it comes first.
        config = make_config(per_video_excerpt_cap=1)
        excerpts = [
            make_excerpt("v1", 50.0, 60.0, "two boards", ("A620", "B650E")),
            make_excerpt("v1", 500.0, 510.0, "four boards", ("A620", "B650E", "X670E", "Taichi")),
        ]

        kept = cap_per_video(excerpts, config)

        assert [e.start_seconds for e in kept] == [500.0]

    def test_a_tie_on_density_breaks_towards_the_earlier_start(self) -> None:
        config = make_config(per_video_excerpt_cap=1)
        excerpts = [
            make_excerpt("v1", 200.0, 210.0, "late", ("A620", "B650E", "X670E")),
            make_excerpt("v1", 100.0, 110.0, "early", ("A620", "B650E", "Taichi")),
        ]

        kept = cap_per_video(excerpts, config)

        assert [e.text for e in kept] == ["early"]

    def test_the_result_is_chronological_even_though_ranking_was_not(self) -> None:
        config = make_config(per_video_excerpt_cap=3)
        excerpts = [
            make_excerpt("v1", 900.0, 910.0, "sparse late", ("A620",)),
            make_excerpt("v1", 100.0, 110.0, "dense early", ("A620", "B650E", "X670E")),
            make_excerpt("v1", 500.0, 510.0, "middling", ("A620", "B650E")),
            make_excerpt("v1", 700.0, 710.0, "sparse", ("Taichi",)),
        ]

        kept = cap_per_video(excerpts, config)

        # Ranked densest-first that is 100s, 500s, then the earlier of the two
        # single-canonical windows — but it is handed back as a timeline.
        assert [e.start_seconds for e in kept] == sorted(e.start_seconds for e in kept)
        assert [e.start_seconds for e in kept] == [100.0, 500.0, 700.0]

    def test_a_video_exactly_at_the_cap_is_untouched(self) -> None:
        config = make_config(per_video_excerpt_cap=3)
        excerpts = [
            make_excerpt("v1", 0.0, 10.0, "a", ("A620",)),
            make_excerpt("v1", 100.0, 110.0, "b", ("A620", "B650E", "X670E")),
            make_excerpt("v1", 200.0, 210.0, "c", ("Taichi",)),
        ]

        assert cap_per_video(excerpts, config) == tuple(excerpts)

    def test_a_video_under_the_cap_is_untouched(self) -> None:
        config = make_config(per_video_excerpt_cap=10)
        excerpts = [
            make_excerpt("v1", 0.0, 10.0, "a", ("A620",)),
            make_excerpt("v1", 100.0, 110.0, "b", ("B650E",)),
        ]

        assert cap_per_video(excerpts, config) == tuple(excerpts)

    def test_the_cap_applies_per_video_not_across_videos(self) -> None:
        config = make_config(per_video_excerpt_cap=2)
        excerpts = [
            make_excerpt("v1", 0.0, 10.0, "v1 sparse", ("A620",)),
            make_excerpt("v1", 100.0, 110.0, "v1 dense", ("A620", "B650E", "X670E")),
            make_excerpt("v1", 200.0, 210.0, "v1 pair", ("A620", "B650E")),
            make_excerpt("v2", 0.0, 10.0, "v2 sparse", ("Taichi",)),
            make_excerpt("v2", 100.0, 110.0, "v2 dense", ("A620", "B650E", "X670E")),
            make_excerpt("v2", 200.0, 210.0, "v2 pair", ("A620", "B650E")),
        ]

        kept = cap_per_video(excerpts, config)

        assert len(kept) == 4
        by_video: dict[str, list[str]] = {}
        for excerpt in kept:
            by_video.setdefault(excerpt.video_id, []).append(excerpt.text)
        assert by_video == {
            "v1": ["v1 dense", "v1 pair"],
            "v2": ["v2 dense", "v2 pair"],
        }

    def test_one_video_over_the_cap_does_not_cost_another_video_anything(self) -> None:
        config = make_config(per_video_excerpt_cap=2)
        excerpts = [
            make_excerpt("v1", 0.0, 10.0, "a", ("A620", "B650E", "X670E")),
            make_excerpt("v1", 100.0, 110.0, "b", ("A620", "B650E")),
            make_excerpt("v1", 200.0, 210.0, "c", ("A620",)),
            make_excerpt("v2", 50.0, 60.0, "solo", ("Taichi",)),
        ]

        kept = cap_per_video(excerpts, config)

        assert [e.text for e in kept if e.video_id == "v2"] == ["solo"]

    def test_empty_input_gives_an_empty_tuple(self) -> None:
        assert cap_per_video([], make_config(per_video_excerpt_cap=2)) == ()

    def test_two_runs_over_the_same_input_agree(self) -> None:
        config = make_config(per_video_excerpt_cap=2)
        excerpts = [
            make_excerpt("v1", 300.0, 310.0, "a", ("A620", "B650E")),
            make_excerpt("v1", 100.0, 110.0, "b", ("A620", "X670E")),
            make_excerpt("v1", 200.0, 210.0, "c", ("Taichi", "B650E")),
        ]

        assert cap_per_video(excerpts, config) == cap_per_video(excerpts, config)
