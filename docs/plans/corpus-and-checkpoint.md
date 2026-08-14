---
slug: corpus-and-checkpoint
status: draft              # draft | in-flight | merged
created: 2026-08-14
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1, R2, R3, R4, R5, R6, R7, R17, R18, R20, R21, R22, R23, R24]
---

# Corpus and the cost checkpoint — Plan

Implements the MVP milestone of `docs/DESIGN.md`: everything from enumerating
the channel to printing a cost projection, with no model invoked at any point.
The milestone ends at the checkpoint by design — the pipeline has no code path
that continues into inference, which is what makes the stop structural rather
than a promise.

## Uncertainties

Asked at plan scope before any slice was written; rulings recorded as given.

- **Q:** How should the milestone be cut into vertical slices? — **proposed:**
  four slices (index / fetch / select / estimate).
  **Ruling:** five slices — normalization and the alias table get their own
  slice, because that is where the recall risk lives and it deserves its own
  checkpoint.
- **Q:** How should the corpus distinguish a real long-form video from a
  livestream, given that his normal uploads routinely run 40–90 minutes and
  some deep dives exceed two hours? — **proposed:** trust `yt-dlp`'s live flag
  only, exclude Shorts under ~2 minutes, no duration ceiling.
  **Ruling:** include livestreams too. Only Shorts are excluded. Maximum recall;
  the cost consequence is measured at the checkpoint rather than guessed at now.
- **Q:** What format should the work bundles take? — **proposed:** markdown, one
  file per bundle.
  **Ruling:** XML. The agent corrected the premise — XML tags are the
  recommended structure for Claude prompts because tagged boundaries are
  attended to reliably, *not* because they are cheaper (closing tags cost more
  tokens than markdown headings). Settled shape: XML tags as the structure,
  plain prose inside them.
- **Q:** Should the code call `yt-dlp` as a subprocess or import it as a
  library? — **proposed:** subprocess with JSON output.
  **Ruling:** library. The owner's reasoning (local execution) was accepted with
  a correction: process startup is negligible, but reusing one client across
  ~1000 videos avoids standing up fresh HTTP state per video. Isolated behind
  one module either way.
- **Q:** Program design decisions the design doc does not settle. — **proposed
  and accepted without objection:** stdlib `argparse`; a `config.toml` at the
  repository root holding every R17 lever with defaults in code; the alias table
  as a data file rather than Python; `data/` gitignored so the cache never
  enters git; JSONL for the index; chars÷4 as the starting token factor.

**Raised later, when slice 2 was about to be built** (2026-08-14). The slice as
written had no legal home for the caption download: `ytdlp.py` is the only
module permitted to import yt-dlp, and it was not in slice 2's file list, so
the fetch had nowhere to live and — worse — the blind test author had no
declared surface to fake. That is the exact failure slice 1's signature block
was written to prevent, reproduced one slice later. Proposals, for the owner's
ruling as this revision merges:

- **Q:** Where does the caption download live? — **proposed:** a second boundary
  function `fetch_caption_track` in `ytdlp.py`, declared in the signatures
  below, with `ytdlp.py` added to slice 2's file list and the estimate raised
  from ~420 to ~460 lines. The alternative — importing yt-dlp inside
  `transcripts.py` — would break the single-network-boundary rule that makes the
  suite's offline guarantee checkable at one place.
- **Q:** How is "this video has no captions" distinguished from "reaching
  YouTube failed"? — **proposed:** the boundary returns `None` for a video with
  no caption track and raises for anything else. The two are different outcomes
  in the design's failure ledger (`no_captions` vs `fetch_error`), and a
  boundary that folded them together would make that distinction guesswork
  upstream.
- **Q:** Does `fetch_transcript` read and write the cache, or does `fetch_all`?
  — **proposed:** `fetch_all` owns the cache entirely. Splitting it leaves
  "retry only what failed" spread across two functions with no single place to
  check it.

**One design decision made here, not in the design doc.** Each subcommand lives
in its own module under `commands/`, and the CLI dispatches by importing the
module named after the subcommand. This exists so that no two slices touch the
same file: a single `cli.py` carrying a hand-maintained subcommand table would
be edited by all five slices, which breaks parallel authorship. `config.py`
declares every lever up front in slice 1 for the same reason — later slices read
it and never edit it.

## The work, sliced

<!-- This heading deliberately does not begin with the word "Slice".
`.github/scripts/plan-parse.sh` treats every heading matching `^#+\s*Slice` as a
slice, so a bare `## Slices` section header is parsed as a slice that declares
no files and no estimate, and the whole plan fails to parse — which empties the
reviewer's facts table and blocks the pull request. `docs/plans/_TEMPLATE.md`
carried the same defect and is fixed in the same pull request; the underlying
parser behaviour is logged in `docs/escapes.md`, and the fix to the parser
itself is the owner's, since it is a gate path. -->


## Slice 1 — The channel becomes a video index on disk

- **Delivers:** `uv run find-best-mobo index` enumerates every upload on the
  channel from 2023-01-01 to today and writes `data/index.jsonl`, one record per
  video, each carrying its classification and the reason it was included or
  excluded. Prints a summary: total found, Shorts excluded, kept. Covers R1,
  R18, R22, R23; establishes the config and CLI that every later slice uses.
- **Files:** `src/find_best_mobo/config.py`, `src/find_best_mobo/cli.py`,
  `src/find_best_mobo/ytdlp.py`, `src/find_best_mobo/index.py`,
  `src/find_best_mobo/commands/__init__.py`,
  `src/find_best_mobo/commands/index.py`, `config.toml`, `.gitignore`,
  `tests/test_config.py`, `tests/test_index.py`,
  `tests/fixtures/channel_entries.json`
- **Estimate:** ~380 lines

### Signatures

```python
@dataclass(frozen=True)
class Config:
    channel_url: str
    start_date: date
    data_dir: Path
    shorts_max_seconds: int
    mention_threshold: int
    window_before_seconds: int
    window_after_seconds: int
    per_video_excerpt_cap: int
    bundle_token_cap: int
    calibration_batch_size: int
    batch_count: int
    chars_per_token: float
    consecutive_fetch_error_limit: int
    fetch_error_rate_limit: float
    missing_caption_rate_limit: float


def load_config(path: Path) -> Config: ...


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    upload_date: date
    duration_seconds: int
    was_live: bool
    classification: str  # "regular" | "short"
    inclusion: str  # "pending" | "excluded_short" | "excluded_out_of_range"


def classify(entry: dict[str, object], config: Config) -> Video: ...
def enumerate_channel(config: Config) -> Iterator[Video]: ...
def write_index(videos: Iterable[Video], path: Path) -> int: ...
def read_index(path: Path) -> Iterator[Video]: ...


def main(argv: Sequence[str] | None = None) -> int: ...
def run(config: Config, args: Namespace) -> int: ...


# The network boundary. This is the only module that imports yt-dlp, and the
# only surface a test may fake — declared here because a test author who has to
# guess at it fakes one level deeper and the two sides then disagree at the
# seam rather than on behaviour.
def list_channel_entries(channel_url: str, start_date: date) -> Iterator[dict[str, object]]: ...
```

**Two rules the signatures cannot carry, settled here after both slice-1 workers
resolved them differently:**

- **A Short uploaded before the start date is excluded as a Short.**
  `classification="short"` and `inclusion="excluded_short"` win over
  `excluded_out_of_range`, because the slice ties that classification and
  inclusion pair together unconditionally. Check the duration before the date.
- **At most one video may report a zero duration.** A missing duration is read
  as 0, which classifies as a Short and therefore excludes the video. That is
  acceptable for exactly one video — a stream in progress reports no duration,
  and he can only be live in one place at a time. Two or more zero-duration
  videos mean the zero is caused by something other than being live, and videos
  are being dropped silently. The `index` command must therefore report the
  zero-duration count in its summary, and warn loudly when it exceeds one,
  naming the affected video ids so the cause can be found.
- **Flat channel listing carries no upload date.** `yt-dlp`'s flat playlist
  entries omit `upload_date` unless the `youtubetab:approximate_date` extractor
  argument is set, so a naive implementation classifies the entire channel as
  out-of-range and yields an empty corpus. `list_channel_entries` must set it,
  and the resulting dates are approximate — which `docs/architecture.md` records
  as a known rough edge, since it means a video near the 2023-01-01 boundary may
  fall on either side of it.

## Slice 2 — Transcripts land in a local cache, and gaps are visible

- **Delivers:** `uv run find-best-mobo fetch` downloads and caches every indexed
  video's caption track under `data/transcripts/`, retrying only previously
  failed videos on a rerun. Every failure is written to `data/failures.jsonl`
  with its class. The run halts and prints the ledger when either trigger fires.
  Covers R2, R24, R21, R22.
- **Files:** `src/find_best_mobo/transcripts.py`,
  `src/find_best_mobo/ledger.py`, `src/find_best_mobo/commands/fetch.py`,
  `src/find_best_mobo/ytdlp.py`, `tests/test_transcripts.py`,
  `tests/test_ledger.py`, `tests/fixtures/captions_vtt.txt`
- **Estimate:** ~460 lines

### Signatures

```python
@dataclass(frozen=True)
class Cue:
    start_seconds: float
    text: str


@dataclass(frozen=True)
class Transcript:
    video_id: str
    cues: tuple[Cue, ...]


@dataclass(frozen=True)
class FetchFailure:
    video_id: str
    title: str
    upload_date: date
    failure_class: str  # "no_captions" | "fetch_error"
    detail: str
    attempts: int


class HaltTriggered(Exception):
    def __init__(self, trigger: str, ledger: Sequence[FetchFailure]) -> None: ...


class Ledger:
    def __init__(self, path: Path, config: Config, indexed_count: int) -> None: ...
    def record(self, failure: FetchFailure) -> None: ...
    def record_success(self) -> None: ...
    def check_triggers(self) -> str | None: ...
    def failures(self) -> tuple[FetchFailure, ...]: ...
    def failed_ids(self) -> frozenset[str]: ...


def parse_vtt(raw: str) -> tuple[Cue, ...]: ...
def cache_path(video_id: str, config: Config) -> Path: ...
def load_cached(video_id: str, config: Config) -> Transcript | None: ...
def fetch_transcript(video: Video, config: Config) -> Transcript: ...
def fetch_all(videos: Iterable[Video], config: Config, ledger: Ledger) -> int: ...


# The network boundary for captions, added to `ytdlp.py` beside
# `list_channel_entries` — that module is the only one that imports yt-dlp, and
# this slice must not be the exception. It is the ONLY surface a test may fake
# for this slice, declared here for the same reason slice 1 declared its
# boundary: a test author who has to guess fakes one level deeper, and the two
# blind authors then disagree at the seam instead of on behaviour.
#
# Returns the raw caption track as WebVTT text. Returns None when the video has
# no caption track at all — an ordinary outcome that the ledger classes as
# "no_captions", not an error. Anything that goes wrong reaching YouTube raises,
# and the caller classes it "fetch_error".
def fetch_caption_track(video_id: str, config: Config) -> str | None: ...
```

**Two behaviours the signatures cannot carry:**

- **`fetch_transcript` never consults the cache and never writes it.** It
  fetches, parses, and returns. `fetch_all` owns the cache: it checks
  `load_cached` first, calls `fetch_transcript` only on a miss, and writes the
  result. Keeping the decision in one place is what makes "retry only previously
  failed videos on a rerun" a property of one function rather than an emergent
  one.
- **A halt raises `HaltTriggered` out of `fetch_all`, after the ledger has been
  written to disk.** The command catches it, prints the ledger, and returns a
  non-zero exit code. A halt is a deliberate stop with its evidence saved, not a
  crash — everything fetched before it stays cached, and a rerun resumes.

## Slice 3 — Mangled caption text folds onto real model names

- **Delivers:** `uv run find-best-mobo aliases --check` reports, for every
  canonical entity in `data/aliases.toml`, how many videos mention it and which
  surface forms matched — so the alias table's recall can be inspected by hand
  before it silently decides the corpus. Normalization collapses the spacing
  damage auto-captions inflict on part numbers. Covers R3.
- **Files:** `src/find_best_mobo/normalize.py`, `src/find_best_mobo/aliases.py`,
  `data/aliases.toml`, `src/find_best_mobo/commands/aliases.py`,
  `tests/test_normalize.py`, `tests/test_aliases.py`
- **Estimate:** ~340 lines

### Signatures

```python
@dataclass(frozen=True)
class Alias:
    canonical: str
    kind: str  # "board" | "family" | "chipset" | "cpu" | "vendor"
    surface_forms: tuple[str, ...]


@dataclass(frozen=True)
class Mention:
    video_id: str
    canonical: str
    start_seconds: float
    matched_form: str


def normalize(text: str) -> str: ...
def load_aliases(path: Path) -> tuple[Alias, ...]: ...
def compile_matcher(aliases: Sequence[Alias]) -> Pattern[str]: ...
def find_mentions(transcript: Transcript, matcher: Pattern[str]) -> tuple[Mention, ...]: ...
def find_title_hits(video: Video, matcher: Pattern[str]) -> frozenset[str]: ...
```

## Slice 4 — The corpus narrows to the videos actually about AM5 boards

- **Delivers:** `uv run find-best-mobo select` writes `data/selected.jsonl` and
  prints the threshold's effect: how many videos came in on a title hit, how
  many on the mention count, how many were excluded, and what raising or
  lowering the threshold by one would change. Covers R4, R17.
- **Files:** `src/find_best_mobo/select.py`,
  `src/find_best_mobo/commands/select.py`, `tests/test_select.py`
- **Estimate:** ~280 lines

### Signatures

```python
@dataclass(frozen=True)
class Selection:
    video: Video
    reason: str  # "title_hit" | "threshold" | "excluded_below_threshold"
    mentions: tuple[Mention, ...]
    distinct_canonicals: int


@dataclass(frozen=True)
class ThresholdReport:
    threshold: int
    title_hits: int
    threshold_passes: int
    excluded: int
    would_include_at_minus_one: int
    would_exclude_at_plus_one: int


def select_video(
    video: Video, transcript: Transcript, matcher: Pattern[str], config: Config
) -> Selection: ...
def select_all(config: Config) -> tuple[Selection, ...]: ...
def threshold_report(selections: Sequence[Selection], config: Config) -> ThresholdReport: ...
def write_selected(selections: Iterable[Selection], path: Path) -> int: ...
def read_selected(path: Path) -> Iterator[Selection]: ...
```

## Slice 5 — Bundles, batches, and the cost projection that stops the pipeline

- **Delivers:** `uv run find-best-mobo estimate` cuts excerpt windows around
  every mention (2 minutes before, 5 after, overlapping windows merged), packs
  them into XML bundles under `data/bundles/batch-N/`, assigns those bundles to
  a small calibration batch plus three larger recency-ordered batches, and
  prints the projection: videos indexed, videos selected, excerpt characters,
  bundle count, projected tokens per batch and in total, and the chars-per-token
  factor used. Then it stops. Covers R5, R6, R7, R17, R20, R23.
- **Files:** `src/find_best_mobo/excerpt.py`, `src/find_best_mobo/bundle.py`,
  `src/find_best_mobo/estimate.py`,
  `src/find_best_mobo/commands/estimate.py`, `tests/test_excerpt.py`,
  `tests/test_bundle.py`, `tests/test_estimate.py`
- **Estimate:** ~480 lines

### Signatures

```python
@dataclass(frozen=True)
class Excerpt:
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    text: str
    canonicals: tuple[str, ...]


@dataclass(frozen=True)
class Bundle:
    bundle_id: str
    batch: int
    excerpts: tuple[Excerpt, ...]
    projected_tokens: int


@dataclass(frozen=True)
class Projection:
    videos_indexed: int
    videos_selected: int
    excerpt_characters: int
    bundle_count: int
    tokens_per_batch: tuple[int, ...]
    total_tokens: int
    chars_per_token: float


def cut_windows(
    transcript: Transcript, mentions: Sequence[Mention], video: Video, config: Config
) -> tuple[Excerpt, ...]: ...
def merge_overlapping(excerpts: Sequence[Excerpt]) -> tuple[Excerpt, ...]: ...
def cap_per_video(excerpts: Sequence[Excerpt], config: Config) -> tuple[Excerpt, ...]: ...
def estimate_tokens(text: str, config: Config) -> int: ...
def pack_bundles(excerpts: Sequence[Excerpt], config: Config) -> tuple[Bundle, ...]: ...
def assign_batches(bundles: Sequence[Bundle], config: Config) -> tuple[Bundle, ...]: ...
def render_bundle(bundle: Bundle) -> str: ...
def write_bundles(bundles: Iterable[Bundle], config: Config) -> int: ...
def project(bundles: Sequence[Bundle], selections: Sequence[Selection], config: Config) -> Projection: ...
def render_projection(projection: Projection) -> str: ...
```

The rendered bundle is XML structure with prose inside it — tags delimit each
excerpt and its provenance, and the transcript text sits between them unmarked:

```xml
<bundle id="batch-1-003">
  <excerpt video_id="..." start="1042">
    <video_title>...</video_title>
    <boards>X870E Taichi, B650E</boards>
    <transcript>...</transcript>
  </excerpt>
</bundle>
```

## Out of scope

- Every model-invoking stage: extraction, synthesis, tier-3 inference. This plan
  ends at the projection, and no code path continues past it.
- The claims schema and the claim store — they belong to M2, and specifying them
  here would fix the agent contract before the calibration batch has said
  anything about what the excerpts actually contain.
- The report generator, tiering, the safety axis, and recency weighting (M2–M4).
- Retrying or re-cutting at a narrower window. The levers exist as config from
  slice 5 onward; deciding to turn them is a post-calibration act, not code.
- Any attempt to make the pipeline a single command. The manual step between
  corpus and extraction is the checkpoint.
