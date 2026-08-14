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
