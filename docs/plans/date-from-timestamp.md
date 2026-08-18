---
slug: date-from-timestamp
status: draft
created: 2026-08-16
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1, R25]
---

# Upload dates from the listing's timestamp — Plan

The first real run enumerated 1215 videos and kept none of them. `classify()`
reads `upload_date`; a flat channel listing does not return that field. It
returns `timestamp`. Every record fell back to the `0001-01-01` sentinel and was
excluded as out of range — including videos squarely on topic and in range.

The `youtubetab:approximate_date` extractor argument is present and does work.
It fills `timestamp`, not `upload_date`. The corpus plan asserted otherwise and
nothing checked — logged as ESC-21.

This is one slice. It is a bug fix, not a feature, and it is planned because
every change gets a plan — not because it is large.

## Summary

Fix the bug that made the first real run useless: 1215 videos enumerated, none
kept. `classify` reads `upload_date`; the flat channel listing returns
`timestamp` instead, so every video fell back to a sentinel date and was
excluded as out of range — including an on-topic X870E analysis from December
2025 the owner spot-checked.

Decisions the owner has already made, and what this plan does with them:

- **Approximate dates, no per-video fetching.** One network call for the whole
  channel, not 1215. Ruled 2026-08-15.
- **A fixed two-month slop constant, not a config lever.** The listing's dates
  are bucketed to roughly mid-month, so the comparison date moves back far
  enough that nothing uploaded from 2023-01-01 onward can be excluded. Some 2022
  videos come along; that is the accepted trade, and it means the index will
  contain 2022 videos marked `pending`.
- **The recorded date stays the real one.** Only the comparison shifts, so the
  index never claims a video was uploaded on a date it wasn't.

One slice, ~140 lines, in `src/find_best_mobo/index.py` and its tests. Planned
because every change is planned, not because it is large.

The fixture matters more than the code. 452 tests passed while the corpus was
empty, because every fixture entry supplied `upload_date` — the shape the plan
claimed, not the shape yt-dlp sends. The test fixture must therefore carry
entries in the real listing shape, or this class of bug stays invisible.

Not in scope: the eight zero-duration videos, and anything downstream of the
index — `fetch`, `select` and `estimate` were never wrong, only starved.

## Uncertainties

Both settled by the owner on 2026-08-15, before this plan was written.

- **Q:** Exact dates or approximate ones? Fetching each video individually gives
  an exact `upload_date` at the cost of ~1215 network calls instead of one.
  — **proposed:** accept the listing's approximate dates.
  **Ruling:** approximate. No per-video fetching.
- **Q:** The listing's timestamps are bucketed — observed values land on the
  16th of a month, and two different videos shared one timestamp — so a video
  near the cutoff can be misplaced by weeks. How should the boundary handle it?
  — **proposed:** a configurable slop margin.
  **Ruling:** a **fixed constant**, not a lever. It must guarantee that anything
  from 2023-01-01 onward is included, accepting that some 2022 videos come along
  for the ride. Two months is acceptable if that is what it takes.

## The work, sliced

## Slice 1 — In-range videos survive the index

- **Delivers:** `./scripts/run.sh index` produces an index in which videos
  uploaded from 2023-01-01 onward are kept rather than excluded. The owner's
  spot-check video (`Q6fJWPZMC5M`, an ASUS Crosshair X870E Vcore analysis
  uploaded 2025-12-03) is `inclusion="pending"` rather than
  `excluded_out_of_range`, and the summary reports a non-zero kept count.
  Covers R1.
- **Files:** `src/find_best_mobo/index.py`, `tests/test_index.py`,
  `tests/fixtures/channel_entries.json`
- **Estimate:** ~140 lines

### Signatures

`classify` and `Video` keep their existing shapes — this changes what
`classify` reads, not what it returns.

```python
# Fixed by owner ruling, not configuration: the listing's dates are bucketed to
# roughly mid-month, so the comparison date is moved back far enough that no
# video uploaded on or after config.start_date can be excluded. Two months is
# deliberately more than the observed bucketing needs.
DATE_SLOP_DAYS: int = 62


def effective_start_date(config: Config) -> date: ...
def classify(entry: dict[str, object], config: Config) -> Video: ...
```

### Behaviour the signatures cannot carry

- **`upload_date` is preferred when present, `timestamp` is the fallback.** The
  full per-video extraction path does return `upload_date` as a `YYYYMMDD`
  string, so both shapes must parse. A `timestamp` is epoch seconds, interpreted
  as UTC.
- **The date recorded on the `Video` is the real one**, not the shifted one.
  Only the comparison moves: a video is out of range when its date is before
  `effective_start_date(config)`, which is `config.start_date` minus
  `DATE_SLOP_DAYS`. The index therefore contains 2022 videos marked `pending`,
  which is the owner's accepted trade.
- **Neither field present is still `excluded_out_of_range`** with the
  `0001-01-01` sentinel, unchanged.
- **Duration is still checked before date**, so the existing Short-wins rule is
  untouched.

### The fixture is the point

The tests passed throughout while the corpus was empty, because every fixture
entry supplies `upload_date` — the shape the plan claimed, not the shape yt-dlp
sends. `tests/fixtures/channel_entries.json` must therefore carry entries in the
**real listing shape**: `upload_date` absent or null, `timestamp` present, live
markers absent. Keep entries in the full-extraction shape too, since both paths
are real, but the listing shape is the one that was missing and the one that
broke the run.

## Out of scope

- The eight videos reporting no duration. The owner's zero-duration warning
  fired correctly and named them; whether a missing duration should keep
  classifying a video as a Short is a separate decision, not yet ruled.
- Per-video exact dates, ruled out above.
- Anything downstream of the index. `fetch`, `select` and `estimate` are
  unchanged; they were never wrong, they were starved.
