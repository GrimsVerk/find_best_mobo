---
slug: capped-whole-transcript-path
status: draft
created: 2026-08-19
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1001, R28]
---

# The whole-transcript path, capped at the bundle cap — Plan

Implements **OD-5** (`docs/DESIGN.oracle.md`), which added **R1001**:

> A video takes the whole-transcript path only when its full transcript fits
> within the bundle token cap. Above the cap it falls back to excerpts
> regardless of its R28 ratio, so one video's submission always fits in one
> bundle and the 80% rule can never create the lumpy cost it exists to remove.
> The projection reports how many videos took each path and what each path
> costs, so the routing is observable at the checkpoint.

R1001 is a bound on R28's path, and R28's path does not exist in the tree yet:
`docs/plans/whole-transcript-threshold.md` planned it and then forbade building
it ("do not build this slice until it is answered"), waiting on exactly the
ruling OD-5 has now made. OD-5 asks for that plan to be revised; a steward may
not write outside `docs/plans/oracle/`, so this plan carries the whole
behaviour instead — the routing and its cap together, as one thing.

## Summary

Build R28's saturated-video routing **with** OD-5's cap, in the `estimate`
stage. A video whose excerpts have grown to cover it is sent as one whole
transcript — unless that transcript would not fit inside a single bundle, in
which case it stays on the excerpt path however saturated it is.

- **This plan builds the routing, not just the cap.** The slice in
  `docs/plans/whole-transcript-threshold.md` is superseded and must not also be
  built — building both would deliver the same behaviour twice, differently.
  That plan's own text still says the slice is blocked, which is now false; only
  the owner can correct it.
- **The cap is the existing `bundle_token_cap`.** No new configuration lever.
  "Fits" means projected tokens at the configured chars-per-token factor — the
  same estimator the packer uses — not characters.
- **The 80% threshold stays a module constant**, per the owner's 2026-08-15
  ruling, measured on the merged *and capped* excerpts (what would actually be
  sent) against the whole transcript, characters on both sides, joined the same
  way so the two are comparable.
- **Three outcomes are reported, not two:** whole, excerpts, and
  excerpts-because-over-cap. The third is the only thing that makes OD-5's cap
  observable at all — without it a capped-back video is indistinguishable from
  an ordinary sparse one, and nothing measures the decision.
- **Routing lives in a new `submission.py`.** `Excerpt` gains one field, `form`,
  defaulted so nothing existing changes shape; the bundle XML gains a `form`
  attribute so the extraction agent can tell a transcript from a window.
- **The projection gains per-path counts, characters and projected tokens**, and
  `project()` gains a submissions argument to compute them from.

Costs to the owner: the bundle XML gains an attribute (an output-format change
to the file M2's agent will read); the projection prints three more lines; and
R28 is now named by two plans, this one and the superseded one. Nothing
deliberately left out is silent — see "Out of scope".

Not done here: the merge double-count (that is R1000/OD-4's plan, and this plan
should be built after it — see "Sequencing"), window sizes, the per-video cap,
selection, and the extraction prompt's wording.

Open questions, for the oracle next cycle: whether building the routing here
rather than waiting on a revision of `whole-transcript-threshold.md` is the
intended reading of OD-5; whether this plan should name R28 in `covers:` when
another plan already does; and whether the over-cap fallback count belongs in
the projection. All three are recorded below and proceeded on.

## Uncertainties

Unattended, and a steward cannot stop for a ruling or file a `BL-<n>` — the one
path it may write is this file. So every guess is recorded here and in the run
report, and the plan continues on the best reading of OD-5. **None of these has
been ruled on.**

- **Q:** Does this plan build R28's routing itself, or only the cap on top of
  `docs/plans/whole-transcript-threshold.md`'s unbuilt slice 1? — **risk:** HIGH
  (it decides what the slices are)
  — **proposed:** build it here, self-contained, superseding that slice.
  OD-5 asks for that plan to be revised to carry R1000 and R1001; a steward
  cannot edit it, and a cap-only plan would depend on a slice whose own document
  still says "do not build this slice", which nothing will lift while nobody is
  awake.
  **Ruling:** none — proceeded on the default (steward, unattended). For the
  oracle next cycle.
- **Q:** Should `covers:` name R28 when `whole-transcript-threshold.md` already
  covers it? — **risk:** HIGH (it changes what `coverage.sh` reads)
  — **proposed:** yes. This plan genuinely delivers R28's behaviour, and
  `AGENTS.md` says to list what the plan delivers; two plans naming one
  requirement is visible and harmless, a plan delivering an unnamed requirement
  is not.
  **Ruling:** none — proceeded on the default.
- **Q:** Does the projection report the cap-forced fallback as its own count?
  — **risk:** HIGH (it changes the `Projection` dataclass, a Signatures block)
  — **proposed:** yes. R1001 says "how many videos took each path"; the capped
  population is a third path, and `AGENTS.md`'s measurement rule says a decision
  nothing can observe is a decision nobody can evaluate.
  **Ruling:** none — proceeded on the default.
- **Q:** Where does the routing live? — **risk:** LOW (module placement, cheap
  to move) — **proposed:** a new `src/find_best_mobo/submission.py`, not
  `excerpt.py` as the superseded plan proposed. Excerpting is three separate
  judgements already (`excerpt.py`'s own docstring); routing is a fourth and a
  different one, and keeping it out of `excerpt.py` also keeps this plan clear
  of the module R1000's plan rewrites. Per OD-12 every shared type's module is
  named in the Signatures blocks below.
  **Ruling:** none — proceeded on the default.
- **Q:** What exactly is "the characters in its full transcript"? — **risk:**
  LOW (a measurement basis, one line to change) — **proposed:** the cue texts
  joined with single spaces, which is precisely how `_text_between` builds
  excerpt text, so numerator and denominator are the same kind of string.
  Summing bare cue lengths on one side and joined lengths on the other would
  bias the ratio by one space per cue.
  **Ruling:** none — proceeded on the default.
- **Q:** Does the 80% threshold become a config lever? — **risk:** LOW
  — **proposed:** no. R17 enumerates the levers and this is not among them; the
  superseded plan made it a module constant and the owner's ruling fixed the
  number. It moves to config the day R17 says so.
  **Ruling:** none — proceeded on the default.
- **Q:** Build order against R1000 (OD-4)? — **risk:** LOW (sequencing, not
  design) — **proposed:** after it. Correctness here does not depend on it, but
  the ratio does: while merged excerpts still double-count their overlaps the
  ratio is inflated, so more videos route whole than should. The cap bounds what
  that can cost, which is why this is not a blocker.
  **Ruling:** none — proceeded on the default.

## What this makes partly wrong

`docs/plans/whole-transcript-threshold.md` (slug `whole-transcript-threshold`,
covering R5, R17, R28) is now partly wrong in three places, and this plan
supersedes it rather than amending it:

1. Its second uncertainty — "Is there an upper bound on the whole-transcript
   path?" — reads `Ruling: pending — do not build this slice until it is
   answered`. OD-5 answered it: the bundle token cap.
2. Its **Slice 1** builds the routing this plan builds. Only one of the two may
   be built. This one carries the cap; that one does not.
3. Its **Out of scope** excludes "the ceiling in the open uncertainty above",
   which is now in scope — here.

Its `Signatures` block also differs from this one: it puts `excerpt_ratio` and
`choose_submission` in `excerpt.py` and calls the routing product `form`, where
this plan puts them in `submission.py` and distinguishes the three-valued
routing `path` from the two-valued rendered `form`.

Nothing else in the tree is contradicted. `docs/plans/corpus-and-checkpoint.md`
is merged and stays accurate: this changes what `estimate` sends, not how it
enumerates, fetches, normalizes, selects or batches.

## Sequencing

R1000 (OD-4, re-cut merged windows) and this plan both change what the
`estimate` stage counts, and R1000's plan rewrites `merge_overlapping` in
`excerpt.py`. `AGENTS.md` holds one pipeline pull request in flight at a time,
so the two cannot be built concurrently; build R1000's first, because the ratio
this plan routes on is only honest once each transcript character is counted
once. Built in the other order the routing is still correct — inflated ratios
send more videos whole, and the cap is what stops that being expensive.

## The work, sliced

## Slice 1 — A saturated video is sent whole, unless it is bigger than a bundle

- **Delivers:** `./scripts/run.sh estimate` sends one continuous transcript for
  a video whose excerpts have grown to cover it, excerpts for the rest, and
  excerpts for a saturated video whose transcript would not fit in one bundle.
  Observable in `data/bundles/`: the saturated video appears as a single block
  of its whole transcript, and no such block exceeds the bundle token cap.
  Covers R1001, R28.
- **Files:** `src/find_best_mobo/submission.py`, `src/find_best_mobo/excerpt.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_submission.py`, `tests/test_estimate_routing.py`
  <!-- One line deliberately: plan-parse.sh reads backticked paths from the
  `**Files:**` LINE only, so a wrapped list silently drops everything after the
  first line — including the test paths the blind test-writer is given. -->

- **Estimate:** ~360 lines

### Signatures

Shared types and where they live (OD-12): `VideoSubmission` and the three path
constants are new in `find_best_mobo.submission`; `Excerpt` stays in
`find_best_mobo.excerpt` and gains one field; `Transcript` and `Cue` stay in
`find_best_mobo.transcripts`; `Video` in `find_best_mobo.index`; `Config` in
`find_best_mobo.config`; `estimate_tokens` in `find_best_mobo.bundle`.

```python
# find_best_mobo/excerpt.py — one added field, defaulted so every existing
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


# find_best_mobo/submission.py — new module.

WHOLE_TRANSCRIPT_RATIO: float = 0.80

EXCERPTS = "excerpts"
WHOLE = "whole"
EXCERPTS_OVER_CAP = "excerpts_over_cap"


@dataclass(frozen=True)
class VideoSubmission:
    """One video's contribution, which path it took, and what that path cost."""

    video_id: str
    video_title: str
    path: str  # EXCERPTS | WHOLE | EXCERPTS_OVER_CAP
    blocks: tuple[Excerpt, ...]
    excerpt_characters: int
    transcript_characters: int
    projected_tokens: int


def transcript_text(transcript: Transcript) -> str: ...
def excerpt_ratio(excerpts: Sequence[Excerpt], transcript: Transcript) -> float: ...
def choose_submission(
    video: Video, transcript: Transcript, excerpts: Sequence[Excerpt], config: Config
) -> VideoSubmission: ...
```

### Behaviour the signatures cannot carry

- **The ratio is measured on the excerpts that would actually be sent** — after
  merging and after `cap_per_video`. Measuring before the merge counts overlap
  twice and pushes nearly everything over the line; measuring before the cap
  routes a video whole on excerpts that were then thrown away.
- **Characters, both sides, joined identically.** `transcript_text` joins cue
  texts with single spaces, exactly as `_text_between` does, and
  `transcript_characters` is that string's length. `excerpt_characters` is the
  summed length of the excerpt texts.
- **Exactly at the threshold is the whole path** — the ruling says "80% or
  more".
- **The cap is `config.bundle_token_cap`, measured in projected tokens.** A
  video is routed `WHOLE` when `estimate_tokens(transcript_text(...), config)`
  is at or below the cap; at or above the ratio but over the cap it is routed
  `EXCERPTS_OVER_CAP` and its blocks are the excerpts unchanged. This is the
  whole of R1001: one video's submission then always fits inside one bundle, so
  the 80% rule can never produce the lumpy request it exists to prevent.
- **A `WHOLE` submission is exactly one block**, spanning the transcript: start
  is the first cue's start (0.0 with no cues), end is the last cue's start —
  the same convention `cut_windows` uses, where a cue's end is not known — text
  is `transcript_text`, `canonicals` is the distinct sorted union of the
  excerpts' canonicals, and `form` is `"whole"`.
- **A video with no transcript, or one whose text is empty, takes the excerpt
  path** and contributes its excerpts unchanged, rather than dividing by zero.
  A video with no excerpts has ratio 0.0 and contributes nothing, as today.
- **`projected_tokens` is the submission's own cost** — `estimate_tokens` over
  the blocks it will actually contribute — so the projection does not have to
  re-derive it, and a reader can check one video's routing against one number.
- **The command wires it in and nothing else moves.** `commands/estimate.py`
  builds each video's excerpts exactly as today, passes them through
  `choose_submission`, packs `submission.blocks` in the order the submissions
  were produced (recency preserved), and passes the submissions to `project`
  alongside the bundles — see slice 3's signature. Nothing here can invoke a
  model, and the stage still stops at the projection.

## Slice 2 — The bundle says which form each block is

- **Delivers:** a bundle's XML states, per block, whether it is a whole
  transcript or a window, so the extraction agent M2 writes can be told which
  it is holding and ask the right thing of it. A whole-transcript block sits
  inside one bundle, never split and never alone-by-overflow. Covers R1001.
- **Files:** `src/find_best_mobo/bundle.py`, `tests/test_bundle.py`
- **Estimate:** ~145 lines

### Signatures

No signature changes. `render_bundle(bundle: Bundle) -> str` and
`pack_bundles(excerpts: Sequence[Excerpt], config: Config) -> tuple[Bundle, ...]`
keep their shapes; `Bundle` stays in `find_best_mobo.bundle` and `Excerpt` in
`find_best_mobo.excerpt`, now carrying `form`.

### Behaviour the signatures cannot carry

- **The `<excerpt>` element gains a `form` attribute**, rendered from
  `Excerpt.form`, escaped like every other attribute. The XML does not change
  shape and the element is not renamed: nothing downstream reads these files
  yet, and a rename would be a second change riding along with this one.
- **The attribute is always present**, `form="excerpts"` included, so a reader
  never has to infer meaning from an absent attribute.
- **Determinism is unchanged** (R23): the same submissions render the same
  bytes, and the attribute is derived, never computed from a clock or a set
  iteration order.
- **The packer is unchanged and must stay so.** With slice 1's cap no whole
  block can exceed `bundle_token_cap`, so the "an over-cap excerpt gets a bundle
  to itself" branch is no longer reachable for whole blocks — it stays in place
  for over-cap *excerpt* blocks, which the per-video cap does not bound. Assert
  the invariant rather than removing the branch: no bundle contains a `whole`
  block whose projected tokens exceed the cap.

## Slice 3 — The projection says which path each video took, and what it cost

- **Delivers:** the printed projection reports, alongside the existing funnel,
  how many videos were sent whole, how many as excerpts, how many reached the
  threshold but were sent as excerpts because they exceeded the bundle cap, and
  the characters and projected tokens each path accounts for. The owner can see
  at the checkpoint what the 80% rule and its cap are doing before spending.
  Covers R1001.
- **Files:** `src/find_best_mobo/estimate.py`, `tests/test_estimate.py`
- **Estimate:** ~220 lines

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
    videos_over_cap: int
    whole_characters: int
    whole_tokens: int
    excerpt_tokens: int


def project(
    bundles: Sequence[Bundle],
    selections: Sequence[Selection],
    submissions: Sequence[VideoSubmission],
    config: Config,
) -> Projection: ...
def render_projection(projection: Projection) -> str: ...
```

### Behaviour the signatures cannot carry

- **The path figures come from the submissions, not the bundles.** A bundle
  cannot say why a video is on the excerpt path — a capped-back video looks
  exactly like a sparse one there — and the cap-forced count is the number that
  makes OD-5 observable.
- **`excerpt_characters` keeps its meaning and narrows it**: characters of
  *excerpt-form* text. `whole_characters` is the whole-form text. The two sum to
  what the old field counted, so a reader comparing runs across this change is
  not silently comparing different quantities.
- **Every count is a count of videos**, not of blocks or bundles:
  `videos_whole + videos_excerpted + videos_over_cap` equals the number of
  submissions, and `videos_over_cap` counts videos that reached the ratio and
  were sent as excerpts anyway.
- **The rendered projection states the cap it applied**, in the same breath as
  the counts, for the same reason the chars-per-token factor is printed: a
  routing number without the bound that produced it invites the reader to treat
  it as a property of the corpus rather than of the configuration.
- **No submissions is a real value, not an error.** An empty corpus reports
  zeroes on every path. (OD-9's R1005 governs the *absent index* case and is a
  different plan's work; nothing here weakens it.)

At assembly, `docs/architecture.md`'s "Estimating the cost, and stopping"
section gains the routing step between its current steps 4 and 5, and its
step 8 gains the per-path figures — a slice is not finished until that file
describes what now exists.

## Measurement

`AGENTS.md`'s ratchet asks what notices this change. Three things do, and none
is new machinery:

- the projection itself, which now prints the three path counts and their costs
  at every checkpoint run;
- the bundle files, where a whole-transcript block is visible as one block
  carrying `form="whole"`;
- the suite: the routing boundary cases (just below, exactly at, just above the
  ratio; just at and just over the cap) are pinned as tests in slice 1, and the
  no-whole-block-over-the-cap invariant in slice 2.

## Out of scope

- **The merge double-count.** R1000 (OD-4) fixes `merge_overlapping` to re-cut
  from the cues; this plan measures the ratio on whatever the merge produces.
  Both change the same numbers, and building them in the same change would make
  it impossible to say which one moved them.
- **Window sizes, the per-video cap, the mention threshold, selection.**
  Untouched; the R17 levers keep their current meanings.
- **The extraction stage's prompt wording.** This plan decides what a bundle
  contains and what it says about itself; what the agent is told to do with a
  whole transcript belongs to M2.
- **Per-mention timestamps inside a whole-transcript block.** A whole block
  carries one start and one end, as an excerpt does; the design's provenance
  requirement (V11) is met the same way it is for excerpts today, and any
  improvement is M2's, not a change smuggled in here.
- **Making the threshold or the cap configurable beyond `bundle_token_cap`.**
  No new lever; R17 enumerates the levers and neither is on that list.
- **Revising `docs/plans/whole-transcript-threshold.md`.** A steward may not
  write outside `docs/plans/oracle/`. Its slice must not be built; marking it
  superseded is the owner's edit to make.
