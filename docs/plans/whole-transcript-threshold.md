---
slug: whole-transcript-threshold
status: draft
created: 2026-08-16
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R5, R17]
---

# Whole transcript when the excerpts nearly are one — Plan

Excerpt windows around every keyword mention overlap heavily on videos that
mention boards constantly, and the merged windows end up costing several times
what they were meant to save. The owner's ruling of 2026-08-15, recorded in
`docs/DECISIONS.md` by this pull request: when a video's excerpts total **80% or
more** of the characters in its full transcript, stop excerpting it and send the
whole transcript with a full-review instruction instead. Below that ratio, the
excerpts are sent as they are today.

The reasoning is that past roughly that ratio you are paying excerpt overhead
plus duplication to deliver nearly the whole text anyway, and a model reading
one continuous transcript does better than one reading overlapping fragments of
it.

## Uncertainties

One settled, one open and awaiting the owner.

- **Q:** What is the threshold? — **proposed:** a ratio, tunable.
  **Ruling:** 80% of total transcript characters, measured per video, comparing
  the summed characters of that video's excerpts against its full transcript.
- **Q:** Is there an upper bound on the whole-transcript path? Livestreams are
  in the corpus by owner ruling and several run past three hours, which is
  roughly 30–50k tokens in a single request. Dozens of those qualifying at once
  is a large, lumpy cost that the 80% rule would create rather than avoid.
  — **proposed:** a fixed ceiling — above it, fall back to excerpts even when
  the ratio says otherwise, on the grounds that the rule exists to save money
  and should not be the thing that spends it. A ceiling near the bundle token
  cap keeps one video inside one bundle.
  **Ruling:** _pending — do not build this slice until it is answered._

## The work, sliced

## Slice 1 — A saturated video is sent whole, not in pieces

- **Delivers:** `./scripts/run.sh estimate` sends the whole transcript for any
  video whose excerpts reach the threshold, and excerpts for the rest. The
  projection reports how many videos took each path and what each path costs, so
  the saving is visible rather than asserted. Bundles carry which path a video
  took, so the extraction stage can instruct the model accordingly.
  Covers R5, R17.
- **Files:** `src/find_best_mobo/excerpt.py`, `src/find_best_mobo/bundle.py`,
  `src/find_best_mobo/estimate.py`, `tests/test_excerpt.py`,
  `tests/test_bundle.py`, `tests/test_estimate.py`
- **Estimate:** ~260 lines

### Signatures

```python
WHOLE_TRANSCRIPT_RATIO: float = 0.80


@dataclass(frozen=True)
class VideoSubmission:
    """One video's contribution, and which form it takes."""

    video_id: str
    video_title: str
    form: str  # "excerpts" | "whole"
    excerpts: tuple[Excerpt, ...]  # empty when form == "whole"
    whole_text: str  # empty when form == "excerpts"
    excerpt_characters: int
    transcript_characters: int


def excerpt_ratio(excerpts: Sequence[Excerpt], transcript: Transcript) -> float: ...
def choose_submission(
    video: Video, transcript: Transcript, excerpts: Sequence[Excerpt], config: Config
) -> VideoSubmission: ...
```

### Behaviour the signatures cannot carry

- **The ratio is measured after merging and capping**, on the excerpts that
  would actually be sent. Measuring before merge counts the overlap twice and
  would push nearly everything over the threshold.
- **Characters, not tokens.** The owner specified characters, and characters are
  the thing the pipeline can count exactly; the token projection is derived from
  them as it already is elsewhere.
- **A video with no transcript, or an empty one, takes the excerpt path** and
  contributes nothing, rather than dividing by zero.
- **Exactly at the threshold is the whole-transcript path** — the ruling says
  "80% or more".
- **`render_bundle` marks the form** so the extraction agent can tell a full
  transcript from a set of excerpts and ask for the right thing. The existing
  XML structure gains an attribute; it does not change shape.

## Out of scope

- The extraction stage's prompt wording. This slice decides what a bundle
  contains and says which form it is; what the agent is told to do with a full
  transcript belongs to M2.
- Re-cutting window sizes. The excerpt window stays at 2 minutes before and 5
  after; this rule is about what to do when those windows have already covered
  the video.
- The ceiling in the open uncertainty above. Once ruled, it is a small addition
  to `choose_submission` — but the slice must not be built before then, because
  the ruling changes which videos take which path.
