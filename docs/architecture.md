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

What exists today is the whole corpus milestone — a CLI that enumerates the
Buildzoid channel into a classified video index, one that fetches and caches
each kept video's captions behind a failure ledger, one that folds the
spacing damage auto-captions inflict on part numbers onto canonical board names,
and one that narrows the corpus to the videos carrying real alias evidence. On
top of it sits Stage B, the first work in the project that spends anything: one
command extracts one batch of bundles into claims, validates them against a
schema Python owns, appends them to an append-only store, and stops before it
has spent 10% of the weekly subscription limit. Everything between the two —
excerpting, routing, bundling and the projection — runs in `estimate`, which
stops at the projection and hands the decision to continue to `extract`.

## Components

| Component | Responsible for |
| --- | --- |
| CLI dispatcher (`cli.py`) | Parsing the arguments it owns — `--config`, `--help`, the command name — loading configuration, and handing off to the subcommand module named on the command line. Everything it does not recognise is forwarded to that module, which owns its parsing and its errors (OD-10, R1006); a module may declare `parse_args`, and one that does not gets a parser accepting nothing, so a typo is still an exit-2 error naming the stage. It holds no list of subcommands and no flag names: adding a stage, or a flag to one, means editing a module and never the dispatcher. Every shipped stage declares `parse_args`, so `find-best-mobo <stage> --help` documents that stage; `tests/test_cli_stages.py` walks the package and fails if a later stage does not. |
| Shared refusals (`artifacts.py`) | Saying what each stage requires of the one before it, in one message shape. An ABSENT artifact names itself and the command that produces it, and the stage exits 1; a PRESENT-but-empty one is a real value and is reported as what it is (OD-9, R1005). `MissingArtifact` subclasses `FileNotFoundError`, so no existing handler had to change. |
| Configuration (`config.py`) | Declaring every lever the whole pipeline will ever have — including ones no stage uses yet — and reading them from `config.toml`, with in-code defaults so an absent key or file is never a crash. Paths are levers too: `data_dir` for the corpus cache and `alias_table_path` for the hand-authored alias table, which is why the two can be moved independently. One lever has no default and cannot get one: `extraction_model` is empty until `config.toml` names a model, and extraction REFUSES rather than choosing — a chars-per-token factor measured against one model does not transfer to another, so no model name appears anywhere in `src/`. |
| Network boundary (`ytdlp.py`) | The only code that touches `yt-dlp` or the network. Lists a channel's uploads via flat playlist extraction (no downloads), reusing one client for the whole run, and yields raw entry dicts. |
| Index (`index.py`) | Classifying each raw entry into a video record (regular or Short; pending, excluded-as-Short, or out-of-range) and reading/writing the index as deterministic JSONL. Classification is pure — no I/O. |
| `index` subcommand (`commands/index.py`) | The stage itself: enumerate, write `data/index.jsonl`, print the summary counts. |
| Transcripts (`transcripts.py`) | Parsing WebVTT into timed cues, and owning the on-disk transcript cache. Fetching and caching are deliberately separate: the fetch never consults the cache, so "reruns never refetch" lives in exactly one place. |
| Failure ledger (`ledger.py`) | Recording every fetch failure with its class, carrying attempt counts across runs, and deciding when the run must halt. It is rewritten on every record, so evidence is on disk even when the run stops abruptly. |
| `fetch` subcommand (`commands/fetch.py`) | The stage itself: read the index, fetch what is pending and uncached, print the summary — or, on a halt, the trigger and the ledger. The per-video extraction it already runs also yields the DESCRIPTION, stored in the cache record at no extra request (OD-8, R1004). It requests `json3` and falls back to WebVTT, records which per video, and says so in the summary — prominently when the fallback was used (OD-24, R1013). |
| Normalization (`normalize.py`) | Folding caption text and titles into one comparable form: case, scattered punctuation, hyphens (which fold to a space, so the table's `steel legend` meets a caption's `steel-legend` — OD-6, R1002), and above all the spacing damage that renders `X670E` as `x 670 e`. Pure and total. |
| Alias table (`aliases.py`, path from `alias_table_path`) | Mapping many surface forms onto one canonical entity, and finding those entities in normalized text with a single compiled pattern. Each form compiles split-tolerantly (OD-6, R1002): an optional space between adjacent characters inside a word, a required one where the form itself has a space — so `toma hawk` matches `tomahawk` while `aorusmaster` never matches `aorus master`, because the alias's own space needs a real token boundary to land on. Matching is scoped to ONE cue's text (OD-15, R1010): a name the captions break across a cue boundary is COUNTED and never matched, because a mention spanning two cues has no single cue start and R5 cuts every excerpt window from that field. A `kind = "chipset"` alias additionally contributes its ITX form — every declared form plus a trailing `i`, so `b850i` finds B850 without relaxing the right boundary (OD-7, R1003). The table is hand-authored input, not derived data, and every loader takes its path from configuration rather than building one (OD-11, R1007). |
| `aliases` subcommand (`commands/aliases.py`) | The inspection stage: report, per canonical, how many videos mention it and which forms actually matched — so the table's recall is looked at before it silently decides the corpus. Requires the table, the index and the transcript-cache DIRECTORY; an empty cache yields a report of zeros rather than a refusal (OD-9, R1005). |
| Selection (`select.py`) | Deciding which videos are actually about AM5 boards, and saying what the threshold currently costs. A title hit is an automatic include; otherwise the video needs enough DISTINCT boards mentioned in the body. Pure decision logic, plus its own deterministic JSONL. |
| `select` subcommand (`commands/select.py`) | The stage itself: require the index, the alias table and the transcript-cache directory before deciding anything (OD-9, R1005), then read index and cached transcripts, write `data/selected.jsonl`, and print the threshold's effect. |
| Excerpting (`excerpt.py`) | Cutting a wide asymmetric window around each mention, merging windows that overlap, and capping how many survive per video. Also the one definition of a transcript's text as a single line (`transcript_text`), which the saturation ratio's denominator and the whole path's own text both read, so the two cannot drift. Pure — it never reads the disk. |
| Routing (`submission.py`) | Deciding whether a video is sent as excerpts or as its whole transcript, and cutting a whole transcript into bundle-sized parts at cue boundaries (OD-13, R28, R1008). The ratio decides and size never does; a `VideoSubmission` carries the chosen blocks and their projected cost. Pure — it never reads the disk. |
| Bundling (`bundle.py`) | Grouping blocks into token-capped work bundles, assigning them to a calibration batch and larger batches after it, and rendering each as XML on disk. Every `<excerpt>` states its `form`, `part` and `parts` (R28, R1008), always present and never inferred from an absent attribute, so a reader can be told whether it is holding a window or one part of a whole transcript. |
| Claim schema (`claims.py`) | The shape of one piece of evidence, and the refusal that keeps a model honest (R9, BL-23). Every field of `docs/DESIGN.md` §9's Claim is required, every vocabulary value is exact, and an UNKNOWN field is a fault rather than something to drop — a model inventing a field misunderstood the contract, and discarding it hides that. Every fault is reported at once, never the first. Pure — it never reads the disk. |
| Claim store (`claimstore.py`) | The append-only store, tagged by batch (R10, R27). Writes are atomic per FILE: every claim in a valid file lands or none does. A batch already stored cannot be ingested again — the mirror of R27 is that no completed work is silently REWRITTEN either, and a rerun that doubled a batch would corrupt every count downstream while every gate stayed green. |
| `ingest` subcommand (`commands/ingest.py`) | Validate one claims file and append it, or refuse naming every fault and append nothing. Spends nothing and invokes nothing. |
| Model boundary (`extract.py`) | The only code in the project that invokes a model, and therefore the only code that spends money. One bundle in, one claims file on disk, and the four token counts the call reported back beside it — fresh input, output, cache creation and cache read, kept apart and never summed (R8). The subscription pays, through `claude -p`, because R26's cap is written against the weekly SUBSCRIPTION meter and an API call would never move it (`docs/DECISIONS.md`, 2026-08-25). The model's output is written to disk BEFORE it is validated, always, including when validation then fails (R27): the spend has already happened, and a rejected file is the only record of what the model said. Validation happens here rather than at ingest, so R9's retry-or-set-aside decision is made where the spend was. One seam — a lazily built CLI runner — so every test in the tree runs offline, free, and on a machine with no subscription. |
| Extraction prompt (`prompts/extract-claims.md`) | What the agent is actually asked: the bundle format it will be reading, what counts as a claim, the three vocabularies exactly as `claims.py` spells them, and an output contract of a bare JSON array with those eight keys and no others. A tracked file rather than a string literal, reachable only through `extract.prompt_text`, because R23's "the same bundle produces a comparable file twice" is false the moment the prompt can change without a diff. |
| Projection (`estimate.py`) | Counting what a run would cost and saying so openly, including the chars-per-token factor, which is a guess until the calibration batch measures it, and the per-path routing figures R1008 asks for — counts, characters and tokens per path, and every whole transcript that spans more than one bundle, by id. |
| `estimate` subcommand (`commands/estimate.py`) | The stage itself, and the end of the milestone: cut, merge, cap, pack, batch, write, print the projection, stop. |
| Spend guard (`spend.py`) | Reading the meter, and saying when the effort has spent what it was given (R26). One label governs — `Weekly (7-day)`, the account-wide one, by the owner's 2026-08-25 ruling — because the model-scoped limit beside it ignores spend on every other model, while the account-wide figure comes from Anthropic's own usage endpoint and counts every session on the subscription. `omarchy-agent-usage-claude --limits-only --force` answers first and `claude -p "/usage"` is the fallback; the reading records WHICH answered, because the fallback starts a session and so spends against the very limit it reports. The ceiling is ten points above the reading the batch STARTED at, clamped at 100%: R26 caps the extraction effort, not the account, so a run beginning at 43% stops at 53% rather than refusing outright. Taking a reading is one seam, for the reason the network boundary is one: no test may invoke a reader. |
| `extract` subcommand (`commands/extract.py`) | The explicit continue command R7 promises: one named batch, one bundle at a time, with a reading before, part-way through and after (R26). The part-way one is what makes it a guard rather than a receipt. A stop is not a rollback — every bundle already extracted stays extracted and every validated claim is still appended — and it exits non-zero so nothing downstream mistakes a partial batch for a whole one (R27). A claims file that fails the schema costs its own bundle and not the batch: one retry, then the bundle is set aside, named in the output, and left unconsumed (R9). |

## Data flow

- YouTube --(flat channel listing, one raw entry dict per upload)--> network boundary
- network boundary --(raw entries)--> index classification --(video records)--> `data/index.jsonl`
- `config.toml` --(levers)--> every component, loaded once by the CLI dispatcher
- `data/index.jsonl` --(pending video records)--> fetch stage
- network boundary --(raw WebVTT)--> transcript parsing --(timed cues)--> `data/transcripts/<video_id>.json`
- fetch failures --(class, detail, attempts)--> `data/failures.jsonl`, and back in as the retry list on the next run
- `data/transcripts/` --(cached transcripts)--> normalization --(comparable text)--> alias matching
- the alias table at `alias_table_path` --(canonical entities and their surface forms)--> one compiled pattern --(mentions with timestamps)--> selection
- index + transcripts + matcher --(one decision per video, exclusions included)--> `data/selected.jsonl`
- selections + cached transcripts --(windows around mentions, merged and capped)--> excerpts --(routed per video: excerpts, or the whole transcript in bundle-sized parts)--> blocks --(packed to a token cap)--> bundles --> `data/bundles/batch-N/*.xml`
- bundles + selections --(counts and a stated token factor)--> the printed projection, and then nothing
- `prompts/extract-claims.md` + one `data/bundles/batch-N/*.xml` --(the prompt as the argument, the bundle on standard input)--> `claude -p` --(the model's answer, written down before it is judged)--> `data/claims/batch-N/*.json`, and the call's four token counts back to the caller
- a claims file --(validated against the schema, every fault at once)--> claims --(appended, tagged by batch, never rewritten)--> `data/claims.jsonl`
- `data/bundles/batch-N/*.xml` --(one bundle at a time)--> the extraction boundary --(one claims file per bundle, written before anything reads it)--> validated claims --(one append for the batch)--> `data/claims.jsonl`
- the usage reader --(the `Weekly (7-day)` percentage, three times per batch)--> the spend guard --(a ceiling ten points above the batch's baseline)--> carry on, or stop with the bundles that remain named

## Main paths

### Building the video index

1. The owner runs `uv run find-best-mobo index` (optionally `--config <path>`).
2. The dispatcher loads configuration and imports the `index` command module by
   name.
3. The command enumerates the channel through the network boundary: every
   upload, lazily, without downloading anything.
4. Each entry is classified. Duration at or below the Shorts threshold means
   excluded as a Short — checked before anything else, so a pre-2023 Short is
   excluded as a Short, not as out-of-range. Otherwise the video's date is
   taken from its exact upload date when the entry carries one, and from the
   listing's timestamp (epoch seconds, read as UTC) when it doesn't — the flat
   channel listing only sends the timestamp, which is why the index must read
   it. A video whose date falls before the start date, moved back by a fixed
   two-month slop, is excluded as out-of-range; a video with neither field is
   too. Everything else — livestreams explicitly included — is kept as
   pending, for the selection stage to judge later. Only Shorts are ever
   excluded on duration; there is no ceiling.
5. Every video, excluded or not, becomes one line of `data/index.jsonl`
   carrying its classification and inclusion reason — exclusions are recorded,
   never implied.
6. A summary prints: total videos found, how many fell outside the date range,
   how many were excluded as Shorts, how many were kept, and then the
   zero-duration videos split by the SHAPE of their listing entry — how many
   were the flat listing's Shorts shape (no duration and no date in either
   field, which is how that listing returns a Short), and how many carried a
   real date with no duration. Both lines print every run, including as zero.
7. A warning follows the summary only for the second group, naming every
   affected video id, in the order they appear in the index — and it fires for
   ONE such entry. A dated entry with no duration is not the listing's Shorts
   shape, so something else zeroed its duration and a real video is silently
   leaving the corpus; the ids are named to make the cause chaseable. The old
   rule warned above a COUNT of one, on the premise that only a stream in
   progress can lack a duration. BL-15 measured that false — eight genuine
   Shorts, every run — so the banner was a permanent false alarm and a ninth id
   inside it would have been invisible (OD-14, R1009).

Rerunning rewrites the index from a fresh listing; given the same listing and
configuration the file is byte-identical (records sorted by upload date then
video id, keys sorted within each record).

### Fetching transcripts

1. The owner runs `uv run find-best-mobo fetch`. Without an index it says so and
   stops — the stages are deliberately separate commands. It then creates
   `data/transcripts/` whether or not it goes on to cache anything, including
   when the run halts part-way on an R24 trigger: the directory's existence is
   how every later stage knows fetch has RUN (OD-9, R1005).
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

1. The owner runs `uv run find-best-mobo aliases --check`, or
   `./scripts/run.sh aliases`. It reads the index and the cached transcripts;
   without either it says which stage to run first. An EMPTY transcript cache
   is not "without": `fetch` ran and cached nothing, so the report prints every
   canonical at zero and exits 0 (OD-9, R1005). The numbers say plainly that
   nothing was scanned, which is the honest answer — where calling it a missing
   cache sent the owner to re-run a stage that had already run.
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

**The stage runs as `uv run find-best-mobo aliases --check`.** It was
unreachable from the command line until 2026-08-24: the top-level parser
rejected `--check` before dispatch, because the dispatcher deliberately holds
no subcommand table (BL-5). OD-10/R1006 fixed that without adding one — the
dispatcher forwards what it does not recognise, and the stage owns its own
parsing.

### Narrowing the corpus

1. The `select` stage refuses before it starts if the index, the alias table or
   the transcript cache DIRECTORY is absent, naming the stage that produces it
   (OD-9, R1005) — an absent cache means `fetch` never ran and no video could
   have passed the threshold, so a report over it would measure the missing
   corpus and read as a measurement of the lever. An EMPTY cache is a real
   state and selects normally. Then it reads the index, keeps the videos the
   index left pending, and loads each one's cached transcript in turn. It also counts, per video, how many alias matches existed only across an adjacent-cue join and were therefore NOT counted as mentions — carried in `selected.jsonl` and summed into the report, printed on every run including as zero, so the first real corpus run says which videos R1010's scoping costs; a video
   with no cached transcript is still selected on its title, which is the
   per-video tolerance R24 owns and which this rule does not touch. It then
   reports its COVERAGE — how many of the pending videos had a transcript to
   read — on every run, and refuses if that is zero over a non-empty corpus
   (OD-23, R1012). That case is `fetch` half-done rather than not run: the
   directory exists and is empty of what this video needed, so every body is
   empty because none was read, and a threshold report over it is a
   measurement of the missing corpus wearing the shape of a measurement of the
   lever.
2. An alias hit in the **title** is an automatic include. He titles videos after
   what they are about, so a title hit is the strongest signal available and it
   does not need corroborating.
3. Otherwise, an alias hit in the **description** is an automatic include too —
   author-written, short and unmangled by speech-to-text, which makes it the
   highest-signal field the corpus has (OD-8, R1004). It yields no mentions and
   moves no distinct-canonical count: a description has no cue, so it has no
   timestamp, and R5 cuts every excerpt window from one. The report says how
   many videos came in that way and how many of those nothing else would have
   admitted — the second being what reads as the signal's ADDITION, since a
   video can satisfy two rules at once.
4. Otherwise the video must mention at least N **distinct** canonicals in the
   body. Distinct, not total: ten mentions of one board is one board being
   discussed, while three different boards is the comparison passage the
   shortlist actually needs. N is configuration and defaults to 3.
5. Every video gets a record, excluded ones included — exclusions are recorded,
   never implied, the same rule the index follows.
6. The report says what the threshold is currently costing: how many came in on
   a title, how many on the count, how many were excluded, and — stated as
   directions rather than bare numbers — how many MORE would enter if it were
   one lower and how many would DROP if it were one higher. Title hits are
   immune to both, so they are never counted in either.

That last part is the tuning lever made visible: the threshold can be moved and
the stage re-run from cache, with no refetching (R17).

### Estimating the cost, and stopping

0. Before anything is cut, the stage requires all three upstream artifacts in
   pipeline order — `data/index.jsonl` (`index`), `data/transcripts/` (`fetch`),
   `data/selected.jsonl` (`select`) — and refuses naming the first that is
   absent (OD-9, R1005). Pipeline order is what makes the message actionable:
   told to run `select` first, the owner would run a stage that itself refuses.
   Nothing is written on a refusal, so `data/bundles/` is left exactly as it
   was found. A present-but-EMPTY artifact is a real value and projects real
   zeros.
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
5. Each video is then ROUTED (`submission.py`, R28, R1008). If its surviving
   excerpts already cover **80% or more** of the transcript, the whole
   transcript is sent instead: at that point the excerpts are the transcript
   with gaps in it, paid for as excerpts and missing the passages between the
   mentions for no saving worth having. The ratio is measured on the blocks that
   would actually be sent — after the merge and after the cap — because
   measuring earlier counts overlap twice or routes on excerpts that were then
   thrown away. **Size is never consulted** (OD-13): a three-hour saturated
   stream goes whole exactly as a thirty-minute one does. A transcript too large
   for one bundle is cut at CUE boundaries into consecutive parts and delivered
   across sequential bundles, never bounced back to excerpts. A cue is never
   split; one whose own tokens exceed the cap becomes a part on its own.
6. Blocks are packed greedily into bundles under a token cap. An excerpt too
   big for the cap gets a bundle to itself rather than being dropped or split:
   losing evidence to a cap must be visible, never silent.
7. Bundles go to a small calibration batch first, then to larger batches. The
   calibration batch exists to turn the projection into a measurement before the
   larger spend.
8. Each bundle is written as XML — tags carry the structure and provenance, the
   transcript sits inside them as prose, because tagged boundaries are attended
   to reliably by a model. Each `<excerpt>` carries `form`, `part` and `parts`.
   **A whole transcript's parts land one per bundle, in ascending order, in
   strictly ascending bundles** — that is a property of slice 1's splitting, not
   something the packer arranges: a part is closed only when the next cue would
   carry it over the cap, so any two consecutive parts together exceed the cap
   and can never share a bundle.
9. The projection prints: videos indexed and selected, excerpt volume, bundle
   count, tokens per batch and in total, and **the chars-per-token factor
   itself**, stated openly as an estimate rather than buried as a constant. It
   also splits the corpus by path (R1008): how many videos went whole and how
   many as excerpts, the characters and projected tokens each path accounts
   for, how many whole transcripts exceed one bundle's cap, and each of those by
   id with the number of bundles it spans. **The cap is printed beside the
   spans**, for the same reason the token factor is printed beside the totals: a
   span reported without the bound that produced it reads as a property of the
   corpus rather than of the configuration. The path figures are derived from
   the submissions and the span figures from the bundles, and the suite asserts
   the two agree — intent and outcome disagreeing is a defect the projection
   should surface, not smooth over.

Then it stops. Continuing is a separate decision, and `extract` below is the
command that decision invokes — nothing in `estimate` reaches it.

### Extracting one batch, and stopping before the line

This is the first path in the project that spends anything, and every part of
its shape follows from that.

0. `find-best-mobo extract --batch N` requires `data/bundles/batch-N/`, naming
   `estimate` as what produces it (OD-9, R1005). A directory that exists and
   holds no bundles is a real value: nothing to extract, nothing spent, exit 0.
1. If the claim store already holds batch N, the run refuses **before** taking a
   reading or making a call. The store refuses a second append for a batch it
   holds, so extracting one again would pay for claims that could never land —
   better to learn that for nothing than for twelve bundles.
2. A reading is taken. It fixes the ceiling for this effort at ten points above
   itself, and it is checked immediately — only an account already at its weekly
   limit fails that check, and it should fail it before paying for a bundle to
   find out.
3. Bundles are extracted in name order, which is the order `bundle.py` numbers
   them in, which is recency order: a batch stopped part-way has done the most
   useful bundles in it rather than an arbitrary subset. Each bundle is handed
   to the extraction boundary, which writes the model's output to disk before
   anything reads it (R27), and the file that comes back is validated by the
   same schema `ingest` uses. **Python validates; the agent is never trusted to
   self-check** (BL-23).
4. A file that fails the schema is reported with every fault at once and the
   bundle is extracted ONE more time. A second failure sets the bundle aside: it
   is named in the output, it stays unconsumed, and the batch carries on (R9).
   Halting there would strand the bundles already paid for, which is the waste
   R27 exists to prevent. Both attempts' token counts are kept — a call that
   produced a malformed file is still a call that was paid for.
5. **Half way through the batch, the meter is read again.** That reading is what
   makes this a guard rather than a receipt: with only a reading at each end,
   the command would discover an overrun instead of preventing one, which is the
   failure R26 is written against. A batch of one bundle has no part-way point
   and takes two readings rather than a repeated one.
6. The moment a reading reaches the ceiling, the batch stops. **A stop is not a
   rollback.** Every bundle already extracted stays extracted, every validated
   claim is appended, and the output names what is done, what was set aside,
   what remains, and what the meter read. The exit code is non-zero, so nothing
   downstream mistakes a partial batch for a whole one.
7. An extraction that RAISES stops the batch rather than setting one bundle
   aside. A broken boundary will be broken for the next bundle too, and eleven
   more failed calls would spend eleven more times to learn the same thing.
8. A closing reading is taken, and the batch's claims are appended in one call.
   The report prints the four token components separately and never summed (R8)
   — a single total is dominated by cache reads, which on this machine outnumber
   fresh input by more than four orders of magnitude — and prints the readings
   beside them without converting one into the other. Tokens and subscription
   points are different quantities measured by different instruments; the
   conversion between them is a labelled estimate that belongs with the
   calibration record, not a line in a summary.

## State and storage

- `config.toml` (repository root) — every pipeline lever, flat keys. In git.
- `aliases.toml` (repository root) — the hand-authored alias table. **Input,
  not cache**, which is why it sits beside `config.toml` rather than under
  `data/`: tracked normally, carried by a fresh clone, and reached through the
  `alias_table_path` lever so it never follows `data_dir` (OD-11, R1007). It
  lived at `data/aliases.toml` until 2026-08-24, kept in git by a `git add -f`
  that every ignore-respecting tool misread; `tests/test_alias_table_location.py`
  is what stops it drifting back.
- `data/index.jsonl` — one JSON record per video. Local-only, gitignored, as
  the whole `data/` tree will be: the corpus never enters git.
- `data/transcripts/<video_id>.json` — one cached transcript per video, timed
  cues in file order, the video's description verbatim (OD-8, R1004), and
  `source_format`: which caption format the cues were parsed from (OD-24,
  R1013). `json3` is YouTube's own segment format, one event per line of
  speech; `vtt` is the same track rendered for display, which for automatic
  captions is ROLL-UP — a cue per display frame, so every line arrives three
  times and a name inside a two-line frame inherits the FIRST line's timestamp.
  The VTT path de-duplicates on parse, so no cached transcript holds the same
  line three times whichever route produced it, but the two are not
  interchangeable: only json3 carries per-segment timing, and a question about
  one claim's timestamp has a different answer depending on the path. A record
  written before this field reads `unknown` — never guessed at, because a guess
  would be true today and a lie the moment anyone replays the reasoning. A
  record written before descriptions were stored has no such key and loads with
  an empty one — R1004 forbids a forced refetch, so the existing cache keeps
  working and simply carries no description signal. The cache is the resumability story: it is what a rerun
  reads instead of refetching. **The DIRECTORY is itself an artifact.** `fetch`
  creates it whether or not it caches anything, so its absence means fetch has
  not run and `select` and `estimate` refuse; an empty directory means fetch ran
  and got nothing, which is a real state they both accept (OD-9, R1005). Before
  that rule the directory appeared only on the first successful write, so the
  two were indistinguishable on disk.
- `data/failures.jsonl` — this run's fetch failures, rewritten on every record.
  It doubles as the next run's retry list.
- `data/selected.jsonl` — one record per pending video: the video, why it was
  included or excluded, its body mentions, its distinct-canonical count, and
  `has_transcript` — whether that video's transcript was in the cache when it
  was selected. The last is written here rather than re-derived downstream so
  that `select` and `estimate` print the SAME coverage figure; two stages each
  counting for themselves would diverge the moment their populations do, and
  they already do (R1012).
- `data/bundles/batch-N/bundle-NNN.xml` — the work bundles, one file each,
  byte-identical across runs given the same cache and configuration.
- `prompts/extract-claims.md` (repository root) — what the extraction agent is
  asked. **Input, not cache**, and tracked in git for the same reason
  `aliases.toml` is: R23's comparability claim rests on the prompt being a
  versioned artifact, so a change to it is a diff someone can point at when two
  batches disagree. Reached only through `extract.prompt_text`.
- `data/claims/batch-N/bundle-NNN.json` — what the model said about one bundle,
  written verbatim the moment it arrives and never tidied, deleted or repaired.
  Not the store: these are unvalidated, one per bundle, and a file here that
  failed validation stays here as the record of a spend that already happened
  (R27). `data/claims.jsonl` is the validated store the ingest step appends to,
  and nothing moves between the two except through that step.

## Absence is not emptiness

Every stage boundary in this pipeline is a file, and the two ways a file can
fail to give you data are different facts. BL-7 measured what happens when they
are conflated: `estimate` read a missing `data/index.jsonl` as zero videos
indexed, and the projection — the one number the owner spends against — was
silently wrong in a way indistinguishable from a real empty corpus.

`artifacts.py` holds the rule. An ABSENT artifact names itself and the command
that produces it, and the stage exits 1. A PRESENT-but-empty one is a real value
and is reported as what it is: an empty index is a channel with nothing in
range, an empty transcript cache is a corpus with no captions, and a recall
report over the latter is all zeros rather than a refusal. `MissingArtifact`
subclasses `FileNotFoundError`, so no existing handler had to learn a new
exception.

The per-video tolerance is a different rule and is untouched: a selected video
with no cached transcript has nothing to excerpt and is not an error, because a
title hit needs no caption track (R2, R24). What R1005 governs is the absence of
the cache ITSELF.

## Known rough edges

- **Upload dates from flat listing are approximate, and the boundary leans
  into it.** Flat extraction only carries a date at all because the
  `youtubetab:approximate_date` extractor argument is set, and what it fills is
  the timestamp, not an exact upload date. The timestamps are bucketed —
  observed values land mid-month, and two videos can share one — so instead of
  trusting them at the boundary, the range comparison moves the start date back
  by a fixed two-month slop. Nothing uploaded from 2023-01-01 onward can fall
  out; the price, accepted by owner ruling, is that some late-2022 videos enter
  the index as pending. The date recorded on each video is always the real
  (approximate) one, never the shifted one.
- **A missing duration classifies as a Short.** Missing or null duration is
  treated as 0, which is at or below the Shorts threshold. Deliberate — it
  never crashes — but it means a listing that omitted durations would
  quietly exclude everything as Shorts. The `index` summary therefore counts
  these separately, split by listing shape, and warns on any dated entry that
  lacks a duration — which is what turns that silent failure into a visible one.
  The counts deliberately overlap the Shorts count rather
  than being subtracted from it: a zero-duration video really was excluded as a
  Short, and the second line says why that may be wrong.
- **A video with no date at all is recorded as `0001-01-01`.** When an entry
  carries neither an exact upload date nor a listing timestamp, the record
  keeps its out-of-range exclusion visible rather than inventing a plausible
  date. A timestamp of zero is not this case — it is a real date, 1970-01-01.
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

- **A whole submission's parts partition the transcript, and the arithmetic says
  so.** `split_whole` takes cues in order and never splits one, so the parts'
  texts sum to `transcript_characters(transcript) - (part_count - 1)` — one
  joining space consumed at each split. That equality is the proof no speech was
  dropped and none repeated; it is asserted rather than described. A part's span
  runs from its first cue's start to its last cue's START, the convention
  `cut_windows` already uses because a cue's end is not known.
- **A merged excerpt is the speech in its span, exactly once.**
  `merge_overlapping` takes the video's transcript and RE-CUTS the merged span
  from the cues rather than gluing two window texts together (OD-4, R1000). The
  bound is a property, not an estimate: merged spans are disjoint and cue
  membership is decided on the cue's start alone, so a video's summed excerpt
  characters can never exceed `transcript_characters(transcript)` — the same
  single-space join an excerpt uses, and also the denominator R28's saturation
  ratio needs, so the two cannot drift apart. Before this, partial overlap
  concatenated and the inflation compounded with mention density: BL-10 measured
  4.8x on a 33-minute review, and the real corpus on 2026-08-24 gave 57x on a
  91-minute one. The whole-corpus projection fell from 232.7M characters to
  19.9M.
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
- **A fenced answer costs a whole retry.** The model's output is written
  verbatim and validated as it stands — no fence stripping, no repair — so an
  answer wrapped in a code fence fails validation as "not JSON" and the bundle
  has to be read again. Deliberate: a stage that tidied up the output would hide
  the misunderstanding the prompt needs to fix, and the file on disk is what
  shows the reason. The prompt says so twice, and this is the cost if it stops
  working.
- **A batch's claims are appended in ONE call, at the end of the run.** The
  store refuses a batch it already holds (that is the mirror of R27: no
  completed work is silently rewritten), so appending per bundle would be
  refused from the second bundle onward. One append per batch is the only shape
  that works, and it has a consequence worth stating: the bundles a stopped
  batch never reached cannot later be added to the store under the same batch
  number without moving the store aside. Nothing model-produced is lost either
  way — every claims file is on disk as it was produced (R27) — but the store's
  record of that batch is closed once the run that opened it ends.
- **`./scripts/run.sh` has no `extract` stage.** The wrapper validates a fixed
  list of stage names and forwards no flags, and its own text promises that
  nothing in it spends money. Extraction is run directly, one batch at a time:
  `uv run find-best-mobo extract --batch 1`.
- **A run with no failures does not rewrite `data/failures.jsonl`.** The ledger
  is written when a failure is recorded, so a clean rerun after a failing one
  leaves the old file in place and it reads as current. Raised for a ruling
  rather than fixed unilaterally — see the slice 2 pull request.
