# Finding Best Mobo by Buildzoid — Architecture

<!-- The living description of what exists RIGHT NOW. Updated at the end of every
slice (AGENTS.md, "Architecture doc"), so it describes the system as built, never
as planned. `docs/DESIGN.md` is the intent and doesn't change; this changes.

Keep it at the level of LOGIC, NOT CODE. Components and what each is responsible
for, what data moves between them, what happens on the main paths. No signatures,
no line-by-line description, nothing that a rename would invalidate — if a
refactor that changes no behaviour would force an edit here, it's too low-level.

It has two readers and they keep each other honest: the owner, who does not read
the code and needs somewhere to understand the system; and the next agent, which
starts with no context beyond this repository and reads this first to get its
bearings. Written for the human, it stays truthful; written at all, it saves the
agent from rediscovering the system by grepping.

Delete these comments or leave them; they don't render. -->

What exists today is the whole corpus milestone, five stages: a CLI that enumerates the
Buildzoid channel into a classified video index, one that fetches and caches
each kept video's captions behind a failure ledger,, one that folds the
spacing damage auto-captions inflict on part numbers onto canonical board names,
and one that narrows the corpus to the videos carrying real alias evidence. No
excerpting and no model involvement — those are the last slice of the
`corpus-and-checkpoint` plan and the milestones beyond it.

## Components

| Component | Responsible for |
| --- | --- |
| CLI dispatcher (`cli.py`) | Parsing the command line, loading configuration, and handing off to the subcommand module named on the command line. It holds no list of subcommands: adding a stage means adding a module, never editing the dispatcher. |
| Configuration (`config.py`) | Declaring every lever the whole pipeline will ever have — including ones no stage uses yet — and reading them from `config.toml`, with in-code defaults so an absent key or file is never a crash. |
| Network boundary (`ytdlp.py`) | The only code that touches `yt-dlp` or the network. Lists a channel's uploads via flat playlist extraction (no downloads), reusing one client for the whole run, and yields raw entry dicts. |
| Index (`index.py`) | Classifying each raw entry into a video record (regular or Short; pending, excluded-as-Short, or out-of-range) and reading/writing the index as deterministic JSONL. Classification is pure — no I/O. |
| `index` subcommand (`commands/index.py`) | The stage itself: enumerate, write `data/index.jsonl`, print the summary counts. |
| Transcripts (`transcripts.py`) | Parsing WebVTT into timed cues, and owning the on-disk transcript cache. Fetching and caching are deliberately separate: the fetch never consults the cache, so "reruns never refetch" lives in exactly one place. |
| Failure ledger (`ledger.py`) | Recording every fetch failure with its class, carrying attempt counts across runs, and deciding when the run must halt. It is rewritten on every record, so evidence is on disk even when the run stops abruptly. |
| `fetch` subcommand (`commands/fetch.py`) | The stage itself: read the index, fetch what is pending and uncached, print the summary — or, on a halt, the trigger and the ledger. |
| Normalization (`normalize.py`) | Folding caption text and titles into one comparable form: case, scattered punctuation, and above all the spacing damage that renders `X670E` as `x 670 e`. Pure and total. |
| Alias table (`aliases.py`, `data/aliases.toml`) | Mapping many surface forms onto one canonical entity, and finding those entities in normalized text with a single compiled pattern. The table is hand-authored input, not derived data. |
| `aliases` subcommand (`commands/aliases.py`) | The inspection stage: report, per canonical, how many videos mention it and which forms actually matched — so the table's recall is looked at before it silently decides the corpus. |
| Selection (`select.py`) | Deciding which videos are actually about AM5 boards, and saying what the threshold currently costs. A title hit is an automatic include; otherwise the video needs enough DISTINCT boards mentioned in the body. Pure decision logic, plus its own deterministic JSONL. |
| `select` subcommand (`commands/select.py`) | The stage itself: read index and cached transcripts, write `data/selected.jsonl`, print the threshold's effect. |
| Excerpting (`excerpt.py`) | Cutting a wide asymmetric window around each mention, merging windows that overlap, and capping how many survive per video. Pure — it never reads the disk. |
| Bundling (`bundle.py`) | Grouping excerpts into token-capped work bundles, assigning them to a calibration batch and larger batches after it, and rendering each as XML on disk. |
| Projection (`estimate.py`) | Counting what a run would cost and saying so openly, including the chars-per-token factor, which is a guess until the calibration batch measures it. |
| `estimate` subcommand (`commands/estimate.py`) | The stage itself, and the end of the milestone: cut, merge, cap, pack, batch, write, print the projection, stop. |

## Data flow

- YouTube --(flat channel listing, one raw entry dict per upload)--> network boundary
- network boundary --(raw entries)--> index classification --(video records)--> `data/index.jsonl`
- `config.toml` --(levers)--> every component, loaded once by the CLI dispatcher
- `data/index.jsonl` --(pending video records)--> fetch stage
- network boundary --(raw WebVTT)--> transcript parsing --(timed cues)--> `data/transcripts/<video_id>.json`
- fetch failures --(class, detail, attempts)--> `data/failures.jsonl`, and back in as the retry list on the next run
- `data/transcripts/` --(cached transcripts)--> normalization --(comparable text)--> alias matching
- `data/aliases.toml` --(canonical entities and their surface forms)--> one compiled pattern --(mentions with timestamps)--> selection
- index + transcripts + matcher --(one decision per video, exclusions included)--> `data/selected.jsonl`
- selections + cached transcripts --(windows around mentions, merged and capped)--> excerpts --(packed to a token cap)--> bundles --> `data/bundles/batch-N/*.xml`
- bundles + selections --(counts and a stated token factor)--> the printed projection, and then nothing

## Main paths

### Building the video index

1. The owner runs `uv run find-best-mobo index` (optionally `--config <path>`).
2. The dispatcher loads configuration and imports the `index` command module by
   name.
3. The command enumerates the channel through the network boundary: every
   upload, lazily, without downloading anything.
4. Each entry is classified. Duration at or below the Shorts threshold means
   excluded as a Short — checked before anything else, so a pre-2023 Short is
   excluded as a Short, not as out-of-range. Otherwise an upload date before
   the start date (or missing entirely) means excluded as out-of-range.
   Everything else — livestreams explicitly included — is kept as pending, for
   the selection stage to judge later. Only Shorts are ever excluded on
   duration; there is no ceiling.
5. Every video, excluded or not, becomes one line of `data/index.jsonl`
   carrying its classification and inclusion reason — exclusions are recorded,
   never implied.
6. A summary prints: total videos found, how many fell outside the date range,
   how many were excluded as Shorts, how many were kept, and how many reported
   no duration at all.
7. If more than one video reported no duration, a warning follows the summary
   naming every affected video id, in the order they appear in the index. One
   such video is expected and harmless; more than one means durations are being
   zeroed by some other cause and real videos are silently leaving the corpus,
   so the ids are named to make the cause chaseable.

Rerunning rewrites the index from a fresh listing; given the same listing and
configuration the file is byte-identical (records sorted by upload date then
video id, keys sorted within each record).

### Fetching transcripts

1. The owner runs `uv run find-best-mobo fetch`. Without an index it says so and
   stops — the stages are deliberately separate commands.
2. Only videos the index kept as pending are considered. Anything already in the
   cache is skipped without a network call, which is what makes a rerun cheap
   and resumable.
3. Each remaining video's captions are fetched through the network boundary and
   parsed into timed cues. A video with no caption track is an ordinary outcome,
   not an error, and is recorded as such.
4. Every failure goes to the ledger with its class, the underlying detail, and
   how many runs have now tried it. The run continues past a failure — one bad
   video must not end a corpus pass.
5. After each failure the halt triggers are checked: three consecutive fetch
   errors, fetch errors past 3% of the pending set, or missing captions past 5%.
   A fired trigger stops the run, names itself, and prints the ledger.
6. Otherwise a summary prints: pending, already cached, fetched this run, and
   failures split by class.

A rerun retries what failed and skips what succeeded, so the ledger shrinks as
problems resolve. Transcripts are written one at a time and never all held in
memory, so a 1000-video channel costs no more than one video's worth.

### Inspecting the alias table

1. The owner runs the `aliases` stage with `--check`. It reads the index and the
   cached transcripts; without either it says which stage to run first.
2. Every surface form in the table and every piece of text are put through the
   same normalization, so the two meet in one space rather than the table
   guessing at what captions look like.
3. One compiled pattern carries every surface form, longest first, so a longer
   name wins over a shorter one that is a substring of it.
4. The report lists every canonical with the videos and mentions it matched and
   the forms that actually fired — and **names the canonicals that matched
   nothing at all**, which is the table's most important defect and the reason
   this stage exists as something a person looks at.

Ordering is deterministic, so two runs over the same cache print identically.

**This stage is not reachable from the command line yet.** The top-level parser
rejects `--check` before dispatch, because the dispatcher deliberately holds no
subcommand table and this slice does not touch it. The stage works and is
tested through its entry point; the wiring is an open plan question recorded in
`docs/BACKLOG.md`.

### Narrowing the corpus

1. The `select` stage reads the index, keeps the videos the index left pending,
   and loads each one's cached transcript in turn.
2. An alias hit in the **title** is an automatic include. He titles videos after
   what they are about, so a title hit is the strongest signal available and it
   does not need corroborating.
3. Otherwise the video must mention at least N **distinct** canonicals in the
   body. Distinct, not total: ten mentions of one board is one board being
   discussed, while three different boards is the comparison passage the
   shortlist actually needs. N is configuration and defaults to 3.
4. Every video gets a record, excluded ones included — exclusions are recorded,
   never implied, the same rule the index follows.
5. The report says what the threshold is currently costing: how many came in on
   a title, how many on the count, how many were excluded, and — stated as
   directions rather than bare numbers — how many MORE would enter if it were
   one lower and how many would DROP if it were one higher. Title hits are
   immune to both, so they are never counted in either.

That last part is the tuning lever made visible: the threshold can be moved and
the stage re-run from cache, with no refetching (R17).

### Estimating the cost, and stopping

1. The `estimate` stage reads the selections and takes only the included ones,
   most recent video first — recency is what the batches are ordered by, so the
   first batch is the most useful one to spend on.
2. Around every mention it cuts a window: **2 minutes before, 5 minutes after**.
   Asymmetric because a verdict follows the analysis rather than preceding it,
   and wide on purpose, to be narrowed later on evidence rather than guessed
   tight now. Narrowing re-runs from cache and refetches nothing (R17).
3. Windows that overlap or touch are merged, so one dense passage is one excerpt
   rather than five copies of itself.
4. Each video keeps at most a configured number of excerpts, ranked by how many
   distinct boards they mention — density of boards being the best available
   proxy for "this is the comparison passage".
5. Excerpts are packed greedily into bundles under a token cap. An excerpt too
   big for the cap gets a bundle to itself rather than being dropped or split:
   losing evidence to a cap must be visible, never silent.
6. Bundles go to a small calibration batch first, then to larger batches. The
   calibration batch exists to turn the projection into a measurement before the
   larger spend.
7. Each bundle is written as XML — tags carry the structure and provenance, the
   transcript sits inside them as prose, because tagged boundaries are attended
   to reliably by a model.
8. The projection prints: videos indexed and selected, excerpt volume, bundle
   count, tokens per batch and in total, and **the chars-per-token factor
   itself**, stated openly as an estimate rather than buried as a constant.

Then it stops. Nothing downstream of this exists yet, deliberately.

## State and storage

- `config.toml` (repository root) — every pipeline lever, flat keys. In git.
- `data/index.jsonl` — one JSON record per video. Local-only, gitignored, as
  the whole `data/` tree will be: the corpus never enters git.
- `data/transcripts/<video_id>.json` — one cached transcript per video, timed
  cues in file order. The cache is the resumability story: it is what a rerun
  reads instead of refetching.
- `data/failures.jsonl` — this run's fetch failures, rewritten on every record.
  It doubles as the next run's retry list.
- `data/selected.jsonl` — one record per pending video: the video, why it was
  included or excluded, its body mentions, and its distinct-canonical count.
- `data/bundles/batch-N/bundle-NNN.xml` — the work bundles, one file each,
  byte-identical across runs given the same cache and configuration.
- `data/aliases.toml` — the hand-authored alias table. Unlike everything else
  under `data/`, this is **input rather than cache**: it is tracked in git
  (forced past the ignore rule) because a fresh clone with no alias table would
  match nothing. That it lives here at all is an open plan question.

## Known rough edges

- **Upload dates from flat listing are approximate.** Flat extraction only
  carries a date at all because the `youtubetab:approximate_date` extractor
  argument is set (without it, every video would silently classify as
  out-of-range and the corpus would be empty). The dates it produces are
  approximations, so a video near the 2023-01-01 boundary may fall on either
  side of it.
- **A missing duration classifies as a Short.** Missing or null duration is
  treated as 0, which is at or below the Shorts threshold. Deliberate — it
  never crashes — but it means a listing that omitted durations would
  quietly exclude everything as Shorts. The `index` summary therefore counts
  these separately and warns above one, which is what turns that silent failure
  into a visible one. The count deliberately overlaps the Shorts count rather
  than being subtracted from it: a zero-duration video really was excluded as a
  Short, and the second line says why that may be wrong.
- **A missing upload date is recorded as `0001-01-01`.** The record keeps its
  out-of-range exclusion visible rather than inventing a plausible date.
- **A corrupt cache entry reads as absent.** A damaged transcript file is
  refetched rather than crashing the run, which is right for a cache but means
  silent corruption costs a refetch instead of announcing itself.
- **Normalization will not join a part number to an ordinary word.** The
  rejoining rule is bounded: multi-letter words never participate, so `ryzen 9`
  and `in 2023` survive intact. Without that bound `a 7800 X 3 D` welds into
  `a7800x3d` and matches nothing — the fix for one kind of caption damage
  silently causing another.
- **A title hit needs no corroboration at all.** A video whose title mentions a
  board is included even with an empty transcript, so a mistitled or
  tangentially-titled video enters the corpus on that alone. Deliberate — recall
  matters more than precision at this stage, and the excerpting slice will find
  nothing to excerpt in a video that only mentions a board in passing.
- **A merged excerpt double-counts its overlap, and not slightly.**
  `merge_overlapping` has no access to the cues and cannot re-cut, so on partial
  overlap it concatenates — and with many overlapping windows the concatenation
  compounds. Measured against a real 33-minute review: a 28,438-character
  transcript became one 137,246-character excerpt, **4.8x the whole transcript**.
  This entry previously called the effect slight; that was written from theory,
  before any real transcript existed to check it against. The inflation scales
  with mention density rather than being a constant factor, so the projected
  token count cannot be corrected by dividing. Recorded in `docs/BACKLOG.md`.
- **The token projection is a guess until the calibration batch runs.** The
  chars-per-token factor starts at 4.0 and is configuration, not a measurement.
  It is printed with the projection precisely so it is not mistaken for one.
- **`estimate` reports zero videos indexed if the index is missing** rather than
  refusing to run. The projection stays otherwise correct, but its denominator
  reads as a real number when it is an absence.
- **The alias table's recall is a human judgement, not a measured one.** The
  shipped table is a starting point covering the AM5 chipsets, five vendors, ten
  board families and five CPUs. Nothing knows what it is missing; the `aliases`
  stage exists to make that inspectable rather than to answer it.
- **A run with no failures does not rewrite `data/failures.jsonl`.** The ledger
  is written when a failure is recorded, so a clean rerun after a failing one
  leaves the old file in place and it reads as current. Raised for a ruling
  rather than fixed unilaterally — see the slice 2 pull request.
