"""Transcript coverage at `estimate` — the figure beside the cost, and the refusal.

Written blind from `docs/plans/oracle/transcript-coverage-guard.md` (slice 2)
while the implementation is authored in parallel, so failing imports and
`TypeError`s on the new field are the expected state until assembly.

**R1012** (OD-23) requires the cost projection to print "the same coverage
figure" beside its character count, so no projection can be read without seeing
what fraction of the corpus produced it. "The same" is why the figure is READ
off the selections rather than re-derived from disk: `select` counts the pending
videos and `estimate` counts the included ones, so two independent
measurements would disagree by construction.

**BL-27** is the console output this makes impossible: a zero-character,
zero-token projection closing with R7's "The pipeline STOPS here", printed over
a corpus in which no speech had been read at all. The refusal REPLACES that
block rather than sitting above it — a warning next to the checkpoint's success
language annotates it instead of separating it.

`TestTheDistinguishingPair` is the point of the whole plan: the same selections,
the same zero mentions, and opposite verdicts depending on whether the corpus
was read.
"""

from __future__ import annotations

import json
from argparse import Namespace
from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import Mention
from find_best_mobo.commands.estimate import run
from find_best_mobo.config import Config
from find_best_mobo.estimate import Projection, project, render_projection
from find_best_mobo.index import Video
from find_best_mobo.select import Coverage, Selection, write_selected
from find_best_mobo.transcripts import Cue, Transcript, cache_path

TITLE_HIT = "title_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"

# The noun slice 2 counts in: the population beside `characters of excerpt
# text` is the videos that were excerpted, not the ones `select` considered.
SELECTED_NOUN = "selected videos"


def make_config(
    data_dir: Path,
    *,
    window_before_seconds: int = 10,
    window_after_seconds: int = 10,
    per_video_excerpt_cap: int = 10,
    bundle_token_cap: int = 40,
    calibration_batch_size: int = 1,
    batch_count: int = 3,
    chars_per_token: float = 1.0,
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


def make_mention(canonical: str, video_id: str, start: float = 100.0) -> Mention:
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
    has_transcript: bool,
) -> Selection:
    return Selection(
        video=video,
        reason=reason,
        mentions=mentions,
        distinct_canonicals=len({mention.canonical for mention in mentions}),
        has_transcript=has_transcript,
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


def fetched(config: Config) -> Path:
    """The empty cache directory a `fetch` run leaves behind (R1005).

    Every corpus here creates it. Without it the older, coarser refusal fires
    and ALSO names `fetch`, so a coverage test that skipped this step would
    pass against an implementation that has no coverage check at all.
    """
    cache_dir = config.data_dir / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def write_transcript(config: Config, video_id: str, *cues: tuple[float, str]) -> Path:
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
    return path


def bundle_files(config: Config) -> list[Path]:
    return sorted((config.data_dir / "bundles").rglob("*.xml"))


def lines_with(output: str, token: str) -> list[str]:
    return [line for line in output.splitlines() if token.lower() in line.lower()]


def line_index(output: str, token: str) -> int:
    """The index of the one output line mentioning `token`."""
    hits = [
        index for index, line in enumerate(output.splitlines()) if token.lower() in line.lower()
    ]
    assert len(hits) == 1, f"expected exactly one line mentioning {token!r}:\n{output}"
    return hits[0]


# Two 40-character excerpt texts, a one-character-per-token factor and a
# 40-token bundle cap: one excerpt per bundle, every number countable.
TEXT_NEW = "the b650e board is the pick here for am5"
TEXT_OLD = "the x670e board is the pick here for am5"
TEXT_SKIP = "the a620 board is the pick here for am5"

NEWER = make_video("new", "Deep dive", upload_date=date(2025, 1, 2))
OLDER = make_video("old", "X670E boards, ranked", upload_date=date(2024, 1, 1))
SKIPPED = make_video("skip", "Power supply teardown", upload_date=date(2026, 1, 1))


def build_corpus(
    tmp_path: Path,
    *,
    cached: Sequence[str] = ("new", "old", "skip"),
    flagged: Sequence[str] = ("new", "old", "skip"),
) -> Config:
    """Three selections — two included, one excluded — cached and flagged at will.

    `cached` chooses which transcripts exist on disk; `flagged` chooses which
    selections claim `has_transcript`. They are separate arguments because the
    plan says the figure is read off the SELECTIONS and never re-derived from
    disk, and the only way to pin that is to make the two disagree.

    The excluded video is the most RECENT and is always cached, so a coverage
    figure taken over every row rather than the included ones reports 3 as its
    denominator instead of 2.
    """
    config = make_config(tmp_path / "data")
    write_index_lines(
        [NEWER, OLDER, SKIPPED, make_video("shortie", inclusion="excluded_short")],
        config.data_dir / "index.jsonl",
    )
    write_selected(
        [
            make_selection(
                NEWER,
                THRESHOLD,
                (make_mention("B650E", "new"),),
                has_transcript="new" in flagged,
            ),
            make_selection(
                OLDER,
                TITLE_HIT,
                (make_mention("X670E", "old"),),
                has_transcript="old" in flagged,
            ),
            make_selection(
                SKIPPED,
                EXCLUDED,
                (make_mention("A620", "skip"),),
                has_transcript="skip" in flagged,
            ),
        ],
        config.data_dir / "selected.jsonl",
    )
    fetched(config)
    texts = {"new": TEXT_NEW, "old": TEXT_OLD, "skip": TEXT_SKIP}
    for video_id in cached:
        write_transcript(config, video_id, (100.0, texts[video_id]))
    return config


class TestProjectCarriesCoverage:
    def test_the_population_is_the_included_selections(self, tmp_path: Path) -> None:
        """The figure annotates `characters of excerpt text`, which is summed over the INCLUDED
        videos.

        A coverage figure over a different set than the number it sits beside is
        worse than none: it would read as a comment on the excerpt total while
        measuring something else.
        """
        config = make_config(tmp_path / "data")
        write_index_lines([NEWER, OLDER, SKIPPED], config.data_dir / "index.jsonl")
        selections = [
            make_selection(NEWER, THRESHOLD, has_transcript=True),
            make_selection(OLDER, TITLE_HIT, has_transcript=False),
            make_selection(SKIPPED, EXCLUDED, has_transcript=True),
        ]

        assert project([], selections, config).coverage == Coverage(considered=2, with_transcript=1)

    def test_an_excluded_selection_never_lowers_the_figure(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([NEWER, OLDER, SKIPPED], config.data_dir / "index.jsonl")
        selections = [
            make_selection(NEWER, THRESHOLD, has_transcript=True),
            make_selection(OLDER, TITLE_HIT, has_transcript=True),
            make_selection(SKIPPED, EXCLUDED, has_transcript=False),
        ]

        assert project([], selections, config).coverage == Coverage(considered=2, with_transcript=2)

    def test_the_denominator_is_the_videos_selected_figure(self, tmp_path: Path) -> None:
        """Two numbers in one block that must never diverge, taken from one population."""
        config = make_config(tmp_path / "data")
        write_index_lines([NEWER, OLDER, SKIPPED], config.data_dir / "index.jsonl")
        selections = [
            make_selection(NEWER, THRESHOLD, has_transcript=True),
            make_selection(OLDER, TITLE_HIT, has_transcript=False),
            make_selection(SKIPPED, EXCLUDED, has_transcript=True),
        ]

        projection = project([], selections, config)

        assert projection.coverage.considered == projection.videos_selected

    def test_the_flag_is_read_off_the_selections_not_the_disk(self, tmp_path: Path) -> None:
        """`project` is pure over what it is handed, and stays that way.

        Nothing is cached here at all. Re-deriving the figure with `load_cached`
        would report zero, reintroduce the two-measurements problem R1012's
        "the same coverage figure" rules out, and make a pure function touch
        the filesystem.
        """
        config = make_config(tmp_path / "data")
        write_index_lines([NEWER, OLDER], config.data_dir / "index.jsonl")
        selections = [
            make_selection(NEWER, THRESHOLD, has_transcript=True),
            make_selection(OLDER, TITLE_HIT, has_transcript=True),
        ]

        assert project([], selections, config).coverage == Coverage(considered=2, with_transcript=2)

    def test_a_file_on_disk_does_not_override_a_recorded_miss(self, tmp_path: Path) -> None:
        """The other direction of the same rule: the record decides, not the current tree.

        A cache that filled in AFTER `select` ran is precisely BL-27's
        situation — the selections were made without it, and the projection
        describes the selections.
        """
        config = make_config(tmp_path / "data")
        write_index_lines([NEWER, OLDER], config.data_dir / "index.jsonl")
        fetched(config)
        write_transcript(config, "new", (100.0, TEXT_NEW))
        write_transcript(config, "old", (100.0, TEXT_OLD))
        selections = [
            make_selection(NEWER, THRESHOLD, has_transcript=False),
            make_selection(OLDER, TITLE_HIT, has_transcript=False),
        ]

        assert project([], selections, config).coverage == Coverage(considered=2, with_transcript=0)

    def test_no_included_selections_is_zero_of_zero(self, tmp_path: Path) -> None:
        """An empty population is a real result and reports as one (R1005)."""
        config = make_config(tmp_path / "data")
        write_index_lines([SKIPPED], config.data_dir / "index.jsonl")
        selections = [make_selection(SKIPPED, EXCLUDED, has_transcript=True)]

        assert project([], selections, config).coverage == Coverage(considered=0, with_transcript=0)

    def test_nothing_at_all_projects_zero_coverage(self, tmp_path: Path) -> None:
        config = make_config(tmp_path / "data")
        write_index_lines([], config.data_dir / "index.jsonl")

        assert project([], [], config).coverage == Coverage(considered=0, with_transcript=0)


SAMPLE = Projection(
    videos_indexed=123,
    videos_selected=45,
    excerpt_characters=678900,
    bundle_count=7,
    tokens_per_batch=(11, 22, 33, 0),
    total_tokens=66,
    chars_per_token=3.5,
    coverage=Coverage(considered=45, with_transcript=17),
)


class TestRenderProjectionShowsCoverage:
    def test_the_coverage_is_stated_in_this_stage_s_noun(self) -> None:
        """The projection prints the figure itself, in the population it excerpted.

        "pending videos" would be the wrong label here: `select` considered 285
        and this block is about the 45 that were selected.
        """
        text = render_projection(SAMPLE)

        assert f"17 of 45 {SELECTED_NOUN} had a cached transcript" in text

    def test_it_sits_directly_beside_the_character_count(self) -> None:
        """R1012: no projection can be READ without seeing what produced it.

        Adjacent, because that is the line the figure qualifies — a coverage
        number parked at the end of the block is a number the reader meets
        after they have already priced the run.
        """
        text = render_projection(SAMPLE)
        characters = line_index(text, "characters of excerpt text")
        coverage = line_index(text, "had a cached transcript")

        assert abs(characters - coverage) == 1, (
            f"the coverage line must sit beside the character count:\n{text}"
        )

    def test_two_projections_differing_only_in_coverage_render_differently(self) -> None:
        """The figure is really printed, not merely carried."""
        other = replace(SAMPLE, coverage=Coverage(considered=45, with_transcript=45))

        assert render_projection(SAMPLE) != render_projection(other)

    def test_full_coverage_still_prints(self) -> None:
        """On every run, whether or not anything is wrong."""
        text = render_projection(
            replace(SAMPLE, coverage=Coverage(considered=45, with_transcript=45))
        )

        assert f"45 of 45 {SELECTED_NOUN} had a cached transcript" in text


class TestEstimateCommandPrintsCoverage:
    def test_a_normal_run_prints_the_coverage_of_what_it_excerpted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Two included selections, both read — and the excluded one is not in the denominator."""
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"2 of 2 {SELECTED_NOUN} had a cached transcript" in out

    def test_a_partial_cache_prints_its_fraction_and_still_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A partial cache is tolerated exactly as before: R24's per-video rule is untouched."""
        config = build_corpus(tmp_path, cached=("old", "skip"), flagged=("old", "skip"))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"1 of 2 {SELECTED_NOUN} had a cached transcript" in out
        assert bundle_files(config) != []

    def test_no_selections_at_all_prints_zero_of_zero_and_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Emptiness is not absence: nothing selected is a finished run with nothing to price."""
        config = make_config(tmp_path / "data")
        write_index_lines([], config.data_dir / "index.jsonl")
        write_selected([], config.data_dir / "selected.jsonl")
        fetched(config)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"0 of 0 {SELECTED_NOUN} had a cached transcript" in out

    def test_only_excluded_selections_is_not_a_refusal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The population is the INCLUDED selections, so an all-excluded run has an empty one.

        Nothing was excerpted, so there is nothing whose coverage could be
        missing — and a corpus in which no video passed the threshold is a
        result the pipeline must be able to report.
        """
        config = make_config(tmp_path / "data")
        write_index_lines([SKIPPED], config.data_dir / "index.jsonl")
        write_selected(
            [make_selection(SKIPPED, EXCLUDED, has_transcript=False)],
            config.data_dir / "selected.jsonl",
        )
        fetched(config)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"0 of 0 {SELECTED_NOUN} had a cached transcript" in out
        assert "find-best-mobo fetch" not in out


class TestZeroCoverageRefuses:
    def test_it_returns_one_and_names_fetch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Zero coverage over a non-empty included set is an unmet precondition (R1012).

        `fetch` has run — the cache directory exists and holds the excluded
        video's transcript — so the coarser R1005 refusal cannot be what fires
        here. What is missing is any speech behind the numbers about to be
        priced.
        """
        config = build_corpus(tmp_path, cached=("skip",), flagged=("skip",))

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" in out
        assert "Traceback" not in out

    def test_it_does_not_print_the_projection(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A zero-token projection is the artifact BL-27 says must stop existing."""
        config = build_corpus(tmp_path, cached=("skip",), flagged=("skip",))

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "projected tokens" not in out, f"a refusal must not print a projection: {out!r}"

    def test_it_never_prints_the_stop_sentence(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R7's "The pipeline STOPS here" is the checkpoint's success language.

        BL-27's whole finding is that it closed a run which had read nothing,
        and that a warning beside it would annotate the projection rather than
        separate it. So the refusal REPLACES the block: the sentence is absent,
        not merely qualified.
        """
        config = build_corpus(tmp_path, cached=("skip",), flagged=("skip",))

        assert run(config, Namespace()) == 1

        lowered = capsys.readouterr().out.lower()
        assert "stops here" not in lowered
        assert "pipeline stops" not in lowered

    def test_it_writes_no_bundles(self, tmp_path: Path) -> None:
        """The check runs before a single window is cut, so `data/bundles/` is untouched."""
        config = build_corpus(tmp_path, cached=("skip",), flagged=("skip",))

        assert run(config, Namespace()) == 1

        assert not (config.data_dir / "bundles").exists()

    def test_it_leaves_an_earlier_bundle_tree_exactly_as_it_found_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A refused run is not a partial run: nothing is cut, and nothing is cleared."""
        config = build_corpus(tmp_path, cached=("skip",), flagged=("skip",))
        stale = config.data_dir / "bundles" / "batch-1" / "bundle-001.xml"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("<bundle>from an earlier run</bundle>\n", encoding="utf-8")

        assert run(config, Namespace()) == 1
        capsys.readouterr()

        assert stale.read_text(encoding="utf-8") == "<bundle>from an earlier run</bundle>\n"
        assert bundle_files(config) == [stale]

    def test_the_recorded_flag_decides_even_when_the_cache_is_on_disk(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every transcript is cached NOW; none of them was read when these selections were made.

        This is BL-27's ordering, frozen: the cache finished filling twelve
        minutes after `select` wrote the file. The projection describes the
        selections, so the selections are what it must refuse over — and the
        operator's fix is to re-run the stages in order, which the message says
        by naming `fetch`.
        """
        config = build_corpus(tmp_path, cached=("new", "old", "skip"), flagged=())

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" in out
        assert not (config.data_dir / "bundles").exists()

    def test_one_covered_selection_is_enough_to_proceed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The boundary is exactly zero. No coverage FLOOR is introduced here."""
        config = build_corpus(tmp_path, cached=("new", "skip"), flagged=("new", "skip"))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" not in out
        assert f"1 of 2 {SELECTED_NOUN} had a cached transcript" in out


# The pair R1012 names, built from one corpus so the only variable is whether
# the transcripts were ever read. Both videos are title hits with NO mentions:
# nothing to excerpt, nothing to bundle, nothing to spend.
SILENT_A = make_video("quiet-a", "X670E rundown", upload_date=date(2025, 3, 1))
SILENT_B = make_video("quiet-b", "The B650E boards, ranked", upload_date=date(2024, 3, 1))


def build_silent_corpus(tmp_path: Path, *, cached: bool) -> Config:
    """Two included selections with genuinely zero mentions, read or unread.

    `cached=True` is a corpus Buildzoid never named a board in: the captions
    were fetched and they mention nothing. `cached=False` is BL-27's run: the
    same rows, the same empty mention lists, and no speech behind them.
    """
    config = make_config(tmp_path / "data")
    write_index_lines([SILENT_A, SILENT_B], config.data_dir / "index.jsonl")
    write_selected(
        [
            make_selection(SILENT_A, TITLE_HIT, (), has_transcript=cached),
            make_selection(SILENT_B, TITLE_HIT, (), has_transcript=cached),
        ],
        config.data_dir / "selected.jsonl",
    )
    fetched(config)
    if cached:
        write_transcript(config, "quiet-a", (100.0, "he talks about power supplies here"))
        write_transcript(config, "quiet-b", (100.0, "and then about fan curves for a while"))
    return config


class TestTheDistinguishingPair:
    """The two runs BL-27 could not tell apart, and R1012 requires the suite to.

    Identical selections, identical zero mentions, identical zero cost. One of
    them is an answer about the corpus; the other is a run that never read it.
    """

    def test_a_read_corpus_with_no_mentions_still_projects_a_real_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silence that was OBSERVED is a result, and the pipeline reports it (V12).

        Full coverage, no mentions, no excerpts, no bundles, no tokens — and
        the checkpoint reached honestly, so R7's stop sentence belongs here.
        """
        config = build_silent_corpus(tmp_path, cached=True)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"2 of 2 {SELECTED_NOUN} had a cached transcript" in out
        assert "Traceback" not in out
        assert lines_with(out, "token"), f"the projection must be printed: {out!r}"
        assert "stop" in out.lower(), f"a real projection still closes with R7's stop: {out!r}"
        assert bundle_files(config) == []

    def test_the_same_selections_unread_refuse_instead(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The assertion that would have been red on BL-27's measured run.

        Nothing about the rows changed: same videos, same empty mention lists,
        same zero cost. Only the coverage differs, and it is the difference
        between "no board was mentioned" and "no speech was read".
        """
        config = build_silent_corpus(tmp_path, cached=False)

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" in out
        assert "projected tokens" not in out
        assert "stops here" not in out.lower()
        assert not (config.data_dir / "bundles").exists()

    def test_the_two_runs_do_not_print_the_same_thing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BL-27's measurement in one line: the failing run and the finished one were comparable.

        They are the same corpus at the console — same counts, same zero — so
        an operator returning to the output had no signal at all. After R1012
        they cannot read alike.
        """
        read = build_silent_corpus(tmp_path / "read", cached=True)
        unread = build_silent_corpus(tmp_path / "unread", cached=False)

        assert run(read, Namespace()) == 0
        finished = capsys.readouterr().out
        assert run(unread, Namespace()) == 1
        refused = capsys.readouterr().out

        assert finished != refused
        assert finished.strip() != ""
        assert refused.strip() != ""
