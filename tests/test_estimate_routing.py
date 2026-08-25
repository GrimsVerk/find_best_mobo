"""Slice 1 of R28/R1008, end to end — what `estimate` actually writes to disk.

Written blind from `docs/plans/oracle/capped-whole-transcript-path.md` alone, in
a worktree at a commit where the routing does not exist, so failing imports are
the expected state until assembly. Nothing is faked: the index, the selections
and the transcript cache are real files under `tmp_path`, and the stage touches
no network.

`tests/test_submission.py` pins the routing and the split as units. This file
pins the one thing a unit cannot: that the command measures the ratio on the
blocks it is about to send — AFTER the cluster re-cut and AFTER the per-video cap
— and that a saturated transcript too large for one bundle lands across
sequential bundle files with nothing repeated and nothing dropped.

Every corpus below is built so the routing is legible from the bundle text
alone. Each video's cues are tagged with its own letter, so a passage can be
attributed to one video by eye, and a saturated video deliberately keeps a tail
cue that NO excerpt window covers: that tail appearing in `data/bundles/` is what
distinguishes the whole path from the excerpt path, and its absence is what
distinguishes the excerpt path from the whole one.

Slice 1 adds no XML attributes — `form`, `part` and `parts` are slice 2's — so
nothing here reads them.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as it is in
# tests/test_excerpt.py and tests/test_estimate.py: `find_best_mobo.submission`
# does not exist yet, so the isort rule classifies it as third-party and would
# demand a different grouping from the one it demands once it does.
from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import Mention
from find_best_mobo.commands.estimate import run
from find_best_mobo.config import Config
from find_best_mobo.excerpt import (
    cap_per_video,
    cut_windows,
    merge_overlapping,
    transcript_characters,
    transcript_text,
)
from find_best_mobo.index import Video
from find_best_mobo.select import Selection, write_selected
from find_best_mobo.transcripts import Cue, Transcript, cache_path
from find_best_mobo.submission import WHOLE_TRANSCRIPT_RATIO

TITLE_HIT = "title_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"

# Every cue in every corpus here is nine characters wide, so a transcript of N
# cues joins to 10N - 1 characters and each fixture's ratio can be read off the
# cue count. The first two characters tag the video and the cue, so no passage
# from one video can be mistaken for a passage from another.
CUE_WIDTH = 9
CUE_SECONDS = 10.0


def cue_text(tag: str, index: int) -> str:
    stem = f"{tag}{index}"
    return stem + "x" * (CUE_WIDTH - len(stem))


def cue_texts(tag: str, count: int) -> tuple[str, ...]:
    return tuple(cue_text(tag, index) for index in range(count))


def make_config(
    data_dir: Path,
    *,
    window_before_seconds: int = 0,
    window_after_seconds: int = 45,
    per_video_excerpt_cap: int = 10,
    bundle_token_cap: int = 10_000,
    calibration_batch_size: int = 12,
    batch_count: int = 3,
    chars_per_token: float = 1.0,
) -> Config:
    """One character per token, so a cap reads as a character count."""
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
    video_id: str,
    title: str = "Deep dive",
    *,
    inclusion: str = "pending",
    upload_date: date = date(2024, 6, 15),
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


def make_mention(canonical: str, video_id: str, start: float) -> Mention:
    return Mention(
        video_id=video_id,
        canonical=canonical,
        start_seconds=start,
        matched_form=canonical.lower(),
    )


def make_selection(
    video: Video,
    reason: str = THRESHOLD,
    mentions: tuple[Mention, ...] = (),
    *,
    has_transcript: bool = True,
) -> Selection:
    return Selection(
        video=video,
        reason=reason,
        mentions=mentions,
        distinct_canonicals=len({mention.canonical for mention in mentions}),
        has_transcript=has_transcript,
    )


def make_transcript(video_id: str, tag: str, count: int) -> Transcript:
    return Transcript(
        video_id=video_id,
        cues=tuple(
            Cue(start_seconds=index * CUE_SECONDS, text=text)
            for index, text in enumerate(cue_texts(tag, count))
        ),
    )


def write_index_lines(videos: Sequence[Video], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for video in videos:
        record = asdict(video)
        record["upload_date"] = video.upload_date.isoformat()
        lines.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_transcript(config: Config, transcript: Transcript) -> None:
    """Write the cache file in the shape `load_cached` reads."""
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


def bundle_files(config: Config) -> list[Path]:
    """Every written bundle, in packing order — the bundle id, not the batch folder."""
    return sorted((config.data_dir / "bundles").rglob("*.xml"), key=lambda path: path.name)


def blocks_per_bundle(config: Config) -> list[list[str]]:
    return [
        re.findall(r"<transcript>(.*?)</transcript>", path.read_text(encoding="utf-8"), re.S)
        for path in bundle_files(config)
    ]


def blocks_in_order(config: Config) -> list[str]:
    return [block for bundle in blocks_per_bundle(config) for block in bundle]


def boards_in_order(config: Config) -> list[str]:
    boards: list[str] = []
    for path in bundle_files(config):
        boards.extend(re.findall(r"<boards>(.*?)</boards>", path.read_text(encoding="utf-8"), re.S))
    return boards


def written_text(config: Config) -> str:
    return "".join(path.read_text(encoding="utf-8") for path in bundle_files(config))


def excerpts_the_command_would_build(
    transcript: Transcript, selection: Selection, config: Config
) -> tuple[str, ...]:
    """Cut, merge-and-re-cut, cap — the three steps the command runs before routing."""
    windows = cut_windows(transcript, selection.mentions, selection.video, config)
    kept = cap_per_video(merge_overlapping(windows, transcript), config)
    return tuple(excerpt.text for excerpt in kept)


# --- The two-video corpus: one saturated video, one just below the line. ------
#
# `S` has eleven cues (109 characters). Two OVERLAPPING windows merge into its
# first nine cues (89 characters) and a third, disjoint window picks up its last
# cue (9 characters), so 98 of 109 characters are excerpted — ratio 0.899, the
# whole path. Two excerpts survive the merge rather than one, which is what makes
# the canonicals on the whole block a UNION rather than a copy. `S9xxxxxxx`, the
# tenth cue, is covered by no window at all: it appearing in a bundle is the
# proof the whole transcript went.
#
# `N` has ten cues (99 characters) and windows that overlap harder, merging into
# eight cues — 79 characters, ratio 0.798, just below the line — so it is
# excerpted and `N8xxxxxxx` and `N9xxxxxxx` are absent. Summed BEFORE the merge
# `N` is at 98/99, so a router measuring there would send it whole: that is what
# makes this pair a test rather than a demonstration.

SAT_CUES = 11
NEAR_CUES = 10
SAT_CHARACTERS = SAT_CUES * CUE_WIDTH + (SAT_CUES - 1)
NEAR_CHARACTERS = NEAR_CUES * CUE_WIDTH + (NEAR_CUES - 1)
SAT_EXCERPTED = 98
NEAR_EXCERPTED = 79

SAT_MENTIONS = (("X670E", 0.0), ("A620", 40.0), ("B840", 100.0))
NEAR_MENTIONS = (("B650E", 0.0), ("B840", 30.0))


def build_pair_corpus(tmp_path: Path, **overrides: object) -> Config:
    config = make_config(tmp_path / "data", **overrides)  # type: ignore[arg-type]
    saturated = make_video("sat", "Deep dive", upload_date=date(2025, 1, 2))
    near = make_video("near", "X670E boards, ranked", upload_date=date(2024, 1, 1))
    skipped = make_video("skip", "Power supply teardown", upload_date=date(2026, 1, 1))
    write_index_lines([saturated, near, skipped], config.data_dir / "index.jsonl")
    write_selected(
        [
            make_selection(
                saturated,
                THRESHOLD,
                tuple(make_mention(name, "sat", start) for name, start in SAT_MENTIONS),
            ),
            make_selection(
                near,
                TITLE_HIT,
                tuple(make_mention(name, "near", start) for name, start in NEAR_MENTIONS),
            ),
            make_selection(skipped, EXCLUDED, (make_mention("A620", "skip", 0.0),)),
        ],
        config.data_dir / "selected.jsonl",
    )
    write_transcript(config, make_transcript("sat", "S", SAT_CUES))
    write_transcript(config, make_transcript("near", "N", NEAR_CUES))
    write_transcript(config, make_transcript("skip", "K", 10))
    return config


class TestTheCorpusGeometry:
    """Guards the numbers every routing assertion below rests on."""

    def test_the_transcripts_are_the_size_the_arithmetic_assumes(self, tmp_path: Path) -> None:
        config = build_pair_corpus(tmp_path)

        assert transcript_characters(make_transcript("sat", "S", SAT_CUES)) == SAT_CHARACTERS == 109
        assert (
            transcript_characters(make_transcript("near", "N", NEAR_CUES)) == NEAR_CHARACTERS == 99
        )
        assert config.bundle_token_cap == 10_000

    def test_the_saturated_video_is_at_or_above_the_threshold_after_the_merge(
        self, tmp_path: Path
    ) -> None:
        config = build_pair_corpus(tmp_path)
        transcript = make_transcript("sat", "S", SAT_CUES)
        selection = make_selection(
            make_video("sat"),
            THRESHOLD,
            tuple(make_mention(name, "sat", start) for name, start in SAT_MENTIONS),
        )
        texts = excerpts_the_command_would_build(transcript, selection, config)

        assert texts == (" ".join(cue_texts("S", 9)), cue_text("S", 10))
        assert sum(len(text) for text in texts) == SAT_EXCERPTED
        assert SAT_EXCERPTED / SAT_CHARACTERS >= WHOLE_TRANSCRIPT_RATIO

    def test_the_near_miss_video_is_below_the_threshold_after_the_merge(
        self, tmp_path: Path
    ) -> None:
        config = build_pair_corpus(tmp_path)
        transcript = make_transcript("near", "N", NEAR_CUES)
        selection = make_selection(
            make_video("near"),
            TITLE_HIT,
            tuple(make_mention(name, "near", start) for name, start in NEAR_MENTIONS),
        )
        texts = excerpts_the_command_would_build(transcript, selection, config)

        assert sum(len(text) for text in texts) == NEAR_EXCERPTED
        assert NEAR_EXCERPTED / NEAR_CHARACTERS < WHOLE_TRANSCRIPT_RATIO

    def test_before_the_merge_the_near_miss_video_would_have_been_sent_whole(
        self, tmp_path: Path
    ) -> None:
        """The discriminator is real: its unmerged windows come to 98 of 99."""
        config = build_pair_corpus(tmp_path)
        transcript = make_transcript("near", "N", NEAR_CUES)
        windows = cut_windows(
            transcript,
            tuple(make_mention(name, "near", start) for name, start in NEAR_MENTIONS),
            make_video("near"),
            config,
        )
        unmerged = sum(len(window.text) for window in windows)

        assert unmerged == 98
        assert unmerged / NEAR_CHARACTERS >= WHOLE_TRANSCRIPT_RATIO


class TestASaturatedVideoIsSentWhole:
    def test_a_normal_run_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        assert "Traceback" not in capsys.readouterr().out

    def test_the_saturated_video_is_one_block_of_its_whole_transcript(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert blocks_in_order(config)[0] == transcript_text(make_transcript("sat", "S", SAT_CUES))

    def test_the_tail_cue_no_window_covered_is_still_sent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`S9xxxxxxx` can only be in a bundle because the whole transcript went."""
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert cue_text("S", 9) in written_text(config)

    def test_the_whole_block_carries_the_union_of_the_videos_canonicals(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert boards_in_order(config)[0] == "A620, B840, X670E"

    def test_the_saturated_video_contributes_exactly_one_block(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        blocks = [block for block in blocks_in_order(config) if "S0" in block]
        assert len(blocks) == 1

    def test_no_passage_of_the_saturated_video_is_sent_twice(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = written_text(config)
        for index in range(SAT_CUES):
            assert written.count(cue_text("S", index)) == 1


class TestTheRatioIsMeasuredAfterTheMerge:
    def test_a_video_below_the_threshold_after_merging_is_still_excerpted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        transcript = make_transcript("near", "N", NEAR_CUES)
        assert blocks_in_order(config)[1] == " ".join(cue_texts("N", 8))
        assert blocks_in_order(config)[1] != transcript_text(transcript)

    def test_the_cues_no_window_covered_are_absent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = written_text(config)
        assert cue_text("N", 8) not in written
        assert cue_text("N", 9) not in written

    def test_the_excerpted_video_contributes_the_characters_it_was_measured_on(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        near_blocks = [block for block in blocks_in_order(config) if "N0" in block]
        assert sum(len(block) for block in near_blocks) == NEAR_EXCERPTED


# --- The cap corpus: two disjoint windows, only one of which survives R17. ----
#
# `C`'s two windows never touch, so the merge changes nothing and the pre-cap sum
# is 98/99. `per_video_excerpt_cap=1` throws the later one away, leaving 49/99,
# and the video must therefore be EXCERPTED. A router that measured before the
# cap would send it whole on excerpts it had already discarded.

CAP_CUES = 10
CAP_CHARACTERS = CAP_CUES * CUE_WIDTH + (CAP_CUES - 1)
CAP_MENTIONS = (("X670E", 0.0), ("A620", 50.0))


def build_cap_corpus(tmp_path: Path) -> Config:
    config = make_config(tmp_path / "data", per_video_excerpt_cap=1)
    video = make_video("capped", "Deep dive", upload_date=date(2025, 3, 3))
    write_index_lines([video], config.data_dir / "index.jsonl")
    write_selected(
        [
            make_selection(
                video,
                THRESHOLD,
                tuple(make_mention(name, "capped", start) for name, start in CAP_MENTIONS),
            )
        ],
        config.data_dir / "selected.jsonl",
    )
    write_transcript(config, make_transcript("capped", "C", CAP_CUES))
    return config


class TestTheRatioIsMeasuredAfterTheCap:
    def test_before_the_cap_the_video_would_have_been_sent_whole(self, tmp_path: Path) -> None:
        config = build_cap_corpus(tmp_path)
        transcript = make_transcript("capped", "C", CAP_CUES)
        windows = cut_windows(
            transcript,
            tuple(make_mention(name, "capped", start) for name, start in CAP_MENTIONS),
            make_video("capped"),
            config,
        )
        merged = merge_overlapping(windows, transcript)

        unmerged = sum(len(excerpt.text) for excerpt in merged)
        assert len(merged) == 2
        assert unmerged / CAP_CHARACTERS >= WHOLE_TRANSCRIPT_RATIO

    def test_after_the_cap_it_is_below_the_threshold(self, tmp_path: Path) -> None:
        config = build_cap_corpus(tmp_path)
        transcript = make_transcript("capped", "C", CAP_CUES)
        selection = make_selection(
            make_video("capped"),
            THRESHOLD,
            tuple(make_mention(name, "capped", start) for name, start in CAP_MENTIONS),
        )
        texts = excerpts_the_command_would_build(transcript, selection, config)

        surviving = sum(len(text) for text in texts)
        assert texts == (" ".join(cue_texts("C", 5)),)
        assert surviving == 49
        assert surviving / CAP_CHARACTERS < WHOLE_TRANSCRIPT_RATIO

    def test_the_run_sends_the_surviving_excerpt_and_not_the_transcript(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_cap_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert blocks_in_order(config) == [" ".join(cue_texts("C", 5))]

    def test_the_capped_away_passages_never_reach_a_bundle(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_cap_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = written_text(config)
        for index in range(5, 10):
            assert cue_text("C", index) not in written


# --- The big corpus: one saturated transcript twenty times the bundle cap. ----
#
# Sixty nine-character cues join to 599 characters; the cap is 30 tokens, so the
# split takes three cues per part (29 characters) and the transcript is delivered
# as twenty parts. One window covers the first fifty-three cues (529 characters,
# ratio 0.883), so the video is saturated and the last seven cues are the proof
# that it went whole rather than as that single 529-character excerpt.

BIG_CUES = 60
BIG_CHARACTERS = BIG_CUES * CUE_WIDTH + (BIG_CUES - 1)


def build_big_corpus(tmp_path: Path, *, bundle_token_cap: int = 30) -> Config:
    config = make_config(
        tmp_path / "data",
        window_after_seconds=520,
        bundle_token_cap=bundle_token_cap,
    )
    video = make_video("big", "Deep dive", upload_date=date(2025, 6, 1))
    write_index_lines([video], config.data_dir / "index.jsonl")
    write_selected(
        [make_selection(video, THRESHOLD, (make_mention("X670E", "big", 0.0),))],
        config.data_dir / "selected.jsonl",
    )
    write_transcript(config, make_transcript("big", "B", BIG_CUES))
    return config


class TestASaturatedTranscriptLargerThanOneBundle:
    def test_the_geometry_is_what_the_arithmetic_assumes(self, tmp_path: Path) -> None:
        config = build_big_corpus(tmp_path)
        transcript = make_transcript("big", "B", BIG_CUES)
        selection = make_selection(
            make_video("big"), THRESHOLD, (make_mention("X670E", "big", 0.0),)
        )
        texts = excerpts_the_command_would_build(transcript, selection, config)

        covered = sum(len(text) for text in texts)
        assert transcript_characters(transcript) == BIG_CHARACTERS == 599
        assert covered == 529
        assert covered / BIG_CHARACTERS >= WHOLE_TRANSCRIPT_RATIO
        assert config.bundle_token_cap == 30

    def test_the_run_returns_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = build_big_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        assert "Traceback" not in capsys.readouterr().out

    def test_it_is_delivered_across_sequential_bundles_one_part_each(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_big_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert [len(bundle) for bundle in blocks_per_bundle(config)] == [1] * 20

    def test_the_parts_rejoin_into_the_whole_transcript_in_bundle_order(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_big_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        transcript = make_transcript("big", "B", BIG_CUES)
        assert " ".join(blocks_in_order(config)) == transcript_text(transcript)

    def test_the_character_arithmetic_holds_across_the_bundles(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_big_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        blocks = blocks_in_order(config)
        assert sum(len(block) for block in blocks) == BIG_CHARACTERS - (len(blocks) - 1)

    def test_nothing_is_repeated_and_nothing_is_dropped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_big_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = written_text(config)
        for index in range(BIG_CUES):
            assert written.count(cue_text("B", index)) == 1

    def test_no_cue_is_split_across_two_parts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_big_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        rejoined = " ".join(blocks_in_order(config))
        assert rejoined.split(" ") == list(cue_texts("B", BIG_CUES))

    def test_it_did_not_fall_back_to_excerpts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The last seven cues no window covered are in the bundles."""
        config = build_big_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = written_text(config)
        for index in range(53, BIG_CUES):
            assert cue_text("B", index) in written


class TestSizeIsNeverConsultedWhenRouting:
    def test_the_same_video_goes_whole_under_a_far_smaller_cap(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_big_corpus(tmp_path, bundle_token_cap=9)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        blocks = blocks_in_order(config)
        assert len(blocks) == BIG_CUES
        assert " ".join(blocks) == transcript_text(make_transcript("big", "B", BIG_CUES))

    def test_the_cap_changes_only_how_many_blocks_it_arrives_in(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        roomy = build_big_corpus(tmp_path / "roomy", bundle_token_cap=10_000)
        assert run(roomy, Namespace()) == 0
        capsys.readouterr()
        tight = build_big_corpus(tmp_path / "tight", bundle_token_cap=30)
        assert run(tight, Namespace()) == 0
        capsys.readouterr()

        whole = transcript_text(make_transcript("big", "B", BIG_CUES))
        assert blocks_in_order(roomy) == [whole]
        assert len(blocks_in_order(tight)) == 20
        assert " ".join(blocks_in_order(tight)) == whole


class TestTheRestOfTheStageIsUnmoved:
    def test_the_most_recent_video_still_comes_first(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        blocks = blocks_in_order(config)
        assert blocks[0].startswith("S0")
        assert blocks[1].startswith("N0")

    def test_an_excluded_selection_contributes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = written_text(config)
        assert cue_text("K", 0) not in written
        assert "skip" not in written

    def test_a_selection_with_no_cached_transcript_is_not_an_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        video = make_video("nocaps", "Deep dive", upload_date=date(2025, 5, 5))
        write_index_lines([video], config.data_dir / "index.jsonl")
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)
        write_selected(
            [make_selection(video, THRESHOLD, (make_mention("B650E", "nocaps", 0.0),))],
            config.data_dir / "selected.jsonl",
        )

        assert run(config, Namespace()) == 0
        assert "Traceback" not in capsys.readouterr().out
        assert bundle_files(config) == []

    def test_the_stage_still_prints_the_projection_and_stops(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert "Cost projection" in out
        assert "STOPS" in out

    def test_two_runs_over_the_same_corpus_write_the_same_bytes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_pair_corpus(tmp_path)
        assert run(config, Namespace()) == 0
        capsys.readouterr()
        first = written_text(config)
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert written_text(config) == first
