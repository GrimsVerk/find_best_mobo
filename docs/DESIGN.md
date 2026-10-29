---
title: Finding Best Mobo by Buildzoid
status: in-review     # draft | in-review | approved
created: 2026-08-14
related: []
---

# Finding Best Mobo by Buildzoid — Design Doc

## 1. Summary

A throwaway pipeline that turns one YouTube channel's spoken output into a
purchase decision. It collects every regular Buildzoid
([Actually Hardcore Overclocking](https://www.youtube.com/@ActuallyHardcoreOverclocking))
upload from 2023-01-01 to the present, keeps only the videos genuinely about
AM5 motherboards, extracts what he says about specific boards, and assembles a
tiered report. The tiers are the point: boards he **tested**, boards he
**reasons about or has heard about from people he trusts**, and boards that are
**near-twins in design** of an approved board and can be argued to inherit its
verdict. Every claim in the report carries the video title, a timestamped link,
and a short verbatim snippet, so any verdict can be spot-checked in seconds.
The dominant selection criterion is not performance — it is that the board must
not damage the CPU.

## 2. Problem & motivation

Motherboard reviews are dominated by feature checklists and synthetic
benchmarks, neither of which predicts the two things that actually matter for a
long-lived AM5 build: whether the power delivery has real headroom for a future
top-end part, and whether the vendor's firmware will do something to the CPU
that kills it. The ASRock AM5 degradation episodes made the second question
concrete — a board can be well-built and still destroy the chip through voltage
and firmware behaviour.

Buildzoid is the most useful single source on both questions, because he reads
the actual VRM topology and talks about firmware voltage behaviour rather than
scores. But the knowledge is locked in hundreds of hours of unstructured,
digressive video with no index. Finding "what does he think of the X870E boards
that won't cook my CPU" today means watching or scrubbing dozens of videos, and
the answer is spread across them rather than sitting in any one.

The purchase is imminent — a current AM5 CPU now, with a Zen 6 drop-in later —
so the cost of getting it wrong is a dead CPU or a board that throttles under a
part released in a year's time.

## 3. Goals and non-goals

**Goals**

- Produce one decision-ready report, tiered by evidence strength, with every
  claim traceable to a video title, timestamp, and short quote.
- Treat CPU-damaging voltage and firmware behaviour as a hard exclusion, scored
  separately from VRM capacity — they are different failure modes with
  different causes.
- Rank for headroom under the heaviest plausible Zen 6 part, on a board bought
  today.
- Separate what he tested from what he inferred from what *we* inferred, and
  never let an inference read as a measurement.
- Keep inference spend visible and bounded: nothing is sent to a model before
  the owner sees a projection, the work runs in batches, and how many batches a
  run does is the owner's to say — one, several, or all of them.
- Stay disposable. This is a tool for one decision, not a product.

**Non-goals**

- Not a general video search engine, a transcript archive, or a Q&A chatbot
  over the corpus.
- No price tracking, stock checking, or retailer integration.
- No attempt to reconcile Buildzoid against other reviewers — the whole premise
  is that this is *his* opinion, extracted faithfully.
- Not a Zen 7 longevity guarantee. AM5 is committed through Zen 6; Zen 7 is
  expected to need a new socket, so no amount of VRM overspec buys it. The
  report states this rather than pricing it in.
- No Intel, no AM4, no server platforms.
- Not intended to run on a schedule. Every model-invoking run is STARTED
  deliberately — by the owner, or by an agent the owner told to start it. What
  a run does once started is a parameter rather than a further decision: it
  extracts the number of batches it was given and then stops, reports and
  waits. Nothing starts itself, and nothing continues past R26's ceiling.

## 4. Users & core use cases

The only user is the repository owner, buying one board.

**Main path.** As the buyer, I run the corpus stage, read the cost projection,
and decide whether the inference spend is acceptable. I then run extraction,
most recent videos first, saying how many batches this run should do — one at
first, so I can check after the calibration batch that reality matched the
estimate, and all of them once I have seen enough to trust the number. When I have enough coverage, I generate the
report and use its tier-1 and tier-2 sections as my shortlist, spot-checking two
or three claims against the linked timestamps before spending money.

**Stop-early path.** As the buyer, after three batches I see that a fourth is
mostly surfacing boards already covered. I stop, generate a report stamped with
its partial coverage, and buy from it — knowing exactly what fraction of the
corpus it rests on rather than assuming completeness.

**Safety path.** As the buyer, I want any board he has flagged for dangerous
voltage or firmware behaviour to be impossible to reach through the shortlist —
it appears only in a separate warnings section, with the quote that condemned
it, so I can't accidentally buy it on the strength of a good VRM review from
another video.

**Inheritance path.** As the buyer, I find that the specific board he praised is
unavailable or overpriced. Tier 3 tells me which sibling boards share the rail
design, VRM components, and firmware lineage closely enough to plausibly inherit
the verdict — clearly marked as reasoning, with a confidence level, and with the
specific fact I would need to confirm myself before buying.

## 5. Requirements

**Functional**

- **R1** — Enumerate the channel's regular uploads from 2023-01-01 to the run
  date into a deterministic index (video id, title, upload date, duration).
  Shorts and long livestreams are excluded by classification rules recorded in
  the index, not silently.
- **R2** — Fetch and cache each indexed video's caption track to local disk.
  Reruns read the cache and never refetch, and retry only previously failed
  videos. A failure is logged to a failure ledger — video id, title, date,
  failure class (no caption track available / fetch or network error), and the
  error — and the run continues.
- **R3** — Normalize caption text before matching: case, punctuation, and the
  spacing damage auto-captions inflict on part numbers, folding variant
  spellings of a board or CPU name onto one canonical alias.
- **R4** — Select candidate videos: an alias hit in the **title** is an
  automatic include; otherwise the video needs at least N normalized alias
  mentions in the body. N is configurable, defaults to 3, and the selection
  stage reports how many videos the current N includes and excludes.
- **R5** — Cut excerpt windows around each mention — overlapping windows merged
  — each carrying its start timestamp and its source video's title and id. The
  window is asymmetric and starts deliberately wide: 2 minutes before the
  mention and 5 minutes after, because a verdict follows the analysis rather
  than preceding it. Window size is configuration, and narrowing it re-runs the
  corpus stage from cache without refetching anything. Merging is transitive
  **clustering** (owner's 2026-08-19 ruling, `docs/DECISIONS.md`): windows that
  overlap join one cluster, a video's excerpts are its clusters, and each
  transcript character appears in at most one cluster (R1000's re-cut). A
  mention-dense video coalesces toward one big cluster; a long stream that
  mentions the board only at the start and the end yields two small clusters
  and stays cheap.
- **R6** — Group excerpts into work bundles capped by projected token load, and
  assign bundles to recency-ordered batches: a small calibration batch first,
  then larger batches.
- **R7** — Before any model is invoked, print a cost projection: videos indexed,
  videos selected, total and per-batch excerpt volume, bundle count, projected
  token load, and the chars-per-token factor used, stated openly. Extraction is
  a separate command from the projection and is always started deliberately, so
  no spend begins by itself. **How many batches that command does is its
  argument, not a further decision per batch**: it extracts the number it was
  given, then stops, reports what it spent and what remains, and waits. R26's
  ceiling stops it earlier whatever the number was, so "all of them" is bounded
  by a real reading rather than by trust.
- **R8** — After the calibration batch, record two quantities and keep them
  apart. **Tokens:** the projection's figure against the token counts the run's
  own model calls report, summed across every call the batch made, including any
  the run delegated to a spawned worker. Their delta corrects the chars-per-token
  factor for subsequent projections, because both sides are tokens. The four
  components a call reports — fresh input, output, cache creation and cache read
  — are recorded separately and never as a single total: a cache read is not
  billed as fresh input, and on the owner's machine cache reads already outnumber
  fresh input by more than four orders of magnitude, so a summed figure is
  dominated by the cheapest tokens in it. **Subscription points:** the R26
  readings taken before and after the batch, whose difference is what the batch
  cost against the weekly limit. Neither quantity is derived from the other. A
  token-to-points conversion is recorded beside them as a labelled ESTIMATE, with
  every assumption it rests on written out rather than implied. Every estimate
  this pipeline makes is stored that way — the projection, its chars-per-token
  factor, and this conversion — so a finished run can be compared against what it
  predicted and each estimate corrected from the comparison. An estimate whose
  assumptions are not stored beside it cannot be corrected, only replaced.
- **R9** — Extract claims from each bundle into a validated schema. A bundle
  whose output fails validation is reported and retried or set aside — never
  silently dropped.
- **R10** — Store claims append-only, tagged by batch, so a stop between batches
  loses no work and any batch can be resumed.
- **R11** — Synthesize claims into per-board dossiers assigned to exactly one of
  three tiers: tested by him, reasoned or secondhand from sources he trusts, or
  design-analogous inference.
- **R12** — Score CPU-safety (voltage and firmware behaviour) on an axis
  separate from VRM capacity. A board carrying an unretracted safety warning is
  excluded from the shortlist and appears only in a warnings section with its
  condemning quote.
- **R13** — For tier 3, propose sibling boards and verify their claimed design
  similarity against external sources before publication. Every tier-3 entry is
  marked as inference, carries a confidence level, and names the specific fact
  the buyer should confirm.
- **R14** — Emit a markdown report: tiered shortlist, per-board dossiers, a
  warnings section, and the failure ledger. Every claim shows its video title, a
  timestamped YouTube link, and a short verbatim snippet sufficient to verify
  it.
- **R15** — Weight recent verdicts above old ones in ranking, and flag a verdict
  as stale when the board's assessment rests only on early-platform videos.
- **R16** — Generate a valid report from however many batches have landed,
  stamped with its coverage: date range covered and share of selected corpus
  extracted.
- **R17** — Support the cost-saving levers as configuration rather than code
  changes: excerpt window size, per-video excerpt cap, mention threshold,
  near-duplicate excerpt removal, and batch token cap. Changing any of them
  re-runs the corpus stage from cache, so tuning after a batch costs CPU time
  and no refetching.
- **R24** — The run halts for joint review when failures exceed either trigger:
  3 consecutive fetch errors, or cumulative fetch errors passing 3% of indexed
  videos. Videos with genuinely no caption track are counted separately under a
  5% trigger. The halt states which trigger fired and prints the ledger. The
  ledger is reprinted in the final report regardless of whether a trigger fired,
  so missing coverage is visible at the point of use.

- **R25** — The date boundary uses a fixed slop constant, not a configuration
  lever. The channel listing's dates are approximate — bucketed to roughly
  mid-month — so the comparison date is the start date minus a fixed two months,
  guaranteeing that every video uploaded from 2023-01-01 onward is included and
  accepting that some 2022 videos are included with them. Per-video exact dates
  are explicitly rejected: they would cost one network call per video instead of
  one for the channel, to sharpen a boundary that is a preference rather than a
  rule.
- **R26** — Total model spend for the extraction effort is capped at 10% of the
  owner's weekly subscription limits. The cap is enforced against real readings
  rather than the projection: a reading is taken before a batch, after it, and
  part-way through a long one, and a run stops before crossing the line instead
  of discovering the overrun afterwards. **The run takes the reading itself.** On
  Omarchy the reader is `omarchy-agent-usage-claude --limits-only --force`, an
  ordinary command that returns the limits as JSON without starting a session;
  `claude -p "/usage"` is the fallback when that fails, and it is a fallback
  rather than the default because it starts a session and so spends against the
  very limit it is reading. A session with neither reader relies on other means.
  The limits themselves come from Anthropic's own usage endpoint, so they account
  for every session on the subscription rather than only the ones on this
  machine — while the same reader's per-model TOKEN counts are local, and that
  difference is why R8 keeps the two quantities apart. The readings are reported
  in whole percentage points, which sets the floor on what a calibration batch
  must consume to be measurable at all. The owner's own figure remains the
  tiebreaker where a reading and the owner disagree.
- **R27** — No completed work is lost to an overrun. Every model output is
  written to disk as it is produced rather than at the end of a batch, and full
  transcripts are retained after excerpting rather than discarded. Exceeding the
  estimate must cost the overrun and never the work already paid for.
- **R28** — Excerpting is skipped for a video whose excerpts have grown to cover
  it. Where the summed characters of a video's excerpts reach 80% or more of the
  characters in its full transcript, the whole transcript is sent with a
  full-review instruction instead; below that ratio, the excerpts are sent.
  Overlapping windows on a board-heavy video otherwise cost several times what
  excerpting was meant to save, while delivering nearly the whole text anyway.
  The ratio is computed from the re-cut cluster characters (R5, R1000). **The
  whole-transcript path is not capped** — this supersedes R1001
  (§14, OD-5), by the owner's 2026-08-19 ruling in
  `docs/DECISIONS.md`: a video at or above the ratio is information-dense by
  measurement, and paying for all of it is V4's choice. The lumpy-spend
  concern R1001 answered is handled where it arises — sparse long streams
  cluster small and never reach the ratio. A transcript larger than one
  bundle's token cap is delivered across sequential bundles rather than
  falling back to excerpts; the mechanics are the implementing plan's to
  specify.

**Non-functional**

- **R18** — Platform / targets: Linux CLI, Python 3.12, `uv`-managed, plus
  Claude Code agents run in this repository. No GUI, no service, no packaging
  for distribution.
- **R19** — Cost / resource limits: no API key exists and none will be
  provided. All inference runs on the owner's Claude Code subscription, via
  agents. Python code must never require an LLM call to complete a stage.
- **R20** — The test suite runs offline and deterministically. Network access,
  `yt-dlp`, and every model stage are exercised against fixture files. A test
  needing an unavailable optional resource skips with a stated reason.
- **R21** — Privacy / data handling: the transcript corpus is local-only and
  never redistributed. The report quotes only short snippets, sufficient to
  locate and verify a claim, alongside a link to the source video.
- **R22** — Performance / scale: the corpus stage must handle a channel of
  1000+ videos without holding all transcripts in memory at once, and must be
  resumable after interruption.
- **R23** — Reproducibility: given the same cache and configuration, the corpus
  and bundling stages produce byte-identical output.

## 6. Constraints & assumptions

**Constraints**

- No API key. Every model-invoking stage is a Claude Code agent run on the
  owner's subscription, which makes model usage a scarce shared resource and
  makes the checkpoint (R7) load-bearing rather than a nicety.
- Model and effort tiers are fixed by owner ruling: Opus 5 throughout, low
  effort for per-excerpt extraction, medium for synthesis, high where genuine
  reasoning is required (tier-3 inference).
- `yt-dlp` is the one approved new dependency.
- Repository process is whatever `AGENTS.md` says.
- The purchase is for a current AM5 CPU with a Zen 6 drop-in later, so the
  report optimizes for a board bought today.

**Assumptions**

- Auto-generated captions exist for essentially all videos in range, and are
  accurate enough on model numbers after normalization for a mention-count
  filter to work. If normalization proves unable to recover part numbers
  reliably, R4's recall collapses and the threshold approach needs rethinking.
- He mentions a board he is discussing several times, so a mention-count filter
  approximates topical relevance. Videos that discuss a board seriously exactly
  twice will be lost; the tunable threshold and the reported in/out counts exist
  to make that trade visible.
- A 2-before/5-after window captures the verdict. His digressive style means a
  conclusion may sit well away from the last mention — this is the main quality
  risk of the cost-saving design, and the calibration batch is where it gets
  checked. If verdicts still arrive clipped at this width, the excerpt approach
  itself is in question, not just the number.
- AM5 ends at Zen 6. If external verification contradicts this, the longevity
  framing changes, not the pipeline.
- The channel's back catalogue is stable enough that a full rerun is
  unnecessary; the cache is authoritative once populated.

## 7. Proposed approach (high level)

The system splits at the model boundary. Deterministic work is Python and is
tested; judgment is agents and is checkpointed. Python never calls a model, and
agents never scrape YouTube. They meet at files on disk.

**Stage A — Corpus (Python, no inference).**

- *Enumerator* → queries the channel through `yt-dlp`, applies the date range
  and the shorts/livestream exclusions, writes the video index.
- *Fetcher* → downloads and caches each video's caption track. Logs every
  failure with its class and continues, halting only when a failure trigger
  fires.
- *Normalizer* → folds caption text into a canonical form and resolves the
  alias table (board families, chipsets, CPU models, vendors) against it.
- *Selector* → applies title-auto-include and the mention threshold, and
  reports the in/out effect of the current threshold.
- *Excerpter* → cuts and merges timestamped context windows around mentions.
- *Bundler* → packs excerpts into token-capped bundles and assigns them to
  recency-ordered batches.
- *Estimator* → prints the cost projection and **stops**. Extraction is a
  separate command (§Stage B); nothing here starts it.

**Stage B — Extraction (agents, batch by batch).** An agent reads one bundle and
writes one claims file: for each board mentioned, what was said, in which of the
claim categories, about which subject (VRM capacity, voltage/firmware safety,
memory behaviour, features, value), with the short verbatim snippet, its
timestamp, and its video's title and id. Low effort, because this is reading
comprehension, not reasoning. An ingest step validates each file against the
schema and appends it to the append-only claim store, tagged by batch. A run
extracts the number of batches it was asked for — one, several, or every batch
still pending — and then stops, reports and waits. Each batch's claims land
before the next one starts, so a run stopped by R26's ceiling or by its own
count leaves every batch it finished intact and every batch it did not reach
untouched.

**Stage C — Synthesis (agents, medium effort).** Claims are grouped per board
into a dossier: capacity assessment, safety assessment, the strongest supporting
quotes, verdict recency, and the tier the evidence supports. Contradictions
across time are resolved in favour of the more recent statement, with the
superseded one retained and shown.

**Stage D — Inheritance (agents, high effort, web-verified).** For each tier-1
approved board, agents propose sibling boards plausibly sharing rail design, VRM
components, and firmware lineage; a verification pass checks the similarity claim
against external sources. Survivors enter tier 3 marked as inference, with a
confidence level and the fact to confirm before buying.

**Stage E — Report (Python).** Assembles the markdown: shortlist ranked on
safety first and capacity second with recency weighting, dossiers grouped by
tier, a warnings section for excluded boards, the coverage stamp, and the
failure ledger.

Data flows one way — index → cache → normalized → selected → excerpts →
bundles → claims → dossiers → report — with every intermediate on disk, so any
stage can be rerun without repeating the ones before it.

## 8. Key design decisions & alternatives

**Decision: split the pipeline at the model boundary.**
Options: a Python program calling an LLM API; a fully agentic run with no
program; the split. There is no API key and there will not be one, which
removes the first outright. A fully agentic run cannot count mentions across a
thousand transcripts reliably, cannot be tested, and cannot be repeated. The
split keeps everything mechanical in tested Python and everything judgment-based
in agents, and has the useful side effect that the checkpoint is structural: the
program simply has no way to proceed into inference on its own.

**Decision: prefilter and excerpt rather than feed whole transcripts.**
Options: full transcripts of selected videos; excerpt windows; a cheap triage
model between the two. Whole transcripts are the highest-recall option and
several times the cost, on a subscription where cost is the binding constraint.
A triage model stage adds a place where a good video gets discarded with no
record. Excerpt windows keep the recall risk in one place — window size — which
is tunable and inspectable, and cut token load severalfold given how much of his
runtime is digression. The calibration batch exists specifically to check
whether the windows are catching verdicts.

**Decision: start the window wide and narrow it only on evidence.**
Options: start narrow and widen if verdicts look clipped; start wide and narrow
if cost demands it. The two errors are not symmetric. A too-narrow window
produces a report that reads as complete while quietly missing conclusions, and
nothing in the output signals it — the failure is invisible. A too-wide window
produces a correct report that costs too much, and the cost is measured on the
very first batch. So the first run is wide (2 minutes before, 5 after), and
narrowing is a decision taken against calibration numbers. Because the corpus
stage is deterministic and cached, re-cutting at a narrower window costs CPU
time only.

**Decision: safety scored on its own axis, as a hard exclusion.**
Options: one composite quality score; two axes. A composite score lets a board
with excellent power delivery and dangerous firmware outrank a modest, safe
board — the exact mistake this project exists to avoid. The failure modes have
different causes (component choice versus firmware voltage judgment) and
different consequences (throttling versus a dead CPU), so they are scored and
presented separately, and a safety warning removes a board from the shortlist
regardless of how good its VRM is.

**Decision: three tiers, structurally separated in the output.**
Options: a single ranked list with confidence annotations; hard tiers. Confidence
annotations get skimmed past; the whole reason for the report is that the reader
must not confuse "he measured this" with "we reasoned this". Tiers make the
distinction impossible to miss, and let tier 3 be regenerated or discarded
without touching the evidence-backed sections.

**Decision: tier 3 uses model knowledge plus web verification.**
Options: model knowledge alone, flagged; a hand-curated spec table; model plus
web verification; drop the tier. Model knowledge alone will assert VRM
configurations confidently and sometimes wrongly, which is the worst outcome for
a report meant to prevent an expensive mistake. A curated table is reliable but
turns the project into a spec-scraping exercise. Verification keeps the
inference cheap to generate while giving each claim a chance to be refuted
before publication — at the cost of an extra agent stage and its usage.

**Decision: log transcript failures and continue, halting on two triggers.**
Options: fail hard on any gap; fail hard unless each gap is individually waived;
log-and-continue with halt triggers; best-effort and silent. Silent gaps are
disqualifying — a shortlist that skipped a third of the corpus looks identical
to a complete one. Pure fail-hard cannot complete, because some videos genuinely
have no caption track. Per-video waivers preserve strictness but demand a manual
ruling on every incidental miss, which is ceremony that will be clicked through.

The chosen rule separates the two causes instead. A **streak** trigger — 3
consecutive fetch errors — catches a block or throttle within seconds of it
starting, because systemic failure arrives in a burst. A **rate** trigger — 3%
of indexed videos — catches slow attrition that never trips the streak. Videos
with no caption track at all are a different, expected population and get their
own looser 5% trigger, so a channel with scattered uncaptioned uploads doesn't
keep stopping a healthy run. The ledger records the class of every failure, so
when we do stop we can see which kind of problem we have rather than inferring
it, and it is reprinted in the report so incomplete coverage stays visible at
the point of use rather than buried in a log.

**Decision: hard checkpoint before inference, then calibrate, then batch.**
Options: run it and see; estimate then run; estimate, calibrate, batch. An
estimate built on a chars-per-token guess is a guess, and being wrong by 3x on a
subscription budget is the failure that ends the project. The calibration batch
converts the guess into a measurement having spent a small fraction of the
budget, and the batching means the decision to continue is taken with real
numbers rather than with the guess. The owner takes that decision by choosing
how many batches the next run does, which is one at a time while the numbers
are still unfamiliar and all of them once they are not — a knob rather than a
gate, because a gate that must be passed every few minutes is one that gets
propped open. The cost-saving levers are agreed in advance (R17) so that a
bad calibration result leads to turning knobs rather than to a redesign.

**Decision: append-only claim store, batch-tagged, partial report always valid.**
Options: rebuild the store per run; append-only. Append-only makes stopping free:
no batch's work is contingent on the next one, and a report can be produced at
any boundary. It also makes the natural stopping signal measurable — the rate at
which a batch surfaces boards no earlier batch mentioned.

**Decision: recency weighting rather than a hard date cutoff inside the range.**
Options: only consider 2024+; weight by recency. Early-platform videos contain
genuinely useful design commentary — the AGESA and firmware landscape they
describe is obsolete, but VRM analysis is not. Weighting keeps the signal and
flags the staleness; a cutoff throws both away.

## 9. Data model / key entities

- **Video** — id, title, upload date, duration, classification (regular / short
  / livestream), inclusion reason (title hit, threshold pass, excluded,
  transcript unavailable).
- **Transcript** — video id, ordered cues of (start time, text), plus the
  normalized form used for matching. Cached on disk, authoritative once written.
- **Alias** — a canonical entity (board model, board family, chipset, CPU model,
  vendor) and its known spoken and mangled spellings. The alias table is data,
  not code, so widening it does not require a rewrite.
- **Mention** — video id, alias, timestamp, matched surface form.
- **Excerpt** — video id, video title, start and end timestamp, text, and the
  mentions it covers. The unit of everything downstream.
- **Bundle** — an ordered set of excerpts under the token cap, with its batch
  number. The unit of agent work.
- **Claim** — board, video id, video title, timestamp, short verbatim snippet,
  claim category (tested / reasoned / secondhand / warning), subject (VRM
  capacity / voltage-firmware safety / memory / features / value), polarity, and
  the extracting batch. The atom of evidence.
- **FetchFailure** — video id, title, upload date, failure class (no caption
  track / fetch error), error detail, and attempt count. The ledger is the set
  of these, and it is what both halt triggers are computed from.
- **BoardDossier** — board, vendor, chipset, tier, capacity assessment, safety
  assessment, supporting claims, superseded claims, recency, staleness flag, and
  for tier 3: the analogue it inherits from, the shared-design argument, its
  verification result, confidence, and the fact to confirm.
- **Report** — the assembled markdown, its coverage stamp, its configuration
  snapshot, and the failure ledger.

## 10. External dependencies & integrations

- **`yt-dlp`** — channel enumeration and caption retrieval. Owner-approved. The
  only new runtime dependency. Isolated behind one module so that a YouTube
  change or a switch to another tool touches one file.
- **YouTube auto-generated captions** — the corpus itself. No formal API
  contract; breakage is expected and handled by the failure ledger and its halt
  triggers.
- **Claude Code agents on the owner's subscription** — every inference stage.
  Not an API integration: the contract is files on disk, a bundle in and a
  claims file out.
- **Web search, via agents** — tier-3 verification only.
- Existing repository tooling — `uv`, `ruff`, `mypy`, `pytest`, pre-commit, and
  the CI gates — used as they stand.

## 11. Risks & open questions

- **Excerpt windows may clip the verdict.** He states a conclusion minutes away
  from where he named the board. This is the central quality risk of the
  cost-saving design, and the reason the window starts wide rather than tight.
  Mitigation: the calibration batch is inspected for verdicts that arrive
  without their reasoning, and the window is configuration. Open: whether
  2-before/5-after is enough, and what it costs — both only measurable after
  batch 1.
- **A wide window may make batch 1 expensive enough to distort the estimate.**
  On videos dedicated to one board the merged windows approach the full
  transcript, which is correct but not cheap. Accepted deliberately: an
  overestimate is visible and correctable, an under-caught verdict is neither.
- **Caption mangling may defeat the mention threshold.** If part numbers survive
  captioning too poorly, R4 loses videos silently. Partly mitigated by title
  auto-include and the reported in/out counts. Open: the true recall of the
  alias table, checkable only by hand-auditing a sample of excluded videos.
- **Tier-3 hallucination.** Verification reduces but does not eliminate
  confidently wrong VRM claims. Mitigation: tier separation, explicit confidence,
  and naming the fact to confirm. Residual risk is accepted knowingly.
- **Subscription usage may make full corpus coverage infeasible.** This is the
  reason for the checkpoint and the batches. The designed answer is a partial
  report with an honest coverage stamp, not a degraded full report.
- **YouTube blocking or throttling** mid-corpus. Mitigated by caching and
  resumability; a sustained block stalls the project and would need a rethink.
- **Verdict staleness.** Firmware changes; a 2023 condemnation may have been
  fixed by a later AGESA, and the fix may never be mentioned on camera.
  Mitigation: recency weighting and staleness flags. Open: whether a "was this
  ever retracted" pass over later videos is worth its cost.
- **He may simply not have covered the boards available at purchase time.** The
  report would then be thin at tier 1 and lean heavily on tier 3, which is the
  weakest tier. Open until the corpus is built.
- **Open: does anything in the corpus bear on AM5's life past Zen 6?** Worth
  reporting if found, but not assumed either way.
- **Open: the stopping rule.** "New boards per batch has dropped" is the
  intended signal; the threshold at which to stop is a judgement to make with
  real numbers, not to fix now.

## 12. Milestones / phasing

**MVP — Corpus and the cost checkpoint (no inference)**

- Scope: enumeration, caption fetch and cache, normalization and alias table,
  selection, excerpting, bundling and batch assignment, and the cost projection
  report. Covers R1–R7, R24, R17, R18, R20–R23.
- Acceptance criteria: a full run over the channel produces the video index, a
  populated cache, the selected set with the threshold's in/out effect reported,
  bundles assigned to a calibration batch plus three larger batches, and a
  printed projection stating videos, excerpt volume, bundle count, projected
  tokens, and the factor used. No model is invoked at any point. The suite passes
  offline against fixtures. Every transcript failure appears in the ledger with
  its class, and both halt triggers are demonstrated firing under test.

**M2 — Calibration batch and provisional report**

- Scope: the extraction agent contract and claims schema, the validating ingest
  and append-only store, the calibration batch, the projected-versus-actual
  comparison, and a minimal report generator. Covers R8–R10, R14 (partially),
  R16, R21.
- Acceptance criteria: batch 1 extracts to validated claims; the delta between
  projected and actual usage is reported and the factor corrected; a report
  generates from batch 1 alone with a correct coverage stamp and with every claim
  carrying video title, timestamped link, and snippet. The owner has inspected a
  sample of excerpts for clipped verdicts and ruled on whether to keep the wide
  window or narrow it and re-cut from cache.

**M3 — Batches 2–4, synthesis, and the tier-1/tier-2 report**

- Scope: the remaining planned batches, dossier synthesis, the two evidence-based
  tiers, the safety axis and its exclusion rule, and recency weighting. Covers
  R11, R12, R14, R15.
- Acceptance criteria: dossiers exist for every board with claims; every board is
  in exactly one tier; boards with unretracted safety warnings appear only in the
  warnings section; the report ranks safety first and capacity second; a stop
  decision is taken on real numbers against the new-boards-per-batch signal.

**Later**

- **M4 — Tier 3.** Analogue proposal, web verification, confidence levels and
  the confirm-before-buying note. Covers R13.
- **M5 — Remaining corpus, if justified.** Only if M3's stopping signal says
  more coverage is still buying new information.
- **M6 — Cost-saving pass, if the calibration demands it.** Applying the R17
  levers and re-running affected batches.

## 13. Success criteria

- **S1** — A full corpus run completes with every video in range either
  transcribed and cached, or recorded in the failure ledger with its class and
  error. No silent gaps, and the ledger appears in the report.
  *(Mechanically checkable.)*
- **S10** — Both halt triggers fire under test: 3 consecutive fetch errors, and
  cumulative fetch errors crossing 3% of indexed videos, with the no-caption
  class counted separately against its own 5% trigger.
  *(Mechanically checkable.)*
- **S2** — The cost projection is printed before any inference, extraction is
  a separate command that never starts itself, and a run stops after the number
  of batches it was given or at R26's ceiling, whichever comes first.
  *(Mechanically checkable.)*
- **S3** — After the calibration batch, the token projection, the token actual
  the run's own calls reported, their delta and the corrected factor are recorded
  together, and the R26 points readings taken around the batch are recorded
  beside them as a separate quantity, with the token-to-points conversion and its
  assumptions. *(Mechanically checkable — the records are committed files and
  `tests/test_calibration_records.py` checks them. `omarchy-agent-usage-claude --limits-only
  --force` supplies the points readings on this machine as JSON; it does not
  supply the token figure the factor is corrected from, which is why the two are
  recorded apart.)*
- **S4** — **(owner)** Every claim in the report carries its video title, a working
  timestamped link, and a short verbatim snippet. The owner picks any five
  claims at random and all five are locatable within a minute at their stated
  timestamps. *(Owner verifies.)*
- **S5** — Every board in the report sits in exactly one tier, and no tier-3
  entry is presented without its inference marker, confidence level, and the
  fact to confirm. *(Mechanically checkable.)*
- **S6** — No board carrying an unretracted safety warning appears in the
  shortlist; each such board appears in the warnings section with its condemning
  quote. *(Mechanically checkable given the claim store; the judgement of what
  counts as a warning is owner-verified.)*
- **S7** — A report generated at any completed batch boundary is valid and
  correctly stamped with the date range and corpus share it covers. *(Mechanically
  checkable.)*
- **S8** — **(owner)** The owner can name a board to buy, and state which tier it came from
  and which video and timestamp backs it. This is the criterion the project
  exists for. *(Owner verifies — a judgement call.)*
- **S9** — The suite passes offline and deterministically, with `yt-dlp` and
  every agent stage exercised against fixtures. *(Mechanically checkable.)*

## 14. Requirements added from evidence (R1000+)

Decisions made from 2026-08-19 to 2026-08-24 from logged backlog evidence
(`BL-<n>`, now in git history), formerly kept in `docs/DESIGN.oracle.md`. They
are requirements like any other. All are built except R1001, which is
superseded. OD-4 to OD-11 are kept in full; OD-13 onward are condensed to
their requirement text (the full entries are in git history). OD-1 to OD-3,
OD-12 and OD-19 to OD-21 governed the summer delivery process and are dropped.

### OD-4 — Merged excerpt windows are re-cut from the cues, never concatenated

- **Date:** 2026-08-19
- **Evidence:** BL-10
- **Requirements added:** R1000
- **Requirements superseded:** (none)
- **Vision statement relied on:** V3 — "Cost is about not being *stupid* — not spending budget I could have used on other projects — rather than a hard constraint."
- **Vision statements against:** V4 — "Given a choice between a cheaper run and a better-sourced answer, take the better answer." — it does not forbid this: the inflation is the *same* text repeated wherever windows overlap, so removing it buys no worse-sourced answer; no information is traded away, only duplication.
- **Alternatives considered:** Divide the projection by an empirical inflation factor — rejected: BL-10 measured that the inflation scales with mention density, so no constant divides it out, and a corrected number derived from wrong text is still wrong per video. Send saturated videos whole and ignore the merge defect — rejected: R28's 80% ratio is computed from the excerpt characters, so the defect corrupts the very measurement that routes around it, and sub-threshold videos stay inflated. Re-cut from the cues — chosen.
- **Rationale:** The checkpoint exists to produce one number the owner spends against, and the measured case shows that number 4.8x wrong on a real video (28,438-character transcript → 137,246-character merged excerpt). `merge_overlapping` concatenates on partial overlap, so overlapping text is counted once per window instead of once. This is exactly the "stupid" spend V3 rules out: paying repeatedly for identical characters.

**R1000** — When overlapping excerpt windows are merged, the merged span is
re-cut from the transcript cues so that each transcript character appears at
most once in a video's excerpts. The summed excerpt characters of a video never
exceed its transcript's characters, and both the cost projection and the R28
saturation ratio are computed from the re-cut text. The measured real-video case
from BL-10 lands as a regression fixture asserting that bound.

The signature change BL-10 anticipates (`merge_overlapping` gains access to the
cues) is the plan's to specify. Measurement: the checkpoint's own projection is
the observable this changes, the R28 path counts make the routing visible, and
the regression fixture pins the bound — no new collection mechanism is needed.

### OD-5 — Excerpting stays; the whole-transcript path is capped at the bundle token cap

- **Date:** 2026-08-19
- **Evidence:** BL-13, BL-10
- **Requirements added:** R1001
- **Requirements superseded:** (none)
- **Vision statement relied on:** V10 — "Where some other goal can only be met by processing content with no AMD or AM5 signal, that goal loses and a cheaper design is chosen."
- **Vision statements against:** V4 — "Given a choice between a cheaper run and a better-sourced answer, take the better answer." — it does not forbid this: where the evidence is dense, R28 already sends the video as one continuous transcript, which is the whole of BL-13's quality argument for exactly the videos it matters on; and the calibration batch (R8, milestone M2's clipped-verdict inspection) is the designed instrument for measuring whether excerpts cost answer quality on sparse videos. If it shows that, the finding is logged evidence and this decision is superseded at the cost of one entry.
- **Alternatives considered:** Adopt BL-13 wholesale — send every selected video whole, delete excerpting (superseding R5, most of R17, R28) — rejected on three grounds: the 4.8x measurement is the saturated case, which R28 plus R1000 already resolves (with an honest ratio the dense video goes whole and costs its transcript, never 4.8x); on a sparsely-matching video the text outside every mention window is precisely the no-signal material V10 says loses to a cheaper design, and excerpts remain several times cheaper there; and the owner's recorded 2026-08-16 ruling explicitly *kept* excerpting below the threshold — BL-13 is a logged proposal, and reversing a recorded owner ruling with no new measurement beyond the one R28 already answers is not this ledger's to do. Unbounded whole-transcript path — rejected: multi-hour livestreams are in the corpus by owner ruling, and dozens qualifying at once is the lumpy spend the rule exists to remove. Cap at the bundle token cap — chosen, as the blocked plan itself proposed.
- **Rationale:** The hybrid the owner landed (R28) is the right shape once its measurement is honest; what it lacks is the upper bound its own plan flagged as blocking. The vision decides the residual conflict: cost yields to information quality (V4) exactly where the signal is, and material without signal loses to the cheaper design (V10) everywhere else — which is what excerpts-below-threshold, whole-above-threshold, capped-at-the-bundle does.

**R1001** — *Superseded by the owner's 2026-08-19 ruling (`docs/DECISIONS.md`) and R28: the whole-transcript path is not capped.* Original text: A video takes the whole-transcript path only when its full
transcript fits within the bundle token cap. Above the cap it falls back to
excerpts regardless of its R28 ratio, so one video's submission always fits in
one bundle and the 80% rule can never create the lumpy cost it exists to
remove. The projection reports how many videos took each path and what each
path costs, so the routing is observable at the checkpoint.

The cap above was overruled by the owner the same day; R28 carries the
current rule (clusters, uncapped whole-transcript path, sequential bundles).

### OD-6 — An alias split across caption tokens still matches

- **Date:** 2026-08-19
- **Evidence:** BL-8
- **Requirements added:** R1002
- **Requirements superseded:** (none)
- **Vision statement relied on:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not."
- **Vision statements against:** V7 — "I would rather the system filter hard and hand me three videos than be safe and hand me thirty." — it does not forbid this: V7 is about how many videos reach the owner, not about a matcher that cannot see a board's name. A video lost to `toma hawk` is not filtered hard; it is invisible, and its board silently drops out of the answer V1 calls the whole product.
- **Alternatives considered:** Split-tolerant surface forms in the alias table alone — rejected as the *general* fix: hand-enumerating every possible split point for every alias is unbounded maintenance for a mechanical transformation; the table stays the right home only for genuine mishearings. Matching against a whitespace-stripped copy of the whole text — rejected: stripping erases token boundaries, which is exactly the trap BL-8 names — `the b650` fuses to `theb650` and boundary checks become impossible. Token-join matching with boundary alignment — chosen.
- **Rationale:** Auto-captions routinely split product names, and the measured recall test found the shipped table blind to `toma hawk`, `aor us master` and `air us elite` — silent losses in the corpus the whole product is built from. The fix must join what captions split without un-anchoring what boundaries protect.

**R1002** — Matching recovers caption-split alias forms: an alias also matches
where its normalized text equals the concatenation of *adjacent whole tokens* —
the match starts at a token start, ends at a token end, and every space inside
the alias aligns with a token boundary. An alias never matches a proper
substring of a fused token, so `b650` can never be found inside `theb650`.
Normalization folds hyphens to spaces, so `steel-legend` folds onto the table's
`steel legend`. Mishearings no join can recover (`air us` for `aorus`) remain
the alias table's job — it is data, per §9 — and the table gains the observed
spoken forms. BL-8's measured 52-variant set lands as a fixture; the named
failures must match.

Measurement: the `aliases --check` recall report and R4's selection in/out
counts already observe this; the variant fixture pins it in the suite.

### OD-7 — A chipset's ITX variant counts as the chipset

- **Date:** 2026-08-19
- **Evidence:** BL-9
- **Requirements added:** R1003
- **Requirements superseded:** (none)
- **Vision statement relied on:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not."
- **Vision statements against:** V10 — "Where some other goal can only be met by processing content with no AMD or AM5 signal, that goal loses and a cheaper design is chosen." — it does not forbid this: an ITX review of an AM5 board is AM5 signal of the strongest kind, the opposite of the no-chance-of-relevance material V10 guards the budget against. The mention threshold still gates body matches.
- **Alternatives considered:** Hand-listed `b850i`-style surface forms in the table — workable and data-not-code, but every chipset needs remembering, including future ones. Relaxing the right boundary generally — rejected: the boundary is right in general; it is what stops `b650` matching inside longer tokens. A derived ITX form for chipset aliases (surface forms generated from the canonical, or an equivalent suffix-aware rule) — chosen; which mechanism is the plan's choice, the behaviour is fixed here.
- **Rationale:** ITX boards are named `<chipset>I`, and the measured case is total: a 33-minute review of the MSI MPG B850I Edge TI matched `B850` zero times, in title and body both, so the automatic title include misses too. Every ITX review in the corpus is affected, and ITX is where one-DIMM-per-channel memory behaviour lives — boards the report cannot afford to be blind to.

**R1003** — A chipset alias also matches its ITX variant token — the chipset
followed by a trailing `i` (`b850i`, `x870i`, `b650i`) — in titles and bodies
alike, counted as a mention of that chipset, while the right-boundary rule
stays in force for everything else. Regression: the real B850I review's title
auto-includes on its chipset.

Measurement: same as R1002 — the recall report, the selection counts, and the
regression case.

### OD-8 — The video description is recorded at fetch and matched at selection

- **Date:** 2026-08-19
- **Evidence:** BL-11
- **Requirements added:** R1004
- **Requirements superseded:** (none)
- **Vision statement relied on:** V2 — "**Surfacing videos that are dense in information about *this* problem** — packed with useful knowledge about board safety and the boards I would actually buy."
- **Vision statements against:** V10 — "Where some other goal can only be met by processing content with no AMD or AM5 signal, that goal loses and a cheaper design is chosen." — it does not forbid this: a description hashtag is author-written, short, and unmangled by speech-to-text — the highest-signal field the corpus has. A video tagged `#B850` is the opposite of no-chance-of-relevance material, and reading a field already in hand costs nothing.
- **Alternatives considered:** Widen R1's enumeration to fetch descriptions — rejected: flat playlist extraction does not return them, so that shape really would cost one request per video, which is the cost BL-11 correctly flags and the same per-video fetching the owner declined for dates. Ignore descriptions — rejected: the measured video is found by its description hashtag and by nothing else the pipeline reads; discarding the one field that names the board is discarding V2's densest signal. Record at the fetch boundary — chosen, because the cost objection is empty there: `fetch_caption_track` already runs a full per-video extraction, and the description arrives in it today and is thrown away.
- **Rationale:** BL-11 weighed this as "an extra request per video"; in the built system that premise is false. The per-video extraction already happens for every pending video at fetch, so the description is free precisely for the population selection considers. The real B850I video — invisible to title and transcript matching both — carries `#B850` in its description, which normalizes to a clean canonical hit.

**R1004** — The fetch stage records each video's description, taken from the
same per-video extraction that already retrieves its caption track — no
additional network request. Selection treats a normalized alias hit in the
description as an automatic include, like a title hit, recorded under its own
inclusion reason so the index and the selection report state how many videos
the signal added. A video cached before descriptions were recorded simply has
no description signal — never an error, and no forced refetch. Where the
description is the only signal and the video has no caption track, the failure
ledger still governs; a description cannot conjure a transcript.

Measurement: the inclusion reason in the index (R1/§9) and R4's selection
report make the new signal's effect countable per run.

### OD-9 — A projection with a missing input refuses instead of understating

- **Date:** 2026-08-19
- **Evidence:** BL-7
- **Requirements added:** R1005
- **Requirements superseded:** (none)
- **Vision statement relied on:** V3 — "Cost is about not being *stupid* — not spending budget I could have used on other projects — rather than a hard constraint."
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; refusing to print a wrong number stops no work and spends nothing)
- **Alternatives considered:** Keep the forgiving zero — rejected: a projection whose denominator silently reads 0-videos-indexed is indistinguishable from a real empty corpus, and it is the one number the checkpoint exists to make trustworthy. Print with a warning — rejected: R7 makes the projection the stop the owner decides at; a warned-but-printed number still invites the decision. Refuse, naming the missing stage — chosen.
- **Rationale:** The checkpoint is load-bearing (R7, and the no-API-key constraint that makes usage a scarce shared resource). A projection the owner spends against must never understate itself because an input was absent; absence and emptiness are different facts and must read differently.

**R1005** — A pipeline stage whose upstream artifact is missing refuses to run,
naming the absent artifact and the stage that produces it. In particular,
`estimate` never prints a projection when the index is absent. A present-but-
empty artifact is a real value and is reported as what it is; absence is an
error. Observable directly in the command's exit and message, pinned by tests.

### OD-10 — Every subcommand flag is reachable from the CLI

- **Date:** 2026-08-19
- **Evidence:** BL-5
- **Requirements added:** R1006
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; CLI mechanics are below the vision's altitude)
- **Alternatives considered:** A central subcommand/flag table in the dispatcher — rejected: it recreates the shared edit point slice 1's design deliberately avoided (no two slices edit the dispatcher). Keep the Python-invocation workaround — rejected: the stated deliverable (`uv run find-best-mobo aliases --check`) stays unreachable, `run-scripts` carries a visible workaround that names BL-5, and the defect recurs for every later subcommand that takes a flag — BL-5 itself names slices 4 and 5. Forward unrecognised arguments to the subcommand — chosen: one small dispatcher change, each subcommand owns its own parsing, and the no-table property is preserved.
- **Rationale:** BL-5 is the item its own entry called first worth ruling on: not cosmetic, blocks a stated deliverable, and structural — the top-level parser rejects `--check` before dispatch ever happens. The fix keeps the design decision that caused it (no subcommand table) while removing what it accidentally forbade.

**R1006** — Every flag a subcommand documents is reachable from the CLI: the
top-level dispatcher forwards arguments it does not recognise to the invoked
subcommand, which owns their parsing and their errors. `uv run find-best-mobo
aliases --check` works, and a future flagged subcommand requires no dispatcher
edit. The `scripts/run.sh` workaround (invoking `aliases` through Python) reverts
to a plain CLI call.

### OD-11 — The alias table is a tracked input at a configured path

- **Date:** 2026-08-19
- **Evidence:** BL-4, BL-6
- **Requirements added:** R1007
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; where a file lives is below the vision's altitude)
- **Alternatives considered:** Keep `data/aliases.toml` force-added — rejected: `data/` is gitignored because the corpus never enters git (R21), and a hand-authored input surviving there by `git add -f` contradicts the directory's stated meaning; every tool that respects the ignore file misreads it, and the arrangement survives only until someone cleans the ignored directory. Package data under `src/` — rejected: the table is owner-editable input, not code. A tracked path at the repository root, named by configuration — chosen, and it settles BL-6's ambiguity in the same motion: loaders read the path from config, never assume it.
- **Rationale:** BL-4 identified the category error — the alias table is hand-authored input, not cached corpus — and BL-6 showed the plan's silence made two blind authors guess (they happened to agree). One requirement fixes both: a tracked home, and one authoritative way to find it.

**R1007** — The alias table is a git-tracked, hand-authored input living
outside the gitignored corpus directory — default `aliases.toml` at the
repository root — and every loader takes its path from configuration rather
than assuming a location. The `git add -f` exception is retired; a fresh clone
carries the table. Migration moves the existing file and its config default in
one change, observable by `aliases --check` running from a clean checkout.

### OD-13 — The whole-transcript path is uncapped; an over-cap transcript spans sequential bundles

2026-08-20. Evidence: BL-14, BL-13. Supersedes R1001. Follows the owner's 2026-08-19 ruling (`docs/DECISIONS.md`).

**R1008** — The cost projection reports the routing per path: how many videos
were sent as whole transcripts and how many as excerpts, and the characters and
projected tokens each path accounts for. For the whole-transcript path it also
reports how many videos exceed one bundle's token cap and the number of
sequential bundles each such transcript spans, so the uncapped path's largest
submissions are visible at the checkpoint before anything is spent. Supersedes
R1001: the observability is kept, the cap and the excerpt-fallback above it are
not.

### OD-14 — The zero-duration warning judges the listing shape, not the count

2026-08-20. Evidence: BL-15. On the first real index run all eight durationless entries were genuine Shorts, so the old warning was a permanent false positive that would hide a real drop.

**R1009** — The index stage distinguishes the flat listing's Shorts shape from
a real anomaly by the evidence in each entry, never by how many entries lack a
duration. An entry with no duration and no date in either listing field
(`upload_date`, `timestamp`) is the expected Shorts shape: it classifies as it
does today and is reported as a one-line count ("N Shorts reported no duration
(expected)"), with no banner. The loud warning fires only for an entry carrying
a real date but no duration — the shape of a genuine video being silently
dropped — and names each such video id. The suite pins the distinguishing
pair: a dateless, durationless entry does not trip the warning, and a dated,
durationless one does.

### OD-15 — R1002 applies within one cue; a cross-cue split is counted, never matched

2026-08-20. Evidence: BL-16. A mention spanning two cues has no single start time, and R5's windows and R14's links are cut from that start.

**R1010** — Mention matching applies R1002's token-join rule within one cue's
normalized text: a mention is never synthesized from text spanning a cue
boundary, so every mention's `start_seconds` is the start of the one cue
containing it — the anchor R5's excerpt windows are cut from and R14's
timestamped links point at. The scoping is measured, not assumed: the matching
stage also detects matches that exist only in the normalized concatenation of
adjacent cues — a match that starts in one cue's text and ends in the next's —
and reports the count per run (zero included) in the selection report, without
ever emitting a mention for one. The suite pins the distinguishing pair: an
alias split across a cue boundary yields no mention and increments the
counter, and the same split within one cue yields a mention and does not.

### OD-16 and OD-17 — Reconstructed test fixtures say so

2026-08-20. Evidence: BL-17, BL-18.

BL-8's original 52 caption variants and the real B850I review title were lost.
The fixtures for R1002 and R1003 are labelled reconstructions: they may be sized
by the lost originals but never claim measured provenance beyond what was
observed (the three named R1002 failures; the board name `MSI MPG B850I Edge TI`
and its zero `B850` matches).

### OD-18 — `--help` after a subcommand prints the subcommand's help

2026-08-20. Evidence: BL-19, BL-5. Elaborates R1006.

`find-best-mobo <stage> --help` is forwarded like any other flag and prints
that stage's help, as `git`, `pip` and `uv` do. `find-best-mobo --help` and a
bare `find-best-mobo` keep the top-level output (exit 0 and 2).

### OD-22 — Stage B's calibration and spend readings are committed evidence

2026-08-20. Evidence: BL-23 (Stage B, approved by the owner). Where the record lives: `docs/DECISIONS.md`, 2026-08-25.

**R1011** — Stage B's measurements are committed evidence, not console output.
The calibration record R8 requires — projected tokens, actual usage, the delta,
and the corrected chars-per-token factor — and the spend-guard readings R26
requires around each batch (before, part-way through a long one, after) are
written to git-tracked files outside the gitignored corpus directory, keyed to
the batch they describe. The suite checks the shape of every committed
record (`tests/test_calibration_records.py`; before v2 this was
`acceptance/S3.sh`). The fraction the spend guard enforces is read from one
configured place whose default is R26's figure, so an owner edit to that figure
reaches the guard as a one-line change and a restated number elsewhere is never
a second source.

### OD-23 — Transcript coverage is reported on every run, and zero coverage refuses

2026-08-24. Evidence: BL-27. `select` once ran before `fetch` had finished, and `estimate` printed a zero-cost projection without a word of warning.

**R1012** — Every stage that reads the transcript cache reports its COVERAGE of
the population it is working on: how many of the videos it considered had a
cached transcript to read, printed on every run whether or not anything is
wrong. Zero coverage over a non-empty selection is an unmet precondition rather
than a result — the stage refuses, names the stage that produces the missing
input, and exits non-zero, in the shape R1005 already gives a missing artifact.
A partial cache stays tolerated exactly as today; the per-video rule R24's
failure ledger owns is unchanged. The cost projection prints the same coverage
figure beside its character count, so no projection can be read without seeing
what fraction of the corpus produced it. The suite pins the distinguishing
pair: a selection whose videos all have transcripts and genuinely zero mentions
still reports a real (zero) projection, and a selection whose videos have none
does not.

### OD-24 — Captions are fetched as json3; VTT stays as a fallback that says so

2026-08-24. Evidence: BL-28. Roll-up VTT stored every spoken word about three times (2.84x over 285 transcripts); json3 does not.

**R1013** — The caption fetch requests `json3` and prefers it, reading a
transcript as the concatenation of every segment of every event, `aAppend`
events included — they carry real speech, and dropping them loses words. Each
cue's start time comes from the segment timing json3 supplies rather than from
a display frame, so a mention's `start_seconds` is the moment its own words were
spoken.

WebVTT remains the fallback for a track offering no `json3`, and its roll-up
duplication is removed on parse rather than stored: no video's cached transcript
may contain the same line three times whichever path produced it.

**The path taken is recorded per video in the cache record and reported in the
run summary**, so a transcript's provenance is never a question asked later
about a cache that cannot answer it. A run that used the fallback for any video
says so prominently, because a fallback nobody notices is a reconstruction
silently mixed in with verbatim text.

---

## Assumptions made while writing this doc

Flagged so a wrong one is easy to catch:

- Corpus scope is 2023-01-01 to the run date, regular uploads only, with long
  livestreams and Shorts excluded. Only the recency-weighting option was
  explicitly chosen; the rest is the default I proposed.
- Model and effort assignment: Opus 5 low for extraction, medium for synthesis,
  high for tier-3 reasoning — taken directly from the owner's ruling and applied
  to stages the ruling did not name individually.
- Transcript failures are logged and tolerated, halting only on the two
  triggers, per the owner's revision of the original fail-hard rule. The
  specific numbers (3 consecutive, 3% cumulative, 5% for missing caption tracks)
  are my proposal, confirmed by the owner, and are configuration rather than
  constants in code.
- The report is generated for one buyer and one build; no multi-user, no
  configuration profiles.
- The starting excerpt window is fixed here (2 minutes before, 5 after) because
  the wide-first decision is a design position, not a tuning detail. Batch sizes
  and the exact token cap are left to the plan, because the calibration batch is
  what should set them.
