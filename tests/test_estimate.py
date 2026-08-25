"""Tests for slice 5 — the cost projection, and the structural stop.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. Nothing under test is faked: the index, the selections and
the transcript cache are real files under `tmp_path` in the shapes slices 1–4
document, and this slice touches no network at all.

The corpus in `build_corpus` is arranged so every projected number is checkable
by hand: two included videos with one 40-character excerpt each, a token factor
of exactly one character per token, and a bundle cap of exactly one excerpt.

`TestSaturatedVideoIsPinnedAtItsTranscript` is R1000's regression (OD-4), built
from BL-10's measured geometry as a synthetic cached transcript: the whole
`estimate` path runs over it and the summed excerpt characters are asserted
never to exceed the transcript's own.

The last class here is the point of the whole milestone. `estimate` prints a
number and stops; there is no code path from it into inference, and
`TestNoInferencePath` is what fails if someone later wires one in.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-5 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import ast
import json
import re
from argparse import Namespace
from collections.abc import Sequence
from dataclasses import asdict, fields, replace
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.artifacts import MissingArtifact
from find_best_mobo.aliases import Mention
from find_best_mobo.bundle import (
    Bundle,
    assign_batches,
    estimate_tokens,
    pack_bundles,
    render_bundle,
)
from find_best_mobo.commands.estimate import run
from find_best_mobo.config import Config
from find_best_mobo.estimate import Projection, project, render_projection
from find_best_mobo.excerpt import (
    Excerpt,
    cap_per_video,
    cut_windows,
    merge_overlapping,
    transcript_characters,
    transcript_text,
)
from find_best_mobo.index import Video
from find_best_mobo.select import Coverage, Selection, read_selected, write_selected
from find_best_mobo.submission import EXCERPTS, WHOLE, VideoSubmission, choose_submission
from find_best_mobo.transcripts import Cue, Transcript, cache_path, load_cached

TITLE_HIT = "title_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"


def make_config(
    data_dir: Path,
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
    """`has_transcript` defaults to True: these fixtures describe videos that were read.

    The coverage tests pass it explicitly, which is the only way the flag should
    ever be false in a fixture (R1012).
    """
    return Selection(
        video=video,
        reason=reason,
        mentions=mentions,
        distinct_canonicals=len({mention.canonical for mention in mentions}),
        has_transcript=has_transcript,
    )


def make_excerpt(text: str, video_id: str = "v1") -> Excerpt:
    return Excerpt(
        video_id=video_id,
        video_title="Board roundup",
        start_seconds=100.0,
        end_seconds=200.0,
        text=text,
        canonicals=("B650E",),
    )


def make_bundle(bundle_id: str, batch: int, tokens: int, text: str = "some excerpt text") -> Bundle:
    return Bundle(
        bundle_id=bundle_id,
        batch=batch,
        excerpts=(make_excerpt(text),),
        projected_tokens=tokens,
    )


def make_projection(**named: object) -> Projection:
    """A `Projection` carrying every field the plan's Signatures block names.

    Built through a helper rather than written as a literal, for one reason the
    plan leaves open: `render_projection(projection)` takes nothing but the
    projection, yet the rendered text must state THE BUNDLE TOKEN CAP it split
    against — and the Signatures block names no field to carry it. Whatever
    field slice 3 adds for that is filled here with a blank of its own type, so
    a test about the named fields is not derailed by a field it has no opinion
    about. `coverage` (R1012, already on the dataclass) is named here because
    the tests below it do have an opinion about it.

    A key that is NOT a field of `Projection` fails loudly: that is the
    dataclass having dropped or renamed something the plan promised.
    """
    values: dict[str, object] = {
        "videos_indexed": 0,
        "videos_selected": 0,
        "excerpt_characters": 0,
        "bundle_count": 0,
        "tokens_per_batch": (),
        "total_tokens": 0,
        "chars_per_token": 4.0,
        "coverage": Coverage(considered=0, with_transcript=0),
        "videos_whole": 0,
        "videos_excerpted": 0,
        "whole_characters": 0,
        "whole_tokens": 0,
        "excerpt_tokens": 0,
        "videos_over_bundle_cap": 0,
        "bundles_spanned": (),
    }
    values.update(named)
    declared = {field.name: field for field in fields(Projection)}
    unknown = sorted(set(values) - set(declared))
    assert not unknown, (
        f"Projection has no field(s) {unknown} — the plan's Signatures block names them"
    )
    for name, field in declared.items():
        values.setdefault(name, _blank_field(field.type))
    return Projection(**values)  # type: ignore[arg-type]


def _blank_field(annotation: object) -> object:
    """A zero value for a field the plan never wrote down. See `make_projection`."""
    text = str(annotation)
    if text.startswith("tuple"):
        return ()
    if text.startswith("float"):
        return 0.0
    if text.startswith("Coverage"):
        return Coverage(considered=0, with_transcript=0)
    return 0


def expected_projection(actual: Projection, **named: object) -> Projection:
    """`actual` with every field a test HAS an opinion about replaced by `named`.

    Equality against this stays exact for every field named — it fails if any
    one of them is wrong, and it fails if a field is missing — while a field the
    plan never wrote down (see `make_projection`) is carried across rather than
    guessed at.
    """
    unknown = sorted(set(named) - {field.name for field in fields(Projection)})
    assert not unknown, f"Projection has no field(s) {unknown}"
    return replace(actual, **named)  # type: ignore[arg-type]


def whole_block(video_id: str, part: int, part_count: int, text: str) -> Excerpt:
    """One block of a whole transcript, in the shape `split_whole` produces."""
    return Excerpt(
        video_id=video_id,
        video_title="Deep dive",
        start_seconds=0.0,
        end_seconds=10.0,
        text=text,
        canonicals=("B650E",),
        form=WHOLE,
        part=part,
        part_count=part_count,
    )


def make_submission(
    video_id: str,
    path: str,
    blocks: Sequence[Excerpt],
    config: Config,
    *,
    excerpt_characters: int | None = None,
    whole_transcript_characters: int | None = None,
    title: str = "Deep dive",
) -> VideoSubmission:
    """One hand-built submission, for the cases the real router cannot produce."""
    sent = sum(len(block.text) for block in blocks)
    return VideoSubmission(
        video_id=video_id,
        video_title=title,
        path=path,
        blocks=tuple(blocks),
        excerpt_characters=sent if excerpt_characters is None else excerpt_characters,
        transcript_characters=(
            sent if whole_transcript_characters is None else whole_transcript_characters
        ),
        projected_tokens=sum(estimate_tokens(block.text, config) for block in blocks),
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


def write_transcript(config: Config, video_id: str, *cues: tuple[float, str]) -> None:
    """Write the cache file in the shape slice 2 documents for `load_cached`."""
    transcript = Transcript(
        video_id=video_id,
        cues=tuple(Cue(start_seconds=start, text=text) for start, text in cues),
    )
    path = cache_path(video_id, config)
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


def states_number(text: str, value: int) -> bool:
    """Does `text` state `value` as a number, plain or thousands-grouped?"""
    plain = re.escape(str(value))
    grouped = re.escape(f"{value:,}")
    pattern = rf"(?<![\d,.]){plain}(?![\d,.])|(?<![\d,.]){grouped}(?![\d,.])"
    return re.search(pattern, text) is not None


def lines_with(output: str, token: str) -> list[str]:
    return [line for line in output.splitlines() if token.lower() in line.lower()]


class TestProject:
    def test_every_field_over_a_hand_built_corpus(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3, chars_per_token=4.0)
        write_index_lines(
            [
                make_video("a"),
                make_video("b"),
                make_video("c"),
                make_video("short", inclusion="excluded_short"),
            ],
            config.data_dir / "index.jsonl",
        )
        # The two declared token counts are `estimate_tokens` of the two texts
        # at 4.0 characters per token (40 -> 10, 60 -> 15). The fixture has to
        # be self-consistent now that R1008 splits the SAME tokens per path:
        # a bundle claiming a total its own blocks do not add up to would make
        # the split unreadable rather than merely odd.
        bundles = [
            make_bundle("bundle-001", 1, 10, "x" * 40),
            make_bundle("bundle-002", 2, 15, "y" * 60),
        ]
        selections = [
            make_selection(make_video("a"), TITLE_HIT),
            make_selection(make_video("b"), THRESHOLD),
            make_selection(make_video("c"), EXCLUDED),
        ]
        # The submissions that produced those blocks, both on the excerpt path
        # (R1008): the per-path figures are read off the submissions, so a
        # projection called without them is a different corpus, not this one.
        submissions = [
            make_submission("a", EXCERPTS, (make_excerpt("x" * 40, "a"),), config),
            make_submission("b", EXCERPTS, (make_excerpt("y" * 60, "b"),), config),
        ]

        projection = project(bundles, selections, submissions, config)

        assert projection == expected_projection(
            projection,
            videos_indexed=3,
            videos_selected=2,
            excerpt_characters=100,
            bundle_count=2,
            tokens_per_batch=(10, 15, 0, 0),
            total_tokens=25,
            chars_per_token=4.0,
            # Two INCLUDED selections, both with transcripts; the excluded
            # video is not in the population this number annotates.
            coverage=Coverage(considered=2, with_transcript=2),
            videos_whole=0,
            videos_excerpted=2,
            whole_characters=0,
            whole_tokens=0,
            excerpt_tokens=25,
            videos_over_bundle_cap=0,
            bundles_spanned=(),
        )

    def test_videos_indexed_counts_only_the_pending_ones(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines(
            [
                make_video("a"),
                make_video("b"),
                make_video("s1", inclusion="excluded_short"),
                make_video("s2", inclusion="excluded_short"),
                make_video("o1", inclusion="excluded_out_of_range"),
            ],
            config.data_dir / "index.jsonl",
        )

        assert project([], [], [], config).videos_indexed == 2

    def test_videos_selected_excludes_the_below_threshold_ones(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        selections = [
            make_selection(make_video("a"), TITLE_HIT),
            make_selection(make_video("b"), THRESHOLD),
            make_selection(make_video("c"), THRESHOLD),
            make_selection(make_video("d"), EXCLUDED),
            make_selection(make_video("e"), EXCLUDED),
        ]

        assert project([], selections, [], config).videos_selected == 3

    def test_videos_selected_is_zero_when_everything_was_excluded(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        selections = [make_selection(make_video(vid), EXCLUDED) for vid in ("a", "b")]

        assert project([], selections, [], config).videos_selected == 0

    def test_excerpt_characters_totals_the_excerpt_text(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        blocks = (make_excerpt("z" * 7), make_excerpt("z" * 13), make_excerpt("z" * 100))
        bundles = [
            Bundle("bundle-001", 1, blocks[:2], 5),
            Bundle("bundle-002", 2, blocks[2:], 25),
        ]
        # Excerpt-form blocks, so `excerpt_characters` still counts every one
        # of them after R1008 narrowed it to the excerpt path.
        submissions = [make_submission("v1", EXCERPTS, blocks, config)]

        assert project(bundles, [], submissions, config).excerpt_characters == 120

    def test_excerpt_characters_counts_text_not_markup(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        block = make_excerpt("hello")
        bundles = [Bundle("bundle-001", 1, (block,), 2)]
        submissions = [make_submission("v1", EXCERPTS, (block,), config)]

        assert project(bundles, [], submissions, config).excerpt_characters == 5

    def test_tokens_per_batch_is_indexed_from_batch_one(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [
            make_bundle("bundle-001", 1, 5),
            make_bundle("bundle-002", 1, 7),
            make_bundle("bundle-003", 4, 900),
        ]

        projection = project(bundles, [], [], config)

        assert projection.tokens_per_batch[0] == 12
        assert projection.tokens_per_batch[3] == 900

    def test_empty_batches_contribute_zero_and_are_still_present(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [make_bundle("bundle-001", 1, 42)]

        projection = project(bundles, [], [], config)

        assert projection.tokens_per_batch == (42, 0, 0, 0)
        assert len(projection.tokens_per_batch) == 4

    def test_the_tuple_length_follows_the_configured_batch_count(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=5)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")

        projection = project([make_bundle("bundle-001", 2, 3)], [], [], config)

        assert len(projection.tokens_per_batch) == 6
        assert projection.tokens_per_batch == (0, 3, 0, 0, 0, 0)

    def test_total_tokens_is_the_sum_over_every_bundle(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [
            make_bundle("bundle-001", 1, 100),
            make_bundle("bundle-002", 2, 250),
            make_bundle("bundle-003", 4, 7),
        ]

        projection = project(bundles, [], [], config)

        assert projection.total_tokens == 357
        assert projection.total_tokens == sum(projection.tokens_per_batch)

    def test_bundle_count_is_the_number_of_bundles(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [make_bundle(f"bundle-{n:03d}", 1, 1) for n in range(1, 8)]

        assert project(bundles, [], [], config).bundle_count == 7

    def test_the_chars_per_token_factor_comes_from_config(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", chars_per_token=3.25)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")

        assert project([], [], [], config).chars_per_token == 3.25

    def test_nothing_at_all_projects_zeros(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3, chars_per_token=4.0)
        write_index_lines([], config.data_dir / "index.jsonl")

        projection = project([], [], [], config)

        assert projection == expected_projection(
            projection,
            videos_indexed=0,
            videos_selected=0,
            excerpt_characters=0,
            bundle_count=0,
            tokens_per_batch=(0, 0, 0, 0),
            total_tokens=0,
            chars_per_token=4.0,
            coverage=Coverage(considered=0, with_transcript=0),
            videos_whole=0,
            videos_excerpted=0,
            whole_characters=0,
            whole_tokens=0,
            excerpt_tokens=0,
            videos_over_bundle_cap=0,
            bundles_spanned=(),
        )


# Every number here is distinct from every other, so a line printed from the
# wrong field cannot be mistaken for the right one. The R1008 figures are
# internally consistent as well: 4 + 41 videos is the 45 selected, 50 + 16
# tokens is the 66 total, and the two spanning transcripts are the two videos
# over the bundle cap.
SAMPLE = make_projection(
    videos_indexed=123,
    videos_selected=45,
    excerpt_characters=678900,
    bundle_count=7,
    tokens_per_batch=(11, 22, 33, 0),
    total_tokens=66,
    chars_per_token=3.5,
    coverage=Coverage(considered=45, with_transcript=40),
    videos_whole=4,
    videos_excerpted=41,
    whole_characters=500000,
    whole_tokens=50,
    excerpt_tokens=16,
    videos_over_bundle_cap=2,
    bundles_spanned=(("vidzulu", 3), ("vidalpha", 5)),
)


class TestRenderProjection:
    def test_every_counted_field_is_stated(self) -> None:
        text = render_projection(SAMPLE)

        for value in (123, 45, 678900, 7, 66):
            assert states_number(text, value), f"{value} is missing from:\n{text}"

    def test_every_batch_total_is_stated(self) -> None:
        text = render_projection(SAMPLE)

        for value in (11, 22, 33):
            assert states_number(text, value), f"batch total {value} is missing from:\n{text}"

    def test_an_empty_batch_is_reported_rather_than_omitted(self) -> None:
        text = render_projection(SAMPLE)

        assert states_number(text, 0), f"the empty batch must be shown as 0:\n{text}"

    def test_the_chars_per_token_factor_is_stated(self) -> None:
        text = render_projection(SAMPLE)

        assert "3.5" in text, f"the factor in force must be printed:\n{text}"

    def test_the_factor_is_named_as_an_estimate(self) -> None:
        text = render_projection(SAMPLE)

        factor_lines = [line for line in text.splitlines() if "3.5" in line]
        assert factor_lines, f"the factor in force must be printed:\n{text}"
        assert any("estimat" in line.lower() for line in factor_lines), (
            "the chars-per-token factor is a guess until it is measured, and "
            f"must read as one: {factor_lines!r}"
        )

    def test_the_calibration_batch_is_named_as_what_corrects_it(self) -> None:
        lowered = render_projection(SAMPLE).lower()

        assert "calibration" in lowered, "the projection must say what will correct the estimate"

    def test_it_says_plainly_that_the_pipeline_stops_here(self) -> None:
        lowered = render_projection(SAMPLE).lower()

        assert "stop" in lowered, f"the projection must say the pipeline stops:\n{lowered}"

    def test_it_says_plainly_that_no_model_is_invoked(self) -> None:
        lowered = render_projection(SAMPLE).lower()

        assert "invok" in lowered
        assert re.search(
            r"\b(no|not|never|neither|nothing)\b[^.\n]{0,80}\bmodel\b"
            r"|\bmodel\b[^.\n]{0,80}\b(no|not|never)\b",
            lowered,
        ), f"the projection must say no model is invoked:\n{lowered}"

    def test_the_statement_about_stopping_comes_last(self) -> None:
        text = render_projection(SAMPLE).rstrip()
        tail = text.lower().splitlines()[-1]

        assert "model" in tail or "stop" in tail, (
            f"the last thing the reader sees must be the stop: {tail!r}"
        )

    def test_rendering_twice_is_identical(self) -> None:
        assert render_projection(SAMPLE) == render_projection(SAMPLE)

    def test_two_different_projections_do_not_render_the_same(self) -> None:
        other = make_projection(
            videos_indexed=1,
            videos_selected=1,
            excerpt_characters=2,
            bundle_count=1,
            tokens_per_batch=(1, 0, 0, 0),
            total_tokens=1,
            chars_per_token=4.0,
            coverage=Coverage(considered=0, with_transcript=0),
        )

        assert render_projection(SAMPLE) != render_projection(other)


# Two 40-character excerpt texts, with a one-character-per-token factor and a
# 40-token bundle cap: one excerpt per bundle, and every number below countable.
TEXT_NEW = "the b650e board is the pick here for am5"
TEXT_OLD = "the x670e board is the pick here for am5"
TEXT_SKIP = "the a620 board is the pick here for am5"


def corpus_config(tmp_path: Path) -> Config:
    return make_config(
        tmp_path / "data",
        window_before_seconds=10,
        window_after_seconds=10,
        per_video_excerpt_cap=10,
        bundle_token_cap=40,
        calibration_batch_size=1,
        batch_count=3,
        chars_per_token=1.0,
    )


def build_corpus(tmp_path: Path) -> Config:
    """Three selected videos: two included with captions, one excluded.

    The excluded one is the MOST RECENT, so a command that forgot to filter it
    out would put it in `bundle-001` and be caught by the recency test rather
    than passing quietly.
    """
    config = corpus_config(tmp_path)
    newer = make_video("new", "Deep dive", upload_date=date(2025, 1, 2))
    older = make_video("old", "X670E boards, ranked", upload_date=date(2024, 1, 1))
    skipped = make_video("skip", "Power supply teardown", upload_date=date(2026, 1, 1))
    write_index_lines(
        [newer, older, skipped, make_video("shortie", inclusion="excluded_short")],
        config.data_dir / "index.jsonl",
    )
    write_selected(
        [
            make_selection(newer, THRESHOLD, (make_mention("B650E", "new", 100.0),)),
            make_selection(older, TITLE_HIT, (make_mention("X670E", "old", 100.0),)),
            make_selection(skipped, EXCLUDED, (make_mention("A620", "skip", 100.0),)),
        ],
        config.data_dir / "selected.jsonl",
    )
    write_transcript(config, "new", (100.0, TEXT_NEW))
    write_transcript(config, "old", (100.0, TEXT_OLD))
    write_transcript(config, "skip", (100.0, TEXT_SKIP))
    return config


def bundle_files(config: Config) -> list[Path]:
    return sorted((config.data_dir / "bundles").rglob("*.xml"))


class TestEstimateCommand:
    def test_the_corpus_texts_are_the_size_the_arithmetic_assumes(self) -> None:
        # Guards the numbers every test below counts on.
        assert len(TEXT_NEW) == 40
        assert len(TEXT_OLD) == 40

    def test_a_normal_run_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        assert "Traceback" not in capsys.readouterr().out

    def test_a_normal_run_writes_the_bundles_under_their_batch_directories(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert [path.relative_to(config.data_dir).as_posix() for path in bundle_files(config)] == [
            "bundles/batch-1/bundle-001.xml",
            "bundles/batch-2/bundle-002.xml",
        ]

    def test_the_bundles_carry_the_excerpt_text(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = "".join(path.read_text(encoding="utf-8") for path in bundle_files(config))
        assert TEXT_NEW in written
        assert TEXT_OLD in written

    def test_the_most_recent_video_lands_in_the_first_bundle(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        first = (config.data_dir / "bundles" / "batch-1" / "bundle-001.xml").read_text(
            encoding="utf-8"
        )
        assert TEXT_NEW in first
        assert TEXT_OLD not in first

    def test_an_excluded_selection_contributes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = "".join(path.read_text(encoding="utf-8") for path in bundle_files(config))
        assert TEXT_SKIP not in written
        assert "skip" not in written
        assert len(bundle_files(config)) == 2

    def test_a_selection_whose_transcript_is_missing_is_not_an_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        video = make_video("nocaps", "Deep dive", upload_date=date(2025, 5, 5))
        write_index_lines([video], config.data_dir / "index.jsonl")
        # A `fetch` run leaves this directory whether or not it cached anything
        # (R1005), and this test is about a state where fetch HAS run. Creating
        # it restores exactly the state the test was always about; nothing is
        # weakened.
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)
        write_selected(
            [make_selection(video, THRESHOLD, (make_mention("B650E", "nocaps", 100.0),))],
            config.data_dir / "selected.jsonl",
        )

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert "Traceback" not in out
        assert bundle_files(config) == []

    def test_a_missing_transcript_does_not_stop_the_videos_that_have_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)
        cache_path("new", config).unlink()

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = "".join(path.read_text(encoding="utf-8") for path in bundle_files(config))
        assert TEXT_OLD in written
        assert TEXT_NEW not in written

    def test_the_projection_is_printed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert out.strip() != ""
        assert lines_with(out, "bundle"), f"the bundle count must be printed: {out!r}"
        assert lines_with(out, "token"), f"the token projection must be printed: {out!r}"
        assert states_number(out, 80), f"80 projected tokens in total: {out!r}"

    def test_the_printed_projection_says_the_pipeline_stops(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        lowered = capsys.readouterr().out.lower()
        assert "stop" in lowered
        assert "model" in lowered

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

    def test_two_runs_write_byte_identical_bundles(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        before = {path: path.read_bytes() for path in bundle_files(config)}
        assert run(config, Namespace()) == 0
        capsys.readouterr()

        assert {path: path.read_bytes() for path in bundle_files(config)} == before
        assert before != {}

    def test_a_missing_index_refuses_and_names_the_index_stage(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BL-7's measured defect: the projection used to print with a silent zero.

        `videos_indexed` is the denominator of the one figure the owner spends
        against. Absent is not zero (R1005).
        """
        config = corpus_config(tmp_path)
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)
        write_selected([], config.data_dir / "selected.jsonl")

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "No index at" in out
        assert "find-best-mobo index" in out
        assert "Traceback" not in out
        assert "projected tokens" not in out, "a refusal must not print a projection"

    def test_a_missing_index_writes_no_bundles(self, tmp_path: Path) -> None:
        """The checks run before anything is cut, so a refusal leaves the tree alone."""
        config = corpus_config(tmp_path)
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)
        write_selected([], config.data_dir / "selected.jsonl")

        assert run(config, Namespace()) == 1

        assert not (config.data_dir / "bundles").exists()

    def test_an_absent_transcript_cache_refuses_and_names_fetch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No cache directory at all means `fetch` never ran — a precondition, not a result."""
        config = corpus_config(tmp_path)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        write_selected([], config.data_dir / "selected.jsonl")

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" in out
        assert "Traceback" not in out

    def test_the_earliest_missing_stage_is_the_one_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With nothing on disk, `index` is named — not whatever this stage opened last.

        Pipeline order is what makes the message actionable: told to run
        `select` first, the owner runs a stage that would itself refuse.
        """
        config = corpus_config(tmp_path)
        config.data_dir.mkdir(parents=True, exist_ok=True)

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo index" in out
        assert "fetch" not in out and "select" not in out

    def test_project_itself_raises_on_a_missing_index(self, tmp_path: Path) -> None:
        """The refusal lives in the function that reads the artifact, not only in the command."""
        config = corpus_config(tmp_path)

        with pytest.raises(MissingArtifact):
            project((), (), (), config)

    def test_a_missing_selected_file_returns_one_naming_what_to_run_first(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        # A `fetch` run leaves this directory whether or not it cached anything
        # (R1005), and this test is about a state where fetch HAS run. Creating
        # it restores exactly the state the test was always about; nothing is
        # weakened.
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "select" in out.lower(), f"the message must name the select command: {out!r}"
        assert "Traceback" not in out

    def test_a_missing_selected_file_writes_no_bundles(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        # A `fetch` run leaves this directory whether or not it cached anything
        # (R1005), and this test is about a state where fetch HAS run. Creating
        # it restores exactly the state the test was always about; nothing is
        # weakened.
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)

        assert run(config, Namespace()) == 1
        capsys.readouterr()

        assert not (config.data_dir / "bundles").exists()

    def test_no_selections_at_all_still_returns_zero_and_prints(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        write_index_lines([], config.data_dir / "index.jsonl")
        write_selected([], config.data_dir / "selected.jsonl")
        # A `fetch` run leaves this directory whether or not it cached anything
        # (R1005), and this test is about a state where fetch HAS run. Creating
        # it restores exactly the state the test was always about; nothing is
        # weakened.
        (config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert out.strip() != ""
        assert "Traceback" not in out


# The saturated video: BL-10's geometry, rebuilt synthetically (R1000, OD-4).
#
# PROVENANCE. The numbers this fixture imitates were MEASURED, on a real
# 33-minute review in the local corpus: a 28,438-character transcript came out
# of the concatenating merge as a single 137,246-character excerpt — 4.8x the
# whole transcript — and the cost projection, the one number the checkpoint
# exists to produce, was wrong by that factor. Those figures are recorded here
# and are deliberately NOT asserted: R21 holds the corpus local-only and never
# redistributed, so no caption text is checked in and the text below is
# synthetic. What is asserted is the BOUND R1000 states, which the measured case
# violated by 4.8x and which this shape reproduces.
SATURATED_VIDEO_ID = "saturated"
SATURATED_TITLE = "Every AM5 board I have looked at this year"
# ~33 minutes of speech: a cue every 3 seconds from 0s to 1,977s.
CUE_SPACING_SECONDS = 3.0
CUE_COUNT = 660
# 42 characters of cue text plus the single space that joins it to the next one
# is ~43 characters per cue, for a transcript of ~28.4k characters.
CUE_FILLER = "the vrm on this board holds up ok!"
# A mention roughly every 60 seconds: 33 windows of 120-before/300-after, each
# overlapping its neighbours, so the whole video merges into a single span.
MENTION_SPACING_SECONDS = 60.0
MENTION_COUNT = 33


def saturated_marker(index: int) -> str:
    """Cue `index`'s unique tag, ZERO-PADDED.

    Padding is load-bearing for the duplication assertions: unpadded, `"cue 1"`
    is a substring of `"cue 10"` and the counting would answer a different
    question than the one asked.
    """
    return f"cue {index:03d}"


def saturated_cues() -> tuple[tuple[float, str], ...]:
    return tuple(
        (index * CUE_SPACING_SECONDS, f"{saturated_marker(index)} {CUE_FILLER}")
        for index in range(CUE_COUNT)
    )


def saturated_corpus(tmp_path: Path) -> Config:
    """One selected video whose mentions saturate it, on disk under `tmp_path`.

    Written as a CACHED TRANSCRIPT so the real path runs end to end —
    `load_cached` → `cut_windows` → `merge_overlapping` → `cap_per_video` →
    `pack_bundles` → `project` — rather than the assertions being made against
    hand-built excerpts that no stage produced.
    """
    config = make_config(
        tmp_path / "data",
        window_before_seconds=120,
        window_after_seconds=300,
        per_video_excerpt_cap=10,
        bundle_token_cap=24000,
        calibration_batch_size=1,
        batch_count=3,
        chars_per_token=4.0,
    )
    video = make_video(SATURATED_VIDEO_ID, SATURATED_TITLE, upload_date=date(2025, 3, 4))
    write_index_lines([video], config.data_dir / "index.jsonl")
    write_selected(
        [
            make_selection(
                video,
                THRESHOLD,
                tuple(
                    make_mention(
                        "B650E" if index % 2 else "X670E",
                        SATURATED_VIDEO_ID,
                        index * MENTION_SPACING_SECONDS,
                    )
                    for index in range(MENTION_COUNT)
                ),
            )
        ],
        config.data_dir / "selected.jsonl",
    )
    write_transcript(config, SATURATED_VIDEO_ID, *saturated_cues())
    return config


def saturated_excerpts(config: Config) -> tuple[Transcript, tuple[Excerpt, ...]]:
    """The video's excerpts, off the real pipeline, from the cache on disk."""
    transcript = load_cached(SATURATED_VIDEO_ID, config)
    assert transcript is not None
    selection = next(iter(read_selected(config.data_dir / "selected.jsonl")))
    windows = cut_windows(transcript, selection.mentions, selection.video, config)
    return transcript, cap_per_video(merge_overlapping(windows, transcript), config)


class TestSaturatedVideoIsPinnedAtItsTranscript:
    """R1000: a video's excerpts never out-run its own transcript.

    PROVENANCE — BL-10, measured on a real 33-minute review: a 28,438-character
    transcript produced a single 137,246-character merged excerpt, 4.8x the
    transcript, because `merge_overlapping` concatenated the text of every
    overlapping window. The geometry below reproduces that video (~33 minutes, a
    cue every ~3 seconds of ~43 characters, a mention every ~60 seconds); the
    words do not, and the two measured figures are recorded rather than asserted,
    because R21 keeps the captions local-only and this transcript is synthetic.
    """

    def test_the_fixture_reproduces_the_measured_geometry(self, tmp_path: Path) -> None:
        # Guards the shape every assertion below depends on. If this drifts, the
        # regression stops being the case BL-10 measured.
        config = saturated_corpus(tmp_path)
        transcript, _ = saturated_excerpts(config)

        assert len(transcript.cues) == CUE_COUNT
        assert transcript.cues[-1].start_seconds == pytest.approx(1977.0)
        assert 27_500 <= transcript_characters(transcript) <= 29_500
        assert len({cue.text for cue in transcript.cues}) == CUE_COUNT

    def test_every_window_overlaps_so_the_video_merges_into_one_span(self, tmp_path: Path) -> None:
        config = saturated_corpus(tmp_path)
        transcript, excerpts = saturated_excerpts(config)

        assert len(excerpts) == 1
        assert excerpts[0].start_seconds == 0.0
        assert excerpts[0].end_seconds == pytest.approx(
            (MENTION_COUNT - 1) * MENTION_SPACING_SECONDS + config.window_after_seconds
        )

    def test_the_summed_excerpt_characters_do_not_exceed_the_transcripts(
        self, tmp_path: Path
    ) -> None:
        config = saturated_corpus(tmp_path)
        transcript, excerpts = saturated_excerpts(config)

        total = sum(len(excerpt.text) for excerpt in excerpts)

        assert total <= transcript_characters(transcript), (
            f"{total} excerpt characters against {transcript_characters(transcript)} "
            "in the transcript — this is the 4.8x BL-10 measured"
        )

    def test_the_bound_is_not_met_by_emitting_nothing(self, tmp_path: Path) -> None:
        config = saturated_corpus(tmp_path)
        _, excerpts = saturated_excerpts(config)

        assert sum(len(excerpt.text) for excerpt in excerpts) > 0

    def test_no_line_of_cue_text_appears_twice_across_the_excerpts(self, tmp_path: Path) -> None:
        config = saturated_corpus(tmp_path)
        transcript, excerpts = saturated_excerpts(config)

        repeated = [
            index
            for index in range(len(transcript.cues))
            if sum(excerpt.text.count(saturated_marker(index)) for excerpt in excerpts) > 1
        ]

        assert repeated == [], f"cues carried more than once: {repeated[:5]}"

    def test_the_projections_character_figures_are_that_same_bounded_sum(
        self, tmp_path: Path
    ) -> None:
        """The number the owner reads must be the number that is bounded.

        R1008 SPLIT that number in two: this video is saturated, so it now
        takes the whole path and its characters are reported as
        `whole_characters` rather than as `excerpt_characters`. The two sum to
        exactly what the single old field counted, which is why the bound is
        asserted on the sum — narrowing the field must not narrow the
        guarantee, and a reader comparing runs across the change is comparing
        the same quantity.
        """
        config = saturated_corpus(tmp_path)
        transcript, excerpts = saturated_excerpts(config)
        selections = tuple(read_selected(config.data_dir / "selected.jsonl"))
        submission = choose_submission(selections[0].video, transcript, excerpts, config)
        bundles = pack_bundles(submission.blocks, config)

        projection = project(bundles, selections, (submission,), config)

        sent = projection.excerpt_characters + projection.whole_characters
        assert sent == sum(len(block.text) for block in submission.blocks)
        assert 0 < sent <= transcript_characters(transcript)

    def test_the_command_prints_a_character_count_within_the_bound(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = saturated_corpus(tmp_path)
        transcript, excerpts = saturated_excerpts(config)
        expected = sum(len(excerpt.text) for excerpt in excerpts)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert states_number(out, expected), (
            f"the projection must state {expected} characters of excerpt text: {out!r}"
        )
        assert expected <= transcript_characters(transcript)

    def test_the_written_bundles_hold_no_repeated_passage(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = saturated_corpus(tmp_path)
        transcript, _ = saturated_excerpts(config)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = "".join(path.read_text(encoding="utf-8") for path in bundle_files(config))
        assert written != ""
        repeated = [
            index
            for index in range(len(transcript.cues))
            if written.count(saturated_marker(index)) > 1
        ]
        assert repeated == [], f"cues written more than once: {repeated[:5]}"

    def test_the_regression_runs_twice_to_the_same_projection(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # R23, on the path this plan changes: the re-cut must not introduce
        # anything that varies between runs.
        config = saturated_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        first = capsys.readouterr().out
        assert run(config, Namespace()) == 0
        second = capsys.readouterr().out

        assert first == second
        assert first.strip() != ""


# --------------------------------------------------------------------------
# R1008 (OD-13): the projection says which path each video took, what it cost,
# and what spans bundles.
#
# The arithmetic below is countable by hand: ONE character per token and a
# 40-token bundle cap, so a block's characters ARE its tokens and a 39-character
# cue is a bundle's worth on its own. The five submissions cover every case the
# figures have to separate — a whole transcript over two bundles, a whole
# transcript inside one, a whole transcript over three, an ordinary excerpted
# video, and a video that contributes no blocks at all.
# --------------------------------------------------------------------------

SPAN_BUNDLE_CAP = 40
WHOLE_CUE_CHARACTERS = 39

# Deliberately not in alphabetical order, and the two spanning videos span
# DIFFERENT numbers of bundles: a span list sorted by id, or by size, is then a
# different tuple from the one submission order gives (R23).
SPANNING_FIRST = "zulu"  # newest, whole, two parts, two bundles
WHOLE_SINGLE = "mid"  # whole, one part, one bundle — never a "span"
SPANNING_SECOND = "alpha"  # whole, three parts, three bundles
EXCERPTED = "old"  # the ordinary excerpt path
SILENT = "quiet"  # excerpt path with no excerpts at all: no blocks, still a video


def sized_text(tag: str, length: int) -> str:
    """`tag`, padded to EXACTLY `length` characters, so every figure is countable."""
    assert length > len(tag) + 1, f"{tag!r} does not fit in {length} characters"
    return f"{tag} " + "z" * (length - len(tag) - 1)


def routed_config(tmp_path: Path) -> Config:
    return make_config(
        tmp_path / "data",
        per_video_excerpt_cap=10,
        bundle_token_cap=SPAN_BUNDLE_CAP,
        calibration_batch_size=1,
        batch_count=3,
        chars_per_token=1.0,
    )


def whole_submission(
    video_id: str,
    cue_count: int,
    config: Config,
    *,
    cue_characters: int = WHOLE_CUE_CHARACTERS,
    title: str = "Deep dive",
) -> VideoSubmission:
    """A video whose one excerpt covers its whole transcript, routed by slice 1.

    Ratio 1.0, so `choose_submission` takes the whole path and `split_whole`
    decides the parts. The projection is then reading REAL routing rather than a
    hand-asserted `path` — which matters, because the whole claim under test is
    that the submissions and the bundles agree about the same run.
    """
    cues = tuple(
        Cue(start_seconds=index * 10.0, text=sized_text(f"{video_id}{index}", cue_characters))
        for index in range(cue_count)
    )
    transcript = Transcript(video_id=video_id, cues=cues)
    covering = Excerpt(
        video_id=video_id,
        video_title=title,
        start_seconds=cues[0].start_seconds,
        end_seconds=cues[-1].start_seconds,
        text=transcript_text(transcript),
        canonicals=("B650E",),
    )
    return choose_submission(make_video(video_id, title), transcript, (covering,), config)


def excerpts_submission(
    video_id: str,
    excerpt_lengths: Sequence[int],
    config: Config,
    *,
    cue_count: int = 5,
    title: str = "Deep dive",
) -> VideoSubmission:
    """A video the router leaves on the excerpt path: its excerpts cover little of it."""
    cues = tuple(
        Cue(
            start_seconds=index * 10.0,
            text=sized_text(f"{video_id}c{index}", WHOLE_CUE_CHARACTERS),
        )
        for index in range(cue_count)
    )
    transcript = Transcript(video_id=video_id, cues=cues)
    excerpts = tuple(
        Excerpt(
            video_id=video_id,
            video_title=title,
            start_seconds=float(index),
            end_seconds=float(index) + 1.0,
            text=sized_text(f"{video_id}e{index}", length),
            canonicals=("B650E",),
        )
        for index, length in enumerate(excerpt_lengths)
    )
    return choose_submission(make_video(video_id, title), transcript, excerpts, config)


def routed_submissions(config: Config) -> tuple[VideoSubmission, ...]:
    """The five videos, in SUBMISSION order — newest first, as the command packs them."""
    return (
        whole_submission(SPANNING_FIRST, 2, config),
        whole_submission(WHOLE_SINGLE, 1, config, cue_characters=20),
        whole_submission(SPANNING_SECOND, 3, config),
        excerpts_submission(EXCERPTED, (10, 15), config),
        excerpts_submission(SILENT, (), config),
    )


def routed_bundles(submissions: Sequence[VideoSubmission], config: Config) -> tuple[Bundle, ...]:
    """The bundles the command would write: the submissions' blocks, in order."""
    blocks = [block for submission in submissions for block in submission.blocks]
    return assign_batches(pack_bundles(blocks, config), config)


def routed_corpus(
    tmp_path: Path,
) -> tuple[Config, list[Selection], tuple[VideoSubmission, ...], tuple[Bundle, ...]]:
    config = routed_config(tmp_path)
    videos = [
        make_video(video_id)
        for video_id in (SPANNING_FIRST, WHOLE_SINGLE, SPANNING_SECOND, EXCERPTED, SILENT)
    ]
    write_index_lines(videos, config.data_dir / "index.jsonl")
    selections = [make_selection(video, THRESHOLD) for video in videos]
    submissions = routed_submissions(config)
    return config, selections, submissions, routed_bundles(submissions, config)


def bundles_holding(bundles: Sequence[Bundle], video_id: str, form: str) -> int:
    """How many DISTINCT bundles hold a block of `form` belonging to `video_id`."""
    return sum(
        1
        for bundle in bundles
        if any(block.video_id == video_id and block.form == form for block in bundle.excerpts)
    )


class TestTheRoutedFixture:
    """Guards the geometry every figure below is counted against."""

    def test_the_paths_and_the_parts_are_what_the_arithmetic_assumes(self, tmp_path: Path) -> None:
        _, _, submissions, _ = routed_corpus(tmp_path)
        by_id = {submission.video_id: submission for submission in submissions}

        assert [submission.video_id for submission in submissions] == [
            SPANNING_FIRST,
            WHOLE_SINGLE,
            SPANNING_SECOND,
            EXCERPTED,
            SILENT,
        ]
        assert [by_id[SPANNING_FIRST].path, by_id[WHOLE_SINGLE].path] == [WHOLE, WHOLE]
        assert by_id[SPANNING_SECOND].path == WHOLE
        assert [by_id[EXCERPTED].path, by_id[SILENT].path] == [EXCERPTS, EXCERPTS]
        assert [len(by_id[vid].blocks) for vid in (SPANNING_FIRST, WHOLE_SINGLE)] == [2, 1]
        assert [len(by_id[SPANNING_SECOND].blocks), len(by_id[EXCERPTED].blocks)] == [3, 2]
        assert by_id[SILENT].blocks == ()
        assert by_id[SPANNING_FIRST].transcript_characters == 79
        assert by_id[WHOLE_SINGLE].transcript_characters == 20
        assert by_id[SPANNING_SECOND].transcript_characters == 119

    def test_the_bundles_are_the_ones_the_span_figures_are_counted_from(
        self, tmp_path: Path
    ) -> None:
        _, _, _, bundles = routed_corpus(tmp_path)

        assert len(bundles) == 7
        assert bundles_holding(bundles, SPANNING_FIRST, WHOLE) == 2
        assert bundles_holding(bundles, WHOLE_SINGLE, WHOLE) == 1
        assert bundles_holding(bundles, SPANNING_SECOND, WHOLE) == 3
        assert bundles_holding(bundles, EXCERPTED, EXCERPTS) == 1


class TestPerPathFigures:
    """R1008: how many videos took each path, and what each path accounts for."""

    def test_every_new_field_over_the_hand_built_corpus(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        projection = project(bundles, selections, submissions, config)

        assert projection == expected_projection(
            projection,
            videos_whole=3,
            videos_excerpted=2,
            excerpt_characters=25,
            whole_characters=215,
            whole_tokens=215,
            excerpt_tokens=25,
            videos_over_bundle_cap=2,
            bundles_spanned=((SPANNING_FIRST, 2), (SPANNING_SECOND, 3)),
        )

    def test_the_counts_are_counts_of_videos_not_of_blocks(self, tmp_path: Path) -> None:
        """Eight blocks over five videos: a block count reads 8 and is wrong."""
        config, selections, submissions, bundles = routed_corpus(tmp_path)
        blocks = sum(len(submission.blocks) for submission in submissions)

        projection = project(bundles, selections, submissions, config)

        assert blocks == 8
        assert projection.videos_whole == 3
        assert projection.videos_excerpted == 2

    def test_the_two_counts_cover_every_submission(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        projection = project(bundles, selections, submissions, config)

        assert projection.videos_whole + projection.videos_excerpted == len(submissions)

    def test_a_video_that_contributed_no_blocks_is_still_a_video(self, tmp_path: Path) -> None:
        """`quiet` has no excerpts, so it reaches no bundle — and is still excerpted.

        This is why the path counts are read off the SUBMISSIONS: the bundles
        have never heard of this video, and counting them would lose it.
        """
        config, selections, submissions, bundles = routed_corpus(tmp_path)
        written = "".join(render_bundle(bundle) for bundle in bundles)

        projection = project(bundles, selections, submissions, config)

        assert SILENT not in written
        assert projection.videos_excerpted == 2
        assert projection.videos_whole + projection.videos_excerpted == 5

    def test_the_characters_are_split_by_form(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        projection = project(bundles, selections, submissions, config)

        assert projection.excerpt_characters == 25
        assert projection.whole_characters == 215

    def test_the_two_character_figures_sum_to_what_the_old_field_counted(
        self, tmp_path: Path
    ) -> None:
        """`excerpt_characters` NARROWED; the pair must still total the old number.

        Anything else silently changes what a reader is comparing between runs.
        """
        config, selections, submissions, bundles = routed_corpus(tmp_path)
        every_block = [block for bundle in bundles for block in bundle.excerpts]

        projection = project(bundles, selections, submissions, config)

        assert projection.excerpt_characters + projection.whole_characters == sum(
            len(block.text) for block in every_block
        )

    def test_the_tokens_are_split_the_same_way(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        projection = project(bundles, selections, submissions, config)

        assert projection.whole_tokens == 215
        assert projection.excerpt_tokens == 25

    def test_the_two_token_figures_sum_to_the_total_and_do_not_double_count(
        self, tmp_path: Path
    ) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        projection = project(bundles, selections, submissions, config)

        assert projection.whole_tokens + projection.excerpt_tokens == projection.total_tokens
        assert projection.total_tokens == 240

    def test_a_whole_videos_would_be_excerpts_are_not_excerpt_characters(
        self, tmp_path: Path
    ) -> None:
        """A whole-path submission still REMEMBERS its excerpt characters.

        `VideoSubmission.excerpt_characters` is what the excerpts would have
        been — it is how the ratio was measured — and it is not what was sent.
        Summing it over every submission would report 243 characters of excerpt
        text for a run that sent 25.
        """
        config, selections, submissions, bundles = routed_corpus(tmp_path)
        every_submission = sum(submission.excerpt_characters for submission in submissions)

        projection = project(bundles, selections, submissions, config)

        assert every_submission == 243
        assert projection.excerpt_characters == 25

    def test_the_figures_do_not_move_between_identical_runs(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        first = project(bundles, selections, submissions, config)
        second = project(bundles, selections, submissions, config)

        assert first == second


class TestBundlesSpanned:
    """R1008: which transcripts crossed a bundle boundary, and over how many."""

    def test_it_names_every_whole_video_over_more_than_one_bundle(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        spanned = project(bundles, selections, submissions, config).bundles_spanned

        assert dict(spanned) == {SPANNING_FIRST: 2, SPANNING_SECOND: 3}

    def test_a_whole_transcript_inside_one_bundle_is_not_listed(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        spanned = project(bundles, selections, submissions, config).bundles_spanned

        assert WHOLE_SINGLE not in dict(spanned)
        assert all(count > 1 for _, count in spanned)

    def test_an_excerpt_path_video_is_never_listed(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        spanned = project(bundles, selections, submissions, config).bundles_spanned

        assert EXCERPTED not in dict(spanned)
        assert SILENT not in dict(spanned)

    def test_the_order_is_submission_order_newest_first(self, tmp_path: Path) -> None:
        """Not sorted by id and not sorted by size: `zulu` spans 2, `alpha` spans 3.

        Either sort would put `alpha` first, so this pins the order R23 asks
        for rather than an ordering that happens to agree with it.
        """
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        spanned = project(bundles, selections, submissions, config).bundles_spanned

        assert spanned == ((SPANNING_FIRST, 2), (SPANNING_SECOND, 3))
        assert [video_id for video_id, _ in spanned] != sorted(video_id for video_id, _ in spanned)

    def test_the_entries_are_video_id_and_bundle_count(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        spanned = project(bundles, selections, submissions, config).bundles_spanned

        for entry in spanned:
            video_id, count = entry
            assert isinstance(video_id, str)
            assert isinstance(count, int)
            assert count == bundles_holding(bundles, video_id, WHOLE)

    def test_the_count_is_bundles_occupied_not_parts_declared(self, tmp_path: Path) -> None:
        """The span figure comes from THE BUNDLES, not from `part_count`.

        A part count is what the router intended; the bundles are what happened.
        Here three declared parts landed in two bundles, and the number R1008
        asks for — how many sequential bundles the transcript spans — is two.
        Reading `part_count` says three, and counting blocks says three.
        """
        config = routed_config(tmp_path)
        write_index_lines([make_video("solo")], config.data_dir / "index.jsonl")
        parts = tuple(
            whole_block("solo", part, 3, sized_text(f"solo{part}", 20)) for part in (1, 2, 3)
        )
        bundles = (
            Bundle("bundle-001", 1, parts[:2], 40),
            Bundle("bundle-002", 2, parts[2:], 20),
        )
        submissions = (
            make_submission("solo", WHOLE, parts, config, whole_transcript_characters=62),
        )

        projection = project(bundles, [], submissions, config)

        assert projection.bundles_spanned == (("solo", 2),)

    def test_it_is_empty_when_no_transcript_crosses_a_boundary(self, tmp_path: Path) -> None:
        config = routed_config(tmp_path)
        write_index_lines([make_video(WHOLE_SINGLE)], config.data_dir / "index.jsonl")
        submissions = (whole_submission(WHOLE_SINGLE, 1, config, cue_characters=20),)
        bundles = routed_bundles(submissions, config)

        projection = project(bundles, [], submissions, config)

        assert len(bundles) == 1
        assert projection.bundles_spanned == ()
        assert projection.videos_whole == 1


class TestIntentAgainstOutcome:
    """The submissions say what the router meant; the bundles say what happened."""

    def test_the_over_cap_count_equals_the_number_of_spanning_transcripts(
        self, tmp_path: Path
    ) -> None:
        """The cross-check R1008 asks for, on a run where intent and outcome agree.

        `videos_over_bundle_cap` is counted from the SUBMISSIONS — whole-path
        videos whose whole transcript is projected over `bundle_token_cap` —
        and `bundles_spanned` is counted from the BUNDLES. Slice 2's invariant
        is the claim that the two must come out the same.
        """
        config, selections, submissions, bundles = routed_corpus(tmp_path)
        over_cap = [
            submission
            for submission in submissions
            if submission.path == WHOLE
            and estimate_tokens("z" * submission.transcript_characters, config)
            > config.bundle_token_cap
        ]

        projection = project(bundles, selections, submissions, config)

        assert [submission.video_id for submission in over_cap] == [
            SPANNING_FIRST,
            SPANNING_SECOND,
        ]
        assert projection.videos_over_bundle_cap == 2
        assert projection.videos_over_bundle_cap == len(projection.bundles_spanned)

    def test_a_transcript_exactly_at_the_cap_is_not_over_it(self, tmp_path: Path) -> None:
        config = routed_config(tmp_path)
        write_index_lines([make_video("edge")], config.data_dir / "index.jsonl")
        submissions = (whole_submission("edge", 1, config, cue_characters=SPAN_BUNDLE_CAP),)
        bundles = routed_bundles(submissions, config)

        projection = project(bundles, [], submissions, config)

        assert submissions[0].transcript_characters == SPAN_BUNDLE_CAP
        assert projection.videos_over_bundle_cap == 0
        assert projection.bundles_spanned == ()

    def test_the_over_cap_count_is_read_off_the_submissions_own_transcripts(
        self, tmp_path: Path
    ) -> None:
        """One cue larger than a whole bundle: over the cap, and spanning nothing.

        The plan's own splitting rule makes this case: a cue is never split, so
        a single over-cap cue becomes one part, and `pack_bundles` gives it a
        bundle to itself. The transcript IS over one bundle's token cap — the
        submission says so — while it occupies exactly one bundle, so the span
        list is empty. `videos_over_bundle_cap` re-derived from
        `len(bundles_spanned)` would report zero here and the cross-check above
        would be checking a number against itself.
        """
        config = routed_config(tmp_path)
        write_index_lines([make_video("giant")], config.data_dir / "index.jsonl")
        submissions = (whole_submission("giant", 1, config, cue_characters=100),)
        bundles = routed_bundles(submissions, config)

        projection = project(bundles, [], submissions, config)

        assert len(submissions[0].blocks) == 1
        assert len(bundles) == 1
        assert projection.videos_over_bundle_cap == 1
        assert projection.bundles_spanned == ()

    def test_an_excerpt_path_video_never_counts_as_over_the_cap(self, tmp_path: Path) -> None:
        """A huge transcript excerpted down to two windows is not an uncapped submission."""
        config = routed_config(tmp_path)
        write_index_lines([make_video(EXCERPTED)], config.data_dir / "index.jsonl")
        submissions = (excerpts_submission(EXCERPTED, (10, 15), config, cue_count=20),)
        bundles = routed_bundles(submissions, config)

        projection = project(bundles, [], submissions, config)

        assert submissions[0].path == EXCERPTS
        assert (
            estimate_tokens("z" * submissions[0].transcript_characters, config)
            > config.bundle_token_cap
        )
        assert projection.videos_over_bundle_cap == 0
        assert projection.bundles_spanned == ()


class TestNoSubmissionsIsARealValue:
    """R1008: an empty corpus reports zeroes on every path, and does not raise."""

    def test_no_submissions_projects_zeroes_and_an_empty_span_list(self, tmp_path: Path) -> None:
        config = routed_config(tmp_path)
        write_index_lines([], config.data_dir / "index.jsonl")

        projection = project([], [], [], config)

        assert projection.videos_whole == 0
        assert projection.videos_excerpted == 0
        assert projection.whole_characters == 0
        assert projection.excerpt_characters == 0
        assert projection.whole_tokens == 0
        assert projection.excerpt_tokens == 0
        assert projection.videos_over_bundle_cap == 0
        assert projection.bundles_spanned == ()

    def test_the_empty_projection_still_renders(self, tmp_path: Path) -> None:
        config = routed_config(tmp_path)
        write_index_lines([], config.data_dir / "index.jsonl")

        text = render_projection(project([], [], [], config))

        assert text.strip() != ""
        assert "Traceback" not in text


class TestRenderProjectionPerPath:
    """R1008's figures have to be printed, or the checkpoint cannot show them."""

    def test_both_path_counts_are_stated(self) -> None:
        text = render_projection(SAMPLE)

        assert states_number(text, 4), f"4 videos sent whole is missing from:\n{text}"
        assert states_number(text, 41), f"41 videos excerpted is missing from:\n{text}"

    def test_both_paths_name_themselves(self) -> None:
        lowered = render_projection(SAMPLE).lower()

        assert "whole" in lowered
        assert "excerpt" in lowered

    def test_the_characters_of_each_path_are_stated(self) -> None:
        text = render_projection(SAMPLE)

        assert states_number(text, 678900), f"excerpt characters missing from:\n{text}"
        assert states_number(text, 500000), f"whole-transcript characters missing:\n{text}"

    def test_the_tokens_of_each_path_are_stated(self) -> None:
        text = render_projection(SAMPLE)

        assert states_number(text, 50), f"whole-path tokens missing from:\n{text}"
        assert states_number(text, 16), f"excerpt-path tokens missing from:\n{text}"

    def test_the_over_cap_count_is_stated(self) -> None:
        text = render_projection(SAMPLE)

        assert states_number(text, 2), f"the over-cap video count is missing:\n{text}"

    def test_every_spanning_transcript_is_named_with_its_bundle_count(self) -> None:
        text = render_projection(SAMPLE)

        for video_id, count in SAMPLE.bundles_spanned:
            named = lines_with(text, video_id)
            assert named, f"{video_id} must be named in the projection:\n{text}"
            assert any(states_number(line, count) for line in named), (
                f"{video_id} must be reported as spanning {count} bundles: {named!r}"
            )

    def test_the_spans_are_printed_in_the_order_the_projection_holds_them(self) -> None:
        text = render_projection(SAMPLE)

        positions = [text.index(video_id) for video_id, _ in SAMPLE.bundles_spanned]

        assert positions == sorted(positions), (
            f"the span list is newest-first (R23) and must print that way:\n{text}"
        )

    def test_an_empty_span_list_names_no_video(self) -> None:
        text = render_projection(make_projection(videos_whole=1, videos_excerpted=2))

        assert "vidzulu" not in text
        assert "vidalpha" not in text
        assert text.strip() != ""

    def test_two_projections_differing_only_in_the_spans_render_differently(self) -> None:
        other = replace(SAMPLE, bundles_spanned=(("vidzulu", 3),), videos_over_bundle_cap=1)

        assert render_projection(other) != render_projection(SAMPLE)

    def test_two_projections_differing_only_in_the_path_split_render_differently(
        self,
    ) -> None:
        other = replace(SAMPLE, videos_whole=41, videos_excerpted=4)

        assert render_projection(other) != render_projection(SAMPLE)

    def test_rendering_the_new_fields_twice_is_identical(self) -> None:
        assert render_projection(SAMPLE) == render_projection(SAMPLE)


class TestRenderedProjectionStatesTheCap:
    """A span reported without the bound that produced it reads as a fact about
    the corpus rather than about the configuration — the same reason the
    chars-per-token factor is printed.

    The cap is put into the projection by `project` rather than by a literal,
    because the plan's Signatures block names no `Projection` field to carry it
    and `render_projection` takes nothing else. These tests therefore pin the
    behaviour and not a field name.
    """

    def test_the_bundle_token_cap_is_stated(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        text = render_projection(project(bundles, selections, submissions, config))

        assert states_number(text, config.bundle_token_cap), (
            f"the {config.bundle_token_cap}-token bundle cap the transcripts were "
            f"split against must be stated:\n{text}"
        )

    def test_the_cap_reads_as_a_bound_rather_than_as_another_total(self, tmp_path: Path) -> None:
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        text = render_projection(project(bundles, selections, submissions, config))
        stated = [
            line for line in text.splitlines() if states_number(line, config.bundle_token_cap)
        ]

        assert stated, f"the bundle token cap must be stated:\n{text}"
        assert any(
            word in line.lower() for line in stated for word in ("cap", "bundle", "limit")
        ), f"the cap must be named as what it is: {stated!r}"

    def test_the_cap_is_stated_beside_the_spans(self, tmp_path: Path) -> None:
        """Beside the spans, in the same breath — not filed away elsewhere."""
        config, selections, submissions, bundles = routed_corpus(tmp_path)

        lines = render_projection(project(bundles, selections, submissions, config)).splitlines()
        cap_at = [
            index
            for index, line in enumerate(lines)
            if states_number(line, config.bundle_token_cap)
        ]
        span_at = [index for index, line in enumerate(lines) if SPANNING_FIRST in line]

        assert cap_at and span_at, f"both the cap and the spans must be printed:\n{lines}"
        assert min(abs(cap - span) for cap in cap_at for span in span_at) <= 4, (
            "the cap belongs beside the spans it produced, not elsewhere in the report:\n"
            + "\n".join(lines)
        )


# One saturated video far larger than a bundle, and one ordinary excerpted one:
# the whole path, end to end, through the real command. Six 39-character cues
# inside one 20-second window at one character per token, against a 47-token
# cap — so the transcript is 239 characters, six parts, six bundles, and 47
# appears nowhere else in the printed report.
SPAN_RUN_CAP = 47
SPAN_RUN_WHOLE = "huge"
SPAN_RUN_EXCERPTED = "tiny"


def spanning_corpus(tmp_path: Path) -> Config:
    config = make_config(
        tmp_path / "data",
        window_before_seconds=10,
        window_after_seconds=10,
        per_video_excerpt_cap=10,
        bundle_token_cap=SPAN_RUN_CAP,
        calibration_batch_size=1,
        batch_count=3,
        chars_per_token=1.0,
    )
    huge = make_video(SPAN_RUN_WHOLE, "Every AM5 board", upload_date=date(2025, 1, 2))
    tiny = make_video(SPAN_RUN_EXCERPTED, "One board", upload_date=date(2024, 1, 1))
    write_index_lines([huge, tiny], config.data_dir / "index.jsonl")
    write_selected(
        [
            make_selection(huge, THRESHOLD, (make_mention("B650E", SPAN_RUN_WHOLE, 8.0),)),
            make_selection(tiny, THRESHOLD, (make_mention("X670E", SPAN_RUN_EXCERPTED, 100.0),)),
        ],
        config.data_dir / "selected.jsonl",
    )
    write_transcript(
        config,
        SPAN_RUN_WHOLE,
        *(
            (index * 3.0, sized_text(f"{SPAN_RUN_WHOLE}{index}", WHOLE_CUE_CHARACTERS))
            for index in range(6)
        ),
    )
    write_transcript(
        config,
        SPAN_RUN_EXCERPTED,
        *((index * 100.0, sized_text(f"{SPAN_RUN_EXCERPTED}{index}", 30)) for index in range(4)),
    )
    return config


class TestTheCommandReportsTheUncappedPath:
    """The checkpoint the owner actually reads: `estimate`, end to end."""

    def test_a_run_over_a_spanning_corpus_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = spanning_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        assert "Traceback" not in capsys.readouterr().out

    def test_the_transcript_really_did_span_six_bundles(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Guards the geometry the printed figures below are counted against.
        config = spanning_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        written = [path.read_text(encoding="utf-8") for path in bundle_files(config)]
        holding = [text for text in written if f'video_id="{SPAN_RUN_WHOLE}"' in text]
        assert len(written) == 7
        assert len(holding) == 6
        assert all('form="whole"' in text for text in holding)

    def test_the_printed_projection_names_the_spanning_transcript(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = spanning_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        named = lines_with(out, SPAN_RUN_WHOLE)
        assert named, f"the spanning transcript must be named by id:\n{out}"
        assert any(states_number(line, 6) for line in named), (
            f"it must be reported as spanning 6 bundles: {named!r}"
        )

    def test_the_printed_projection_states_the_cap_it_split_against(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = spanning_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert states_number(out, SPAN_RUN_CAP), (
            f"the {SPAN_RUN_CAP}-token bundle cap must be stated:\n{out}"
        )

    def test_the_printed_projection_separates_the_two_paths(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = spanning_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert states_number(out, 234), f"234 characters of whole transcript:\n{out}"
        assert states_number(out, 30), f"30 characters of excerpt text:\n{out}"

    def test_two_runs_over_a_spanning_corpus_print_identically(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = spanning_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        first = capsys.readouterr().out
        assert run(config, Namespace()) == 0
        second = capsys.readouterr().out

        assert first == second
        assert first.strip() != ""


# Package roots that only a model client, an HTTP call or a credential store
# would bring in. Absence of every one of them is the milestone's promise.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "anthropic",
        "openai",
        "cohere",
        "litellm",
        "boto3",
        "botocore",
        "google",
        "transformers",
        "torch",
        "httpx",
        "requests",
        "aiohttp",
        "urllib",
        "urllib3",
        "http",
        "socket",
        "ssl",
        "yt_dlp",
        "find_best_mobo.ytdlp",
    }
)

# Source-level tells of a credential read or an inference call, in the forms
# they actually appear in. Deliberately narrow: `model` and `invoke` are words
# the projection itself is required to PRINT, so neither can be banned outright.
FORBIDDEN_SOURCE_PATTERNS = (
    r"\bapi_key\b",
    r"\bAPI_KEY\b",
    r"\bapi-key\b",
    r"x-api-key",
    r"\bbearer\b",
    r"\bos\.environ\b",
    r"\bgetenv\b",
    r"\bmessages\.create\b",
    r"\bcompletions?\.create\b",
    r"\bchat\.completions\b",
)

INFERENCE_MODULES = ("find_best_mobo.estimate", "find_best_mobo.commands.estimate")


def module_source(module_name: str) -> str:
    module = __import__(module_name, fromlist=["__file__"])
    path = getattr(module, "__file__", None)
    assert path is not None, f"{module_name} has no source file"
    return Path(path).read_text(encoding="utf-8")


def imported_roots(source: str) -> set[str]:
    """Every top-level package name this module imports, plus dotted originals."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name)
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            roots.add(node.module)
            roots.add(node.module.split(".")[0])
    return roots


class TestNoInferencePath:
    """R7: the stop is structural. No client, no key, no call — in the source.

    This is the milestone's central promise, so it is asserted against the
    module text rather than against behaviour: a code path that is merely never
    taken today is still a code path, and the whole point of ending here is that
    there is nothing to take.
    """

    @pytest.mark.parametrize("module_name", INFERENCE_MODULES)
    def test_no_model_client_or_transport_is_imported(self, module_name: str) -> None:
        offenders = imported_roots(module_source(module_name)) & FORBIDDEN_IMPORT_ROOTS

        assert offenders == set(), (
            f"{module_name} must not import {sorted(offenders)}: the estimate "
            "command has no code path into inference (R7)"
        )

    @pytest.mark.parametrize("module_name", INFERENCE_MODULES)
    def test_no_credential_read_or_inference_call_appears(self, module_name: str) -> None:
        source = module_source(module_name)

        for pattern in FORBIDDEN_SOURCE_PATTERNS:
            assert re.search(pattern, source) is None, (
                f"{module_name} matches {pattern!r}: the milestone ends at the "
                "projection and reads no credential and calls no model (R7)"
            )

    def test_the_import_check_can_actually_fail(self) -> None:
        # Guards the two tests above against silently passing on a source they
        # failed to read: the same machinery, pointed at a module that really
        # does reach the network, must report it.
        offenders = imported_roots(module_source("find_best_mobo.ytdlp"))

        assert offenders & FORBIDDEN_IMPORT_ROOTS != set()
