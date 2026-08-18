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
  the owner sees a projection, and the work runs in batches with hard stops.
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
- Not intended to run unattended or on a schedule. Every model-invoking stage
  is entered deliberately.

## 4. Users & core use cases

The only user is the repository owner, buying one board.

**Main path.** As the buyer, I run the corpus stage, read the cost projection,
and decide whether the inference spend is acceptable. I then run extraction one
batch at a time, most recent videos first, checking after the calibration batch
that reality matched the estimate. When I have enough coverage, I generate the
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
  corpus stage from cache without refetching anything.
- **R6** — Group excerpts into work bundles capped by projected token load, and
  assign bundles to recency-ordered batches: a small calibration batch first,
  then larger batches.
- **R7** — Before any model is invoked, print a cost projection: videos indexed,
  videos selected, total and per-batch excerpt volume, bundle count, projected
  token load, and the chars-per-token factor used, stated openly. The pipeline
  stops here and does not continue without an explicit separate command.
- **R8** — After the calibration batch, record projected against actual usage,
  report the delta, and correct the factor used for subsequent projections.
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
  rather than the projection: `claude -p "/usage"` returns them headlessly, so a
  reading is taken before a batch, after it, and part-way through a long one,
  and a run stops before crossing the line instead of discovering the overrun
  afterwards. On Omarchy the reader is
  `omarchy-agent-usage-claude --limits-only --force`, which returns the limits as
  JSON without starting a session. The Python pipeline itself still cannot read
  them, and the reading is approximate — it counts only local sessions on the
  owner's machine — so the owner's own figure remains the tiebreaker where the
  two disagree.
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
- Repository process applies in full: plans before code, vertical slices, blind
  tests, and the merge pipeline described in `AGENTS.md`.
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
- *Estimator* → prints the cost projection and **stops**.

**Stage B — Extraction (agents, batch by batch).** An agent reads one bundle and
writes one claims file: for each board mentioned, what was said, in which of the
claim categories, about which subject (VRM capacity, voltage/firmware safety,
memory behaviour, features, value), with the short verbatim snippet, its
timestamp, and its video's title and id. Low effort, because this is reading
comprehension, not reasoning. An ingest step validates each file against the
schema and appends it to the append-only claim store, tagged by batch. Between
batches the pipeline stops.

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
budget, and the batch stops mean the decision to continue is re-taken with real
numbers each time. The cost-saving levers are agreed in advance (R17) so that a
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
- **S2** — The cost projection is printed and the pipeline stops before any
  inference; continuing requires a separate explicit command. *(Mechanically
  checkable.)*
- **S3** — After the calibration batch, projected and actual usage are recorded
  together with the corrected factor. *(Mechanically checkable —
  `omarchy-agent-usage-claude --limits-only --force` reads the real subscription
  limits on this machine as JSON, so actual usage is not owner-only.)*
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
