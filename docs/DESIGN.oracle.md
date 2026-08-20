# Design decisions from evidence — find-best-mobo

The **second design document**, and the only one an agent may write while nobody
is awake.

`docs/DESIGN.md` is `CODEOWNERS`-owned: a change to it waits for the owner. That
is correct — it is the standard every pull request is judged against — and it is
also why unattended work stops at the first thing the evidence contradicts. This
file is the answer. It is append-only, mechanically checked
(`.github/scripts/oracle-decisions.sh`), and deliberately **not** owned, because
ownership here would stop overnight work, which is the point of having it.

Its author is the **oracle** (`/oracle`). Nothing else writes here.

## What may be decided

Only what the evidence already logged. A decision resolves a **recorded
contradiction** between the design and reality:

- an escape — `ESC-<n>` in `docs/escapes.md`;
- a backlog item — `BL-<n>` in `docs/BACKLOG.md`.

Both are cited by rigid id and both must already exist on the default branch.
The oracle cannot invent a design change, and this is what makes that a fact
rather than an instruction: an idea with no logged evidence behind it has
nowhere to be written down. It is not a place to record improvements someone
thought of — those go to `docs/BACKLOG.md` like every other proposal.

**Give backlog items ids** (`BL-1`, `BL-2`, …) if you want them citable. An item
with no id is not evidence as far as the check is concerned.

## Requirement ids start at R1000

Requirement ids share ONE integer space with `docs/DESIGN.md` — the grammar is
`R` followed by digits and there is no namespace mechanism — so anything
numbered here would silently collide with a requirement the owner wrote, and
`.github/scripts/coverage.sh`, which unions both documents, would read two
different requirements as one. Oracle requirements therefore start at **R1000**,
and the check enforces it.

Plans cover these ids exactly like any other: `covers: [R1000]`.

## Append-only, and superseded rather than revised

A decision that has landed is never edited or removed. When one turns out to be
wrong, write a **new** decision that names the old id and says what replaced it
— the same lifecycle `docs/escapes.md` uses. Ids only ever increase.

This is the rule that stops an oracle quietly revising yesterday's ruling, where
the diff would read as an edit rather than as a reversal.

## The schema

Every decision is a `##` heading with the id, then these eight fields:

    ## OD-<n> — one line saying what was decided

    - **Date:** YYYY-MM-DD
    - **Evidence:** ESC-<n>, BL-<n>
    - **Requirements added:** R1000, R1001   (or "(none)")
    - **Requirements superseded:** R1000     (or "(none)")
    - **Vision statement relied on:** V<n> — "<the FULL sentence, verbatim>"
    - **Vision statements against:** V<n> — "<the statement that most nearly
      forbids this>", and why it does not   (or "(none — no statement in
      docs/VISION.md tells against this)")
    - **Alternatives considered:** what else was weighed, and why not
    - **Rationale:** why this, given that evidence and that statement

    Then any prose the decision needs: the requirement text itself, what it
    changes downstream, which plans it affects.

One field is optional, and it is the only thing written here that changes what
another gate does:

    - **Criterion waived:** S3 — <what the criterion's script does not
      recognise about what was built>

See "Waiving a success criterion" below before writing one.

### The sixth field is what makes the fifth honest

A decision that names only the statement supporting it has not weighed the
vision — it has searched it. The owner reading the ledger cannot tell those
apart, because both produce one quoted sentence. Naming the statement that most
nearly forbids the decision, and saying why it does not, is the difference
between a reading and a justification, and it is the one part of this schema an
agent cannot produce without having read the whole file.

Writing `(none)` there is a claim, and a false one is visible the moment the
owner reads the vision alongside the ledger.

### Quote the whole sentence, and name its id

`.github/scripts/oracle-decisions.sh` reads `docs/VISION.md` at the base commit
and fails a decision whose quoted text is not in it. That closes the hole where
this field's entire validation was the presence of a `"` character — a
one-letter quote passed, in a repository with no vision file at all.

A fragment is rejected for a related reason: one short enough to invert is one
too short to cite. Six words lifted out of *"I would trade any feature for a
design I can hold in my head"* can be made to argue for adding complexity, which
is the opposite of what the sentence says, and the ledger entry reads as a clean
derivation either way.

### If `docs/VISION.md` does not exist

Deleting it is a legitimate choice and it means one specific thing: **this
project has no tiebreaker, so the oracle rules with none.** Every decision then
uses the explicit class —

    - **Vision statement relied on:** (no vision statement decided this)

— which is not a formality here, it is the accurate value. That class already
obliges **Alternatives considered** to say what else was weighed and why it
lost, and with no vision that field is the entire record of the reasoning.

Quoting a sentence from a file that is not in the tree is the one thing that
must not happen, and the check now refuses it. If you find yourself reaching
into git history for a statement, the correct field value is the opt-out.

### The vision field is the point

The other six are bookkeeping. **Vision statement relied on** is what makes the
role steerable rather than merely reviewable: when the owner disagrees with a
decision, they can see exactly which sentence of `docs/VISION.md` produced it
and edit *that*, instead of guessing which of ten statements was doing the work
and arguing with each decision one at a time.

Quote the statement. Do not paraphrase it — a paraphrase is the decision
restating itself, and the check refuses a vision field with neither quotation
marks nor the one explicit opt-out:

    (no vision statement decided this)

That opt-out exists for the ruling class the vision genuinely does not decide —
an uncertainty a plan filed, most often — which otherwise could not be written
at all without paraphrasing a statement into existence. Using it moves the
weight onto **Alternatives considered**: what else was weighed and why it lost,
so the owner can still see what a different vision sentence would have changed.
The check refuses the opt-out with `(none)` there. Guessing is allowed;
guessing silently is not.

## What the check enforces

`.github/scripts/oracle-decisions.sh`, on every pull request:

- every new decision cites evidence that exists at the **base commit**;
- every new decision carries all seven fields, non-empty;
- the vision field either quotes a statement or declares the no-vision class,
  and the class demands real alternatives;
- a decision present at the base commit is neither modified nor removed;
- ids are unique and increasing;
- added requirement ids are at or above R1000;
- at most 150 decisions (a runaway-loop backstop, not a real bound);
- plans under `docs/plans/oracle/` cite a decision that has already landed, or
  cover only requirement ids that already exist in a design document — either
  way a plan there implements landed work, it never proposes any;
- a handoff under `docs/oracle/` is never modified after it is written;
- an optional `**Criterion waived:**` field names at least one `S<n>` and
  carries a reason — see below.

## Waiving a success criterion

`docs/DESIGN.md` §13's criteria are scripts under `acceptance/`, run as a
required check on every pull request
(`.github/scripts/acceptance-criteria.sh`). A failing one is routed here: the
acceptance pass files it as a `BL-<n>`, and the oracle rules on it like any
other logged evidence. Three rulings are available.

- **The test is wrong** — it measures something §13 did not ask for, or measures
  it badly. Record the decision citing the evidence; the script is corrected on
  its own pull request.
- **The implementation is wrong** — back to building. That is the ordinary loop
  doing its job and needs nothing special here.
- **The criterion is met by other means** — the implementation solved the
  problem in a way the script does not recognise. This is the case that needs
  the waiver, because a ruling that leaves the check red unblocks nothing: every
  later pull request stays red and work stops.

So a decision may carry:

    - **Criterion waived:** S3 — <why the script does not recognise what was built>

`acceptance-criteria.sh` reads landed waivers at the base commit and skips that
criterion. Four properties make this an exception rather than a hole:

- **Per-criterion, never per-check.** A waiver on `S3` does nothing for `S4`.
- **Cited, append-only, permanent.** It lives in this ledger, so it inherits
  evidence-citation and immutability for free — no new file and no new trust
  boundary. The same idiom as `docs/escapes.md`: an exception written down
  rather than taken silently.
- **Visible twice**, here and as `pending / owner` in `docs/acceptance.md`. The
  gate goes green; the claim of doneness does not.
- **Self-clearing.** If a later change makes `S3` genuinely pass, the next
  acceptance pass records `pass` and the waiver is moot.

**The oracle may not mark a criterion passed.** It rules, it records, it may
waive — and the row stays `pending / owner`, carrying the reasoning. The owner's
own definition of done is adjudicated by the owner. `docs/acceptance.md` is the
one artifact in an unattended run whose pull request requires their review; if
an agent could rule a failing criterion met, the last checkpoint before the
human becomes something an agent can talk its way past, which is the failure the
whole acceptance mechanism exists to prevent.

A bare waiver with no reasoning is refused by the check. The field is the one
place the oracle sets aside the owner's definition of done, so there has to be
something in it the owner can disagree with.

## The one stop, and it is written down

A decision that would violate a core tenet of `docs/VISION.md` is not made. The
oracle writes a **halt entry** instead — same id sequence, same append-only
rule, a different shape:

    ## OD-<n> — HALTED: <what could not be decided>

    - **Date:** YYYY-MM-DD
    - **Evidence:** ESC-<n>
    - **Tenet relied on:** V<n> — "<the verbatim tenet>"
    - **What a decision would have said:** the ruling that was available
    - **What it needs from the owner:** the smallest change to docs/VISION.md
      that would let this be decided, or the ruling to make directly

A halt does not stop the run — the driver moves to the next phase exactly as it
does today. What it stops is the evidence disappearing. Without an entry here, a
tenet stop and an oracle finding nothing worth acting on produce the same
artifact — no decision — and the delivery driver marks the evidence processed
either way, so the one moment the vision actually did its job is the one moment
nothing records. This ledger is the only append-only document an agent may write
unattended, which is exactly what a halt needs.

Everything else it decides on the evidence it has — it never marks a decision
pending, because a pending decision stops work, which is the failure this whole
arrangement exists to prevent. A halt is not a pending decision: it is a
decision not to decide, recorded.

<!-- Append decisions below, newest at the bottom. Never edit one that has
landed; supersede it with a new decision naming its id. -->

## OD-1 — Template-sync conflicts are the template's to fix; nothing is commissioned here

- **Date:** 2026-08-19
- **Evidence:** ESC-17, BL-12
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; the vision governs the product, and this evidence is about the template's own gate)
- **Alternatives considered:** (1) Commission a repository-local change to `template-sync` teaching it about conflict hunks — rejected: `.github/` is a gate path, owner-owned, and changing it from here is gate tampering however good the patch. (2) Rule a documented bypass procedure into `AGENTS.md` (BL-12's direction 3) — rejected for the same reason: `AGENTS.md` is a gated document and not this ledger's to write. (3) Say nothing — rejected: undecided evidence is re-handed to the oracle every run, and silence here reads as "nothing found".
- **Rationale:** Every viable fix BL-12 lists lives in owner-owned gate paths or upstream in the template repository, where the check itself is owned. The design of *this product* is not contradicted by the evidence, so there is no design change to make and no work an agent here may lawfully do. BL-12 stays the standing intent; the incident record (ESC-17) stands.

The orchestrator should NOT plan anything from this decision. The one useful
motion is upstream: the candidate fix ESC-17 already names (compare against the
replay's pre-resolution tree, permitting differences only inside conflict
hunks) belongs in the template repository, and `docs/template-bugs.md` is this
run's collection point for exactly that.

## OD-2 — The process escapes are answered by mechanisms that have since landed; the rest stays with the owner

- **Date:** 2026-08-19
- **Evidence:** ESC-18, ESC-19, ESC-20
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; all three escapes concern agent process, not the product the vision describes)
- **Alternatives considered:** (1) Add product requirements encoding process rules — rejected: `coverage.sh` would then demand plans for behaviour that is not the pipeline's, and the rules already live where they bind (`AGENTS.md`, the driver, the checks). (2) Commission the unbuilt candidates (widening `escape-refs.sh` to all of `docs/`, a pre-open self-review harness) — rejected: both are gate paths (`.github/scripts/`, `.claude/`), owner-owned. (3) Halt — rejected: no tenet is at stake; these are resolved or owner-gated, not undecidable.
- **Rationale:** Checked against the tree, each escape's recurrence is already guarded. ESC-18: candidate (1) exists and is enforced — `.github/scripts/escapes-append-only.sh` holds `docs/escapes.md` immutable (its companion `backlog-append-only.sh` covers the backlog ledgers); candidate (2), widening `escape-refs.sh`, remains owner/template work. ESC-19: the behavioural rule is recorded (an objection is asked in chat or filed in `docs/BACKLOG.md`, never argued in a pull request body — the 2026-08-14 "explicit plan wins" ruling and the plan-rework queue are that rule working), and the earlier-catch harness is `.claude/`-owned. ESC-20: the queue failure cannot recur unattended — `AGENTS.md` now states one pipeline pull request in flight at a time, `deliver-phase.sh` returns WAIT while any is open, and `pr-queue.sh` reports the author's open queue to the reviewer as a computed fact (deliberately a note, not a failure, per the deadlock reasoning in its header). Nothing here is plannable by an agent, and nothing in the product design was wrong.

## OD-3 — Three fixed defects: the fixes and checks that exist are enough, and closure is bookkeeping

- **Date:** 2026-08-19
- **Evidence:** ESC-21, ESC-22, ESC-23
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; the defects are fixed, and what remains is ledger bookkeeping and owner-owned gate work)
- **Alternatives considered:** (1) Add a requirement re-stating the timestamp/upload_date contract — rejected: the owner already landed R25, which is the design answering ESC-21; a second requirement would duplicate it. (2) Commission the actionlint check for ESC-23 here — rejected: `.github/workflows/` is a gate path and the check equally belongs in the template, where the broken file came from. (3) Leave the ids unread — rejected: the driver would re-hand them every run.
- **Rationale:** ESC-21: the fix is merged and the candidate check exists exactly as the stub named it — `src/find_best_mobo/index.py` reads `timestamp` with a fixed `DATE_SLOP_DAYS = 62`, `tests/fixtures/channel_entries.json` carries entries in the real flat-listing shape, and `tests/test_index.py` asserts a timestamp-only in-range video is kept; the design side was settled by the owner as R25. ESC-22 is the model case: `acceptance/S9.sh` is a demonstrated check, observed red against the defect and green against the fix, on its first CI run. ESC-23's fix landed (`auto-merge.yml` hoists `APP_ID` into job-level `env:` and tests `env.APP_ID` in the step `if:`), and the actionlint candidate stays owner/template-owned — the stub stays a stub until that check runs somewhere. Downstream bookkeeping, which is not this role's path to write: completing correction rows in `docs/escapes.md` and closure rows in `docs/escapes.done.md` for ESC-21 and ESC-22, on a chore branch.

## OD-4 — Merged excerpt windows are re-cut from the cues, never concatenated

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

## OD-5 — Excerpting stays; the whole-transcript path is capped at the bundle token cap

- **Date:** 2026-08-19
- **Evidence:** BL-13, BL-10
- **Requirements added:** R1001
- **Requirements superseded:** (none)
- **Vision statement relied on:** V10 — "Where some other goal can only be met by processing content with no AMD or AM5 signal, that goal loses and a cheaper design is chosen."
- **Vision statements against:** V4 — "Given a choice between a cheaper run and a better-sourced answer, take the better answer." — it does not forbid this: where the evidence is dense, R28 already sends the video as one continuous transcript, which is the whole of BL-13's quality argument for exactly the videos it matters on; and the calibration batch (R8, milestone M2's clipped-verdict inspection) is the designed instrument for measuring whether excerpts cost answer quality on sparse videos. If it shows that, the finding is logged evidence and this decision is superseded at the cost of one entry.
- **Alternatives considered:** Adopt BL-13 wholesale — send every selected video whole, delete excerpting (superseding R5, most of R17, R28) — rejected on three grounds: the 4.8x measurement is the saturated case, which R28 plus R1000 already resolves (with an honest ratio the dense video goes whole and costs its transcript, never 4.8x); on a sparsely-matching video the text outside every mention window is precisely the no-signal material V10 says loses to a cheaper design, and excerpts remain several times cheaper there; and the owner's recorded 2026-08-16 ruling explicitly *kept* excerpting below the threshold — BL-13 is a logged proposal, and reversing a recorded owner ruling with no new measurement beyond the one R28 already answers is not this ledger's to do. Unbounded whole-transcript path — rejected: multi-hour livestreams are in the corpus by owner ruling, and dozens qualifying at once is the lumpy spend the rule exists to remove. Cap at the bundle token cap — chosen, as the blocked plan itself proposed.
- **Rationale:** The hybrid the owner landed (R28) is the right shape once its measurement is honest; what it lacks is the upper bound its own plan flagged as blocking. The vision decides the residual conflict: cost yields to information quality (V4) exactly where the signal is, and material without signal loses to the cheaper design (V10) everywhere else — which is what excerpts-below-threshold, whole-above-threshold, capped-at-the-bundle does.

**R1001** — A video takes the whole-transcript path only when its full
transcript fits within the bundle token cap. Above the cap it falls back to
excerpts regardless of its R28 ratio, so one video's submission always fits in
one bundle and the 80% rule can never create the lumpy cost it exists to
remove. The projection reports how many videos took each path and what each
path costs, so the routing is observable at the checkpoint.

This resolves the pending uncertainty that blocks
`docs/plans/whole-transcript-threshold.md` ("do not build this slice until it
is answered"): it is answered. That plan should be revised to carry R1000 and
R1001 before the slice is built.

## OD-6 — An alias split across caption tokens still matches

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

## OD-7 — A chipset's ITX variant counts as the chipset

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

## OD-8 — The video description is recorded at fetch and matched at selection

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

## OD-9 — A projection with a missing input refuses instead of understating

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

## OD-10 — Every subcommand flag is reachable from the CLI

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
edit. The `run-scripts` workaround (invoking `aliases` through Python) reverts
to a plain CLI call.

## OD-11 — The alias table is a tracked input at a configured path

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

## OD-12 — A plan's contract names the module of every shared type

- **Date:** 2026-08-19
- **Evidence:** BL-3
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; plan hygiene is process, below the vision's altitude)
- **Alternatives considered:** Leave placement to the orchestrator's shared contract block — rejected: the contract derives from the plan, and the asymmetric-brief escape already taught that anything both blind sides can observe must live in the plan, not in prompts. A central `types.py` for all shared types — rejected: a dumping ground, and the placement question returns the moment a type outgrows it. The plan's Signatures block states the module of every shared type and exception — chosen.
- **Rationale:** Two blind authors can agree on behaviour while disagreeing on placement, and BL-3 records the cost: the shared contract had to assign modules ad hoc and put `FetchFailure` in `transcripts.py`, which is circular. The built tree has since corrected the placement — `FetchFailure` lives in `ledger.py`, with a compatibility re-export in `transcripts.py`.

No requirement is added; this is a planning-document correction. The next
revision of `docs/plans/corpus-and-checkpoint.md` (and every future plan's
Signatures block) states, per shared type and exception, the module it lives
in. That revision ratifies `FetchFailure` in `ledger.py` and retires the
`transcripts.py` re-export shim. BL-2, outside this run's scope, is the same
class of correction and can ride in the same revision when it is ruled.

## OD-13 — OD-5 is superseded: the whole-transcript path is uncapped, and an over-cap transcript spans sequential bundles

- **Date:** 2026-08-20
- **Evidence:** BL-14, BL-13
- **Requirements added:** R1008
- **Requirements superseded:** R1001
- **Vision statement relied on:** V4 — "Given a choice between a cheaper run and a better-sourced answer, take the better answer."
- **Vision statements against:** V10 — "Where some other goal can only be met by processing content with no AMD or AM5 signal, that goal loses and a cheaper design is chosen." — the statement OD-5 capped the path with, and it does not forbid uncapping it: a video at or above R28's 80% ratio is dense in AM5 signal by measurement, the opposite of no-chance-of-relevance material, and the sparse long stream that would have produced the lumpy request never reaches the ratio once overlapping windows merge into clusters and are re-cut (R5, R1000) — so removing the cap spends nothing on no-signal material.
- **Alternatives considered:** Leave R1001 standing and let the owner's amended R28 override it informally — rejected: the two design documents are read together and `coverage.sh` unions them, so a landed requirement the design's own text now contradicts ("The whole-transcript path is not capped — this supersedes R1001") is exactly the incoherence this ledger's supersession lifecycle exists to close. Keep a softer cap (a higher ceiling, or excerpt-fallback only above some multiple of the bundle cap) — rejected: the owner's 2026-08-19 ruling (`docs/DECISIONS.md`) names the mechanism directly — a transcript larger than one bundle's token cap is delivered across sequential bundles, never bounced back to excerpts — and the lumpy-spend concern R1001 answered is handled at its source by clustering. Supersede R1001 with nothing — rejected: R1001's second sentence carried the routing's observability, and dropping it silently would land a behaviour change at the checkpoint that no requirement obliges anything to report; R1008 keeps the measurement and sheds the cap.
- **Rationale:** OD-5's two grounds are both gone. Its reading of BL-13 as an unapproved proposal it could not adopt against an earlier owner ruling was corrected by the owner themselves — all backlog items through BL-13 are approved as of 2026-08-19 (`docs/BACKLOG.approved.md`), and the owner says so in the ruling's own postmortem clause. And the design it deferred to has been amended by its owner: R5 now specifies transitive clustering with R1000's re-cut, and R28 now states the whole-transcript path is not capped, with over-cap transcripts delivered across sequential bundles. BL-14 filed the residue as HIGH because the merged plan `docs/plans/oracle/capped-whole-transcript-path.md` implements the reversed decision — its slice 1 routes a saturated over-cap video back to excerpts (`EXCERPTS_OVER_CAP`), which is now a rejected behaviour, and its `covers:` names R1001. This decision adopts BL-14's proposed default in full: R1001 is superseded, that plan is partly wrong and must not be built as merged, and the steward re-cuts it to the clustering design before anything builds the routing.

**R1008** — The cost projection reports the routing per path: how many videos
were sent as whole transcripts and how many as excerpts, and the characters and
projected tokens each path accounts for. For the whole-transcript path it also
reports how many videos exceed one bundle's token cap and the number of
sequential bundles each such transcript spans, so the uncapped path's largest
submissions are visible at the checkpoint before anything is spent. Supersedes
R1001: the observability is kept, the cap and the excerpt-fallback above it are
not.

Downstream: `docs/plans/oracle/capped-whole-transcript-path.md` is partly wrong
— slice 1's cap check and `EXCERPTS_OVER_CAP` path, slice 2's
no-whole-block-over-the-cap invariant, and slice 3's `videos_over_cap` count
all implement the superseded R1001 — and it must not be built as merged. Its
sequencing note survives: R1000's re-cut (`recut-merged-excerpts`, merged and
not yet built) still lands first, because the ratio the routing reads is only
honest once each transcript character is counted once.
`docs/plans/whole-transcript-threshold.md` remains the owner's to revise;
nothing here changes that.

## OD-14 — The zero-duration warning judges the listing shape, not the count

- **Date:** 2026-08-20
- **Evidence:** BL-15, ESC-21
- **Requirements added:** R1009
- **Requirements superseded:** (none)
- **Vision statement relied on:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not."
- **Vision statements against:** V12 — "If he did not say it, the answer must say he did not say it." — the nearest, because demoting eight banners to a one-line count could read as making the pipeline quieter about missing data; it does not: every entry is still classified and recorded in the index with its reason (R1), the count still prints on every run, and the banner is restored to firing only when it carries information — silence still reads as silence, and an alarm reads as an alarm again.
- **Alternatives considered:** Delete the warning — rejected: the case it was written for, a genuine video returned with a real date but no duration and silently classified as a Short, is a real silent-drop shape, and BL-15's second cost argues for sharpening that signal, not removing it. Raise the count threshold — rejected: any fixed count is wrong the day the channel posts one more Short, and the premise the current threshold rests on ("only one video can legitimately lack a duration") was measured false on the first real run. Classify from a listing-provided Shorts marker alone (BL-15's direction 2) — not adopted as the requirement: whether the flat listing carries such a marker is a mechanism question for the plan, and the marker's absence would put the warning right back on inference; the plan may use it where present. Judge each entry on its own evidence — chosen, BL-15's directions 1 and 3 together.
- **Rationale:** Measured on the first real index run after the `timestamp` fix: eight videos reported no duration, the 72-character banner fired, and all eight were genuine Shorts in the flat listing's distinct Shorts shape — no `duration` field and no date in either field. That shape is how the flat listing returns Shorts, so it recurs on every run: the warning is a permanent false positive, and its real case — a dated entry with no duration — would be a ninth id invisible inside a list of eight expected ones. The check that exists to catch a silent drop currently guarantees one goes unnoticed, which is a loss V1 cannot afford: a genuine board video misclassified as a Short leaves the corpus before anything downstream can see it. ESC-21 already recorded that fixtures agreeing with the code and disagreeing with the real listing shape cost a full run; the same listing is still not fully described by the fixtures, which is why the requirement pins the distinguishing pair as tests.

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

Measurement: the printed index summary is already captured in the run reports
under `docs/runs/`, and the test pair pins both sides in the suite — no new
collection mechanism is needed.

## OD-15 — R1002 applies within one cue; a cross-cue split is counted, never matched

- **Date:** 2026-08-20
- **Evidence:** BL-16, BL-8
- **Requirements added:** R1010
- **Requirements superseded:** (none)
- **Vision statement relied on:** "When a decision alters behaviour that no existing check, test, run report or review artifact would notice, adding the thing that notices is part of the decision — not a follow-up, and not optional." — this is what decides the measurement half of this ruling (R1010's counter). The within-cue/cross-cue binary itself is a mechanism question no vision statement decides, and **Alternatives considered** carries that weighing.
- **Vision statements against:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not." — the nearest, because scoping out cross-cue splits leaves a class of real mentions unfound. It does not forbid this: the two damage classes differ in kind. Speech-to-text mangling is systematic per name — every utterance of "Tomahawk" arrives as `toma hawk` — so before R1002 the board was invisible *everywhere*, which is the total loss BL-8 measured. A cue boundary falls where the caption timing happens to fall, so a name straddling a break in one utterance is whole in its others (and its within-cue splits now match under R1002); title hits have no cues and description hits (R1004) have none either, so neither include signal is touched. The residue is a per-occurrence fraction, not a per-board blindness — and R1010's counter is what turns "the residue is small" from an assumption into a per-run measurement, so if V1 is in fact being shortchanged, the evidence to say so arrives by design instead of never.
- **Alternatives considered:** (1) Cross-cue matching now — scan cue-joined normalized text and map every match offset back to its source cue — rejected: no cross-cue failure has ever been measured (BL-8's three failures were all tested as within-cue text), the shape change reshapes `find_mentions` and the plan's slice boundaries, and it forces an unforced answer to which cue's `start_seconds` a spanning mention carries — the field R5 cuts every excerpt window from and R14's timestamped links are built on, exactly the expensive-to-reverse decision BL-16 flags. Adopting that structural cost to chase an unquantified marginal recall, while R1002's measured wins land regardless, is backwards. (2) The steward's literal default — scope cross-cue splits out with nothing added — rejected: the loss is silent by construction; no recall report, selection count, fixture or run artifact would ever show a cross-cue miss, so the ruling could never be evaluated against evidence or superseded by it. (3) Merge all cues into one text at parse time and keep per-cue offsets — rejected as (1) in different clothes: the offset mapping and the timestamp question are identical, only moved into the parser. (4) Within-cue rule plus a boundary counter that detects, reports, and never emits — chosen.
- **Rationale:** BL-16 is right that OD-6 fixed the join rule without naming the text the rule runs over, and the shipped fixture confirms the missing case is real: auto-caption cues break mid-phrase (`...Taichi board` / `has a twelve phase VRM`). But plausible and measured are different states of evidence, and the reversal costs are asymmetric: ruling within-cue today and widening later costs one superseding entry and a contained code change; ruling cross-cue today commits `find_mentions`'s shape and a guessed timestamp semantics before any measurement says the case matters. So the ruling takes the cheap, reversible side and instruments the boundary: the counter is one extra scan over adjacent-cue joins, pure CPU, offline, no token spend — V3 is untouched. Confidence is high on the scoping; the counter is the hedge. This also moots BL-16's second question — no mention ever spans cues, so `start_seconds` is always the start of the single cue containing the match — and answers its last one: the plan gains the counter work, and whether that is a fourth slice or folds into an existing one is the steward's sizing call.

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

Measurement: the selection report already lands in the run records under
`docs/runs/`, so the counter rides the existing mechanism; the first real
corpus run quantifies what this ruling scoped out, and a material count is
logged evidence for superseding this decision rather than a silent loss.
