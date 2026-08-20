# Backlog — Finding Best Mobo by Buildzoid

The standing queue of what *might* be built, as opposed to a plan, which covers
the one change being built now. Two sections, and the difference between them is
the owner's approval:

- **Approved** — the owner has said yes. An agent working unattended implements
  these top to bottom, and keeps going until the list is done or it is truly
  blocked (`AGENTS.md`, "Work queue").
- **Proposed** — ideas, written as text, **never coded unprompted**. They move
  up when the owner moves them.

## Approved

_(nothing yet)_

## Plan rework

Objections to what a plan explicitly says, raised while building it. Per the
2026-08-14 ruling in `docs/DECISIONS.md`, the plan is implemented as written and
the objection is recorded HERE rather than argued in a pull request. This list
is the agenda for the next plan revision; an item leaving it means the plan was
fixed, not that the objection lapsed.

**Every item carries a `BL-<n>` id**, the next unused integer, and ids are never
reused — a resolved item keeps its number rather than freeing it, so a citation
written today still means the same thing in six months.

The ids exist so an item can be CITED by id rather than by quoting its text,
the way `docs/escapes.md` entries already are. Ids run across both sections,
because a proposal is evidence about the design exactly as a rework item is.

- **BL-1** — **`corpus-and-checkpoint` slice 2 — a clean rerun leaves a stale failure
  ledger.** `data/failures.jsonl` is rewritten when a failure is recorded, so a
  run with no failures never rewrites it and the previous run's file survives,
  reading as current. Implemented as specified. Options: rewrite unconditionally
  at end of run (preferred), delete on a clean run, or keep it and rename the
  concept to "the last run that had failures".
- **BL-2** — **`corpus-and-checkpoint` slice 2 — the plan cannot express "no captions".**
  `fetch_transcript` is typed `-> Transcript`, leaving no way to signal a video
  with no caption track, which the design treats as an ordinary outcome. Built
  with a `NoCaptions` exception declared in the shared contract instead. The
  plan's signature block should carry it.
- **BL-3** — **`corpus-and-checkpoint` slice 2 — the plan does not say which module a type
  lives in.** The shared contract had to assign them, and got `FetchFailure`
  wrong: placing it in `transcripts.py` is circular. Two blind authors can
  disagree on placement while agreeing on behaviour, so the plan should state it.
- **BL-4** — **`corpus-and-checkpoint` slice 3 — the alias table is filed under a
  gitignored path.** The plan puts it at `data/aliases.toml`, but `data/` is
  gitignored because the corpus never enters git (R21). The alias table is
  hand-authored input, not cached corpus, so a fresh clone would have none. Built
  at the stated path via `git add -f`; it belongs outside `data/`.
- **BL-5** — **`corpus-and-checkpoint` slice 3 — the slice's stated deliverable cannot be
  reached from the command line, and the plan contradicts itself.** It promises
  `uv run find-best-mobo aliases --check`, but its file list excludes
  `src/find_best_mobo/cli.py`, and slice 1's design decision — the dispatcher
  holds no subcommand table so no two slices edit it — means the top-level
  `parse_args` rejects `--check` before dispatch: `error: unrecognized arguments:
  --check`. Built to the file list, so `run(config, Namespace(check=True))` works
  and is tested, while the CLI path does not. **This is the first item worth
  ruling on:** it is not cosmetic, it blocks the deliverable, and it recurs for
  every later subcommand that takes a flag — slices 4 and 5 both do. Fixing it
  means one small change to `cli.py` (pass unrecognised arguments through to the
  subcommand), which is a design decision about the dispatcher and therefore the
  owner's.
- **BL-6** — **`corpus-and-checkpoint` slice 3 — the plan does not say where the alias
  table is loaded from.** Both blind authors independently chose
  `config.data_dir / "aliases.toml"` and so agreed, but the plan says only
  `data/aliases.toml`, which reads as a fixed path. Worth stating.
- **BL-7** — **`corpus-and-checkpoint` slice 5 — a missing index makes the projection
  understate itself silently.** `project` counts `videos_indexed` as 0 when
  `data/index.jsonl` is absent, so `estimate` still prints a projection whose
  denominator reads as a real number rather than an absence. Neither plan nor
  contract said what to do, so it was built the forgiving way. A cost projection
  the owner spends against should probably refuse rather than under-report.
- **BL-8** — **`corpus-and-checkpoint` slice 3 — a split compound word is invisible to the
  alias table.** Auto-captions routinely split product names, and the folding
  rule in `normalize` only joins letter-to-digit transitions, never two
  multi-letter words — so `toma hawk`, `aor us master` and `air us elite` match
  nothing at all, silently. Found offline, before any real run: of 52 mangled
  variants tested against the shipped table, 49 matched and these were the real
  failures. (A hyphenated family name — `steel-legend` against the table's
  `steel legend` — fails for the related reason that `normalize` keeps hyphens;
  marginal, since real product naming rarely hyphenates a family name.)
  Not a simple fix, which is why it is here rather than done: joining any two
  multi-letter words is exactly what welds `the b650` into `theb650` and makes
  the chipset unmatchable, the trap both blind authors independently avoided.
  Plausible directions: split-tolerant surface forms in the table itself (cheap,
  no rule change, but hand-maintained), or matching against a
  whitespace-stripped copy of the text as a second pass. Needs a ruling before
  either is built.
- **BL-9** — **`corpus-and-checkpoint` slice 3 — an ITX board's own chipset is invisible.**
  ITX boards are named `<chipset>I` — `B850I`, `X870I`, `B650I` — and the
  matcher's right boundary `(?![a-z0-9])` refuses to match `b850` inside
  `b850i`. Measured against a real 33-minute review of the MSI MPG B850I Edge
  TI: **`B850` matched zero times**, in a video that is about nothing else. It
  fails in titles too, so the automatic title-hit include misses as well. Every
  ITX review in the corpus is affected, and ITX is exactly where one-DIMM-per-
  channel memory overclocking lives. The boundary is right in general (it stops
  `b650` matching inside a longer token); the fix is probably explicit `b850i`
  -style surface forms, or a suffix rule. Needs a ruling.
- **BL-10** — **`corpus-and-checkpoint` slice 5 — merged excerpts inflate the corpus about
  fivefold, and the cost projection with it.** `merge_overlapping` concatenates
  on partial overlap, and with many overlapping windows the concatenation
  compounds. Measured on the same real video: a 28,438-character transcript
  produced a single 137,246-character excerpt — **4.8x the entire transcript**,
  spanning the whole video. `docs/architecture.md` described this as a slight
  over-estimate; that description was written from theory and is corrected in
  the same commit as this entry. The inflation scales with mention density, so
  it is not a fixed factor that can be divided out. This makes the checkpoint's
  projected token count materially wrong, which is the one number the checkpoint
  exists to produce. Fixing it means giving `merge_overlapping` access to the
  cues so it can re-cut the merged span rather than concatenate — a signature
  change, so it is a plan question.
- **BL-11** — **`corpus-and-checkpoint` — the video description is never read, and it is
  where the chipset actually is.** The pipeline matches against the title and
  the transcript only. The real video's description carries
  `#AMD #ryzen #MSI #B850 #ITX` — the bare `#B850` that normalizes to `b850` and
  matches the canonical cleanly, on the very video whose title (`B850i`) and
  whose spoken audio both miss it. Hashtags are author-written, short, and
  unmangled by speech-to-text, so they are the highest-signal field available and
  the design does not use them. This is a `docs/DESIGN.md` question rather than a
  plan one: R1's index records id, title, date and duration, and nothing
  downstream has a description to read. Worth weighing against the cost — flat
  playlist extraction does not return descriptions, so fetching them is an extra
  request per video.

## Proposed

### BL-12 — Make template updates stop costing a manual intervention

Every `copier update` that conflicts fails the `template-sync` check and needs
an owner bypass to land. It has happened on both updates that conflicted (#4 and
#28) and it will happen on every future one, because the check demands a tree
byte-identical to a replayed update while a conflict is precisely the case
copier hands to a human. This entry is the standing intent to fix it rather than
keep paying it; the incident record is the ratchet's business and is being
logged separately, so nothing here depends on it having landed.

Three directions, not mutually exclusive, roughly in order of preference:

1. **Teach the check about conflicts.** Keep the replay's *pre-resolution* tree
   and require this repository's tree to differ from it only inside hunks copier
   marked as conflicted. Everything outside a conflict hunk stays byte-for-byte,
   so a hand edit smuggled into an untouched file still fails. This is the fix
   named in the escapes entry, and it belongs upstream in the template.
2. **Reduce how often conflicts happen at all.** Most of ours come from
   template-owned documents this project legitimately rewrote — the design doc
   skeleton above all. If the template kept its guidance out of files projects
   are expected to replace wholesale, the conflict surface shrinks.
3. **Make the bypass cheap and visible instead of ad hoc**, if neither of the
   above lands: a documented, logged path for "conflicted sync, resolutions
   reviewed", so the exception is a procedure rather than a judgment call made
   fresh each time under time pressure.

Both the check and the workflow it guards are owner-owned gate paths, so the
ruling is the owner's — this entry exists so it is not rediscovered from scratch
on the next update.

### BL-13 — Send whole transcripts instead of excerpts

Owner's proposal, after the real-transcript run. Excerpting exists to cut cost;
measured against real data it does the opposite.

On the one real video: the transcript is 28,438 characters (~7,100 tokens at the
current factor). Excerpting it produced 137,246 characters (~34,312 tokens).
**Sending the whole transcript is about 4.8x CHEAPER than sending the excerpts
cut from it**, on the only real measurement that exists.

The quality argument runs the same way. A seven-minute window truncates exactly
what makes him worth reading — the caveat three minutes later, the "but
actually" reversal, the passage where he revises an earlier verdict. An agent
holding the whole transcript can weigh a claim against everything else said
about it, which is the analysis the tiering in the design depends on.

It would also delete a whole class of defect at once: window tuning, the merge
double-count, the per-video cap, and the excerpt-window levers in R17 all stop
existing rather than needing to be got right.

What it does NOT remove: the index, the transcript cache and the failure ledger
are all still needed, and **selection still matters** — deciding WHICH videos to
send is the thing that bounds the spend. Only the excerpting stage becomes
unnecessary.

Worth weighing before adopting:
- A ~33-minute video is ~7k tokens, so ~1000 videos is ~7M tokens if everything
  were sent. Selection is what keeps that from being the real number.
- Long livestreams are included by owner ruling and could be far larger than any
  bundle cap, so a per-video size ceiling probably still has to exist somewhere.
- Bundling several whole transcripts into one request still needs a cap; that
  part of slice 5 survives even if excerpting does not.

This touches `docs/DESIGN.md` R5, R6 and R17, so it is recorded here as a
proposal and neither the design nor any plan has been edited.

## Uncertainties awaiting oracle ruling

_(nothing yet — filed by `/plan` when a design leaves a question open; format:_
_`BL-<n>` — the question, the proposed default, HIGH or LOW risk, one line on_
_why that class, and `— filed by: plan`.)_

- **BL-14** — Does the merged plan `capped-whole-transcript-path` still stand
  now that the owner's 2026-08-19 ruling (`docs/DECISIONS.md`) overrules OD-5's
  cap and amends R5/R28 to clustered excerpts with an uncapped whole-transcript
  path? Proposed default: supersede OD-5/R1001 citing that ruling and the
  amended design, mark the plan partly wrong, and have the steward re-cut it to
  the clustering design before anything builds it. **HIGH**: it changes a merged
  plan's slice boundaries and an external routing behaviour, and building the
  capped path as merged would implement a decision the owner has reversed.
  — filed by: owner (recorded from chat by the postmortem session)
- **BL-15** — Must OD-6/R1002's caption-split matching also recover a split that
  straddles two cues — `toma` ending one cue and `hawk` starting the next?
  `find_mentions` normalizes and scans one cue at a time, so a token-join rule
  stated over "the text being matched" leaves cue-spanning splits invisible, and
  R1002 does not say whether that population is in scope. Proposed default: no
  cross-cue joining — R1002's rule reads as tokens inside the text handed to the
  matcher, all three of BL-8's named failures sit inside one cue, and a
  cue-spanning match has no answer to which cue's start time the resulting
  `Mention` carries. **HIGH**: the other answer changes `find_mentions`'s shape
  and with it the plan's Signatures block and a slice boundary — it would have to
  scan the cues joined into one string and map every match offset back to a cue
  start, and R22's one-transcript-at-a-time property would need restating over
  that joined text. The first OD-6 plan (PR #85, preserved at
  `docs/oracle/od-6-plan-draft.md`) was blocked by the review gate for ruling on
  exactly this question itself; the re-cut plan is pending this ruling.
  — filed by: steward
- **BL-16** — What is BL-8's measured 52-variant set? R1002 says "BL-8's
  measured 52-variant set lands as a fixture", but the list itself was never
  committed — the backlog entry records the count (49 matched + 3 failures), the
  three named failures and the damage classes, and nothing in the tree, the
  journal or `docs/runs/` holds the variants. Proposed default, proceeded on in
  `docs/plans/oracle/caption-split-aliases.md`: reconstruct 52 spellings from
  the shipped table's own canonicals across BL-8's damage classes, with the
  three named failures verbatim, and record in the fixture that it is a
  reconstruction rather than the original measurement. **LOW**: it is fixture
  content only — no signature, slice boundary or external format turns on it,
  and replacing the reconstruction with the real set later is an edit to one
  JSON file. Two facts for the ruling: BL-8's arithmetic leaves no room for the
  hyphenated `steel-legend` it also reports failing, and the reconstruction has
  five failing variants rather than three.
  — filed by: steward
- **BL-17** — What title does OD-7/R1003's regression case use? R1003 says "the
  real B850I review's title auto-includes on its chipset", and that title is not
  in the repository: BL-9 records the board (MSI MPG B850I Edge TI) and the
  video's duration, while no index, fixture, journal entry or `docs/runs/`
  artifact holds the video's id or its title. Proposed default, proceeded on in
  `docs/plans/oracle/itx-chipset-variant.md`: use a declared reconstruction,
  `MSI MPG B850I Edge TI review`, with the test's docstring naming BL-9 as its
  provenance and stating that it is rebuilt rather than recorded, and assert
  that the video is admitted on `B850` by its title rather than asserting the
  string itself. **LOW**: it is fixture text only — no signature, slice boundary
  or external format turns on it, and substituting the real title later is a
  one-line edit. OD-15 ruled the same shape of question for R1002's fixture, so
  the default follows it: the reconstruction is declared, never quiet.
  — filed by: steward
- **BL-18** — Does OD-9/R1005 bind `aliases --check`? R1005 states its rule over
  "a pipeline stage", and the repository says this command is not one:
  `scripts/run.sh` calls it a diagnostic and `docs/plans/run-scripts.md` says
  "the pipeline is four stages, not five" — while `docs/architecture.md` calls
  it "the inspection stage". It is the one place in the tree that breaks
  R1005's second sentence: `not any(cache_dir.glob("*.json"))` refuses when the
  transcript cache exists but holds no files, so emptiness reads as absence.
  Proposed default, proceeded on in
  `docs/plans/oracle/refuse-on-missing-artifact.md`: bind it — an absent cache
  directory refuses naming `fetch`, a present-but-empty one reports every
  canonical as never matched, which is a true report of an empty corpus.
  **LOW**: one condition in one command — no slice boundary moves (slice 3
  exists for `select` either way), no Signatures block changes, no artifact on
  disk changes shape, and reversing it is restoring one `if`.
  — filed by: steward
