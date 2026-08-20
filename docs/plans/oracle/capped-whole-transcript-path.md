---
slug: capped-whole-transcript-path
status: draft
created: 2026-08-19
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R28, R1008]
---

# The whole-transcript path, uncapped, across sequential bundles — Plan

**This document was rewritten on 2026-08-20.** It previously implemented
**OD-5 / R1001**, which capped the whole-transcript path at the bundle token cap
and bounced an over-cap video back to excerpts. **OD-13 superseded R1001**, and
this plan now specifies the opposite behaviour. The slug is deliberately
unchanged — CI resolves a plan by its slug appearing in a branch name, so
renaming it would strand every reference OD-13 and the oracle handoffs make to
this path, and a steward may write a plan but not rename or delete one. Read the
slug as an address, not as a description; the plan's subject is the **uncapped**
path.

Implements **OD-13** (`docs/DESIGN.oracle.md`), which supersedes **R1001** and
adds **R1008**:

> The cost projection reports the routing per path: how many videos were sent as
> whole transcripts and how many as excerpts, and the characters and projected
> tokens each path accounts for. For the whole-transcript path it also reports
> how many videos exceed one bundle's token cap and the number of sequential
> bundles each such transcript spans, so the uncapped path's largest submissions
> are visible at the checkpoint before anything is spent. Supersedes R1001: the
> observability is kept, the cap and the excerpt-fallback above it are not.

The behaviour R1008 makes observable is the owner's amended **R28**: at or above
the 80% ratio the whole transcript is sent, **the path is not capped**, and "a transcript
larger than one bundle's token cap is delivered across sequential bundles rather
than falling back to excerpts; the mechanics are the implementing plan's to
specify." Those mechanics are this document.

## Summary

Build R28's saturated-video routing to the design the owner landed: a video whose
clusters have grown to cover it is sent as one whole transcript, **however big it
is**, and a transcript too large for one bundle is delivered across sequential
bundles rather than bounced back to excerpts.

- **No cap is consulted when routing.** At or above R28's 80% ratio the video
  goes whole; below it, excerpts as today. Size decides only how many blocks the
  transcript is delivered in.
- **An over-cap transcript is split at cue boundaries** into consecutive parts,
  each within `bundle_token_cap`, greedy in cue order, never inside a cue. Order
  is preserved, so the parts land in sequential bundles — a property of the
  existing packer, asserted rather than engineered.
- **Blocks say what they are.** `Excerpt` gains `form`, `part` and `part_count`,
  all defaulted; the bundle XML gains `form`, `part` and `parts` attributes — an
  output-format change to the file M2's agent will read.
- **Routing lives in a new `submission.py`**, two-valued (`EXCERPTS` | `WHOLE`);
  the superseded `EXCERPTS_OVER_CAP` path is gone. The 80% threshold stays a
  module constant — R17 enumerates the levers and it is not among them.
- **The projection gains R1008's figures**: per-path video counts, characters and
  projected tokens, plus how many whole-path videos exceed one bundle and how
  many bundles each such transcript spans, named. `project()` gains a submissions
  argument.

Costs: three new XML attributes; five more projection lines and one per spanning
video; **R1001 becomes a requirement no plan covers**, because `coverage.sh` has
no notion of supersession and will report it NOT PLANNED from now on (BL-21); and
**this plan must not be built first though the driver offers it first** — its
slug sorts ahead of `recut-merged-excerpts`, which OD-13 says lands before it
(see "Sequencing"). Not done here: R1000's cluster re-cut, keeping a split
transcript inside one batch, window sizes and the R17 levers, selection, and the
extraction prompt's wording.

No uncertainties: every decision derived from the design, the six closest to the
line worked through below. **What I need you to rule on:**
`docs/plans/whole-transcript-threshold.md` is yours and is still partly wrong —
its slice 1 builds this routing without the clustering or the sequential bundles,
and its "pending" ceiling uncertainty is answered by OD-13. Mark it superseded or
delete it: `deliver-phase.sh` dispatches every plan with no merged `feat/<slug>`
branch, so as written the driver will eventually commission that superseded slice
(BL-20).

## Uncertainties

**No uncertainties — every decision derived from the design.** Nothing here was
guessed, so nothing is filed under "Uncertainties awaiting oracle ruling" and
nothing waits on a ruling. Six questions came close enough to the line that the
derivation is worth showing rather than asserting; an empty section would hide
exactly the reasoning the gate exists to check.

- **Whether to revise this plan in place or replace it under a new slug.**
  Delegated in terms by the handoff that dispatched this work
  (`docs/oracle/handoff-2026-08-20-1.md`: "Simplest shape: revise the existing
  file in place… That choice is yours, not a ruling."). Revised in place, and the
  choice was made twice over. A new slug reads better — `capped-` names the one
  thing this plan no longer does, and under a name sorting after
  `recut-merged-excerpts.md` the driver's own dispatch order would enforce
  OD-13's sequencing instead of contradicting it. But replacing means deleting
  this file, and a steward's tool grant carries no file deletion or rename: the
  role writes plans, it does not remove tree state. Leaving the old plan beside a
  new one was never an option — a merged, unbuilt plan is a plan the driver
  dispatches, and OD-13 says this one must not be built as it stood. So: one
  file, rewritten, with the slug's mismatch stated at the top and the sequencing
  cost stated in the Summary rather than hidden.
- **Where an over-cap transcript is split, and how a part is marked.** Delegated
  by R28 itself ("the mechanics are the implementing plan's to specify") and
  restated by the handoff (ordering, and how a multi-bundle transcript is marked
  so the extraction agent knows it holds a part). Cue boundaries, because they
  are the only boundary the data carries that is not mid-word, and because cue
  membership is already how every excerpt is cut; `part`/`parts` attributes
  beside the `form` attribute this plan's earlier revision designed, because a
  reader holding block 2 of 4 needs both facts and neither is inferable from the
  other; greedy in cue order under `estimate_tokens`, the same estimator the
  packer uses, so the split and the packing cannot disagree about what fits.
- **Which plan's `covers:` names R28.** This one, because its slice 1 delivers
  R28's behaviour and a plan names what it delivers — the same derivation the
  earlier revision recorded. By `AGENTS.md`'s contract test this is not a HIGH
  question: a front-matter list entry is not a slice boundary, not a Signatures
  block, not an external format, and is one line to reverse; the candidate
  answers build identical code. `docs/plans/whole-transcript-threshold.md` also
  names R28 and is the owner's to revise, and `coverage.sh` tolerates two plans
  naming one id.
- **What R1001's supersession does to the coverage report.** Read off
  `.github/scripts/coverage.sh`: it collects requirement ids from
  `docs/DESIGN.md` §5 and from column-anchored `**Requirements added:**` lines in
  the oracle ledger, and has no reading of `**Requirements superseded:**`. R1001
  was added by OD-5 and the ledger is append-only, so it stays in the requirement
  universe permanently while no plan can honestly claim it: the behaviour it
  describes is deliberately not being built. This plan therefore drops R1001 from
  its `covers:` — naming a requirement whose behaviour it refuses to build is the
  over-claim the adequacy note exists to expose, and R1008's own text says which
  half survives. The consequence is disclosed in the Summary and filed as BL-21
  rather than papered over here.
- **Whether a split transcript's parts may cross a batch boundary.** Derived: R6
  assigns batches over bundles in order, OD-13 changes nothing about batching, and
  every part states which part of how many it is — so a calibration batch holding
  part 1 of 4 is legible rather than mysterious. The alternative, keeping a
  transcript inside one batch, would change `assign_batches`, which no requirement
  asks for and which would trade away the recency ordering R6 exists to preserve.
- **What happens to a single cue larger than the bundle cap.** Derived from the
  packer's existing rule and the reasoning `docs/architecture.md` records for it:
  an over-cap block gets a bundle to itself, because losing evidence to a cap must
  be visible, never silent. Splitting inside a cue is the only alternative and it
  cuts a sentence mid-word. The case is vanishingly unlikely — a cue is a few
  seconds of speech — but the behaviour has to be total, and the projection
  reports such a part's span like any other.

Two choices are the plan's own rather than the design's, and are recorded here so
the owner sees them without reading the slices. Routing keeps this plan's earlier
home, a new `src/find_best_mobo/submission.py` rather than `excerpt.py`:
excerpting is three separate judgements already (`excerpt.py`'s own docstring),
routing is a fourth, and keeping it separate keeps the new code clear of the
module R1000's plan rewrites. And the 80% threshold stays a module constant,
because R17 enumerates the configuration levers and it is not among them; it
moves to config the day R17 says so.

## What this revision changes, and what stays wrong

**What the previous revision of this plan got wrong**, all of it R1001's cap,
which OD-13 superseded: slice 1's cap check and its third routing outcome
`EXCERPTS_OVER_CAP`; slice 2's "no whole block exceeds the cap" invariant; slice
3's `videos_over_cap` count; and the `covers:` entry naming R1001. None of it may
be built. What survives is re-used rather than re-derived: `submission.py` as the
routing home, the ratio measured on re-cut post-cap excerpts with characters on
both sides joined identically, the `form` attribute on the bundle XML, the
per-path projection figures, and the sequencing note below.

**`docs/plans/whole-transcript-threshold.md` (slug `whole-transcript-threshold`,
covering R5, R17, R28) stays partly wrong, and only the owner can fix it** —
`CODEOWNERS` holds `docs/plans/` outside `oracle/`. Three places:

1. Its second uncertainty reads `Ruling: pending — do not build this slice until
   it is answered`. OD-5 answered it with a cap; OD-13 answered it again, the
   other way. Either way it is no longer pending.
2. Its **Slice 1** builds this routing — without R5's clustering, without R1000's
   re-cut, and with no account of a transcript larger than a bundle. Only one of
   the two may be built, and it is this one.
3. Its **Out of scope** excludes "the ceiling in the open uncertainty above",
   which is now decided: there is no ceiling.

Its `Signatures` block also differs from this one: it puts `excerpt_ratio` and
`choose_submission` in `excerpt.py` and calls the routing product `form`, where
this plan puts them in `submission.py` and distinguishes the two-valued routing
`path` from the rendered per-block `form`.

Nothing else in the tree is contradicted. `docs/plans/corpus-and-checkpoint.md`
is merged and stays accurate: this changes what `estimate` sends, not how it
enumerates, fetches, normalizes, selects or batches.

## Sequencing

**Build `docs/plans/oracle/recut-merged-excerpts.md` (OD-4 / R1000) before this
plan, and do not take the driver's offer of this one first.**
`.claude/scripts/deliver-phase.sh` walks `docs/plans/**/*.md` in sorted path
order and dispatches the first plan with no merged `feat/<slug>` branch, and this
slug sorts ahead of `recut-merged-excerpts` — so the driver will offer this plan
first, and the orchestrator must decline it until R1000's re-cut has landed. The
handoffs already place sequencing among the queued builds with the orchestrator;
this is that judgement, stated where it is read.

The reason is not tidiness. `merge_overlapping` still concatenates, so a
saturated video's excerpt characters still read several times its transcript's,
and the 80% ratio this plan routes on is only honest once each transcript
character is counted once. Built in the other order the routing is not merely
imprecise but wrong in the expensive direction — an inflated ratio sends videos
whole that are not saturated, and there is no longer a cap to stop it. This plan
also takes `transcript_characters` from R1000's.

Three other merged plans touch files this one touches, and `AGENTS.md` holds one
pipeline pull request in flight at a time, so none of them is built in parallel
with this one: `recut-merged-excerpts` (`excerpt.py`, `commands/estimate.py`),
`refuse-on-missing-artifact` (`estimate.py`, `commands/estimate.py`) and
`subcommand-flag-forwarding` (`commands/estimate.py`). Whichever lands second
carries the rebase.

## The work, sliced

Three slices, and they are **sequential**: slice 2 renders fields slice 1 adds,
and slice 3 counts submissions slice 1 produces. Each updates
`docs/architecture.md`, which is safe precisely because no two of them run at
once.

## Slice 1 — A saturated video is sent whole, however big it is

- **Delivers:** `./scripts/run.sh estimate` sends one continuous transcript for a
  video whose clusters have grown to cover it, and excerpts for the rest. A
  transcript too large for one bundle is cut at cue boundaries into consecutive
  parts and never falls back to excerpts. Observable in `data/bundles/`: the
  saturated video appears as a single block of its whole transcript, or as N
  blocks spread over N sequential bundle files, with no repeated passage and
  nothing dropped. Covers R28.
- **Files:** `src/find_best_mobo/submission.py`, `src/find_best_mobo/excerpt.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_submission.py`, `tests/test_estimate_routing.py`, `docs/architecture.md`
  <!-- One line deliberately: `.github/scripts/plan-parse.sh` reads backticked
  paths from the `**Files:**` LINE only, so a wrapped list silently drops
  everything after the first line — including the test paths the blind
  test-writer is given. -->
- **Estimate:** ~400 lines

### Signatures

Shared types and where they live (**OD-12**): `VideoSubmission`, the two path
constants and `WHOLE_TRANSCRIPT_RATIO` are new in `find_best_mobo.submission`;
`Excerpt` stays in `find_best_mobo.excerpt` and gains three defaulted fields;
`transcript_text` is new in `find_best_mobo.excerpt`, beside the
`transcript_characters` R1000's plan puts there; `Transcript` and `Cue` stay in
`find_best_mobo.transcripts`; `Video` in `find_best_mobo.index`; `Config` in
`find_best_mobo.config`; `estimate_tokens` and `Bundle` in
`find_best_mobo.bundle`.

```python
# find_best_mobo/excerpt.py — three added fields, defaulted so every existing
# construction site keeps working and no other slice has to be touched.


@dataclass(frozen=True)
class Excerpt:
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    text: str
    canonicals: tuple[str, ...]
    form: str = "excerpts"  # "excerpts" | "whole"
    part: int = 1
    part_count: int = 1


def transcript_text(transcript: Transcript) -> str: ...


# find_best_mobo/submission.py — new module.

WHOLE_TRANSCRIPT_RATIO: float = 0.80

EXCERPTS = "excerpts"
WHOLE = "whole"


@dataclass(frozen=True)
class VideoSubmission:
    """One video's contribution, which path it took, and what that path cost."""

    video_id: str
    video_title: str
    path: str  # EXCERPTS | WHOLE
    blocks: tuple[Excerpt, ...]
    excerpt_characters: int
    transcript_characters: int
    projected_tokens: int


def excerpt_ratio(excerpts: Sequence[Excerpt], transcript: Transcript) -> float: ...
def split_whole(
    video: Video,
    transcript: Transcript,
    canonicals: Sequence[str],
    config: Config,
) -> tuple[Excerpt, ...]: ...
def choose_submission(
    video: Video, transcript: Transcript, excerpts: Sequence[Excerpt], config: Config
) -> VideoSubmission: ...
```

### Behaviour the signatures cannot carry

- **One definition of the transcript's text, in one place.**
  `transcript_text(transcript)` is the single-space join of every cue's text —
  the join `_text_between` already performs — and R1000's `transcript_characters`
  becomes `len(transcript_text(transcript))`. Two functions computing that join
  separately would drift, and the ratio's denominator and the whole-path text
  would then disagree by a space per cue.
- **The ratio is measured on the blocks that would actually be sent** — after
  R1000's cluster re-cut and after `cap_per_video`. Measuring before the merge
  counts overlap twice and pushes nearly everything over the line; measuring
  before the cap routes a video whole on excerpts that were then thrown away.
- **Exactly at the threshold is the whole path** — R28 says "80% or more".
- **Size is never consulted when routing.** This is the whole of OD-13:
  `choose_submission` compares the ratio and nothing else, so a three-hour
  saturated stream goes whole exactly as a thirty-minute one does. The bundle cap
  decides only how many blocks the transcript is delivered in.
- **A whole submission is one block per bundle-sized part.** Cues are taken in
  order into a part while
  `estimate_tokens(candidate_text, config) <= config.bundle_token_cap`; the first
  cue that would carry the part over the cap starts the next part. A part's text
  is its cues joined the same way `transcript_text` joins them.
- **A cue is never split.** A single cue whose own projected tokens exceed the cap
  becomes a part on its own and exceeds the cap; nothing is dropped and nothing is
  cut mid-sentence. `pack_bundles` already gives an over-cap block a bundle to
  itself, so it stays visible in the projection as the outsized thing it is.
- **Part numbering is 1-based and complete**: `part` runs 1..`part_count` in cue
  order, and a transcript that fits in one bundle is `part=1, part_count=1`. An
  excerpt-path block keeps the field defaults, so nothing else in the tree has to
  change.
- **The split loses no speech, and the arithmetic says so exactly.** The parts'
  cues partition the transcript's cues in order, so
  `sum(len(block.text) for block in blocks) ==
  transcript_characters(transcript) - (part_count - 1)` — one joining space is
  consumed at each split. This is the assertion that proves the split rather than
  describing it.
- **A part's span** is its first cue's start to its last cue's start — the
  convention `cut_windows` shares, where a cue's end is not known.
- **`canonicals` on a whole block** is the distinct sorted union of the video's
  excerpts' canonicals, repeated on every part, so each part carries its own
  provenance into whichever bundle it lands in.
- **A video with no transcript, or one whose text is empty, takes the excerpt
  path** and contributes its excerpts unchanged, rather than dividing by zero. A
  video with no excerpts has ratio 0.0 and contributes nothing, as today.
- **`projected_tokens` is the submission's own cost** — `estimate_tokens` summed
  over the blocks it will actually contribute — so the projection does not
  re-derive it and a reader can check one video's routing against one number.
- **The command wires it in and nothing else moves.** `commands/estimate.py`
  builds each video's excerpts exactly as today (cut, merge-and-re-cut, cap),
  passes them through `choose_submission`, packs `submission.blocks` in the order
  the submissions were produced so recency survives, and passes the submissions to
  `project` alongside the bundles — slice 3's signature. Nothing here can invoke a
  model, and the stage still stops at the projection.

## Slice 2 — The bundle says which form each block is, and which part

- **Delivers:** a bundle's XML states, per block, whether it is a whole transcript
  or a window and — for a whole transcript — which part of how many, so the
  extraction agent M2 writes can be told what it is holding. A multi-bundle
  transcript's parts appear in ascending order in strictly ascending bundles, one
  part per bundle. Covers R28, R1008.
- **Files:** `src/find_best_mobo/bundle.py`, `tests/test_bundle.py`, `docs/architecture.md`
- **Estimate:** ~170 lines

### Signatures

No signature changes. `render_bundle(bundle: Bundle) -> str` and
`pack_bundles(excerpts: Sequence[Excerpt], config: Config) -> tuple[Bundle, ...]`
keep their shapes; `Bundle` stays in `find_best_mobo.bundle` and `Excerpt` in
`find_best_mobo.excerpt`, now carrying `form`, `part` and `part_count`.

### Behaviour the signatures cannot carry

- **The `<excerpt>` element gains `form`, `part` and `parts` attributes**,
  rendered from `Excerpt.form`, `Excerpt.part` and `Excerpt.part_count`, escaped
  like every other attribute. The XML does not change shape and the element is not
  renamed: nothing downstream reads these files yet, and a rename would be a
  second change riding along with this one.
- **The attributes are always present**, `form="excerpts" part="1" parts="1"`
  included, so a reader never has to infer meaning from an absent attribute.
- **Determinism is unchanged** (R23): the same submissions render the same bytes,
  and the attributes are derived, never computed from a clock or a set iteration
  order.
- **The packer is unchanged, and the sequencing is a property of it.** Slice 1
  closes a part only when the next cue would carry it over the cap, so
  `tokens(part k) + tokens(part k+1) > cap` for every k below the last — two
  consecutive parts can never share a bundle, and greedy in-order packing puts
  nothing between them. Assert the property rather than engineering it: for a
  video routed whole, its parts appear in ascending `part`, in strictly ascending
  bundle index, one part per bundle, with `parts` equal on all of them.
- **The over-cap branch stays.** With no cap on the whole path, a part can exceed
  `bundle_token_cap` only in slice 1's single-giant-cue case, and an over-cap
  *excerpt* block is still possible because `cap_per_video` does not bound one.
  The branch that gives such a block a bundle to itself is not removed.

## Slice 3 — The projection says which path each video took, what it cost, and what spans bundles

- **Delivers:** the printed projection reports, alongside the existing funnel, how
  many videos were sent whole and how many as excerpts, the characters and
  projected tokens each path accounts for, how many whole-path videos exceed one
  bundle's token cap, and — per such video — how many sequential bundles its
  transcript spans. The owner can see the uncapped path's largest submissions at
  the checkpoint, before anything is spent. Covers R1008.
- **Files:** `src/find_best_mobo/estimate.py`, `tests/test_estimate.py`, `docs/architecture.md`
- **Estimate:** ~240 lines

### Signatures

```python
# find_best_mobo/estimate.py — `VideoSubmission` is imported from
# find_best_mobo.submission; `Bundle` from find_best_mobo.bundle; `Selection`
# from find_best_mobo.select.


@dataclass(frozen=True)
class Projection:
    videos_indexed: int
    videos_selected: int
    excerpt_characters: int
    bundle_count: int
    tokens_per_batch: tuple[int, ...]
    total_tokens: int
    chars_per_token: float
    videos_whole: int
    videos_excerpted: int
    whole_characters: int
    whole_tokens: int
    excerpt_tokens: int
    videos_over_bundle_cap: int
    bundles_spanned: tuple[tuple[str, int], ...]


def project(
    bundles: Sequence[Bundle],
    selections: Sequence[Selection],
    submissions: Sequence[VideoSubmission],
    config: Config,
) -> Projection: ...
def render_projection(projection: Projection) -> str: ...
```

### Behaviour the signatures cannot carry

- **The path figures come from the submissions; the span figures come from the
  bundles.** A bundle cannot say why a video is on the excerpt path, and a part
  count cannot say what actually happened to the parts. `bundles_spanned` counts
  the distinct bundles holding a whole-form block of that video, which is the
  number R1008 asks for — what the transcript spans, not what the router intended.
- **The two are cross-checked, and that is a test rather than a comment.**
  `videos_over_bundle_cap` is computed from the submissions — whole-path videos
  whose `estimate_tokens(transcript_text(...))` exceeds `bundle_token_cap` — and
  must equal `len(bundles_spanned)`, which is computed from the bundles. Intent
  and outcome agreeing is the whole claim of slice 2's invariant; a run where they
  disagree is a defect the projection should surface, not smooth over.
- **`bundles_spanned` is `(video_id, bundle_count)` for every whole-path video
  occupying more than one bundle**, in submission order — newest first, and
  deterministic for R23.
- **`excerpt_characters` keeps its name and narrows its meaning** to characters of
  excerpt-form text; `whole_characters` is the whole-form text. The two sum to
  what the old field counted, so a reader comparing runs across this change is not
  silently comparing different quantities. `whole_tokens` and `excerpt_tokens`
  split the projected tokens the same way.
- **Every count is a count of videos**, not of blocks or bundles:
  `videos_whole + videos_excerpted` equals the number of submissions.
- **The rendered projection states the bundle token cap it split against**, in the
  same breath as the spans, for the same reason the chars-per-token factor is
  printed: a span reported without the bound that produced it invites the reader
  to treat it as a property of the corpus rather than of the configuration.
- **No submissions is a real value, not an error.** An empty corpus reports zeroes
  on every path and an empty span list. (OD-9's R1005 governs the *absent index*
  case and is a different plan's work; nothing here weakens it.)

At assembly, `docs/architecture.md`'s "Estimating the cost, and stopping" section
gains the routing and splitting steps between its current steps 4 and 5, the XML
attributes in step 7, and the per-path figures and spans in step 8 — a slice is
not finished until that file describes what now exists.

## Measurement

`AGENTS.md`'s ratchet asks what notices this change. Four things do, and none is
new machinery:

- the projection, which prints the two path counts, their characters and tokens,
  and every spanning transcript by id at every checkpoint run;
- the bundle files, where a whole transcript is visible as blocks carrying
  `form="whole" part="2" parts="4"` in consecutive files;
- the suite: the routing boundary (just below, exactly at, just above the ratio,
  and a saturated transcript far larger than the cap), the split's exact character
  arithmetic, the one-part-per-bundle ordering invariant, and the agreement
  between `videos_over_bundle_cap` and `bundles_spanned`;
- the run records under `docs/runs/`, which already capture the printed
  projection, so the first real corpus run says how much of it took the uncapped
  path and how large the largest submission was.

## Out of scope

- **The cluster re-cut.** R1000 (OD-4) fixes `merge_overlapping` to re-cut from
  the cues and defines `transcript_characters`; this plan is built after it and
  measures the ratio on what it produces. Building both in one change would make
  it impossible to say which one moved the numbers.
- **Keeping a split transcript inside one batch.** R6's batching is untouched, so
  a transcript's parts may straddle a batch boundary. Each part states which part
  of how many it is, so a calibration batch holding part 1 of 4 is legible; the
  span line in the projection makes it visible before the batch is paid for.
- **Splitting an over-cap excerpt block.** Only whole transcripts are split here.
  An excerpt too big for a bundle keeps the behaviour it has: a bundle to itself.
- **Window sizes, the per-video cap, the mention threshold, selection.**
  Untouched; the R17 levers keep their current meanings, and no new lever is added
  — the threshold stays a module constant and the split uses the existing
  `bundle_token_cap`.
- **The extraction stage's prompt wording.** This plan decides what a bundle
  contains and what it says about itself; what the agent is told to do with a
  whole transcript, or with part 2 of 4, belongs to M2.
- **Per-mention timestamps inside a whole-transcript block.** A whole block
  carries one start and one end, as an excerpt does; V11's provenance requirement
  is met the same way it is for excerpts today.
- **Revising `docs/plans/whole-transcript-threshold.md`.** `CODEOWNERS` holds
  `docs/plans/`, and a steward writes only under `docs/plans/oracle/`. Its slice 1
  must not be built; marking it superseded is the owner's edit, and the Summary
  asks for it.
