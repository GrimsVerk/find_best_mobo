"""Tests for slice 5 — excerpt windows cut around mentions.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. Nothing under test is faked: `cut_windows`,
`merge_overlapping` and `cap_per_video` are pure functions over plain records,
and this slice touches no network at all.

The windows here are deliberately small and the cue texts deliberately short, so
that every asserted span and every joined string is checkable by eye rather than
by re-deriving the implementation's arithmetic.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-5 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

from datetime import date
from pathlib import Path

from find_best_mobo.aliases import Mention
from find_best_mobo.config import Config
from find_best_mobo.excerpt import Excerpt, cap_per_video, cut_windows, merge_overlapping
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
    def test_two_overlapping_windows_become_one(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "early"),
                make_excerpt("v1", 50.0, 150.0, "late"),
            ]
        )

        assert spans(merged) == [("v1", 0.0, 150.0)]
        assert merged[0].text == "early late"

    def test_exactly_touching_windows_merge(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "early"),
                make_excerpt("v1", 100.0, 200.0, "late"),
            ]
        )

        assert spans(merged) == [("v1", 0.0, 200.0)]
        assert merged[0].text == "early late"

    def test_a_one_second_gap_does_not_merge(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "early"),
                make_excerpt("v1", 101.0, 200.0, "late"),
            ]
        )

        assert spans(merged) == [("v1", 0.0, 100.0), ("v1", 101.0, 200.0)]
        assert [e.text for e in merged] == ["early", "late"]

    def test_a_contained_span_keeps_the_earlier_text_unchanged(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 200.0, "the whole passage"),
                make_excerpt("v1", 50.0, 100.0, "the whole"),
            ]
        )

        assert spans(merged) == [("v1", 0.0, 200.0)]
        assert merged[0].text == "the whole passage"

    def test_an_identical_span_keeps_the_earlier_text_unchanged(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 200.0, "the whole passage", ("B650E",)),
                make_excerpt("v1", 0.0, 200.0, "the whole passage", ("X670E",)),
            ]
        )

        assert spans(merged) == [("v1", 0.0, 200.0)]
        assert merged[0].text == "the whole passage"
        assert merged[0].canonicals == ("B650E", "X670E")

    def test_a_partial_overlap_concatenates_earlier_then_later(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 50.0, 150.0, "second half"),
                make_excerpt("v1", 0.0, 100.0, "first half"),
            ]
        )

        assert merged[0].text == "first half second half"

    def test_three_chained_windows_collapse_into_one(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "a", ("A620",)),
                make_excerpt("v1", 90.0, 200.0, "b", ("B650E",)),
                make_excerpt("v1", 150.0, 300.0, "c", ("X670E",)),
            ]
        )

        assert spans(merged) == [("v1", 0.0, 300.0)]
        assert merged[0].text == "a b c"
        assert merged[0].canonicals == ("A620", "B650E", "X670E")

    def test_canonicals_are_unioned_distinct_and_resorted(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "early", ("X670E", "taichi")),
                make_excerpt("v1", 50.0, 150.0, "late", ("B650E", "X670E")),
            ]
        )

        assert merged[0].canonicals == ("B650E", "X670E", "taichi")

    def test_different_videos_never_merge_however_close_the_timestamps(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "one"),
                make_excerpt("v2", 0.0, 100.0, "two"),
            ]
        )

        assert len(merged) == 2
        assert set(spans(merged)) == {("v1", 0.0, 100.0), ("v2", 0.0, 100.0)}
        assert {e.text for e in merged} == {"one", "two"}

    def test_different_videos_interleaved_in_time_stay_separate(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "a1"),
                make_excerpt("v2", 50.0, 150.0, "b1"),
                make_excerpt("v1", 60.0, 200.0, "a2"),
            ]
        )

        by_video = {e.video_id: e for e in merged}
        assert len(merged) == 2
        assert (by_video["v1"].start_seconds, by_video["v1"].end_seconds) == (0.0, 200.0)
        assert by_video["v1"].text == "a1 a2"
        assert by_video["v2"].text == "b1"

    def test_unsorted_input_is_handled(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 300.0, 400.0, "third"),
                make_excerpt("v1", 0.0, 100.0, "first"),
                make_excerpt("v1", 350.0, 500.0, "fourth"),
                make_excerpt("v1", 150.0, 200.0, "second"),
            ]
        )

        assert spans(merged) == [
            ("v1", 0.0, 100.0),
            ("v1", 150.0, 200.0),
            ("v1", 300.0, 500.0),
        ]
        assert [e.text for e in merged] == ["first", "second", "third fourth"]

    def test_the_provenance_survives_a_merge(self) -> None:
        merged = merge_overlapping(
            [
                make_excerpt("v1", 0.0, 100.0, "early", title="X670E boards, ranked"),
                make_excerpt("v1", 50.0, 150.0, "late", title="X670E boards, ranked"),
            ]
        )

        assert merged[0].video_id == "v1"
        assert merged[0].video_title == "X670E boards, ranked"

    def test_a_single_excerpt_comes_back_unchanged(self) -> None:
        only = make_excerpt("v1", 10.0, 20.0, "solo", ("A620",))

        assert merge_overlapping([only]) == (only,)

    def test_empty_input_gives_an_empty_tuple(self) -> None:
        assert merge_overlapping([]) == ()

    def test_two_runs_over_the_same_input_agree(self) -> None:
        excerpts = [
            make_excerpt("v2", 40.0, 90.0, "b"),
            make_excerpt("v1", 0.0, 100.0, "a"),
            make_excerpt("v1", 30.0, 60.0, "c"),
        ]

        assert merge_overlapping(excerpts) == merge_overlapping(excerpts)


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
