---
slug: recut-merged-excerpts
status: draft
created: 2026-08-19
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1000]
---

# Merged excerpts are re-cut from the cues — Plan

Implements **OD-4** (`docs/DESIGN.oracle.md`), which adds **R1000** from the
evidence in **BL-10**: `merge_overlapping` concatenates the texts of two
partially overlapping windows, so every character in the overlap is paid for
once per window instead of once. Measured on a real 33-minute review, a
28,438-character transcript produced a single 137,246-character excerpt — 4.8x
the whole transcript — and the cost projection, which is the one number the
checkpoint exists to produce, was wrong by that factor.

## Summary

Give `merge_overlapping` the transcript and let it re-cut the merged span from
the cues, instead of gluing two window texts together. That is the whole change;
everything else follows from it, because the projection already sums the
characters of the excerpts it is handed.

- **The merge takes one video's transcript** —
  `merge_overlapping(excerpts, transcript)`, `ValueError` on an excerpt from
  another video. Today it accepts a mixed-video sequence and keeps videos apart
  itself; the only caller passes one video's windows and R22 forbids holding a
  channel of transcripts at once, so "never merge across videos" becomes
  unaskable rather than enforced. This retires the cross-video merge tests.
- **The bound is a property, not an estimate.** Merged spans are disjoint, cue
  membership is decided on the cue's start alone, so each cue's text lands in at
  most one excerpt: a video's summed excerpt characters can never exceed its
  transcript's characters. Stated in the plan because the blind test author must
  assert it, and it is the assertion R1000 asks for.
- **"The transcript's characters" is defined here**, as the single-space join of
  every cue's text — the same joining rule `_text_between` uses, exposed as
  `transcript_characters(transcript)`. It is also the denominator the R28
  saturation ratio needs, so the two documents cannot drift into two definitions.
- **The regression is a synthetic transcript of the measured shape**, not the
  real captions: R21 holds the corpus local-only and never redistributed. The
  test reproduces BL-10's geometry (~33 minutes, ~28.4k characters, a mention
  roughly every minute) and asserts the bound, 4.8x violated before the fix.
- **Not done here: the R28 whole-transcript path.** R1000 also says the R28
  ratio is computed from the re-cut text. That path does not exist yet — it is
  OD-5/R1001's, in `docs/plans/whole-transcript-threshold.md` — and building it
  here would be a second decision. This plan makes the ratio correct by
  construction and hands that plan `transcript_characters`.
- **What it costs the owner:** one plan needs revising before it is built.
  OD-5 says `whole-transcript-threshold` "should be revised to carry R1000 and
  R1001"; R1000 is delivered here, so that revision should carry **R1001 only**
  and cite this plan for the merge, or two plans claim one requirement.

Two slices, ~330 lines, sequential — the second is the regression against the
first. **Open questions:** all four uncertainties below were resolved on a
default, this being an unattended run; the last one — which plan carries R1000 —
is the one worth the owner's look.

## Uncertainties

Four, none of which had an answer in either design document. This ran
unattended and a steward cannot stop for a ruling, so each was proceeded on and
is recorded here.

- **Q:** What shape does "`merge_overlapping` gains access to the cues" take —
  one `Transcript`, or a mapping of video id to transcript preserving today's
  multi-video input? — **risk:** HIGH (it is the Signatures block)
  — **proposed:** one `Transcript`, `ValueError` on a foreign `video_id`.
  **Ruling:** proceeded on the default. Derived as far as it goes from R22 (one
  transcript in memory at a time) and from the sole call site
  (`commands/estimate.py::_excerpts_for`, already per-video); the guess is that
  no future caller wants the mixed-video form back.
- **Q:** What counts as "its transcript's characters" for the bound? —
  **risk:** HIGH (it is the denominator OD-5's R28 ratio will divide by, and an
  external contract between two plans) — **proposed:** the single-space join of
  every cue's text, matching `_text_between`.
  **Ruling:** proceeded on the default. Any other definition (raw cue text
  summed without separators, the VTT source, a duration-derived figure) makes
  the bound off by the separator count and makes R28's ratio disagree with the
  characters actually sent.
- **Q:** Does "the measured real-video case from BL-10 lands as a regression
  fixture" mean the real caption text? — **risk:** HIGH (fixture content, and a
  data-handling rule) — **proposed:** no; a synthetic transcript reproducing the
  measured geometry, with BL-10's real figures recorded in the test as
  provenance.
  **Ruling:** proceeded on the default. R21 holds the corpus local-only and
  never redistributed, and the cache is not in the tree for a builder to copy
  from anyway. The cost is that the test pins the *bound*, not the literal
  28,438 / 137,246 numbers.
- **Q:** Which plan covers R1000 — this one, or the revision of
  `whole-transcript-threshold` that OD-5 asks for? — **risk:** HIGH (double
  coverage, and the two would build the same change twice)
  — **proposed:** this one; the other carries R1001.
  **Ruling:** proceeded on the default. OD-4 says the signature change "is the
  plan's to specify" and a steward's plan must cover its own decision's
  requirement ids, so R1000 belongs here. Flagged for the owner because OD-5's
  prose reads the other way.

## The work, sliced

Two slices, and deliberately not three: the change is one function's contract
plus the regression that proves it on the case that produced the evidence.
Splitting further would be horizontal — a slice of code with nothing observing
it, then a slice of observation. **They are sequential.** Slice 2 asserts
against the behaviour slice 1 delivers, so it is built after slice 1 has landed,
not beside it.

## Slice 1 — A merged excerpt is the speech in its span, once

- **Delivers:** `estimate`'s projection counts each character of a transcript at
  most once. On a board-heavy video whose windows all overlap, the merged
  excerpt is the video's speech from the first window's start to the last
  window's end — the same text the transcript has there, not that text
  concatenated once per window. Observable as the `characters of excerpt text`
  line of the projection dropping to at most the corpus's transcript characters,
  and in `data/bundles/` holding no repeated passages. Covers R1000.
- **Files:** `src/find_best_mobo/excerpt.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_excerpt.py`, `docs/architecture.md`
  <!-- One line deliberately: `.github/scripts/plan-parse.sh` reads the file
  list off this single line, so a wrapped continuation is invisible to the
  reviewer's scope check. -->
- **Estimate:** ~200 lines

### Signatures

```python
def merge_overlapping(excerpts: Sequence[Excerpt], transcript: Transcript) -> tuple[Excerpt, ...]: ...
def transcript_characters(transcript: Transcript) -> int: ...
```

`Excerpt`, `cut_windows` and `cap_per_video` keep the signatures they have.
`transcript_characters` lives in `src/find_best_mobo/excerpt.py` alongside the
cutting rule it must agree with; `Transcript` and `Cue` stay in
`src/find_best_mobo/transcripts.py`, where they are defined today.

### Behaviour the signatures cannot carry

- **The merged text is `_text_between(transcript, merged_start, merged_end)`** —
  re-cut, never assembled from the two texts. The merged span is the earlier
  start to the further of the two ends, exactly as today.
- **A foreign excerpt is a `ValueError`**, not a silent pass-through: any
  excerpt whose `video_id` differs from `transcript.video_id`. The message names
  both ids. This is the replacement for today's per-video grouping.
- **Merging on touch stays.** A window starting exactly at the open excerpt's
  end merges into it — `excerpt.start_seconds <= open.end_seconds`. This is what
  makes surviving spans strictly disjoint (`next.start > previous.end`), and
  disjointness plus start-only cue membership is the whole proof of the bound.
  Do not relax it to `<` while re-cutting.
- **The bound:** for any transcript and any set of windows cut from it,
  `sum(len(e.text) for e in merge_overlapping(...)) <= transcript_characters(transcript)`.
  It must hold after `cap_per_video` too, which only drops excerpts.
- **`transcript_characters` is `len(" ".join(cue.text for cue in cues))`** — the
  same join `_text_between` performs, so the bound is exact rather than
  approximate. Zero cues is 0 characters, and no division happens here.
- **Canonicals still union and sort** on merge, and ordering stays
  chronological, so R23's byte-identical rerun is untouched.
- **The caller passes the transcript it already loaded.** `_excerpts_for` has it
  in hand; nothing loads a transcript twice and nothing holds more than one
  (R22).
- **`docs/architecture.md`'s "A merged excerpt double-counts its overlap, and
  not slightly" entry is now false** and is corrected in this slice: the
  re-cutting rule and the bound replace it, citing OD-4 and R1000. It is the one
  place the old behaviour is described as accepted-deliberately, so leaving it
  would leave the next agent believing the projection still over-states.

## Slice 2 — The saturated video is pinned at the size of its transcript

- **Delivers:** a regression, built from BL-10's measured case, that fails on the
  concatenating merge and passes on the re-cut one — the whole `estimate` path
  from a cached transcript to the projection, asserting that the summed excerpt
  characters of the saturated video do not exceed its transcript's characters.
  Covers R1000.
- **Files:** `tests/test_estimate.py`
- **Estimate:** ~130 lines

### The fixture

Built in the test module, deterministically, and written into the tmp data
directory as a cached transcript so the real `load_cached` → `cut_windows` →
`merge_overlapping` → `cap_per_video` → `pack_bundles` → `project` path runs. No
network, no checked-in caption text.

The geometry reproduces BL-10's video rather than its words:

- ~33 minutes — 1,980 seconds of cues;
- a cue roughly every 3 seconds, each roughly 43 characters, for a transcript of
  roughly 28,400 characters (BL-10 measured 28,438);
- a mention roughly every 60 seconds, so ~33 windows of 2-before/5-after each
  overlap their neighbours and merge into one span covering the video.

Assertions:

- summed excerpt characters ≤ `transcript_characters(transcript)`;
- summed excerpt characters > 0 — the bound must not be met by emitting nothing;
- the projection's `excerpt_characters` equals that sum, so the number the owner
  reads is the number that is bounded;
- no line of cue text appears twice across the video's excerpts.

The old behaviour produced ~4.8x the transcript on this shape, so the first
assertion is what would have been red. Record BL-10's real figures (28,438 →
137,246) in the test's docstring as the provenance of the numbers above; they
are not asserted, because the text is synthetic.

## Out of scope

- **The R28 whole-transcript path and its ratio.** OD-5/R1001 and
  `docs/plans/whole-transcript-threshold.md` own it. R1000's clause about the
  ratio being computed from the re-cut text is satisfied structurally here — the
  ratio is defined over the excerpts that would actually be sent, and after this
  plan those are the re-cut ones — and `transcript_characters` is the denominator
  it should use.
- **Revising `docs/plans/whole-transcript-threshold.md`.** It is a plan, behind
  `CODEOWNERS`, and it is revised on its own pull request. What that revision
  should say is in the Summary.
- **Window sizes, the per-video cap, and near-duplicate removal.** R5 and R17
  levers, unchanged; this plan does not re-tune what a window is, only what
  merging two of them produces.
- **The chars-per-token factor.** Still a stated guess awaiting the calibration
  batch; a correct character count does not make it a measurement.
- **Any change to `Excerpt`'s shape or to the bundle XML.** The extraction stage
  reads those, and nothing here needs them different.
