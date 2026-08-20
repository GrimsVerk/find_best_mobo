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

## OD-16 — R1002's variant fixture is a labelled reconstruction; the lost original is recorded as unrecoverable

- **Date:** 2026-08-20
- **Evidence:** BL-17, BL-8
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not."
- **Vision statements against:** V12 — "If he did not say it, the answer must say he did not say it. Silence has to read as silence." — the nearest, because a fixture presenting invented variants as "BL-8's measured set" would be exactly that shape one level down: reconstruction wearing measured provenance. It does not forbid this ruling because the ruling forbids that presentation — the fixture declares itself a reconstruction, only the failures BL-8 actually names carry measured provenance, and any failing-today mark must be observed red before it is recorded as such.
- **Alternatives considered:** (1) Pin the observed failures alone (BL-17's stated alternative and the merged plan's own open question): a small fixture of `toma hawk`, `aor us master`, `air us elite`, the `steel-legend` hyphen case and the reject set — rejected: it pins only the fix and discards the larger half of what BL-8 measured, which is that 49 of 52 variants *already matched*. The R1002 slice recompiles every form's pattern, so the class most exposed to silent regression is precisely that already-matching majority, and a failures-only fixture would never notice a pattern rewrite that broke `giga byte` or `x 870 e` — a recall loss V1 cannot see arriving. (2) Recover the original list — rejected: BL-17 already established it is in no commit, no journal entry and no run record; the honest state is *lost*, and this decision records that so no future agent burns a cycle searching again. (3) Reconstruct and assert the count 52 as BL-8's measurement — rejected: the number is not quite supported (BL-8's 49 + 3 = 52 arithmetic, the draft reconstruction's five failing variants), and a suite asserting measured provenance it lacks is the false record `AGENTS.md`'s honesty rule forbids. (4) A labelled reconstruction — breadth across BL-8's damage classes, the named failures verbatim, a `never_match` reject set, and a size floor pinned to the fixture's own landed count — chosen; it is BL-17's proposed default with the provenance claims made honest.
- **Rationale:** BL-17's two "facts worth a ruling" both resolve on a careful read of BL-8. The hyphenated `steel-legend` failure is a parenthetical, related observation — BL-8's own text sets it apart from the 52 tested variants — so 49 matched + 3 failed = 52 is internally consistent and the count needs no room for it. And the draft reconstruction's five failing variants are a property of that reconstruction (it placed hyphen-class cases inside its 52), not evidence that the original had five; nothing obliges a reconstruction to reproduce a failure count, only never to claim one it did not observe. So the number 52 describes a lost list: it may size the reconstruction, and it may never be asserted as measurement. What remains is what the fixture is *for*: pinning R1002's measured wins and protecting the already-matching majority through the pattern rewrite. Both point at breadth with honest labelling, which is what the merged plan's slice 3 already cuts.

What discharges R1002's sentence "BL-8's measured 52-variant set lands as a
fixture; the named failures must match", given that the measured set cannot
land because it no longer exists:

- The fixture **declares itself a reconstruction** and states that BL-8's
  original list is unrecoverable. BL-8's count survives as history in the
  backlog entry, never as a claim of measured provenance in the suite.
- The **three failures BL-8 names** — `toma hawk`, `aor us master`,
  `air us elite` — land verbatim and must match; that clause of R1002 stands
  unchanged. The `steel-legend` hyphen case lands verbatim beside them,
  labelled with its parenthetical provenance.
- A **failing-today mark is demonstrated, or it is labelled unverified**: the
  draft's five `†` marks are recorded as failures only after being observed
  red against the pre-fix matcher and green after — the same
  demonstrated-or-labelled rule the ratchet applies to checks.
- The **`never_match` reject set is part of the fixture**: R1002's
  never-a-proper-substring sentence is only pinned by negative cases.
- The **size assertion is a floor on the fixture's own landed count**, so a
  later tidy-up cannot silently shrink it; its docstring states the count's
  provenance is the reconstruction. The number 52 carries no evidentiary
  weight anywhere in the suite.

Downstream: `docs/plans/oracle/caption-split-aliases.md` builds as merged —
its slice 3 already satisfies every point above, so this ruling is the
next-cycle review `AGENTS.md` promises a LOW default, ratifying it; no re-cut
and no new requirement. Measurement: the fixture is itself the measurement,
alongside the `aliases --check` recall report OD-6 already names — no new
collection mechanism.

## OD-17 — R1003's regression title is a labelled reconstruction; only the board name and the zero-`B850` property carry measured provenance

- **Date:** 2026-08-20
- **Evidence:** BL-18, BL-9
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** V1 — "**Real, sourced information about which boards Buildzoid considers safe** for a 7950X3D or 9950X3D — and which he does not."
- **Vision statements against:** V12 — "If he did not say it, the answer must say he did not say it. Silence has to read as silence." — the nearest, one level down exactly as in OD-16: a test presenting an invented title as "the real B850I review's title" would be reconstruction wearing measured provenance. It does not forbid this ruling because the ruling forbids that presentation — the docstring declares the reconstruction, only what BL-9 actually recorded claims measured provenance, and nothing asserts on the invented wording.
- **Alternatives considered:** (1) Assert on the board-name token alone with no surrounding title (BL-18's stated alternative, the plan's own open question) — rejected: a title that is nothing but the board name exercises the pattern only at string edges, while the failure R1003 fixes lives at both lookaround boundaries mid-text; the invented surroundings buy the realistic mid-title position and cost nothing, because no assertion reads them. (2) Fetch the video's real title from YouTube and commit it — rejected: a title fetched today is not the title BL-9 measured (titles are editable, and the measured string survives in no commit, journal entry or run record), so for the one property that matters — zero `B850` matches at measurement time — a fetched title carries the same reconstruction status while adding a network step V3 has no reason to buy and the offline suite cannot repeat. A future agent that does recover the measured title has logged evidence for superseding this decision — file it, never swap it in silently. (3) A labelled reconstruction — BL-9's board name verbatim, invented surroundings declared, assertions only on the canonical and the matched form — chosen; it is BL-18's proposed default, OD-16's provenance rule applied one file over, with the constraints below making it demonstrable.
- **Rationale:** BL-9's own measurement constrains the reconstruction more tightly than BL-18 notes, in both directions. First, zero `B850` title matches under the pre-fix matcher means the real title cannot have spelled the chipset with a separator — `b850-i` and `b850 i` both leave `b850` with a clean right boundary and would have matched — so the real title carried the chipset only inside an unseparated `B850I` token, which is exactly the shape the verbatim board name `MSI MPG B850I Edge TI` reproduces. The reconstruction is faithful in the one dimension the regression turns on. Second, the reconstruction is *not* faithful in a dimension the shipped table can see: `msi` is a vendor form in `data/aliases.toml`, so a title carrying the board name verbatim title-hits MSI before and after the fix. The reconstruction therefore reproduces BL-9's measured zero-`B850` property and nothing more — in particular it does not reproduce the real video's recorded invisibility to title matching (BL-9, OD-8), and no test or docstring may claim it does.

What discharges R1003's sentence "Regression: the real B850I review's title
auto-includes on its chipset", given that the measured title string is in no
commit, journal entry or run record (`data/index.jsonl` is gitignored):

- The test's docstring **declares the title a reconstruction** and states that
  the measured title is absent from the record — absent, not unknowable: the
  video is public, which is why recovering it later is a supersession with
  logged evidence rather than a silent swap.
- **`MSI MPG B850I Edge TI` lands verbatim from BL-9** and is the only wording
  with measured provenance; the docstring records what BL-9 did measure — zero
  `B850` matches in title and body on a 33-minute review — as the provenance of
  the case, never of the invented string.
- **Nothing asserts on the invented wording**: the assertions are the canonical
  (`B850`) and the matched form (the ITX spelling).
- **The invented surroundings must not contain any form the pre-fix matcher
  resolves to `B850`** — a bare `b850` token in the padding would make the
  regression green before the fix, and a red-then-green observation is the
  demonstration the blind test exists to give. This is OD-16's
  demonstrated-or-labelled rule applied to the one mark this test carries.
- **A test claiming the video was excluded before this plan must arrange that
  itself**: under the shipped table the reconstructed title is vendor-visible,
  so the plan's selection slice demonstrates pre-fix exclusion only against a
  table whose forms the title does not otherwise hit — its own `tmp_path`
  table, as the plan already writes, with no `msi`-like form reachable from
  the title it uses.

Downstream: `docs/plans/oracle/itx-chipset-variant.md` builds as landed — this
is the next-cycle review `AGENTS.md` promises a LOW default, ratifying it; no
re-cut, no covers change, and the constraints above bind slice 2's fixture
author. Measurement: the regression test itself, observed red against the
pre-fix matcher and green after, alongside the recall report and selection
counts R1003 already names — no new collection mechanism.

## OD-18 — `--help` after a subcommand is forwarded: the subcommand's help prints

- **Date:** 2026-08-20
- **Evidence:** BL-19, BL-5
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; which help screen a CLI prints is below the vision's altitude, exactly as OD-10 recorded for the dispatch mechanics this elaborates)
- **Alternatives considered:** (1) Keep today's behaviour — the top-level parser owns `-h/--help` everywhere, so `find-best-mobo aliases --help` prints the dispatcher's help — rejected: R1006's first sentence is that every flag a subcommand *documents* is reachable from the CLI, and a help screen nobody can reach documents nothing — `--check` would stay documented only in source, which is BL-19's own statement of the problem. Worse than the omission, the output is affirmatively wrong: a question asked about `aliases` is answered with a screen that never mentions `aliases` or any flag it takes. And it makes `-h/--help` the one token permanently exempt from R1006's forwarding rule — a special case the dispatcher contract would carry forever, for a screen still reachable as `find-best-mobo --help`. (2) Print both helps, the dispatcher's then the subcommand's — rejected: two usage lines under two prog names read as an error, and no widely-used multi-command CLI answers one question with two screens. (3) Split the pair — keep `-h` top-level, forward `--help` — rejected: the two spellings are one flag everywhere argparse appears, and splitting them turns a convention into a trap. (4) Forward it — the steward's default — chosen.
- **Rationale:** BL-19 is right that R1006 and the shipped CLI disagree on exactly this token: argparse auto-registers `-h/--help` on the top-level parser and consumes it before dispatch, so the one flag R1006 could not reach was the one that documents all the others. Forwarding is also the convention of every multi-command CLI the owner already uses — `git`, `pip`, `uv` all print the subcommand's help after its name — so the chosen behaviour is the one a user will guess first. Nothing reachable is lost: `find-best-mobo --help` and a bare `find-best-mobo` keep today's output and exit codes (0 and 2), as the merged plan pins. The risk class is as filed: one console output, reversible by deleting one branch in `cli.py`, and a wrong ruling here is superseded at the cost of one entry. This is the next-cycle review `AGENTS.md` promises a LOW default, ratifying it.

Downstream: `docs/plans/oracle/subcommand-flag-forwarding.md` builds as merged
— no re-cut, no covers change. Its sequencing note stands: it shares every
command module with `docs/plans/oracle/refuse-on-missing-artifact.md`, and the
two are never built in parallel. Measurement: the plan's own tests pin both
sides — `main(["aliases", "--help"])` exits 0 and the output names `--check`,
`main(["--help"])` prints the top-level help, `main([])` still returns 2 —
and slice 2's package-walking guard test extends the property to every future
stage, so the behaviour this ruling changes is observed by the suite on every
pull request. No new collection mechanism is needed.

## OD-19 — `whole-transcript-threshold` slice 1 is superseded work no agent may build; closing the plan is the owner's edit

- **Date:** 2026-08-20
- **Evidence:** BL-20, BL-14
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** (none — no statement in docs/VISION.md tells against this; which plan a driver dispatches, and how a plan document is closed, is process below the vision's altitude — the routing behaviour itself was decided by the owner's amended R5/R28, R1000 and R1008, not here)
- **Alternatives considered:** (1) Have an agent close the plan — mark it `status: merged`, delete it, or cut slice 1 — rejected: `docs/plans/` is `CODEOWNERS`-held and this plan is the owner's, so every closing edit is theirs, which is BL-20's own finding ("nothing an agent may write does"). (2) Leave the prohibition where it lives today, in the run handoffs — rejected: a handoff instructs one run's orchestrator, while `deliver-phase.sh` selects plans from frontmatter and merged `feat/` branches and reads no handoff, so the prohibition expires exactly when the queue ahead of the plan drains and the dispatch happens — BL-20's scenario. (3) Record the prohibition in this ledger — chosen: plans derive from the design layer (`docs/DESIGN.md` and this file read together, `AGENTS.md` "Mid-run authority") and the review gate reads both at every pull request's base commit, so a statement here is durable and stands in front of every future pull request, which is the strongest mitigation an oracle-writable path affords. A halt was not on the table: no tenet is at stake, and a decision exists.
- **Rationale:** BL-20 is verified against the tree. The plan's `status:` is `draft`; `deliver-phase.sh` skips a plan only on `status: merged` or a merged `feat/<slug>` branch; no `feat/whole-transcript-threshold` branch will ever merge because the routing is being built under `capped-whole-transcript-path`; and the plan sorts last in the walk, so the dispatch happens precisely when everything else is built — unattended, with every mechanical check green. The slice itself is superseded three ways: it routes on a ratio computed from concatenated merged excerpts, which R1000 rules must be re-cut so each transcript character counts once — with the dishonest ratio, saturation over-triggers; it predates R5's clustering; and it treats its own ceiling uncertainty as "pending — do not build" although the owner's 2026-08-19 ruling and OD-13 answered it (uncapped, sequential bundles, R1008's routing report). So the decision makes the inevitable dispatch harmless rather than pretending to prevent it: the prohibition below is design-layer text the review gate reads, and any pull request building the slice contradicts the design at its base commit.

**The standing prohibition:** slice 1 of `docs/plans/whole-transcript-threshold.md`
implements design this ledger and the owner's amended `docs/DESIGN.md` have
superseded, and it must not be built. An orchestrator dispatched with that slug
has nothing lawful to build: the correct motion is to open no pull request,
report this decision, and stop. A pull request that builds the slice anyway
contradicts R5, R28 (as amended), R1000 and R1008 at its base commit, and the
review gate should block it citing this decision.

**The owner's closing edit**, any one of BL-20's three, with one timing nuance:
`status: merged` is the template's own field for work that lands under another
name, but the template says to set it when the work is done — its honest moment
is after `feat/capped-whole-transcript-path` merges, not before. Deleting the
plan, or cutting slice 1 and R28 from it, is honest immediately; the 80%-ratio
ruling the document records is preserved in `docs/DECISIONS.md` either way, so
deletion loses no record.

Measurement: no new mechanism. The run report (`docs/runs/<timestamp>/run.md`)
already records every dispatch, so a dispatch of this slug is durable evidence
in the committed record, and the review gate reads this ledger at the base
commit, so any pull request building the slice meets this decision.

## OD-20 — A superseded requirement id is design history, not unscheduled work: R1001's coverage gap is false and no plan may claim it

- **Date:** 2026-08-20
- **Evidence:** BL-21, BL-14
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** (no vision statement decided this)
- **Vision statements against:** V12 — "Silence has to read as silence." — the nearest, one level down as OD-16 read it: subtracting an id from the coverage universe could make scheduled-looking work vanish silently, absence reading as completion. It does not forbid this because the ruling forbids exactly the silent form: a superseded id is reported as its own excused class, never dropped from the report, and the pairing rule below makes every retirement name its replacement in the ledger's own text.
- **Alternatives considered:** (1) Green the report by having some plan name R1001 in its `covers:` — rejected by name: BL-21 identifies this as the harmful pressure, and it is the over-claim the adequacy note exists to expose — `covers:` is read as "this plan delivers this id", and R1001's behaviour (the cap, the excerpt-fallback above it) is deliberately not being built, so the claim is false the day it is written. (2) Fix `coverage.sh` from here — rejected: `.github/scripts/` is a gate path, owner-owned, and BL-21 is right that the hole is the template's, so the durable fix belongs upstream where every generated project inherits it. (3) Rule only that the gap is false and leave the script's eventual shape open — rejected: BL-21's three directions are not equivalent, and leaving the choice open invites the cheapest implementation, silent subtraction, which is the one form the nearest vision concern actually tells against. (4) Rule the semantics, bind the ledger's own pairing practice as a standing rule, and name the recommended script shape for the owner — chosen.
- **Rationale:** BL-21 is verified against the tree. `coverage.sh`'s `ids_from()` reads `docs/DESIGN.md` §5 and column-anchored `**Requirements added:**` lines from this ledger, and nothing reads `**Requirements superseded:**`; this ledger is append-only, so R1001 sits in the requirement universe permanently; the re-cut plan honestly covers `[R28, R1008]`; therefore `R1001 NOT PLANNED`, exit 1, on every run from now on. The ruling on the semantics: the design layer is its two documents read together, and supersession is this ledger's documented lifecycle — so the current design is the surviving requirements, and a superseded id is design history. `AGENTS.md`'s definition of done ("every requirement of the design … covered by a merged plan") quantifies over surviving requirements; R1001's reported gap is a script limitation, not unscheduled work. Three consequences bind now: no plan may name a superseded id in `covers:`; no planning is commissioned for one; and until the script learns supersession, a `coverage.sh` exit 1 whose only gaps are superseded ids is read as "no gap", citing this decision, by anything that branches on it.

**The standing rule this ledger binds on itself** (BL-21's third direction,
already this ledger's practice): every superseding requirement's text names the
id it retires — R1008 already opens its closing sentence "Supersedes R1001" —
so a reader, and one day the script, can pair every retirement with its
replacement from the text alone.

**The recommended script fix, owner-owned and belonging upstream in the
template:** BL-21's first direction with the second's reporting — subtract the
ids named by column-anchored `**Requirements superseded:**` lines (the same
anchoring that keeps the schema's indented example inert for `**Requirements
added:**`), and report them as their own excused class alongside the
non-functional absences — "superseded (design history): R1001, retired by
R1008" — so the retirement reads as a decision, never as a silent
disappearance.

Measurement: no new mechanism. `coverage.sh`'s own report is the observable —
re-runnable by anyone at any commit — and the run reports under `docs/runs/`
record the driver's phase decisions that branch on it; the pairing rule is
checkable by reading this ledger.

## OD-21 — A steward dispatch for a decision whose every added requirement is superseded is false: the steward writes no plan, cites this decision, and stops

- **Date:** 2026-08-20
- **Evidence:** BL-22, BL-21
- **Requirements added:** (none)
- **Requirements superseded:** (none)
- **Vision statement relied on:** V3 — "Cost is about not being *stupid* — not spending budget I could have used on other projects — rather than a hard constraint." — this is what the conduct half of the ruling turns on: BL-22 measures each false dispatch costing a full unattended session that re-derives the supersession from the ledger before stopping, and the ruling converts that recurring spend into one citation. The dispatch mechanics themselves are process below the vision's altitude, and **Alternatives considered** carries that weighing.
- **Vision statements against:** V12 — "Silence has to read as silence." — the nearest, as OD-20 read it one level down: a steward instructed to write nothing and stop could make a stuck loop read as a quiet, healthy one — absence of artifacts reading as absence of trouble. It does not forbid this because every dispatch is already durably recorded (the run reports under `docs/runs/` log the driver's phase decisions, which is precisely the mechanism that measured BL-22), and the ruling requires the stopping steward to name this decision in its report, so each recurrence lands in the committed record as a symptom of the known livelock, never as silence.
- **Alternatives considered:** (1) Let some plan clear the gap by naming R1001 in its `covers:` — rejected by name in OD-20 and again here: the behaviour R1001 describes (the cap, the excerpt-fallback above it) is deliberately not being built, so the claim is false the day it is written, and the pressure to make it is exactly the harm BL-21 warned the false gap would create. (2) Fix the scripts from here — `coverage.sh` (subtract superseded ids; BL-22's own preferred direction, since the dispatch reads that script's gap list and nothing else, so one parser learns supersession rather than two) or `deliver-phase.sh` step 4 (skip a decision whose every added requirement is superseded) — rejected: `.github/scripts/` and `.claude/scripts/` are owner-owned gate paths, the same ground OD-1 and OD-20 declined to touch; the recommended shapes are recorded below for the owner and belong upstream in the template as both filings say. (3) Game the dispatch's mapping — a new ledger entry whose `**Requirements added:**` line repeats R1001 so the driver's grep resolves the gap to a different decision — rejected outright: it is parser-gaming, it merely renames the livelock (the driver dispatches a steward for the new decision instead), and an added-requirements line asserting an addition that is not one is a false record. (4) A halt — no tenet is at stake and a decision exists. (5) Record the steward's conduct in the design layer, as OD-19 did for the orchestrator's false dispatch — chosen: this ledger is the one durable, oracle-writable text every steward reads at dispatch and the review gate reads at every pull request's base commit.
- **Rationale:** BL-22 is verified against the tree, and it is measured rather than predicted — PR #129, opened mechanically as "Plan for OD-5", contains no plan and only the BL-22 filing itself. The mechanism: `deliver-phase.sh` step 4 takes `coverage.sh`'s gap list, maps each R≥1000 gap back to the decision whose `**Requirements added:**` line names it, and emits `PHASE=STEWARD` before the plan walk and before `PHASE=PLAN`; `coverage.sh` reads no `**Requirements superseded:**` line, so R1001 is a permanent gap, the map permanently yields OD-5, and the driver can never again reach orchestration, milestone planning or acceptance. No agent-writable path can break the loop: this ledger is append-only, both scripts are owner-owned, and the one write that would green the report is the over-claim OD-20 forbids. What this ledger can do is what OD-19 did for BL-20's inevitable dispatch — make it harmless, and now also cheap. The ruling is stated generally because the mechanism is general: a `PHASE=STEWARD` dispatch naming a decision all of whose added requirements are superseded is a false dispatch, and the dispatched steward has nothing lawful to cut. The correct motion is to write no plan, report this decision, and stop — without re-deriving the supersession from the ledger, which is the session-sized spend V3 rules out paying on every cycle. A plan written on such a dispatch implements behaviour the owner reversed and contradicts the surviving design at its base commit (in OD-5's case: R5 and R28 as amended, R1000, R1008); the review gate should block it citing this decision, exactly as OD-19 binds the orchestrator's case. This does not unstick the driver — nothing an oracle may write can — so the unlock is named for the owner below with its priority raised: what OD-20 recorded as the recommended script fix, BL-22 turns into the single edit standing between the driver and any further unattended progress.

**The standing rule:** a steward dispatched for an `OD-<n>` whose every id on
its `**Requirements added:**` line is named on some later decision's
`**Requirements superseded:**` line writes no plan and stops, citing this
decision. Today that set is exactly OD-5 — R1001, retired by R1008 (OD-13) —
and the rule is stated generally so the next supersession does not need a
BL-22 of its own.

**For the owner, in priority order:**

1. **The `coverage.sh` supersession fix OD-20 records** — subtract ids named
   by column-anchored `**Requirements superseded:**` lines and report them as
   their own excused class, never silently — is now the unlock for the whole
   delivery loop, not hygiene: the steward dispatch reads that script's gap
   list and nothing else, so this one edit closes BL-21 and BL-22 together.
   It is owner-owned and the hole is the template's, so it belongs upstream.
2. **The gate-side backstop BL-22 proposes** is worth taking in the same
   motion: `oracle-decisions.sh` fails a plan under `docs/plans/oracle/` whose
   cited decisions' added requirements are all superseded, so a steward that
   misses a supersession is stopped by a check rather than by its own reading.
3. **Fixing this re-arms BL-20's hazard.** The moment the driver passes step 4
   again it resumes the plan walk, and the first thing the unstuck loop may do
   is emit `PHASE=ORCHESTRATE SLUG=whole-transcript-threshold`. OD-19's
   standing prohibition governs that dispatch until the owner's closing edit
   on that plan lands.

Measurement: no new mechanism. The run reports under `docs/runs/` already
record every dispatch and phase decision — they are how BL-22 was measured —
and a stopping steward's citation of this decision lands in that same record;
`coverage.sh`'s report stays re-runnable at any commit, so the moment the
owner's fix lands, the same observable shows the superseded class excused and
the loop advancing.
