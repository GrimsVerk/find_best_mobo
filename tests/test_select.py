"""Tests for slice 4 — the corpus narrows to the videos actually about AM5 boards.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so failing imports are the expected
state until assembly. Nothing under test is faked: the alias tables, indexes and
transcript caches are real files in `tmp_path`, in the shapes slices 1–3
document, and this slice touches no network at all.

The corpora here are arranged so every reported number is checkable by hand, and
so that the numbers that must not be confused with one another (the two what-if
counts especially) are deliberately different values.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-4 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import Alias, Mention, compile_matcher
from find_best_mobo.commands.select import run
from find_best_mobo.config import Config
from find_best_mobo.index import Video
from find_best_mobo.select import (
    Selection,
    ThresholdReport,
    read_selected,
    select_all,
    select_video,
    threshold_report,
    write_selected,
)
from find_best_mobo.transcripts import Cue, Transcript, cache_path

# Four canonicals, so a video can carry anywhere from zero to four distinct
# ones and the distinct count can be steered exactly.
STANDARD_TABLE: tuple[Alias, ...] = (
    Alias(canonical="X670E", kind="chipset", surface_forms=("x670e", "x 670 e")),
    Alias(canonical="B650E", kind="chipset", surface_forms=("b650e", "b 650 e")),
    Alias(canonical="A620", kind="chipset", surface_forms=("a620", "a 620")),
    Alias(canonical="Taichi", kind="family", surface_forms=("taichi",)),
)

# The order `make_selection` draws from when it needs N distinct canonicals.
CANONICALS = ("X670E", "B650E", "A620", "Taichi", "X870E", "B840")

TITLE_HIT = "title_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"

# Vocabulary the what-if lines are allowed to use. Deliberately generous: the
# test is that the DIRECTION is unmistakable, not that a particular sentence was
# written. A line stating a bare number with none of these words is exactly the
# ambiguity the contract forbids.
LOWER_MARKERS = ("lower", "fewer", "less", "minus", "-1", "one down")
RAISE_MARKERS = ("higher", "raise", "rais", "plus", "+1", "increase", "one up", "stricter")
ADDITIONAL_MARKERS = (
    "additional",
    "more",
    "extra",
    "further",
    "also",
    "gain",
    "currently excluded",
    "beyond",
    "on top",
)
DROP_MARKERS = ("drop", "lose", "lost", "fall", "no longer", "out", "exclud")


def make_config(data_dir: Path, *, mention_threshold: int = 3) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=date(2023, 1, 1),
        data_dir=data_dir,
        shorts_max_seconds=120,
        mention_threshold=mention_threshold,
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


def make_video(
    video_id: str,
    title: str = "Deep dive",
    *,
    inclusion: str = "pending",
    upload_date: date = date(2023, 6, 15),
) -> Video:
    return Video(
        video_id=video_id,
        title=title,
        upload_date=upload_date,
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


def empty_transcript(video_id: str) -> Transcript:
    return Transcript(video_id=video_id, cues=())


def make_matcher() -> re.Pattern[str]:
    return compile_matcher(STANDARD_TABLE)


def make_mention(canonical: str, video_id: str = "vid", start: float = 0.0) -> Mention:
    return Mention(
        video_id=video_id,
        canonical=canonical,
        start_seconds=start,
        matched_form=canonical.lower(),
    )


def _canonical(index: int) -> str:
    """A distinct canonical name for any index, not just the first few.

    CANONICALS is a realistic hand-written list, and a test asking for more
    distinct canonicals than it holds must still get DISTINCT ones — repeating a
    name would silently make a distinct-count test assert something weaker than
    it reads.
    """
    if index < len(CANONICALS):
        return CANONICALS[index]
    return f"BOARD-{index}"


def make_selection(reason: str, distinct: int, video_id: str = "vid") -> Selection:
    """A selection whose `mentions` are consistent with its distinct count."""
    mentions = tuple(
        make_mention(_canonical(index), video_id, float(index)) for index in range(distinct)
    )
    return Selection(
        video=make_video(video_id),
        reason=reason,
        mentions=mentions,
        distinct_canonicals=distinct,
    )


def write_aliases(path: Path, aliases: Sequence[Alias] = STANDARD_TABLE) -> Path:
    """Write an alias table as TOML in the shape slice 3's loader reads."""
    blocks = []
    for alias in aliases:
        entry: Mapping[str, object] = {
            "canonical": alias.canonical,
            "kind": alias.kind,
            "surface_forms": list(alias.surface_forms),
        }
        lines = ["[[alias]]"]
        lines += [f"{key} = {json.dumps(value)}" for key, value in entry.items()]
        blocks.append("\n".join(lines))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def write_index_lines(videos: Sequence[Video], path: Path) -> Path:
    """Write the index verbatim, in the order given.

    `write_index` sorts, which is exactly what a test of "order follows the
    index FILE" must not rely on — this writes the lines as handed over.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for video in videos:
        record = asdict(video)
        record["upload_date"] = video.upload_date.isoformat()
        lines.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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


def lines_with(output: str, token: str) -> list[str]:
    """Every output line mentioning `token`, case-insensitively."""
    return [line for line in output.splitlines() if token.lower() in line.lower()]


# Filesystem paths are incidental text, not the report's vocabulary, and every
# one of these assertions reads a line that may carry one. pytest names its temp
# directory after the run counter AND the test, so the path under this very test
# reads `.../pytest-2/test_the_lower_threshold_what_0/...` — which supplies both
# a bare `2` and the word "lower" to a search looking for exactly those. The
# result passed on run 1 and failed on run 2 of the same unchanged suite, which
# is how acceptance/S9.sh (two runs, counts compared) surfaced it.
_PATH = re.compile(r"\S*/\S*")


def without_paths(line: str) -> str:
    """`line` with any path-like token blanked, so only prose is matched."""
    return _PATH.sub(" ", line)


def has_number(line: str, value: int) -> bool:
    return re.search(rf"(?<![\d.]){value}(?![\d.])", without_paths(line)) is not None


def directional_line(output: str, markers: Sequence[str], value: int) -> str:
    """The report line stating `value` in the direction `markers` describes."""
    for line in output.splitlines():
        lowered = without_paths(line).lower()
        if has_number(line, value) and any(marker in lowered for marker in markers):
            return line
    raise AssertionError(f"no line states {value} together with any of {tuple(markers)}:\n{output}")


class TestReportMatchingIgnoresPaths:
    """These helpers must read the report, never the temp path printed inside it."""

    def test_a_number_inside_a_path_is_not_the_report_stating_it(self) -> None:
        line = "Wrote 9 selections to /tmp/pytest-of-me/pytest-2/data/selected.jsonl"

        assert not has_number(line, 2)
        assert has_number(line, 9)

    def test_a_direction_word_inside_a_path_does_not_select_that_line(self) -> None:
        output = (
            "Wrote 9 selections to /tmp/pytest-2/test_the_lower_threshold_0/out.jsonl\n"
            "Lowering the threshold to 2 would include 4 more videos\n"
        )

        assert directional_line(output, LOWER_MARKERS, 2).startswith("Lowering")


class TestSelectVideoTitleHits:
    def test_a_title_hit_with_no_body_mentions_is_still_included(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "X670E rundown")

        selection = select_video(video, empty_transcript("vid1"), make_matcher(), config)

        assert selection.reason == TITLE_HIT
        assert selection.mentions == ()
        assert selection.distinct_canonicals == 0

    def test_a_title_hit_with_one_body_mention_is_still_a_title_hit(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "X670E rundown")
        transcript = make_transcript("vid1", (4.0, "the taichi is fine"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == TITLE_HIT
        assert selection.distinct_canonicals == 1

    def test_a_title_hit_still_populates_mentions_from_the_body(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "X670E rundown")
        transcript = make_transcript(
            "vid1",
            (10.0, "the b650e is fine"),
            (20.0, "and the a620 is not"),
        )

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == TITLE_HIT
        assert [mention.canonical for mention in selection.mentions] == ["B650E", "A620"]
        assert [mention.start_seconds for mention in selection.mentions] == [10.0, 20.0]

    def test_a_title_hit_reports_the_true_distinct_count(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "X670E rundown")
        transcript = make_transcript(
            "vid1",
            (1.0, "b650e and b650e again"),
            (2.0, "the a620 too"),
        )

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.distinct_canonicals == 2
        assert len(selection.mentions) == 3

    def test_the_body_canonical_counts_even_when_it_is_the_title_one(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "X670E rundown")
        transcript = make_transcript("vid1", (1.0, "the x670e again"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == TITLE_HIT
        assert selection.distinct_canonicals == 1

    def test_the_selection_carries_the_video_it_was_given(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "X670E rundown")

        selection = select_video(video, empty_transcript("vid1"), make_matcher(), config)

        assert selection.video == video

    def test_a_title_that_matches_nothing_falls_through_to_the_threshold(self) -> None:
        config = make_config(Path("data"), mention_threshold=1)
        video = make_video("vid1", "Power supply teardown")
        transcript = make_transcript("vid1", (1.0, "the a620 chipset"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == THRESHOLD


class TestSelectVideoDistinctCanonicals:
    """The heart of the slice: distinct canonicals, never the raw mention count."""

    def test_many_mentions_of_one_canonical_are_excluded(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript(
            "vid1", *[(float(index), "the b650e again") for index in range(10)]
        )

        selection = select_video(video, transcript, make_matcher(), config)

        assert len(selection.mentions) == 10
        assert selection.distinct_canonicals == 1
        assert selection.reason == EXCLUDED

    def test_two_distinct_canonicals_many_times_over_are_excluded(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript(
            "vid1",
            (1.0, "x670e b650e x670e b650e"),
            (2.0, "x670e b650e x670e b650e"),
        )

        selection = select_video(video, transcript, make_matcher(), config)

        assert len(selection.mentions) == 8
        assert selection.distinct_canonicals == 2
        assert selection.reason == EXCLUDED

    def test_the_threshold_number_of_different_canonicals_passes(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript("vid1", (1.0, "x670e versus b650e versus a620"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert len(selection.mentions) == 3
        assert selection.distinct_canonicals == 3
        assert selection.reason == THRESHOLD

    def test_fewer_mentions_than_the_threshold_still_pass_on_distinct_count(self) -> None:
        # Three mentions is the same count as the ten-mention video above has
        # canonicals-times-repeats, and it passes where that one failed: the
        # decision is about breadth, not volume.
        config = make_config(Path("data"), mention_threshold=2)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript("vid1", (1.0, "x670e and taichi"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.distinct_canonicals == 2
        assert selection.reason == THRESHOLD

    def test_exactly_at_the_threshold_passes(self) -> None:
        config = make_config(Path("data"), mention_threshold=4)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript(
            "vid1",
            (1.0, "x670e and b650e"),
            (2.0, "a620 and taichi"),
        )

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.distinct_canonicals == 4
        assert selection.reason == THRESHOLD

    def test_one_below_the_threshold_is_excluded(self) -> None:
        config = make_config(Path("data"), mention_threshold=4)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript("vid1", (1.0, "x670e and b650e and a620"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.distinct_canonicals == 3
        assert selection.reason == EXCLUDED

    @pytest.mark.parametrize(
        ("threshold", "expected"),
        [(1, THRESHOLD), (2, THRESHOLD), (3, EXCLUDED), (4, EXCLUDED)],
    )
    def test_the_same_video_flips_as_the_threshold_moves(
        self, threshold: int, expected: str
    ) -> None:
        config = make_config(Path("data"), mention_threshold=threshold)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript("vid1", (1.0, "x670e and taichi and x670e"))

        assert select_video(video, transcript, make_matcher(), config).reason == expected

    def test_a_threshold_of_one_admits_a_single_canonical(self) -> None:
        config = make_config(Path("data"), mention_threshold=1)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript("vid1", (1.0, "the a620 chipset"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == THRESHOLD
        assert selection.distinct_canonicals == 1

    def test_no_mentions_at_all_is_excluded(self) -> None:
        config = make_config(Path("data"), mention_threshold=1)
        video = make_video("vid1", "Power supply teardown")
        transcript = make_transcript("vid1", (1.0, "he talks about power supplies"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == EXCLUDED
        assert selection.distinct_canonicals == 0
        assert selection.mentions == ()


class TestSelectVideoEmptyTranscript:
    def test_an_empty_transcript_can_still_be_a_title_hit(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "The B650E boards, ranked")

        selection = select_video(video, empty_transcript("vid1"), make_matcher(), config)

        assert selection.reason == TITLE_HIT
        assert selection.distinct_canonicals == 0
        assert selection.mentions == ()

    def test_an_empty_transcript_without_a_title_hit_is_excluded(self) -> None:
        config = make_config(Path("data"), mention_threshold=1)
        video = make_video("vid1", "Power supply teardown")

        selection = select_video(video, empty_transcript("vid1"), make_matcher(), config)

        assert selection.reason == EXCLUDED
        assert selection.distinct_canonicals == 0
        assert selection.mentions == ()


class TestSelectVideoMentionOrder:
    @pytest.mark.parametrize(
        ("title", "reason"),
        [
            ("X670E rundown", TITLE_HIT),
            ("Deep dive", THRESHOLD),
        ],
    )
    def test_mentions_follow_cue_order_whatever_the_reason(self, title: str, reason: str) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", title)
        # Cue starts deliberately out of chronological order: the promise is cue
        # order, which is the order the transcript holds them in.
        transcript = make_transcript(
            "vid1",
            (30.0, "taichi"),
            (10.0, "b650e"),
            (20.0, "a620"),
        )

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == reason
        assert [mention.canonical for mention in selection.mentions] == [
            "Taichi",
            "B650E",
            "A620",
        ]
        assert [mention.start_seconds for mention in selection.mentions] == [30.0, 10.0, 20.0]

    def test_an_excluded_video_still_reports_its_mentions_in_cue_order(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        video = make_video("vid1", "Deep dive")
        transcript = make_transcript("vid1", (9.0, "taichi"), (3.0, "taichi again"))

        selection = select_video(video, transcript, make_matcher(), config)

        assert selection.reason == EXCLUDED
        assert [mention.start_seconds for mention in selection.mentions] == [9.0, 3.0]


class TestThresholdReport:
    def test_every_count_over_a_mixed_set(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(TITLE_HIT, 0, "t1"),
            make_selection(TITLE_HIT, 5, "t2"),
            make_selection(THRESHOLD, 3, "p1"),
            make_selection(THRESHOLD, 4, "p2"),
            make_selection(THRESHOLD, 6, "p3"),
            make_selection(EXCLUDED, 2, "e1"),
            make_selection(EXCLUDED, 2, "e2"),
            make_selection(EXCLUDED, 1, "e3"),
            make_selection(EXCLUDED, 0, "e4"),
        ]

        assert threshold_report(selections, config) == ThresholdReport(
            threshold=3,
            title_hits=2,
            threshold_passes=3,
            excluded=4,
            would_include_at_minus_one=2,
            would_exclude_at_plus_one=1,
        )

    def test_no_selections_reports_all_zeros(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)

        assert threshold_report([], config) == ThresholdReport(
            threshold=3,
            title_hits=0,
            threshold_passes=0,
            excluded=0,
            would_include_at_minus_one=0,
            would_exclude_at_plus_one=0,
        )

    def test_the_threshold_reported_is_the_configured_one(self) -> None:
        config = make_config(Path("data"), mention_threshold=7)

        assert threshold_report([make_selection(EXCLUDED, 1, "e1")], config).threshold == 7

    def test_would_include_at_minus_one_counts_only_the_ones_that_would_join(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(EXCLUDED, 2, "e1"),
            make_selection(EXCLUDED, 1, "e2"),
            make_selection(EXCLUDED, 0, "e3"),
        ]

        assert threshold_report(selections, config).would_include_at_minus_one == 1

    def test_would_include_at_minus_one_is_additional_not_a_new_total(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(TITLE_HIT, 0, "t1"),
            make_selection(THRESHOLD, 4, "p1"),
            make_selection(THRESHOLD, 3, "p2"),
            make_selection(EXCLUDED, 2, "e1"),
            make_selection(EXCLUDED, 0, "e2"),
        ]

        report = threshold_report(selections, config)

        # Three videos are in already; exactly one more would join. The answer
        # is 1, not 4.
        assert report.would_include_at_minus_one == 1
        assert report.title_hits + report.threshold_passes == 3

    def test_already_included_videos_are_never_counted_at_minus_one(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(TITLE_HIT, 6, "t1"),
            make_selection(THRESHOLD, 5, "p1"),
        ]

        assert threshold_report(selections, config).would_include_at_minus_one == 0

    def test_would_exclude_at_plus_one_counts_the_ones_that_would_drop(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(THRESHOLD, 3, "p1"),
            make_selection(THRESHOLD, 3, "p2"),
            make_selection(THRESHOLD, 4, "p3"),
            make_selection(THRESHOLD, 9, "p4"),
        ]

        assert threshold_report(selections, config).would_exclude_at_plus_one == 2

    def test_title_hits_are_never_counted_at_plus_one(self) -> None:
        # Every one of these sits below threshold + 1, and every one of them is
        # in on its title. Raising the threshold cannot touch them.
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(TITLE_HIT, 0, "t1"),
            make_selection(TITLE_HIT, 1, "t2"),
            make_selection(TITLE_HIT, 3, "t3"),
        ]

        assert threshold_report(selections, config).would_exclude_at_plus_one == 0

    def test_excluded_videos_are_never_counted_at_plus_one(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)
        selections = [
            make_selection(EXCLUDED, 0, "e1"),
            make_selection(EXCLUDED, 2, "e2"),
        ]

        assert threshold_report(selections, config).would_exclude_at_plus_one == 0

    def test_a_threshold_of_one_is_reported_honestly_and_not_clamped(self) -> None:
        config = make_config(Path("data"), mention_threshold=1)
        selections = [
            make_selection(THRESHOLD, 1, "p1"),
            make_selection(THRESHOLD, 2, "p2"),
            make_selection(EXCLUDED, 0, "e1"),
            make_selection(EXCLUDED, 0, "e2"),
            make_selection(EXCLUDED, 0, "e3"),
        ]

        report = threshold_report(selections, config)

        # At a threshold of 0 every video with any mention comes in — and these
        # excluded ones have none, so all three would. Say so rather than
        # pretending the question is meaningless.
        assert report.would_include_at_minus_one == 3
        assert report.would_exclude_at_plus_one == 1
        assert report.threshold == 1

    def test_accepts_a_tuple_of_selections(self) -> None:
        config = make_config(Path("data"), mention_threshold=3)

        report = threshold_report((make_selection(TITLE_HIT, 0, "t1"),), config)

        assert report.title_hits == 1


def build_corpus(tmp_path: Path, *, mention_threshold: int = 3) -> Config:
    """A nine-video corpus whose every reported number is checkable by hand.

    2 title hits, 3 threshold passes, 4 exclusions. Of the exclusions, two sit
    at 2 distinct canonicals, so lowering the threshold to 2 would add exactly
    those two. Of the passes, exactly one sits at 3, so raising to 4 would drop
    exactly one. The two what-if numbers are therefore different, which is what
    lets a test tell one printed line from the other.
    """
    config = make_config(tmp_path / "data", mention_threshold=mention_threshold)
    write_aliases(config.data_dir / "aliases.toml")
    videos = [
        make_video("t1", "X670E rundown"),
        make_video("t2", "The B650E boards, ranked"),
        make_video("p1", "Deep dive one"),
        make_video("p2", "Deep dive two"),
        make_video("p3", "Deep dive three"),
        make_video("e1", "Deep dive four"),
        make_video("e2", "Deep dive five"),
        make_video("e3", "Deep dive six"),
        make_video("e4", "Power supply teardown"),
    ]
    write_index_lines(videos, config.data_dir / "index.jsonl")
    write_transcript(config, empty_transcript("t1"))
    write_transcript(config, make_transcript("t2", (1.0, "the a620 is fine")))
    write_transcript(config, make_transcript("p1", (1.0, "x670e b650e a620")))
    write_transcript(config, make_transcript("p2", (1.0, "x670e b650e a620 taichi")))
    write_transcript(config, make_transcript("p3", (2.5, "x670e b650e taichi a620")))
    write_transcript(config, make_transcript("e1", (1.0, "x670e and b650e")))
    write_transcript(config, make_transcript("e2", (1.0, "a620 and taichi")))
    write_transcript(config, make_transcript("e3", (1.0, "b650e again and again b650e")))
    # e4 has no cached transcript at all.
    return config


CORPUS_TITLE_HITS = 2
CORPUS_PASSES = 3
CORPUS_EXCLUDED = 4
CORPUS_SELECTED = CORPUS_TITLE_HITS + CORPUS_PASSES
CORPUS_MINUS_ONE = 2
CORPUS_PLUS_ONE = 1


class TestSelectAll:
    def test_the_whole_corpus_is_classified(self, tmp_path: Path) -> None:
        config = build_corpus(tmp_path)

        selections = select_all(config)

        by_id = {selection.video.video_id: selection.reason for selection in selections}
        assert by_id == {
            "t1": TITLE_HIT,
            "t2": TITLE_HIT,
            "p1": THRESHOLD,
            "p2": THRESHOLD,
            "p3": THRESHOLD,
            "e1": EXCLUDED,
            "e2": EXCLUDED,
            "e3": EXCLUDED,
            "e4": EXCLUDED,
        }

    def test_excluded_selections_are_returned_not_dropped(self, tmp_path: Path) -> None:
        config = build_corpus(tmp_path)

        selections = select_all(config)

        excluded = [s for s in selections if s.reason == EXCLUDED]
        assert len(selections) == 9
        assert len(excluded) == CORPUS_EXCLUDED
        assert {s.video.video_id for s in excluded} == {"e1", "e2", "e3", "e4"}

    def test_only_pending_videos_are_considered(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")
        videos = [
            make_video("keep", "X670E rundown"),
            make_video("short", "X670E in sixty seconds", inclusion="excluded_short"),
            make_video("old", "X670E from before", inclusion="excluded_out_of_range"),
        ]
        write_index_lines(videos, config.data_dir / "index.jsonl")
        for video in videos:
            write_transcript(config, make_transcript(video.video_id, (1.0, "x670e b650e a620")))

        selections = select_all(config)

        assert [selection.video.video_id for selection in selections] == ["keep"]

    def test_a_video_with_no_cached_transcript_is_still_selected(self, tmp_path: Path) -> None:
        config = build_corpus(tmp_path)

        (bare,) = [s for s in select_all(config) if s.video.video_id == "e4"]

        assert bare.reason == EXCLUDED
        assert bare.mentions == ()
        assert bare.distinct_canonicals == 0

    def test_a_title_hit_survives_a_missing_transcript(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")
        write_index_lines([make_video("solo", "X670E rundown")], config.data_dir / "index.jsonl")

        (selection,) = select_all(config)

        assert selection.reason == TITLE_HIT
        assert selection.mentions == ()

    def test_order_follows_the_index_file(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")
        # Neither id order nor upload-date order: the file's order is the answer.
        videos = [
            make_video("zzz", "Deep dive", upload_date=date(2024, 5, 1)),
            make_video("aaa", "Deep dive", upload_date=date(2023, 2, 1)),
            make_video("mmm", "Deep dive", upload_date=date(2025, 9, 30)),
        ]
        write_index_lines(videos, config.data_dir / "index.jsonl")

        selections = select_all(config)

        assert [selection.video.video_id for selection in selections] == ["zzz", "aaa", "mmm"]

    def test_two_runs_over_the_same_corpus_agree(self, tmp_path: Path) -> None:
        config = build_corpus(tmp_path)

        assert select_all(config) == select_all(config)

    def test_the_selection_carries_the_full_video_record(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")
        video = make_video("solo", "X670E rundown", upload_date=date(2024, 3, 4))
        write_index_lines([video], config.data_dir / "index.jsonl")

        (selection,) = select_all(config)

        assert selection.video == video

    def test_a_missing_index_raises_file_not_found(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")

        with pytest.raises(FileNotFoundError):
            select_all(config)

    def test_a_missing_alias_table_raises_file_not_found(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("solo", "X670E rundown")], config.data_dir / "index.jsonl")

        with pytest.raises(FileNotFoundError):
            select_all(config)


def round_trip_selections(config: Config) -> tuple[Selection, ...]:
    """Selections built by the real selector, spanning all three reasons."""
    matcher = make_matcher()
    cases = [
        (
            make_video("aaa", "X670E rundown", upload_date=date(2023, 1, 2)),
            make_transcript("aaa", (12.5, "the b650e board"), (61.25, "and the taichi")),
        ),
        (
            make_video("bbb", "Deep dive", upload_date=date(2023, 5, 6)),
            make_transcript("bbb", (0.0, "x670e b650e a620")),
        ),
        (
            make_video("ccc", "Power supply teardown", upload_date=date(2024, 7, 8)),
            make_transcript("ccc", (3.5, "just the a620 here")),
        ),
    ]
    return tuple(select_video(video, transcript, matcher, config) for video, transcript in cases)


class TestWriteAndReadSelected:
    def test_a_round_trip_preserves_everything(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"

        write_selected(selections, path)

        assert tuple(read_selected(path)) == selections

    def test_the_reasons_survive_the_round_trip(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"
        write_selected(selections, path)

        assert [s.reason for s in read_selected(path)] == [TITLE_HIT, THRESHOLD, EXCLUDED]

    def test_the_distinct_count_survives_the_round_trip(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"
        write_selected(selections, path)

        assert [s.distinct_canonicals for s in read_selected(path)] == [2, 3, 1]

    def test_mention_order_and_float_timestamps_survive(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"
        write_selected(selections, path)

        first = next(iter(read_selected(path)))
        assert [m.canonical for m in first.mentions] == ["B650E", "Taichi"]
        assert [m.start_seconds for m in first.mentions] == [12.5, 61.25]
        assert isinstance(first.mentions[0].start_seconds, float)
        assert first.mentions[0].matched_form == "b650e"
        assert first.mentions[0].video_id == "aaa"

    def test_the_full_video_record_survives(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"
        write_selected(selections, path)

        restored = list(read_selected(path))
        assert [s.video for s in restored] == [s.video for s in selections]
        assert restored[2].video.upload_date == date(2024, 7, 8)
        assert restored[2].video.duration_seconds == 3600
        assert restored[2].video.was_live is False
        assert restored[2].video.inclusion == "pending"

    def test_excluded_selections_are_written_too(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"

        write_selected(selections, path)

        ids = [s.video.video_id for s in read_selected(path) if s.reason == EXCLUDED]
        assert ids == ["ccc"]

    def test_the_return_value_is_the_count_written(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"

        written = write_selected(selections, path)

        assert written == 3
        assert len(path.read_text(encoding="utf-8").splitlines()) == 3

    def test_writing_nothing_returns_zero_and_leaves_an_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "selected.jsonl"

        assert write_selected([], path) == 0
        assert path.read_text(encoding="utf-8") == ""
        assert list(read_selected(path)) == []

    def test_accepts_an_iterator_of_selections(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"

        assert write_selected(iter(selections), path) == 3

    def test_two_writes_of_the_same_input_are_byte_identical(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        first = tmp_path / "first.jsonl"
        second = tmp_path / "second.jsonl"

        write_selected(selections, first)
        write_selected(selections, second)

        assert first.read_bytes() == second.read_bytes()
        assert first.read_bytes() != b""

    def test_rewriting_the_same_path_replaces_rather_than_appends(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"

        write_selected(selections, path)
        before = path.read_bytes()
        write_selected(selections, path)

        assert path.read_bytes() == before

    def test_every_line_is_one_json_object_ending_in_a_newline(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"
        write_selected(selections, path)

        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        for line in text.splitlines():
            assert line == line.rstrip(), f"trailing whitespace on {line!r}"
            record = json.loads(line)
            assert set(record) == {"video", "reason", "mentions", "distinct_canonicals"}

    def test_the_record_nests_the_video_and_its_mentions(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", mention_threshold=3)
        selections = round_trip_selections(config)
        path = tmp_path / "selected.jsonl"
        write_selected(selections, path)

        record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert record["video"]["video_id"] == "aaa"
        assert record["video"]["upload_date"] == "2023-01-02"
        assert record["mentions"][0] == {
            "canonical": "B650E",
            "matched_form": "b650e",
            "start_seconds": 12.5,
            "video_id": "aaa",
        }

    def test_a_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list(read_selected(tmp_path / "nowhere" / "selected.jsonl"))


class TestSelectCommand:
    def test_a_normal_run_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        assert "Traceback" not in capsys.readouterr().out

    def test_a_normal_run_writes_selected_jsonl(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        path = config.data_dir / "selected.jsonl"
        restored = list(read_selected(path))
        assert len(restored) == 9
        assert sum(1 for s in restored if s.reason == TITLE_HIT) == CORPUS_TITLE_HITS
        assert sum(1 for s in restored if s.reason == THRESHOLD) == CORPUS_PASSES
        assert sum(1 for s in restored if s.reason == EXCLUDED) == CORPUS_EXCLUDED

    def test_the_report_names_the_threshold_in_force(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path, mention_threshold=3)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        threshold_lines = lines_with(out, "threshold")
        assert any(has_number(line, 3) for line in threshold_lines), (
            f"the threshold in force must be printed: {out!r}"
        )

    def test_the_report_gives_the_title_hit_and_exclusion_counts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert any(has_number(line, CORPUS_TITLE_HITS) for line in lines_with(out, "title")), (
            f"{CORPUS_TITLE_HITS} videos came in on a title hit: {out!r}"
        )
        assert any(has_number(line, CORPUS_EXCLUDED) for line in lines_with(out, "exclud")), (
            f"{CORPUS_EXCLUDED} videos were excluded: {out!r}"
        )

    def test_the_report_gives_the_total_selected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        candidates = lines_with(out, "select") + lines_with(out, "total")
        assert any(has_number(line, CORPUS_SELECTED) for line in candidates), (
            f"{CORPUS_SELECTED} videos are in the corpus: {out!r}"
        )

    def test_the_lower_threshold_what_if_reads_as_an_additional_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        line = directional_line(out, LOWER_MARKERS, CORPUS_MINUS_ONE)
        assert any(marker in line.lower() for marker in ADDITIONAL_MARKERS), (
            "a reader must not have to work out whether the lower-threshold "
            f"number is a new total or an additional count: {line!r}"
        )

    def test_the_higher_threshold_what_if_reads_as_a_count_that_drops_out(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        line = directional_line(out, RAISE_MARKERS, CORPUS_PLUS_ONE)
        assert any(marker in line.lower() for marker in DROP_MARKERS), (
            "the higher-threshold number must read as videos dropping out, not "
            f"as a new total: {line!r}"
        )

    def test_two_runs_print_identically(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        first = capsys.readouterr().out
        assert run(config, Namespace()) == 0
        second = capsys.readouterr().out

        assert first == second
        assert first.strip() != ""

    def test_a_missing_index_returns_one_naming_what_to_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "index" in out.lower(), f"the message must name the index command: {out!r}"
        assert "Traceback" not in out

    def test_a_missing_index_writes_no_output_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        write_aliases(config.data_dir / "aliases.toml")

        assert run(config, Namespace()) == 1
        capsys.readouterr()

        assert not (config.data_dir / "selected.jsonl").exists()

    def test_a_missing_alias_table_returns_one_naming_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("solo", "X670E rundown")], config.data_dir / "index.jsonl")

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "alias" in out.lower(), f"the message must name the alias table: {out!r}"
        assert "Traceback" not in out
