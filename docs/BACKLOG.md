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

- **BL-23** — **Build Stage B: extraction.** Stage A is complete and usable —
  index, fetch, normalize, select, excerpt, bundle and estimate all run, and
  `estimate` stops at the cost projection exactly as R7 requires. Nothing
  consumes what it writes. Stage B is the first stage that reads a bundle and
  produces knowledge, and until it exists every Stage A improvement sharpens an
  input to a stage that is not there. Per the design (§"Stage B — Extraction"):
  an agent reads ONE bundle and writes ONE claims file — for each board
  mentioned, what was said, in which claim category, about which subject (VRM
  capacity, voltage/firmware safety, memory behaviour, features, value), with
  the short verbatim snippet, its timestamp, and its video's title and id. Low
  effort: this is reading comprehension, not reasoning. An ingest step validates
  each file against the schema and appends it to the append-only claim store,
  tagged by batch. **Between batches the pipeline stops.**

  What this item covers, and what it does not:

  1. **The claim schema**, as a file, with the five subjects and the claim
     categories named in the design. Python validates against it; the agent is
     never trusted to self-check.
  2. **The ingest step** — Python, no inference — that validates one claims file
     and appends it to the store. Invalid file: rejected loudly, nothing
     appended, the bundle stays unconsumed.
  3. **The append-only claim store**, tagged by batch, so a rerun cannot
     silently rewrite a claim already paid for (R27).
  4. **The extraction agent's prompt and its contract**, in the repository, so
     the same bundle produces a comparable file twice.
  5. **The explicit continue command** R7 promises. `estimate` stops and says
     continuing is a separate decision; today there is no command that decision
     could invoke. This is that command, and it must take one batch at a time.
  6. **The R26 spend guard around it** — a real usage reading before a batch,
     after it, and part-way through a long one, against the 10% weekly cap,
     stopping BEFORE the line rather than discovering the overrun after. The
     reader is `omarchy-agent-usage-claude --limits-only --force`.
  7. **R8's calibration record** — the first batch is the small calibration
     batch; projected against actual is recorded and the chars-per-token factor
     corrected for later projections. That closes S3.

  **Not covered here**, deliberately: Stage C synthesis, Stage D inheritance and
  Stage E report are separate items. This one ends when a calibration batch has
  been extracted, validated, stored and its factor corrected.

  **Why it needs its own approval:** the whole backlog to date is Stage A. The
  owner's 2026-08-19 blanket approval covered BL-1 through BL-13, all of which
  are input-side. This is the first item that spends model budget on the real
  corpus, so it is approved as its own decision rather than inherited from that
  one. — filed by: the operator of the 2026-08-20 local-lane run, at the owner's
  instruction, after confirming Stage A runs end to end on the real channel


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

### BL-15 — The zero-duration warning cries wolf on every real run

The `index` command warns loudly when more than one video reports no duration,
on the reasoning that a missing duration reads as 0, classifies as a Short, and
silently drops a real video. Exactly one is expected and harmless — a stream in
progress reports no duration, and he can only be live in one place at a time.

On the first index run against the real channel after the `timestamp` fix
landed, **eight** videos reported no duration, so the warning fired:

```
Found 1215 videos on the channel; index written to data/index.jsonl
  910 outside the date range
  20 excluded as Shorts
  285 kept
  8 with no duration reported

!!!! WARNING: 8 videos reported no duration.
```

All eight were then read out of `data/index.jsonl`:

| video id | date | was_live | inclusion | title |
| --- | --- | --- | --- | --- |
| `0pgWWFCvf6w` | none | false | excluded_short | simple and effective DDR5 cooling |
| `FUCLMRq5oOM` | none | false | excluded_short | motherboard collection: ASUS WS Z390 PRO #motherboard |
| `OffiCcQMK-4` | none | false | excluded_short | Adding a POST code display to the Gigabyte B850M Force |
| `PB1iPWcibbw` | none | false | excluded_short | stock MSI 3060Ti Gaming X vcore regulation. #Shorts |
| `T94q9a4JZiI` | none | false | excluded_short | Buildzoid's collection: Gigabyte B850M Force |
| `qd3flkh_eg0` | none | false | excluded_short | My first LN2 overclocking motherboard |
| `rNMZqqg1NI4` | none | false | excluded_short | VRM cooling upgrade for an itx motherboard #overclocking |
| `wEFp9Eo-QZ4` | none | false | excluded_short | Buildzoid's motherboard collection: ASRock 970M Pro3 |

**Every one of them is a genuine Short**, by title alone — two say so in their
own hashtags, the rest are the short-form collection clips. None is a stream in
progress; `was_live` is false for all eight. So the outcome is right:
`excluded_short` is exactly where they belong, and no real video was dropped.

**The warning is a false positive, and it is a permanent one.** Its premise —
"only one video can legitimately report no duration" — is wrong. A flat channel
listing returns Shorts with no `duration` field at all, and the same eight rows
also carry no date in either field (`upload_date` absent AND `timestamp`
absent, which is why the table above reads `none` where the sentinel
`0001-01-01` is recorded). That is a distinct listing shape for Shorts, not an
anomaly, and it will be there on every run.

Two costs, and the second is the one that matters:

1. Every index run ends in a 72-character banner of exclamation marks naming
   eight video ids and telling the operator that real videos are vanishing. They
   are not. An operator who checks — as this one did — spends the time for
   nothing, every run.
2. **It destroys the signal it exists to carry.** The warning was written for a
   real failure mode: a genuine long video coming back with no duration and
   being silently excluded. With eight permanent false alarms in the way, a
   ninth id appearing in that list is invisible. The check that was supposed to
   catch a silent drop now guarantees one goes unnoticed.

Directions, not mutually exclusive:

1. **Judge on evidence, not on count.** A listing entry that has no duration
   *and* no date in either field is the Shorts shape; one that has a real date
   but no duration is the anomaly worth shouting about. Warn on the second only.
2. **Use what the listing already says.** If the flat entry carries any Shorts
   marker of its own, classify on that rather than inferring a Short from a
   duration of zero — the inference is what makes a missing field
   indistinguishable from a genuine short video.
3. **Keep the loud banner for the real case and make the ordinary case a
   count.** "8 Shorts reported no duration (expected)" on one line, with the
   banner reserved for an entry that does not fit the Shorts shape.

Whichever direction is taken, this deserves a test that a dateless,
durationless listing entry does NOT trip the warning, and that a dated one with
no duration still does — the pair that tells the two cases apart. Note that
`docs/escapes.md` ESC-21 already records the cost of trusting fixtures that
agreed with the code and disagreed with the real listing shape; this is the same
listing, still not fully described by the fixtures.

— filed by: the operator of the 2026-08-20 local-lane run, from the first real
index run after the `timestamp` fix (PR #67) landed

### BL-20 — The driver will eventually commission a superseded plan slice

`docs/plans/whole-transcript-threshold.md` is the owner's, `CODEOWNERS`-held, and
partly wrong: OD-13 (and OD-5 before it) answered its "pending" ceiling
uncertainty, and its slice 1 builds R28's routing without R5's clustering,
without R1000's re-cut and with no account of a transcript larger than a bundle.
Two oracle handoffs say to leave it alone and simply never build its slice 1.

The gap is that "never build it" is nobody's job to enforce.
`.claude/scripts/deliver-phase.sh` walks every `docs/plans/**/*.md` in sorted
path order and dispatches an orchestrator for the first plan whose `status:` is
not `merged` and for which no `feat/<slug>` branch has merged. No
`feat/whole-transcript-threshold` branch will ever merge, because the work is
being built under a different slug, so once the plans ahead of it are built the
driver reaches this one and commissions the superseded slice — unattended, with
every check green, because the plan resolves and the branch name matches.

Directions: the owner marks it `status: merged` (the field the template already
documents for work that landed some other way), or deletes it, or drops slice 1
and R28 from it. Any of the three closes it; nothing an agent may write does,
which is why this is filed rather than fixed. — filed by: steward (OD-13 plan
`capped-whole-transcript-path`)

### BL-21 — A superseded requirement id is uncoverable, and coverage says NOT PLANNED forever

`.github/scripts/coverage.sh` builds its requirement universe from `docs/DESIGN.md`
§5 and from column-anchored `**Requirements added:**` lines in
`docs/DESIGN.oracle.md`. It does not read `**Requirements superseded:**`. The
oracle ledger is append-only, so a superseded id — R1001, superseded by OD-13 —
stays in that universe permanently while no plan can honestly claim it: the
behaviour it describes is deliberately not being built.

The effect is that `coverage.sh` reports `R1001 NOT PLANNED` and exits 1 from now
on, and `AGENTS.md`'s definition of done ("every requirement of the design …
covered by a merged plan", mechanical via `coverage.sh`) can never be satisfied
again. The pressure this creates is the harmful part: the cheapest way to make
the report green is for some plan to name R1001 in its `covers:`, which is
exactly the over-claim the adequacy note exists to expose.

Directions: teach `coverage.sh` to subtract ids named by
`**Requirements superseded:**` at the ledger's head; or report superseded ids as
their own class, the way non-functional requirements are already excused; or rule
that a superseding decision's requirement text must name the id it retires so a
reader can pair them. All three live in `.github/scripts/`, a gate path — and the
same hole exists in the template, so the fix probably belongs upstream. — filed
by: steward (OD-13 plan `capped-whole-transcript-path`)

### BL-22 — R1001's false gap livelocks the driver on a steward for OD-5

Measured, not predicted: on 2026-08-20 the driver dispatched a steward for
**OD-5** — a decision OD-13 superseded in full — and that steward wrote no plan,
because OD-5's only requirement R1001 is design history (retired by R1008), the
plan that once implemented it was already re-cut to OD-13 and merged
(`docs/plans/oracle/capped-whole-transcript-path.md`), and naming R1001 in a
`covers:` is the over-claim OD-20 forbids by name. This filing is the record of
that dispatch; nothing else in the repository would hold it.

The mechanism is BL-21's hole reaching a third path, and the consequence is
worse there than in the report. `.claude/scripts/deliver-phase.sh` step 4 takes
`coverage.sh`'s gap list, maps each `R>=1000` gap back to the decision whose
`**Requirements added:**` line names it, and emits `PHASE=STEWARD` whenever that
set is non-empty — before step 5's built-or-unbuilt plan walk and before
`PHASE=PLAN`. R1001 is a permanent gap, so the map permanently yields OD-5 and
the driver emits `PHASE=STEWARD ODS=OD-5` on every cycle and can never reach
orchestration, milestone planning or acceptance again. BL-21 framed the harm as
a definition of done that can never be satisfied plus pressure to over-claim;
the sharper fact is that the delivery loop no longer advances at all, and each
cycle spends a full unattended session re-deriving the supersession from the
ledger in order to stop. A session that does not re-derive it writes a plan for
a behaviour the owner reversed, with every check green — the steward gate cannot
catch it, since `oracle-decisions.sh` asks only that a cited decision has
landed, and OD-5 has.

Note this also suspends BL-20's hazard rather than resolving it: the driver
cannot reach the plan walk that would commission `whole-transcript-threshold`
slice 1 while it is stuck here, so fixing this one re-arms that one, and OD-19's
prohibition is what has to hold at that moment.

Directions: the fix OD-20 already recommends for `coverage.sh` — subtract ids
named by column-anchored `**Requirements superseded:**` lines and report them as
their own excused class — closes this too, since the dispatch reads that
script's gap list and nothing else, which argues for doing it there rather than
teaching a second parser in `deliver-phase.sh`; failing that, skip an `OD-<n>`
all of whose added requirements are superseded, at the dispatch. A gate-side
backstop worth considering either way: have `oracle-decisions.sh` fail a plan
under `docs/plans/oracle/` that cites only superseded decisions, so a steward
that misses the supersession is stopped by a check rather than by its own
reading. All of these live in `.claude/scripts/` and `.github/scripts/`, both
owner-owned gate paths, and the hole is the template's as BL-21's is. — filed
by: steward (dispatched for OD-5; wrote no plan)

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
- **BL-16** — Does R1002 (OD-6) have to recover an alias split across a **cue
  boundary** — `toma` ending one cue and `hawk` beginning the next — or only a
  split inside one cue's text? R1002 fixes the rule ("the concatenation of
  adjacent whole tokens", every alias space landing on a token boundary) but
  never says what text the rule is applied over, and today
  `find_mentions` normalizes and scans **one cue at a time**
  (`src/find_best_mobo/aliases.py`), so a name the captions break at a cue
  break stays invisible after the token-join rule lands. The evidence does not
  settle it either: BL-8's three measured failures — `toma hawk`,
  `aor us master`, `air us elite` — were all tested as within-cue text, and no
  cross-cue case has been measured. The shipped VTT fixture shows auto-caption
  cues breaking mid-phrase (`...Taichi board` / `has a twelve phase...`), so
  the case is plausible but unquantified. Proposed default: **no cross-cue
  joining** — the rule applies within one cue's normalized text, and the plan
  scopes cue-spanning splits out with that stated. **HIGH**: the other answer
  changes `find_mentions`'s shape and therefore the plan's slice boundaries —
  it would have to scan cue-joined text and map every match offset back to the
  cue it started in — and it puts a second question on the table that OD-6
  does not answer, namely which `start_seconds` a mention spanning two cues
  carries. That field is not cosmetic: R5 cuts every excerpt window from it and
  the report's timestamped links are built on it, so a wrong answer is
  expensive to reverse. Ruling this way or that also decides whether OD-6 needs
  a fourth slice. — filed by: steward (OD-6 plan; the same question the closed
  PR #85 draft self-ruled on, preserved at `docs/oracle/od-6-plan-draft.md`)
- **BL-17** — What are BL-8's 52 measured caption variants? R1002 (OD-6) says
  "BL-8's measured 52-variant set lands as a fixture", but BL-8 records only the
  count, the three named failures (`toma hawk`, `aor us master`,
  `air us elite`) and the damage classes — the list itself is in no commit, no
  journal entry and no run record, so the fixture R1002 asks for cannot be
  recovered, only rebuilt. Proposed default: reconstruct 52 variants from the
  shipped table's own canonicals across BL-8's damage classes, with the named
  failures verbatim plus a `never_match` reject set, and state inside the
  fixture that it is a reconstruction rather than the original measurement.
  **LOW**: it is fixture content only — no signature, slice boundary or external
  format turns on it, and the alternative (pin the observed failures alone) is a
  smaller fixture in the same file. Two facts worth a ruling anyway: BL-8's
  arithmetic (49 matched + 3 failures = 52) leaves no room for the hyphenated
  `steel-legend` it also reports failing, and the preserved draft's
  reconstruction had five failing variants rather than three — so a
  reconstruction asserting "52" carries a number the evidence does not quite
  support. — filed by: steward (OD-6/OD-15 plan `caption-split-aliases`;
  proceeded on the default)
- **BL-18** — What is the real B850I review's title? R1003 (OD-7) names the
  regression as "the real B850I review's title auto-includes on its chipset",
  and that title is in no commit, no journal entry and no run record. BL-9
  records the board (`MSI MPG B850I Edge TI`), the 33-minute duration and the
  measured zero `B850` matches in title and body — not the title as YouTube
  spells it — and `data/index.jsonl`, which would hold it, is gitignored and
  absent from a fresh clone. Proposed default: carry BL-9's board name verbatim
  inside a plainly-labelled reconstructed title, with the test's docstring
  stating that the original is unrecoverable, that only the board name has
  measured provenance, and that nothing asserts on the invented wording.
  **LOW**: it is test-fixture content — no signature, slice boundary or external
  format turns on it, and the alternative (assert on the board-name token alone,
  with no surrounding title) is the same test one string shorter. The provenance
  rule applied is the one OD-16 already set for R1002's fixture: a
  reconstruction declares itself, and only what was observed claims measured
  provenance. — filed by: steward (OD-7 plan `itx-chipset-variant`; proceeded on
  the default)
- **BL-19** — When `--help` follows a subcommand — `find-best-mobo aliases
  --help` — whose help prints, the subcommand's or the dispatcher's? R1006
  (OD-10) says every flag a subcommand *documents* is reachable from the CLI
  and that the dispatcher forwards arguments it does not recognise, but
  `-h/--help` is the one token the top-level parser owns today: argparse
  registers it automatically and consumes it before dispatch, so the rule and
  the shipped behaviour disagree on exactly this argument. It matters because
  `--check` is documented nowhere else — a subcommand whose help is
  unreachable documents its flags only in source. Proposed default: **forward
  it** — the top-level parser stops registering help automatically, prints its
  own help only when no subcommand was named, and otherwise passes `--help`
  through, so `find-best-mobo aliases --help` prints the `aliases` parser's
  help; `find-best-mobo --help` and a bare `find-best-mobo` keep today's output
  and exit codes. **LOW**: it changes one console output and nothing else — no
  slice boundary, no Signatures block, no external format, and reversing it is
  deleting one branch in `cli.py`. Filed rather than assumed because it is a
  deliberate divergence from what the CLI does today, and the owner may prefer
  the top-level help to stay reachable after a command name. — filed by:
  steward (OD-10 plan `subcommand-flag-forwarding`; proceeded on the default)
- **BL-24** — May the pipeline take a subscription-usage reading itself, or must
  a reading be handed to it? Refiled from the web test lane's ledger (its
  `BL-20`; that lane's ids collide with this branch's and its branch is frozen
  for the post-mortem, so the item re-enters here under a fresh id). R26 names
  two readers — `claude -p "/usage"` and `omarchy-agent-usage-claude
  --limits-only --force` — and then says "The Python pipeline itself still
  cannot read them", while S3 calls its criterion mechanically checkable
  *because* the omarchy reader returns JSON on this machine. One sentence puts
  the probe outside Python; the other leans on it being reachable, and R8's
  projected-against-actual record needs whichever answer is true before it can
  be built. **HIGH**, and ruled by the owner in chat on 2026-08-24 (recording
  follows in `docs/DECISIONS.md`): on the local machine the run may read usage
  — `omarchy-agent-usage-claude --limits-only --force` first, falling back to
  the `claude -p "/usage"` reader if it fails; a web session has neither and
  relies on other means (time, pull-request counts, or similar). And before
  every unattended run, the agent asks the owner to confirm WHICH limit governs
  the run and WHAT value to use for it — the owner prefers that confirmation
  even where a default exists. — filed by: the 2026-08-24 attended session, at
  the owner's instruction
- **BL-25** — What is "actual usage" in R8 and S3, and what does the reported
  delta compare? Refiled from the web test lane's ledger (its `BL-21`, same
  reason as BL-24). The projection is in tokens and its factor is
  chars-per-token (R7), while the only readings the design names return
  percentage points of a weekly subscription limit and no token count at all
  (R26). The two quantities are not in the same units, so no chars-per-token
  correction follows from a points reading, and R8's three clauses — record
  projected against actual, report the delta, correct the factor — cannot all
  be satisfied from the same number. **HIGH**, and ruled by the owner in chat
  on 2026-08-24 (recording follows in `docs/DECISIONS.md`): record both and
  keep them apart, and additionally attempt an explicit token-to-points
  conversion estimate, with every assumption behind it written down so the
  reasoning can be investigated later. Note the ruling touches what R8/S3 mean,
  and `docs/DESIGN.md` is owner-landed — the design-text correction stays with
  the owner. — filed by: the 2026-08-24 attended session, at the owner's
  instruction
- **BL-26** — Where does the corrected chars-per-token factor land, so that
  subsequent projections use it? Refiled from the web test lane's ledger (its
  `BL-22`, same reason as BL-24). R8 says the factor is corrected "for
  subsequent projections"; today it is a `config.toml` key, R17 makes the cost
  levers configuration, and R23 promises byte-identical output "given the same
  cache and configuration"; nothing says whether the correction is written back
  to configuration, published as a data artifact the projection prefers, or
  only reported for a human to apply. **HIGH**, and ruled by the owner in chat
  on 2026-08-24 (recording follows in `docs/DECISIONS.md`): the proposed
  default stands — the calibration stage writes `data/calibration.json`,
  `estimate` prefers its measured factor over `config.chars_per_token` and
  prints which source it used and whether the number is a measurement or a
  guess, and the configuration key stays the fallback and is never rewritten by
  a stage. — filed by: the 2026-08-24 attended session, at the owner's
  instruction
