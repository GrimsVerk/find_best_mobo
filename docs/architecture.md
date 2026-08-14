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

What exists today is the first two corpus stages: a CLI that enumerates the
Buildzoid channel into a classified video index, and one that fetches and caches
each kept video's captions behind a failure ledger. No selection, no excerpting,
no model involvement — those are later slices of the `corpus-and-checkpoint`
plan.

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

## Data flow

- YouTube --(flat channel listing, one raw entry dict per upload)--> network boundary
- network boundary --(raw entries)--> index classification --(video records)--> `data/index.jsonl`
- `config.toml` --(levers)--> every component, loaded once by the CLI dispatcher
- `data/index.jsonl` --(pending video records)--> fetch stage
- network boundary --(raw WebVTT)--> transcript parsing --(timed cues)--> `data/transcripts/<video_id>.json`
- fetch failures --(class, detail, attempts)--> `data/failures.jsonl`, and back in as the retry list on the next run
- `data/transcripts/` --(cached transcripts)--> later slices

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

## State and storage

- `config.toml` (repository root) — every pipeline lever, flat keys. In git.
- `data/index.jsonl` — one JSON record per video. Local-only, gitignored, as
  the whole `data/` tree will be: the corpus never enters git.
- `data/transcripts/<video_id>.json` — one cached transcript per video, timed
  cues in file order. The cache is the resumability story: it is what a rerun
  reads instead of refetching.
- `data/failures.jsonl` — this run's fetch failures, rewritten on every record.
  It doubles as the next run's retry list.

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
- **A run with no failures does not rewrite `data/failures.jsonl`.** The ledger
  is written when a failure is recorded, so a clean rerun after a failing one
  leaves the old file in place and it reads as current. Raised for a ruling
  rather than fixed unilaterally — see the slice 2 pull request.
