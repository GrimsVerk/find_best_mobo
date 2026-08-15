"""Tests for slice 5 — the cost projection, and the structural stop.

Written blind from the slice spec and the shared contract while the
implementation is authored in parallel, so a failing import is the expected
state until assembly. Nothing under test is faked: the index, the selections and
the transcript cache are real files under `tmp_path` in the shapes slices 1–4
document, and this slice touches no network at all.

The corpus in `build_corpus` is arranged so every projected number is checkable
by hand: two included videos with one 40-character excerpt each, a token factor
of exactly one character per token, and a bundle cap of exactly one excerpt.

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
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import Mention
from find_best_mobo.bundle import Bundle
from find_best_mobo.commands.estimate import run
from find_best_mobo.config import Config
from find_best_mobo.estimate import Projection, project, render_projection
from find_best_mobo.excerpt import Excerpt
from find_best_mobo.index import Video
from find_best_mobo.select import Selection, write_selected
from find_best_mobo.transcripts import Cue, Transcript, cache_path

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
) -> Selection:
    return Selection(
        video=video,
        reason=reason,
        mentions=mentions,
        distinct_canonicals=len({mention.canonical for mention in mentions}),
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
        bundles = [
            make_bundle("bundle-001", 1, 10, "x" * 40),
            make_bundle("bundle-002", 2, 20, "y" * 60),
        ]
        selections = [
            make_selection(make_video("a"), TITLE_HIT),
            make_selection(make_video("b"), THRESHOLD),
            make_selection(make_video("c"), EXCLUDED),
        ]

        assert project(bundles, selections, config) == Projection(
            videos_indexed=3,
            videos_selected=2,
            excerpt_characters=100,
            bundle_count=2,
            tokens_per_batch=(10, 20, 0, 0),
            total_tokens=30,
            chars_per_token=4.0,
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

        assert project([], [], config).videos_indexed == 2

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

        assert project([], selections, config).videos_selected == 3

    def test_videos_selected_is_zero_when_everything_was_excluded(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        selections = [make_selection(make_video(vid), EXCLUDED) for vid in ("a", "b")]

        assert project([], selections, config).videos_selected == 0

    def test_excerpt_characters_totals_the_excerpt_text(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [
            Bundle("bundle-001", 1, (make_excerpt("z" * 7), make_excerpt("z" * 13)), 5),
            Bundle("bundle-002", 2, (make_excerpt("z" * 100),), 25),
        ]

        assert project(bundles, [], config).excerpt_characters == 120

    def test_excerpt_characters_counts_text_not_markup(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [Bundle("bundle-001", 1, (make_excerpt("hello"),), 2)]

        assert project(bundles, [], config).excerpt_characters == 5

    def test_tokens_per_batch_is_indexed_from_batch_one(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [
            make_bundle("bundle-001", 1, 5),
            make_bundle("bundle-002", 1, 7),
            make_bundle("bundle-003", 4, 900),
        ]

        projection = project(bundles, [], config)

        assert projection.tokens_per_batch[0] == 12
        assert projection.tokens_per_batch[3] == 900

    def test_empty_batches_contribute_zero_and_are_still_present(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [make_bundle("bundle-001", 1, 42)]

        projection = project(bundles, [], config)

        assert projection.tokens_per_batch == (42, 0, 0, 0)
        assert len(projection.tokens_per_batch) == 4

    def test_the_tuple_length_follows_the_configured_batch_count(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=5)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")

        projection = project([make_bundle("bundle-001", 2, 3)], [], config)

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

        projection = project(bundles, [], config)

        assert projection.total_tokens == 357
        assert projection.total_tokens == sum(projection.tokens_per_batch)

    def test_bundle_count_is_the_number_of_bundles(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")
        bundles = [make_bundle(f"bundle-{n:03d}", 1, 1) for n in range(1, 8)]

        assert project(bundles, [], config).bundle_count == 7

    def test_the_chars_per_token_factor_comes_from_config(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", chars_per_token=3.25)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")

        assert project([], [], config).chars_per_token == 3.25

    def test_nothing_at_all_projects_zeros(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data", batch_count=3, chars_per_token=4.0)
        write_index_lines([], config.data_dir / "index.jsonl")

        assert project([], [], config) == Projection(
            videos_indexed=0,
            videos_selected=0,
            excerpt_characters=0,
            bundle_count=0,
            tokens_per_batch=(0, 0, 0, 0),
            total_tokens=0,
            chars_per_token=4.0,
        )


SAMPLE = Projection(
    videos_indexed=123,
    videos_selected=45,
    excerpt_characters=678900,
    bundle_count=7,
    tokens_per_batch=(11, 22, 33, 0),
    total_tokens=66,
    chars_per_token=3.5,
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
        other = Projection(
            videos_indexed=1,
            videos_selected=1,
            excerpt_characters=2,
            bundle_count=1,
            tokens_per_batch=(1, 0, 0, 0),
            total_tokens=1,
            chars_per_token=4.0,
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

    def test_a_missing_selected_file_returns_one_naming_what_to_run_first(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "select" in out.lower(), f"the message must name the select command: {out!r}"
        assert "Traceback" not in out

    def test_a_missing_selected_file_writes_no_bundles(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        write_index_lines([make_video("a")], config.data_dir / "index.jsonl")

        assert run(config, Namespace()) == 1
        capsys.readouterr()

        assert not (config.data_dir / "bundles").exists()

    def test_no_selections_at_all_still_returns_zero_and_prints(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = corpus_config(tmp_path)
        write_index_lines([], config.data_dir / "index.jsonl")
        write_selected([], config.data_dir / "selected.jsonl")

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert out.strip() != ""
        assert "Traceback" not in out


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
