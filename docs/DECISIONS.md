# Decisions — Finding Best Mobo by Buildzoid

Settled decisions and why, one dated entry each, newest at the bottom. Don't
relitigate them; to change one, append a superseding entry.

## 2026-08-14 — Longevity target is Zen 6, not Zen 7

The original ask was to overspec the power rails so that a future Zen 7 drop-in
stays feasible. Raised in chat that this spends money on an outcome the socket
decides rather than the board: AM5 is committed through Zen 6, and Zen 7 is
expected to need a new socket. Owner ruled: rank for headroom under the heaviest
plausible Zen 6 part, and have the report state plainly that Zen 7 is not
something a board purchase can buy. Recorded as a non-goal in `docs/DESIGN.md`
§3, with "does the corpus say anything about AM5 past Zen 6" left open in §11.

## 2026-08-14 — All inference runs on the owner's subscription; no API key

Owner ruled that no API key exists or will be provided, and that every model
call runs on their Claude Code subscription. Model is Opus 5 throughout, with
reasoning effort as the cost lever: low for per-excerpt extraction, medium for
synthesis, high where genuine reasoning is required.

This is the constraint that shapes the architecture. A Python program cannot
call the model, so the pipeline splits at the model boundary (see the next
entry), and model usage becomes a scarce shared resource rather than a billable
line item — which is what makes the pre-inference checkpoint load-bearing.

## 2026-08-14 — Split the pipeline at the model boundary

Options: a Python program calling an LLM API; a fully agentic run with no
program; a split. The API option is removed by the no-key ruling. A fully
agentic run cannot reliably count mentions across a thousand transcripts, cannot
be tested, and cannot be repeated.

Chosen: Python owns everything deterministic (enumerate, fetch, normalize,
filter, excerpt, bundle, assemble the report) and writes work bundles to disk;
Claude Code agents read bundles and write structured claims back. Python never
calls a model; agents never scrape YouTube. Side effect worth having: the
checkpoint becomes structural, because the program has no way to enter inference
on its own.

## 2026-08-14 — Prefilter and excerpt rather than send whole transcripts

Owner asked whether prefiltering could reduce inference cost. Options: full
transcripts of selected videos; excerpt windows around board mentions; a cheap
triage model between the two. Chosen: keyword/alias prefilter, then excerpt
windows. Whole transcripts are highest-recall and several times the cost on a
budget where cost is the binding constraint; a triage model adds a place where a
good video is discarded with no record. Excerpting concentrates the recall risk
in one inspectable, tunable number — window size.

## 2026-08-14 — `yt-dlp` approved as the one new dependency

Asked under the AGENTS.md rule that new dependencies need owner approval. Owner
approved `yt-dlp` for channel enumeration and caption retrieval, declining the
option of adding a second caption library. To be isolated behind one module so a
YouTube change or a tool swap touches one file.

## 2026-08-14 — Three tiers, structurally separated

Owner requires the report to distinguish boards Buildzoid tested, boards he
reasons about or has heard about from trusted sources, and boards inferred to
inherit an approved board's verdict by shared design. Options: one ranked list
with confidence annotations, or hard tiers. Chosen: hard tiers, because
annotations get skimmed and the entire point is that an inference must not read
as a measurement.

## 2026-08-14 — Tier 3 uses model knowledge plus web verification

Options: model knowledge alone with flags; a hand-curated spec table; model
knowledge verified against the web; drop the tier. Owner chose verification.
Model knowledge alone asserts VRM configurations confidently and sometimes
wrongly, which is the worst failure mode for a report meant to prevent an
expensive mistake; a curated table turns the project into a spec-scraping
exercise. Every tier-3 entry carries a confidence level and names the specific
fact to confirm before buying.

## 2026-08-14 — Safety is its own axis and a hard exclusion

Raised in chat that "won't kill my CPU" and "best VRM" are different questions
with different causes — firmware voltage judgment versus component choice — and
that a composite score lets a board with excellent power delivery and dangerous
firmware outrank a modest safe board. Chosen: score the two separately, and let
an unretracted safety warning remove a board from the shortlist regardless of
its VRM, leaving it visible only in a warnings section with the condemning
quote.

## 2026-08-14 — Hard checkpoint before inference, then calibrate, then batch

Owner's requirement: stop after scraping and preprocessing, report expected
cost, and decide whether to continue. Extended in chat to three stops rather than
one, because an estimate built on a chars-per-token guess is still a guess.
Chosen: print the projection and stop; run a small most-recent calibration batch
and compare projected against actual; then three larger recency-ordered batches
with a stop after them. The claim store is append-only and batch-tagged, so
stopping is free and a report can be generated at any boundary with a coverage
stamp. Cost-saving levers are agreed in advance as configuration (DESIGN §R17)
so a bad calibration leads to turning knobs rather than redesigning.

## 2026-08-14 — Transcript failures are logged and tolerated, with two halt triggers

Supersedes the earlier fail-hard-on-any-gap position taken while drafting, at the
owner's direction. Fail-hard cannot complete, because some videos genuinely have
no caption track; per-video waivers preserve strictness but demand a ruling on
every incidental miss, which becomes ceremony that gets clicked through.

Chosen: log every failure with its class and continue, halting for joint review
on either of two triggers. Three consecutive fetch errors catches a block or
throttle immediately, because systemic failure arrives in a burst. Cumulative
fetch errors at 3% of indexed videos catches slow attrition that never trips the
streak. Videos with no caption track are a separate expected population with a
looser 5% trigger. Numbers proposed by the agent, confirmed by the owner, and
held as configuration rather than constants. The ledger is reprinted in the final
report so incomplete coverage stays visible where it is used.

## 2026-08-14 — Excerpt window starts wide: 2 minutes before, 5 after

Owner's direction: start wide so a verdict delivered minutes after the board is
named is still caught, and narrow later if the first batches prove it too
expensive. Asymmetric because the conclusion follows the analysis.

The errors are not symmetric either, which is the reasoning worth keeping. A
too-narrow window produces a report that reads as complete while silently
missing conclusions, and nothing in the output signals it. A too-wide window
produces a correct report that costs too much, and the cost is measured on the
first batch. Because the corpus stage is deterministic and cached, re-cutting at
a narrower window costs CPU time and no refetching.

## 2026-08-14 — Livestreams stay in the corpus; only Shorts are excluded

The agent proposed excluding past livestreams by yt-dlp's live flag, warning
that a duration ceiling would silently delete the best content — his normal
uploads routinely run 40–90 minutes and some deep dives exceed two hours. Owner
went further and ruled: include livestreams too. Only Shorts are excluded.

Maximum recall, at the cost of substantially more transcript volume to fetch and
store. The cost consequence is deliberately deferred rather than guessed: it
shows up as a number at the checkpoint, where it can be acted on.

## 2026-08-14 — Work bundles are XML structure with prose inside

Owner asked whether XML could be used, on the understanding that it is the most
token-efficient format. The agent corrected the premise: XML is *not* cheaper —
closing tags cost tokens markdown headings do not. What is true is that XML tags
are the recommended way to delimit sections in a Claude prompt, because tagged
boundaries are attended to reliably.

Chosen on the corrected reasoning: XML tags carry the structure and provenance
(video id, title, timestamp, boards mentioned); the transcript text sits inside
them as plain prose. Cheap body, reliable boundaries.

## 2026-08-14 — `yt-dlp` is imported as a library, not shelled out to

Owner asked whether the library would be faster given local execution. Partly:
process startup is negligible, but reusing one client across ~1000 videos avoids
standing up fresh HTTP state per video, which does add up. Testability does not
decide it either way — the dependency is isolated behind one module and faked at
that boundary regardless. Ruled: library.

## 2026-08-14 — The MVP is five slices, not four

Owner overrode the agent's four-slice proposal (index / fetch / select /
estimate) in favour of five, splitting normalization and the alias table into a
slice of their own. The reasoning is sound and worth recording: that slice is
where the recall risk lives — if caption mangling defeats the alias table, the
corpus is quietly wrong and nothing downstream reveals it — so it earns its own
checkpoint rather than riding along inside selection.

## 2026-08-16 — Approximate upload dates, with a fixed slop constant

The first real run kept 0 of 1215 videos: `classify` reads `upload_date`, which
a flat channel listing never returns. Fixing that raised a real choice, because
the listing's dates are bucketed to roughly mid-month and two different videos
were observed sharing one timestamp.

Options: fetch each video individually for an exact date (~1215 network calls
instead of one), or accept the listing's approximate dates. Owner ruled:
approximate, no per-video fetching.

The boundary is therefore a **fixed constant, not a configuration lever** —
owner's explicit wording — chosen so that anything uploaded from 2023-01-01
onward is guaranteed to be included, accepting that some 2022 videos come along
for the ride. Two months of slop, on the reasoning that the cutoff is a
preference rather than a rule, and that a missed 2023 video is a real loss while
an extra 2022 video costs only a little processing.

## 2026-08-16 — A saturated video is sent whole, not as excerpts

Excerpting around every keyword mention was found to multiply cost roughly
fivefold on videos that mention boards constantly, because the windows overlap
and the merged result approaches the whole transcript anyway.

Owner ruled: measure, per video, the total characters of its excerpts against
the characters of its full transcript. At **80% or more**, send the whole
transcript and ask for a full review. Below that, send the excerpts as now.

The feature is kept rather than abandoned — it earns its keep on videos that
mention a board once in passing. The rule only removes the case where it stops
paying: past that ratio you are buying excerpt overhead plus duplication to
deliver nearly the whole text, and a model reads one continuous transcript
better than overlapping fragments of it.

## 2026-08-16 — Ten percent of the weekly limit, and nothing wasted on the way

Owner set the budget for the whole extraction effort at **10% of their weekly
subscription limits**. Two consequences ruled at the same time:

- The agent cannot read those limits — no tool exposes them — so the ceiling is
  enforced by owner readings before and after the calibration batch, and the
  projection is calibrated against them. This is why `docs/DESIGN.md` §13 marks
  that criterion owner-verified.
- **If the estimate is wrong and the budget is exceeded, nothing already spent
  may be lost.** Every model output is written as it is produced, and full
  transcripts are kept rather than discarded after excerpting — they are already
  downloaded. Overrunning the estimate should cost the overrun, never the work.

## 2026-08-16 — Batch shape confirmed against the first real run

Owner confirmed the design's staging with the numbers now known: run the first
batch, produce a cost estimate from what it actually consumed, then 3–4 further
batches, then reassess. Unchanged from the design's intent; recorded because it
was re-affirmed after the corpus turned out to be 1215 videos rather than the
500–1000 assumed while drafting.

## 2026-08-16 — The agent can read subscription usage after all

The owner asked whether a shell command could reach `/usage`. It can, by two
routes: `claude -p "/usage"` returns the readings headlessly, and on Omarchy
`omarchy-agent-usage-claude --limits-only --force` returns the same limits as
JSON without starting a session at all — so the reading itself costs nothing.

This supersedes the claim made twice in this file and once in the design on the
same day: that no tool exposed the subscription limits. It was an assumption
stated as a fact, and it survived because nobody spent thirty seconds testing
it. The error mattered in a specific direction — it turned an enforceable
ceiling into an estimate to be checked by hand afterwards. The cap of the
earlier entry can now be enforced from inside a run, and `docs/DESIGN.md` §13
therefore treats that criterion as checkable by running a command rather than
owner-only.

Two limits, from the commands' own output: the figure is approximate, and it
counts local sessions on this machine only — not other devices, not claude.ai.
The owner's own figure stays the tiebreaker where the two disagree.

One trap: the omarchy JSON reports `percent` as a fraction of one (`0.35`
means 35%), while `claude -p "/usage"` prints whole percents. Normalise
before comparing.

## 2026-08-19 — Clustered excerpts, an uncapped whole-transcript path, and blanket backlog approval

Owner's ruling, given in chat during the post-run review and recorded here
because chat is not storage. Four parts:

1. **OD-4 stands.** Its reasoning is correct; R1000's re-cut is kept. The
   clustering language below is its formalization, not its reversal.
2. **OD-5 is overruled on the cap.** The whole-transcript path is NOT capped
   at the bundle token cap; R1001 is to be superseded. The lumpy-spend concern
   it answered is handled where it arises instead: excerpt windows keep their
   R5 sizes, but overlapping windows merge transitively into CLUSTERS. A
   mention-dense video coalesces toward one cluster; a long stream that
   mentions the board only at the start and the end yields two small clusters
   and stays cheap. The 80% ratio (R28) is kept and computed from the re-cut
   cluster characters: at or above it, the video is information-dense by
   measurement, and paying for the whole transcript is V4's choice.
3. **Why OD-5 went wrong, in the owner's reading:** the backlog items were
   sitting unapproved, so the oracle treated BL-13 as "a logged proposal" it
   could not adopt against an earlier ruling. All current backlog items
   (BL-1 through BL-13) are approved by the owner as of this date.
4. **Mechanics:** R1001 is superseded (marked in `docs/DESIGN.md` §14). A
   transcript larger than one bundle's token cap is delivered across
   sequential bundles rather than falling back to excerpts; the mechanics are
   the implementing change's to specify.

## 2026-08-24 — Usage readings, units, and where the factor lives

Owner's rulings for Stage B (BL-15, BL-24 to BL-26), given in chat:

1. **BL-15 approved**: the indexer's zero-duration warning must stop firing on
   ordinary Shorts (built as R1009).
2. **Usage readings**: locally the run reads usage itself,
   `omarchy-agent-usage-claude --limits-only --force` first and
   `claude -p "/usage"` only when that fails (it starts a session, so it
   spends against the limit it reads). Without either, rely on other means.
3. **Units**: tokens and subscription points are recorded apart, never one
   derived from the other, plus a best-effort token-to-points conversion with
   every assumption written down (now R8).
4. **The factor**: the calibration stage writes the measured chars-per-token
   factor; `estimate` prefers it over `config.chars_per_token`, prints which
   source it used and whether it is measured or a guess; no stage ever rewrites
   the config key.

## 2026-08-25 — Stage B: the subscription pays, the 7-day limit governs, calibration stays at 12

Owner's rulings, given in chat before Stage B was built:

1. **The subscription pays**, through `claude -p`, not the API on a card. R26
   caps spend at 10% of the weekly subscription limits, and an API call never
   moves that meter: the guard would report healthy while a card was charged.
   It is also the only path where R8's token counts and R26's points come out
   of the same run (Claude Code writes the four token components to its
   transcript).
2. **The cap applies to `Weekly (7-day)`**, the account-wide limit, not the
   model-scoped one beside it.
3. **The calibration batch stays at 12 bundles.** The token comparison is exact
   at any size; the points delta is read in whole percent and may read zero.
   A zero delta is recorded as "unmeasurable at this size", not forced by a
   bigger batch.

## 2026-08-25 — The calibration record is one tracked file per batch

Owner's ruling (recorded in the Stage B plan at the time): the record lives at
`calibration/batch-<n>.json`, git-tracked, with no copy under `data/`. R1011
governs the location, the 2026-08-24 ruling above the semantics. The first real
record (`calibration/batch-1.json`) measured 2.33 characters per token against
the configured 4.0 guess.

## 2026-08-25 — Extraction is a knob, not a gate

R7 used to require a human between every batch. The owner's concern was that
no transcript reach a model before the Python work landed, and that a runaway
run not eat the weekly limit unnoticed. The first is done; the second is R26's
guard. So `extract` takes the number of batches as an argument (`--batches N`
or `all`, default one) and stops at that count or at R26's ceiling, whichever
comes first. A gate that must be passed every few minutes gets propped open.
DESIGN §3, §4, §7, R7, R8, R26, S2 and S3 were changed together.

## 2026-08-25 — Keep motherboard claims; graphics-card claims are the lesser error

Owner's ruling, given in chat twice: "it is way more important to include
motherboards than to exclude gpus". Recall of motherboard claims is the
constraint, precision against graphics cards only the objective; a rule that is
unsure keeps the claim. The extraction prompt now excludes graphics cards like
CPUs and chipsets, and `scripts/drop-gpu-claims.py` removed the graphics-card
claims the first full extraction had already stored, with guards that keep a
claim whenever it might be about a board. The store is derived from the raw
model output (R27), which is never touched, so the removal can be redone.

A bundle whose claims file fails validation is retried once, then set aside:
it stays unconsumed, is named in the run's output, and the batch continues.

## 2026-10-29 — The project is MIT-licensed

Owner ruling, given in chat as the repository went public. This supersedes the
"intentionally unlicensed" rule in `AGENTS.md`: the project is licensed under
MIT (`LICENSE`, `Copyright (c) 2026 GrimsVerk`), and `pyproject.toml` carries
the matching `license` field.

## 2026-10-29 — Moved to template v2; the summer process decisions are retired

The repository moved from the summer template (v0.4.27) to grimsverk-template
v1.0.1. The unattended delivery pipeline is gone (driver, oracle, steward,
plan gates, LLM review, auto-merge, CODEOWNERS, GitHub App identity), so the
entries that only governed it were removed from this file. They are in git
history:

- Requirement ids must match `R<digits>` (a coverage-gate rule; the ids stay)
- #12 merged by owner bypass, and why that is not a precedent
- The agent keeps its own pull request branches up to date
- An explicit plan wins, and the objection goes in the rework queue
- Waiting is mechanical, and belongs to the driver
- Mid-run authority: the design layer rules, the oracle rules it
- Unattended runs act as a GitHub App, not as the owner
- The budget ceiling is subscription percentage points, and it halts
- After a merge, the other open pull requests are updated for you
- The first unattended run may spend 35 percentage points
- Owner's standing ruling for the first unattended run

Product decisions are unchanged. `docs/DESIGN.oracle.md` was folded into
`docs/DESIGN.md` §14 (OD-1 to OD-3 and OD-12 were about process and are
dropped). The approved backlog stays the work queue, minus BL-12 (template-sync
conflicts), which v2 removed by removing the check.
