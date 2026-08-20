# Decisions — Finding Best Mobo by Buildzoid

ADR-lite. One dated entry per decision, newest at the bottom. A recorded ruling
is never silently reversed: to change one, argue it in chat, then append a
superseding entry. History is never rewritten.

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

## 2026-08-14 — Requirement ids must match `R<digits>`

Found while reviewing the design doc before opening its pull request: the
coverage gate (`.github/scripts/coverage.sh`) recognises only `**R<n>**` and
validates a plan's `covers:` entries against `^R[0-9]+$`. Two ids added during
drafting, `R2a` and `S1a`, would have been invisible to it — never counted as
covered, and rejected if a plan claimed them. Renumbered to `R24` and `S10`, and
appended at the end of their lists rather than inserted in sequence.

Worth noting for the ratchet: the coverage gate ignores ids it does not
recognise instead of failing on them, so it fails open on a malformed id. The
gate scripts are human-owned, so this is the owner's to log and fix.

## 2026-08-14 — #12 merged by owner bypass, and why that is not a precedent

The design doc pull request could not pass the `plan` check: the `docs/`
exemption caps at 50 added lines, it added ~731, and no plan can cover the
document that plans are written against. The agent flagged this before opening
the pull request and did not attempt to route around it — raising the cap is
gate tampering under `AGENTS.md`, and gate paths are owner-owned. Owner ruled:
merge by bypass, and log the escape.

The review gate independently reached the same conclusion and returned BLOCK,
citing the agent's own journal entry admitting the pull request was
unauthorised, and noting that `DECISIONS.md` recorded nine rulings from that
session but not this one. That finding was correct on the evidence available to
it. The reviewer runs with fresh context on a runner and cannot see chat, so an
owner ruling made in conversation does not exist as far as any gate is
concerned. This entry is what closes that gap, and the general lesson is the one
`AGENTS.md` already states: chat is not storage.

Recorded in `docs/escapes.md` (#13). Bootstrap, not precedent — the standing
answer is a gate change that gives the design doc a path of its own, which is
the owner's to make.

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

## 2026-08-14 — The agent keeps its own pull request branches up to date

Owner ruling, after a session left four pull requests open at once. When the
later ones auto-merged, the earlier ones fell behind the default branch and had
to be updated by hand before their checks could re-run — work that landed on the
owner purely because an agent had opened a queue it then stopped tending.

Ruled: updating a stale branch is the agent's job, not the owner's. An agent
watching a pull request it opened updates the branch itself as soon as it falls
behind, and does not wait to be asked.

This is a fallback, not a licence to build queues: the standing rule is one open
pull request at a time (`ESC-20`), and a branch that never goes stale needs no
updating. The ruling covers the case where staleness happens anyway — a merge
the agent did not control, or a pull request held for review.

## 2026-08-14 — An explicit plan wins, and the objection goes in the rework queue

Owner ruling, given while plan approval was unavailable. Where a plan states
something explicitly, implement it as written — even where it looks wrong. Do
not deviate, do not argue the exception in a pull request, and do not stall
waiting for a ruling that cannot come.

Two things make that safe rather than merely obedient. First, the objection is
written into `docs/BACKLOG.md` under "Plan rework", where it cannot be missed
when the plans are next revised — an unrecorded objection is the failure mode
this replaces. Second, where the owner has ruled the specification questionable,
a **minimal implementation that passes is acceptable**, because the code is
expected to be rewritten once the plan is fixed; effort spent polishing it is
effort spent twice.

The owner named the trade-off when giving the ruling: it is suboptimal, and it
is preferred to blocking. If it produces real friction or waste, that is
evidence for `docs/escapes.md` — including where the cause is the owner's own
availability. Logged when it costs something, not in advance of it.

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

The entries below shipped with the template — rulings the template's owner made
once so every generated project does not re-ask them. They bind here like any
other entry: to change one for this project, supersede it.

## 2026-08-16 — Waiting is mechanical, and belongs to the driver

Resolves the open question `/deliver` step 4 used to carry (idle vs poll vs
scheduled wake-up). The wait is not agentic: a **driver** — deterministic
tooling, not a model — invokes one headless session per phase and waits between
phases on `gh pr checks --watch`-style polling, so no model budget is spent
watching CI. Run it locally (`.claude/scripts/deliver-loop.sh`) or from a
Claude Code web session (`/deliver-loop`); the mode is chosen explicitly by
which entry point you start. The exit condition stands as previously decided:
wait until **no check is still pending**, never until the pull request is no
longer open — a failing pull request never leaves the open state, so the second
condition makes red indistinguishable from still-running.

## 2026-08-16 — Mid-run authority: the design layer rules, the oracle rules it

Plans derive only from the design layer. When new work surfaces mid-run, it
enters through the chain — the oracle amends `docs/DESIGN.oracle.md` on its own
pull request, a plan follows on its own pull request, then code — never
directly. Uncertainties a plan raises are handled by risk class, judged by a
contract test: **HIGH** if the candidate answers change slice boundaries,
Signatures blocks, external formats or schemas, or anything expensive to
reverse — and when unsure, that doubt itself makes it HIGH. High-risk: the
planner files the question in `docs/BACKLOG.md` and waits for the oracle's
ruling. Low-risk: the planner proceeds on a recorded default and the oracle
reviews it next cycle. Attended runs keep the original behaviour: the owner
rules. The owner steers unattended runs by editing `docs/VISION.md` and
`docs/DESIGN.md`, and reviews at the end.

## 2026-08-16 — Unattended runs act as a GitHub App, not as the owner

A user PAT shares the owner's per-hour API budget with every tool acting as
that user, and the built-in Actions token cannot trigger workflows from its own
events — both were hit in practice. A GitHub App has its own rate-limit budget,
its events fire workflows (so merged branches actually get deleted), and pull
requests it opens are authored as the app, which makes "opened by the owner"
(`.github/scripts/owner-authored.sh`) mean exactly that. Fallback when no App
is configured: `AUTO_MERGE_TOKEN`, then the Actions token plus the nightly
branch sweep.

## 2026-08-16 — The budget ceiling is subscription percentage points, and it halts

An unattended run stops — it does not degrade to a cheaper model or a smaller
scope — when it has consumed its allowance, measured in percentage points of
the owner's subscription rate limit from the run's start. Because that probe is
best-effort, two hard backstops always also apply: a pull-request count and a
wall-clock limit. A loop that quietly gets worse when it runs low is harder to
diagnose than one that stops and says why.

## 2026-08-18 — After a merge, the other open pull requests are updated for you

Branch protection here requires branches to be up to date, so the moment one
pull request merges every other open one becomes unmergeable however green it
is. GitHub calls that `BEHIND`, and it is not a check — it never appears in the
checks list, so the pull request shows a column of green ticks and simply does
not merge. Auto-merge does not rescue it either.

So `auto-merge.yml` updates them: on a merge, `gh pr update-branch` over every
other open pull request in this repository. It **never fails** — a real conflict
is reported and left for a human, not turned into a red check on a pull request
that did nothing wrong — and it **will not run on the built-in Actions token**,
because a push made with that token creates no workflow runs, so the branch
would come up to date with its required checks permanently missing. That is
worse than being behind. Configure the App (`scripts/setup-github.sh --app`);
without it, the run summary says so and nothing is touched.

## 2026-08-19 — Two credentials, total: the App, and the review token. No PATs.

The owner's ruling, taken to reduce setup: a project configures exactly one
GitHub credential — the App (`APP_ID` + `APP_PRIVATE_KEY`) — and one Anthropic
credential — `CLAUDE_CODE_OAUTH_TOKEN` for the review gate. Everything GitHub
needs beyond the built-in Actions token is minted from the App at use time:
`template-sync` mints a read-only token scoped to the template repository
(which is why the App must be installed there too), the driver mints its
pull-request identity per request, and a web session mints `gh`'s token per
turn. `TEMPLATE_TOKEN` and `AUTO_MERGE_TOKEN` are gone, deliberately without
fallbacks — a fallback that must be set up defeats the point of having less to
set up, PATs expire and fail every project at once, and a PAT acts as the
owner, which hollows out `owner-authored.sh`. The App stays at exactly
Contents RW, Pull requests RW, Checks RO: never Administration or Secrets, or
the unattended driver could edit its own gates.

<!-- Append project decisions below, newest at the bottom. -->

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

## 2026-08-18 — The first unattended run may spend 35 percentage points

The 10% ceiling of the earlier entry is the **standing** cap. For the first
truly unattended run it is raised, once, to **35 percentage points of the weekly
limit**. The owner's reason: the weekly window resets in a day or two, so
unspent allowance is lost rather than saved.

**It is a delta, not a level.** The measurement is the difference between a
reading taken before the run starts and one taken after it stops — not the
absolute figure the gauge shows, which already includes everything else spent
this week. The driver takes it as `--budget-points 35`.

**Two readers exist and both were tested on 2026-08-18.** They agree.

- `omarchy-agent-usage-claude --limits-only --force` — JSON, ~0.3s, starts no
  session and therefore costs nothing. **Prefer it**: point `BUDGET_PROBE_CMD`
  at it and `.claude/scripts/budget-probe.sh` uses it instead of the paid path.
- `claude -p "/usage"` — the fallback, and correct, but it starts a small
  session per call, so every probe spends a little of the thing it measures.

**One trap, recorded because it already misled a reader.** The omarchy JSON
reports `percent` as a **fraction of one** — `0.35` means 35%, not 0.35%.
`claude -p "/usage"` prints whole percents. `budget-probe.sh` normalises both
(`v <= 1 ? v * 100 : v`) and emits whole points, which is the form to trust:

    session=10 week=36 week_model=25 reset=Aug 20, 10:59am (Europe/Amsterdam)

Both readings remain approximate and count local sessions on this machine only.

## 2026-08-19 — Owner's standing ruling for the first unattended run

Recorded from the owner, in their words, as the instruction this run operates
under:

> you will work endlessly and tirelessly until this project is done as is
> already defined in these files. use the oracle if you run into places where
> you would need my ruling, that is what the oracle is for, to be my second in
> command.

Three things follow, and they bind every session this run commissions:

- **The design layer is the finish line.** "Done" means what the vision, the
  design and its success criteria already say — not a new scope invented while
  building. Nothing here authorises widening the work.
- **The oracle is the escalation, not the owner.** A question that would
  previously have stopped for a ruling is filed and ruled through the oracle
  chain. Stopping to wait for the owner is the last resort, not the first.
- **Bugs are dug into and fixed, not stepped around.** Each one is recorded, and
  a defect belonging to the *template* is recorded separately in
  `docs/template-bugs.md` so the fixes can be taken upstream after the run.
  A fix applied here to a template-owned file is drift, and saying so is part of
  logging it.

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
   (BL-1 through BL-13) are approved by the owner as of this date — recorded
   in `docs/BACKLOG.approved.md`.
4. **Mechanics for the oracle:** supersede OD-5/R1001 next cycle citing this
   entry and the owner's amended `docs/DESIGN.md` (R5/R28). A transcript
   larger than one bundle's token cap is delivered across sequential bundles
   rather than falling back to excerpts; the mechanics are the implementing
   plan's to specify.
