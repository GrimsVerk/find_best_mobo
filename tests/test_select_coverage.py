"""Transcript coverage at `select` — the figure, and the zero-coverage refusal.

Written blind from `docs/plans/oracle/transcript-coverage-guard.md` (slice 1)
while the implementation is authored in parallel, so failing imports and
`TypeError`s on the new field are the expected state until assembly.

The rule is **R1012** (OD-23): every stage that reads the transcript cache
reports how many of the videos it considered had a cached transcript to read,
printed on every run whether or not anything is wrong, and refuses when that
count is zero over a non-empty population. **BL-27** measured the run this
exists to make impossible — `select` ran twelve minutes before `fetch` finished
writing `data/transcripts/`, wrote 285 rows carrying no mentions at all, and
printed nothing unusual.

Two things these tests are careful about, because they are the two ways an
implementation can look right and be wrong:

- **`has_transcript` records the CACHE HIT, never the mention count.** A cached
  transcript in which no board is named is a real result — silence that was
  actually observed — and must read as coverage. Inferring the flag from
  `mentions` would report BL-27's dead run as a full-coverage one.
- **The population is the PENDING videos**, which is what `select_all` returns:
  not the index rows, and not the included selections. The corpus below carries
  a cached, non-pending video precisely so a denominator taken from the index
  file is a different number and fails.
"""

from __future__ import annotations

import json
import re
from argparse import Namespace
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.aliases import Alias, Mention
from find_best_mobo.commands.select import run
from find_best_mobo.config import Config
from find_best_mobo.index import Video
from find_best_mobo.select import (
    Coverage,
    Selection,
    read_selected,
    render_coverage,
    select_all,
    transcript_coverage,
    write_selected,
)
from find_best_mobo.transcripts import Cue, Transcript, cache_path

STANDARD_TABLE: tuple[Alias, ...] = (
    Alias(canonical="X670E", kind="chipset", surface_forms=("x670e", "x 670 e")),
    Alias(canonical="B650E", kind="chipset", surface_forms=("b650e", "b 650 e")),
    Alias(canonical="A620", kind="chipset", surface_forms=("a620", "a 620")),
    Alias(canonical="Taichi", kind="family", surface_forms=("taichi",)),
)

TITLE_HIT = "title_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"

# The noun slice 1 counts in. The two stages count different populations, which
# is why `render_coverage` takes the word rather than owning it.
PENDING_NOUN = "pending videos"


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
        alias_table_path=data_dir / "aliases.toml",
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


def make_mention(canonical: str, video_id: str = "vid", start: float = 0.0) -> Mention:
    return Mention(
        video_id=video_id,
        canonical=canonical,
        start_seconds=start,
        matched_form=canonical.lower(),
    )


def make_selection(
    video_id: str,
    reason: str,
    *,
    has_transcript: bool,
    canonicals: Sequence[str] = (),
) -> Selection:
    """A selection whose coverage flag and mention list are set independently.

    They are separate arguments on purpose: every test that matters here is
    about a case where the two disagree.
    """
    mentions = tuple(
        make_mention(canonical, video_id, float(index))
        for index, canonical in enumerate(canonicals)
    )
    return Selection(
        video=make_video(video_id),
        reason=reason,
        mentions=mentions,
        distinct_canonicals=len({mention.canonical for mention in mentions}),
        has_transcript=has_transcript,
    )


def write_aliases(path: Path, aliases: Sequence[Alias] = STANDARD_TABLE) -> Path:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for video in videos:
        record = asdict(video)
        record["upload_date"] = video.upload_date.isoformat()
        lines.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def fetched(config: Config) -> Path:
    """Leave the empty cache directory a `fetch` run leaves, and return it.

    R1005 separates "fetch has not run" (no directory) from "fetch ran and
    cached nothing" (a directory, no files). Every corpus here is about the
    SECOND state, so every one of them creates the directory: without it the
    older, coarser refusal fires first and these tests would pass while proving
    nothing about coverage.
    """
    cache_dir = config.data_dir / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def write_transcript(config: Config, video_id: str, *cues: tuple[float, str]) -> Path:
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
    return path


def lines_with(output: str, token: str) -> list[str]:
    return [line for line in output.splitlines() if token.lower() in line.lower()]


# Filesystem paths are incidental text, not the report's vocabulary: pytest's
# temp directory is named after the run counter and the test, so a bare number
# search over a line carrying a path finds numbers nobody printed.
_PATH = re.compile(r"\S*/\S*")


def without_paths(line: str) -> str:
    return _PATH.sub(" ", line)


def has_number(line: str, value: int) -> bool:
    return re.search(rf"(?<![\d.]){value}(?![\d.])", without_paths(line)) is not None


# The four pending videos, and what each one says. "hit" is cached with NO cues
# at all — a real cache hit that is indistinguishable from the empty stand-in
# unless the flag is set where the substitution happens.
PENDING: tuple[str, ...] = ("hit", "pass", "quiet", "bare")
TITLES = {
    "hit": "X670E rundown",
    "pass": "Deep dive one",
    "quiet": "Deep dive two",
    "bare": "Deep dive three",
}
BODIES: dict[str, tuple[tuple[float, str], ...]] = {
    "hit": (),
    "pass": ((1.0, "x670e b650e a620"),),
    "quiet": ((1.0, "he talks about power supplies"),),
    "bare": ((1.0, "x670e b650e a620"),),
}

# The default corpus: four pending videos, three of them cached.
CORPUS_PENDING = 4
CORPUS_CACHED = 3
DEFAULT_CACHED: tuple[str, ...] = ("hit", "pass", "quiet")


def build_corpus(tmp_path: Path, *, cached: Sequence[str] = DEFAULT_CACHED) -> Config:
    """Four pending videos plus one that is not pending, and cached at will.

    Every number a test below asserts is countable from `cached`: the
    denominator is always 4, and the numerator is `len(cached)`. The fifth
    video — a short, so never pending — is ALWAYS cached, so an implementation
    that counted index rows instead of the pending set reports 5 as its
    denominator and every test here fails rather than one of them.
    """
    config = make_config(tmp_path / "data", mention_threshold=3)
    write_aliases(config.alias_table_path)
    videos = [make_video(video_id, TITLES[video_id]) for video_id in PENDING]
    videos.append(make_video("shortie", "X670E in sixty seconds", inclusion="excluded_short"))
    write_index_lines(videos, config.data_dir / "index.jsonl")
    fetched(config)
    for video_id in cached:
        write_transcript(config, video_id, *BODIES[video_id])
    write_transcript(config, "shortie", (1.0, "x670e b650e a620"))
    return config


def flags(config: Config) -> dict[str, bool]:
    return {s.video.video_id: s.has_transcript for s in select_all(config)}


class TestSelectionCarriesTheFlag:
    def test_the_flag_is_part_of_the_record(self) -> None:
        """R1012's datum is written once and read twice, so it is a FIELD.

        The plan's alternative — each stage calling `load_cached` and counting
        for itself — satisfies "report coverage" and quietly breaks "the same
        coverage figure", because the two stages count different populations.
        """
        selection = make_selection("vid", THRESHOLD, has_transcript=True)

        assert selection.has_transcript is True

    def test_two_selections_differing_only_in_the_flag_are_not_equal(self) -> None:
        """The flag is data, not a display detail: it survives comparison, and the file."""
        covered = make_selection("vid", THRESHOLD, has_transcript=True)
        missed = make_selection("vid", THRESHOLD, has_transcript=False)

        assert covered != missed

    def test_the_flag_has_no_default(self) -> None:
        """Nobody may construct a `Selection` without saying whether it was read.

        A default silently answers R1012's question for every caller that
        forgets it, and the answer would be wrong for exactly the population
        BL-27 measured. Making it required is what forces the one place that
        knows — where `select_all` substitutes the empty stand-in — to say so.
        """
        with pytest.raises(TypeError):
            Selection(  # type: ignore[call-arg]
                video=make_video("vid"),
                reason=THRESHOLD,
                mentions=(),
                distinct_canonicals=0,
            )


class TestTranscriptCoverage:
    def test_it_counts_the_flag_over_the_selections_it_is_handed(self) -> None:
        """The whole function: how many of these were actually read."""
        selections = [
            make_selection("a", TITLE_HIT, has_transcript=True),
            make_selection("b", THRESHOLD, has_transcript=True, canonicals=("X670E", "B650E")),
            make_selection("c", EXCLUDED, has_transcript=True),
            make_selection("d", EXCLUDED, has_transcript=False),
        ]

        assert transcript_coverage(selections) == Coverage(considered=4, with_transcript=3)

    def test_no_selections_at_all_is_zero_of_zero(self) -> None:
        """An empty population is a real corpus fact, and this function reports it as one.

        R1005's line between absence and emptiness, applied to the population:
        a channel with nothing in range is not a broken run, so the zero must
        be a value here rather than a signal.
        """
        assert transcript_coverage(()) == Coverage(considered=0, with_transcript=0)

    def test_a_full_cache_covers_everything_it_considered(self) -> None:
        selections = [
            make_selection(f"v{index}", THRESHOLD, has_transcript=True) for index in range(3)
        ]

        assert transcript_coverage(selections) == Coverage(considered=3, with_transcript=3)

    def test_a_cached_transcript_that_names_no_board_is_coverage(self) -> None:
        """The pin that R1012 turns on: coverage is the CACHE HIT, not the mention count.

        BL-27's 285 rows all carried `"mentions":[]`. So does a corpus in which
        Buildzoid genuinely never named a board — and V12 is that those two
        must not read the same. A count taken from `mentions` reports the dead
        run as full coverage and the honest run as zero.
        """
        selections = [
            make_selection("a", EXCLUDED, has_transcript=True),
            make_selection("b", EXCLUDED, has_transcript=True),
        ]

        assert transcript_coverage(selections) == Coverage(considered=2, with_transcript=2)

    def test_mentions_without_a_cache_hit_are_not_coverage(self) -> None:
        """The converse guard: the flag decides, in both directions."""
        selections = [
            make_selection("a", THRESHOLD, has_transcript=False, canonicals=("X670E", "B650E")),
        ]

        assert transcript_coverage(selections) == Coverage(considered=1, with_transcript=0)

    def test_every_selection_counts_whatever_its_reason(self) -> None:
        """The function counts what it is handed; the CALLER chooses the population.

        `select` hands it every pending video and `estimate` hands it the
        included ones — a filter built into this function would make one of
        those two figures a lie about the line it sits beside.
        """
        selections = [
            make_selection("a", EXCLUDED, has_transcript=True),
            make_selection("b", EXCLUDED, has_transcript=False),
        ]

        assert transcript_coverage(selections).considered == 2

    def test_it_accepts_a_tuple(self) -> None:
        selections = (make_selection("a", THRESHOLD, has_transcript=True),)

        assert transcript_coverage(selections) == Coverage(considered=1, with_transcript=1)


class TestRenderCoverage:
    def test_the_rendered_shape_is_the_one_the_plan_states(self) -> None:
        """BL-27's own numbers, in the sentence the plan spells out.

        A figure printed on every run is only comparable across runs if its
        wording is fixed, so the shape is pinned rather than sniffed for.
        """
        text = render_coverage(Coverage(considered=285, with_transcript=189), PENDING_NOUN)

        assert text == "189 of 285 pending videos had a cached transcript"

    def test_the_covered_count_comes_first(self) -> None:
        """ "2 of 5" and "5 of 2" are the same characters and opposite claims."""
        text = render_coverage(Coverage(considered=5, with_transcript=2), PENDING_NOUN)

        assert text.startswith("2 of 5")

    def test_the_noun_is_the_caller_s(self) -> None:
        """Both stages share the renderer, and they count different populations.

        A hard-coded noun would print "pending videos" beside `estimate`'s
        character count, which is measured over the SELECTED ones.
        """
        coverage = Coverage(considered=9, with_transcript=4)

        assert PENDING_NOUN in render_coverage(coverage, PENDING_NOUN)
        assert "selected videos" in render_coverage(coverage, "selected videos")
        assert render_coverage(coverage, PENDING_NOUN) != render_coverage(
            coverage, "selected videos"
        )

    def test_zero_of_zero_renders_as_a_figure_not_an_absence(self) -> None:
        """An empty population still prints, because a run that skips the line is a run nobody can compare."""
        text = render_coverage(Coverage(considered=0, with_transcript=0), PENDING_NOUN)

        assert text == "0 of 0 pending videos had a cached transcript"

    def test_zero_coverage_over_a_real_population_still_renders(self) -> None:
        """The shape BL-27 would have printed, had anything printed it."""
        text = render_coverage(Coverage(considered=285, with_transcript=0), PENDING_NOUN)

        assert text == "0 of 285 pending videos had a cached transcript"


class TestSelectAllRecordsTheCacheHit:
    def test_the_flag_follows_the_cache_file(self, tmp_path: Path) -> None:
        config = build_corpus(tmp_path)

        assert flags(config) == {"hit": True, "pass": True, "quiet": True, "bare": False}

    def test_a_cached_transcript_naming_no_board_is_coverage_not_a_miss(
        self, tmp_path: Path
    ) -> None:
        """ "He said nothing about boards" and "we read nothing" are different facts (V12).

        `quiet` is cached, was read, and mentions no board: it is excluded from
        the corpus and still counts as coverage. This is the assertion that
        fails if the flag is inferred from `mentions` or from the reason.
        """
        config = build_corpus(tmp_path)

        (quiet,) = [s for s in select_all(config) if s.video.video_id == "quiet"]

        assert quiet.reason == EXCLUDED
        assert quiet.mentions == ()
        assert quiet.has_transcript is True

    def test_a_cached_transcript_with_no_cues_is_still_a_cache_hit(self, tmp_path: Path) -> None:
        """The empty CACHED transcript and the empty stand-in are the same value.

        Only the line that substitutes one for the other can tell them apart,
        which is why the plan sets the flag there and passes it into
        `select_video` rather than deriving it from the transcript.
        """
        config = build_corpus(tmp_path)

        (hit,) = [s for s in select_all(config) if s.video.video_id == "hit"]

        assert hit.reason == TITLE_HIT
        assert hit.mentions == ()
        assert hit.has_transcript is True

    def test_an_included_video_without_a_cache_file_is_not_coverage(self, tmp_path: Path) -> None:
        """Being selected says nothing about having been read: a title hit needs no captions."""
        config = make_config(tmp_path / "data")
        write_aliases(config.alias_table_path)
        write_index_lines([make_video("solo", "X670E rundown")], config.data_dir / "index.jsonl")
        fetched(config)

        (selection,) = select_all(config)

        assert selection.reason == TITLE_HIT
        assert selection.has_transcript is False

    def test_the_coverage_of_the_corpus_is_the_pending_figure(self, tmp_path: Path) -> None:
        """Denominator = the pending videos, not the index rows: `shortie` is cached and uncounted."""
        config = build_corpus(tmp_path)

        coverage = transcript_coverage(select_all(config))

        assert coverage == Coverage(considered=CORPUS_PENDING, with_transcript=CORPUS_CACHED)

    def test_an_empty_cache_directory_is_zero_coverage_over_a_real_population(
        self, tmp_path: Path
    ) -> None:
        """BL-27's state, at the library level: `fetch` has run and cached nothing yet.

        The library still returns selections — the refusal is `commands/`'s
        decision, not this function's — but every flag is false, which is what
        makes the refusal computable one layer up.
        """
        config = build_corpus(tmp_path, cached=())

        selections = select_all(config)

        assert transcript_coverage(selections) == Coverage(
            considered=CORPUS_PENDING, with_transcript=0
        )
        assert len(selections) == CORPUS_PENDING


class TestSelectedFileCarriesTheFlag:
    def test_the_flag_survives_the_round_trip(self, tmp_path: Path) -> None:
        """The fact is durable, not a console line: `estimate` reads it back off disk."""
        path = tmp_path / "selected.jsonl"
        selections = (
            make_selection("a", TITLE_HIT, has_transcript=True),
            make_selection("b", EXCLUDED, has_transcript=False),
        )

        write_selected(selections, path)

        assert tuple(read_selected(path)) == selections

    def test_the_record_carries_the_key_as_a_boolean(self, tmp_path: Path) -> None:
        """One additive key, and a real JSON boolean rather than 0/1 or a string."""
        path = tmp_path / "selected.jsonl"
        write_selected((make_selection("a", THRESHOLD, has_transcript=True),), path)

        record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        assert record["has_transcript"] is True

    def test_two_writes_of_the_same_input_are_byte_identical(self, tmp_path: Path) -> None:
        """R23 with one more key present: keys stay sorted inside each record."""
        selections = (
            make_selection("b", THRESHOLD, has_transcript=True, canonicals=("X670E",)),
            make_selection("a", EXCLUDED, has_transcript=False),
        )
        first = tmp_path / "first.jsonl"
        second = tmp_path / "second.jsonl"

        write_selected(selections, first)
        write_selected(selections, second)

        assert first.read_bytes() == second.read_bytes()

    def test_the_coverage_read_back_is_the_coverage_written(self, tmp_path: Path) -> None:
        """`estimate` must be able to state the SAME figure, which means reading it, not redoing it."""
        config = build_corpus(tmp_path)
        path = config.data_dir / "selected.jsonl"
        selections = select_all(config)

        write_selected(selections, path)

        assert transcript_coverage(list(read_selected(path))) == transcript_coverage(selections)


class TestSelectCommandPrintsCoverage:
    def test_a_normal_run_prints_the_coverage_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The figure BL-27's run never printed, in the words the plan gives it."""
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"{CORPUS_CACHED} of {CORPUS_PENDING} {PENDING_NOUN} had a cached transcript" in out

    def test_it_prints_when_nothing_is_wrong_at_all(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A number that appears only on failure is a number nobody can compare across runs.

        That is why BL-27's collapse was invisible: nothing routine reported the
        quantity that had changed.
        """
        config = build_corpus(tmp_path, cached=PENDING)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"{CORPUS_PENDING} of {CORPUS_PENDING} {PENDING_NOUN} had a cached transcript" in out

    def test_a_partial_cache_prints_its_fraction_and_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A partial cache is never an error — R24's per-video tolerance is untouched."""
        config = build_corpus(tmp_path, cached=("pass",))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"1 of {CORPUS_PENDING} {PENDING_NOUN} had a cached transcript" in out
        assert (config.data_dir / "selected.jsonl").exists()

    def test_zero_pending_videos_prints_zero_of_zero_and_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An empty population is a result, not an unmet precondition (R1005).

        A channel with nothing in the date range legitimately produces this,
        and the coverage line still prints — the run reports itself either way.
        """
        config = make_config(tmp_path / "data")
        write_aliases(config.alias_table_path)
        write_index_lines(
            [
                make_video("s1", "X670E in sixty seconds", inclusion="excluded_short"),
                make_video("o1", "X670E from before", inclusion="excluded_out_of_range"),
            ],
            config.data_dir / "index.jsonl",
        )
        fetched(config)

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"0 of 0 {PENDING_NOUN} had a cached transcript" in out
        assert (config.data_dir / "selected.jsonl").exists()

    def test_the_flag_reaches_the_written_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The console line and `data/selected.jsonl` state the same fact, per video."""
        config = build_corpus(tmp_path)

        assert run(config, Namespace()) == 0
        capsys.readouterr()

        restored = {
            s.video.video_id: s.has_transcript
            for s in read_selected(config.data_dir / "selected.jsonl")
        }
        assert restored == {"hit": True, "pass": True, "quiet": True, "bare": False}


class TestZeroCoverageRefuses:
    def test_a_pending_population_with_no_cache_at_all_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BL-27 exactly: `fetch` has run, cached nothing yet, and `select` reads no speech.

        Zero coverage over a non-empty population is an unmet precondition
        rather than a result (R1012), so it exits non-zero and names the stage
        that produces the missing input, in R1005's shape.
        """
        config = build_corpus(tmp_path, cached=())

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" in out
        assert "Traceback" not in out

    def test_the_refusal_says_the_population_it_measured(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ "No transcripts" is unactionable; "none of 4 pending videos" is a measurement."""
        config = build_corpus(tmp_path, cached=())

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert any(has_number(line, CORPUS_PENDING) for line in lines_with(out, "transcript")), (
            f"the refusal must state the population it measured: {out!r}"
        )

    def test_the_refusal_writes_no_selections(self, tmp_path: Path) -> None:
        """A refused run leaves the tree as it found it — no half-answer for the next stage."""
        config = build_corpus(tmp_path, cached=())

        assert run(config, Namespace()) == 1

        assert not (config.data_dir / "selected.jsonl").exists()

    def test_the_refusal_leaves_an_existing_selected_file_untouched(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It refuses BEFORE writing, so a stale artifact is not replaced by a worse one."""
        config = build_corpus(tmp_path, cached=())
        path = config.data_dir / "selected.jsonl"
        write_selected((make_selection("earlier", THRESHOLD, has_transcript=True),), path)
        before = path.read_bytes()

        assert run(config, Namespace()) == 1
        capsys.readouterr()

        assert path.read_bytes() == before

    def test_the_refusal_replaces_the_report_rather_than_annotating_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A warning beside a threshold report annotates it; it does not separate it.

        The report would be a measurement of the missing corpus presented as a
        measurement of the lever — which is what BL-27 measured happening.
        """
        config = build_corpus(tmp_path, cached=())

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "Threshold in force" not in out

    def test_a_title_hit_does_not_rescue_a_zero_coverage_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BL-27's run "selected" 109 videos and had still read nothing.

        Title hits need no captions, so a corpus can select plenty of videos at
        zero coverage. The refusal is conditioned on coverage, never on how
        many videos came out the other end.
        """
        config = make_config(tmp_path / "data")
        write_aliases(config.alias_table_path)
        write_index_lines(
            [make_video("t1", "X670E rundown"), make_video("t2", "The B650E boards, ranked")],
            config.data_dir / "index.jsonl",
        )
        fetched(config)

        assert run(config, Namespace()) == 1

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" in out
        assert not (config.data_dir / "selected.jsonl").exists()

    def test_one_cached_transcript_is_enough_to_proceed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The boundary is exactly zero: no coverage FLOOR is being introduced here.

        Refusing below some fraction would put a number on how much of the
        corpus a projection may be missing, and R1012 does not ask for one.
        """
        config = build_corpus(tmp_path, cached=("quiet",))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert "find-best-mobo fetch" not in out
        assert (config.data_dir / "selected.jsonl").exists()

    def test_a_cached_transcript_that_mentions_nothing_is_not_a_refusal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The honest side of the pair, at `select`: read everything, found nothing.

        Every pending video is cached and only one of them names a board. The
        corpus is nearly silent and the run is finished — coverage is full, so
        there is nothing to refuse.
        """
        config = build_corpus(tmp_path, cached=("hit", "quiet"))
        write_transcript(config, "pass", (1.0, "he talks about power supplies"))
        write_transcript(config, "bare", (1.0, "and then about fan curves"))

        assert run(config, Namespace()) == 0

        out = capsys.readouterr().out
        assert f"{CORPUS_PENDING} of {CORPUS_PENDING} {PENDING_NOUN} had a cached transcript" in out
        assert "find-best-mobo fetch" not in out
