---
slug: zero-duration-listing-shape
status: draft
created: 2026-08-24
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1009]
---

# The zero-duration warning judges the listing shape — Plan

Implements **OD-14** (`docs/DESIGN.oracle.md`), which adds **R1009** from the
evidence in **BL-15**: on the first real index run after the `timestamp` fix,
eight videos reported no duration, the 72-character banner fired, and all eight
were genuine Shorts. The warning's premise — that only one video can
legitimately lack a duration — was measured false, so it is a permanent false
positive, and a ninth id appearing in that list of eight would be invisible.
The check written to catch a silent drop currently guarantees one goes
unnoticed.

## Summary

Judge each entry on the evidence it carries instead of counting them. A flat
listing entry with no duration AND no date is the Shorts shape and reports as a
one-line count; an entry with a real date and no duration is the silent-drop
shape and keeps the banner.

- **The rule is stated on `Video`, not on the raw listing entry.** `classify`
  already folds `upload_date` and `timestamp` into one field and records
  `date.min` when neither was present, so "no date in either listing field" is
  exactly `video.upload_date == date.min` on the built record. Nothing needs
  plumbing back to the raw dict.
- **Two counts replace one.** The summary line becomes two — the expected Shorts
  shape as "N Shorts reported no duration (expected)", and any anomaly as its
  own line — so the number that was drowning the signal now sits beside it
  rather than in front of it.
- **The banner survives, narrowed.** It fires for one or more dated,
  durationless entries and names their ids, which is the case BL-15 argues is
  worth shouting about and the one the count threshold made unreachable.
- **No count threshold anywhere.** The "more than one" test goes; R1009 rules
  the judgement is on evidence, never on how many entries lack a duration, and
  any fixed count is wrong the day the channel posts one more Short.
- **BL-15's eight measured ids land as the regression.** Their titles are
  recorded as provenance and nothing asserts on the wording; what is asserted is
  the shape and the silence.
- **Not done here: classifying from a listing Shorts marker.** OD-14 considered
  BL-15's direction 2 and did not adopt it as the requirement — "the plan may
  use it where present". The flat listing this corpus returns carries no such
  marker on the measured entries, so using one would be building against a field
  that is not there.

Two slices, ~250 lines, sequential — slice 2 is the regression against slice 1.
No uncertainties: every decision derived from the design, with the two that came
closest to the line worked through below.

## Uncertainties

**No uncertainties — every decision derived from the design.** Nothing here was
guessed, so nothing is filed as a `BL-<n>` and nothing waits on a ruling. Two
questions came close enough to the line that the derivation is worth showing.

- **Whether the Shorts shape is read off the raw entry or off `Video`.**
  Derived from what `classify` already does. R1009 names the two listing fields
  `upload_date` and `timestamp`, and `classify` reads both and stores
  `date.min` when neither parsed — so the built record already carries the
  answer losslessly for this question, and reading the raw dict again would mean
  a second parser that can disagree with the first. ESC-21 is the recorded cost
  of fixtures describing the listing differently from the code; one reader is
  how that stays impossible.
- **Whether a dated, durationless entry still classifies as a Short.** Derived
  from R1009's own text: it says the expected shape "classifies as it does
  today" and changes only what is reported, and it says nothing about
  reclassifying the anomaly. So classification is untouched in both cases —
  this plan changes the index summary and nothing about `inclusion`. The
  anomalous video is still excluded as a Short; the banner is what makes that
  visible, which is the entire point of keeping it.

## The work, sliced

Two slices. **They are sequential.** Slice 2 asserts against the output slice 1
produces, so it is built after slice 1 has landed, not beside it.

## Slice 1 — The summary tells a Short's shape from a silent drop

- **Delivers:** `uv run find-best-mobo index` reports a dateless, durationless entry as an expected Shorts count on one line and fires no banner for it; an entry carrying a real date and no duration fires the banner and is named, whether there is one of them or a dozen. The count threshold is gone. On the real channel, BL-15's eight ids stop producing a banner. Covers R1009.
- **Files:** `src/find_best_mobo/commands/index.py`, `tests/test_index_zero_duration.py`
- **Estimate:** ~140 lines

### Signatures

```python
@dataclass(frozen=True)
class ZeroDuration:
    expected_shorts: tuple[str, ...]
    anomalies: tuple[str, ...]


def classify_zero_duration(videos: Sequence[Video]) -> ZeroDuration: ...
```

Both live in `src/find_best_mobo/commands/index.py`, beside the summary they
serve; `Video` stays in `src/find_best_mobo/index.py` where it is defined today,
and `classify`, `enumerate_channel` and `write_index` keep the signatures they
have. `_zero_duration_ids` is replaced by `classify_zero_duration` rather than
kept alongside it — two functions answering the same question is how the two
readings drift apart.

### Behaviour the signatures cannot carry

- **The split is `video.upload_date == date.min`.** A zero-duration video whose
  date is the sentinel is an expected Short; one with any real date is an
  anomaly. Both tuples hold video ids and are sorted the way `write_index`
  sorts — upload date, then video id — so an id printed here is findable in
  `index.jsonl` at the position it was printed in.
- **Only zero-duration videos enter either tuple.** A video with a duration is
  neither shape, whatever its date; a dateless entry with a real duration is
  already excluded out of range by `classify` and is not this rule's business.
- **The count line always prints**, including as zero, for the same reason the
  existing summary lines do: a number present on every run is comparable across
  runs, and BL-15's second cost was a signal that had nowhere to appear.
- **The banner is unconditional on count and conditional on shape.** One
  anomaly fires it. Its text no longer claims that only one such video is
  expected — that premise is what OD-14 retired — and instead says that these
  entries carry a real upload date with no duration, are being read as Shorts
  and excluded, and should be checked against the channel.
- **Neither shape changes `inclusion` or the exit code.** `run` still returns 0;
  the index is written either way. The banner reports, it does not halt — R24's
  halt triggers are `fetch`'s and are not touched here.

## Slice 2 — BL-15's eight ids, pinned as the shape that must stay quiet

- **Delivers:** a regression built from BL-15's measured run that fails on the count-threshold rule and passes on the shape rule — eight dateless, durationless entries produce the expected-Shorts count and no banner, and adding one dated, durationless entry to the same listing produces the banner naming exactly that ninth id. That pair is the one R1009 requires, and the second half is the silent drop the old rule could not surface. Covers R1009.
- **Files:** `tests/test_index_zero_duration.py`, `tests/test_index.py`
- **Estimate:** ~110 lines

### The fixture

Built in the test module from faked listing entries through the real `classify`
→ `run` path, with `list_channel_entries` faked at the boundary as the suite
already does. No network: `tests/conftest.py` fails any test that opens a
non-loopback socket.

The eight entries reproduce BL-15's measured shape rather than its captions:
no `duration` key, no `upload_date` key and no `timestamp` key, `was_live`
false. BL-15's real video ids and titles go in the test's docstring as
provenance — they are what was measured — and nothing asserts on the titles,
because the rule turns on the listing shape and not on wording.

Assertions:

- the eight produce `expected_shorts` of length 8 and `anomalies` empty;
- the printed summary contains the expected-Shorts count line and NO banner —
  asserted on the absence of the banner's own marker, not on the whole text, so
  rewording the message does not fail the test;
- a ninth entry with a real `upload_date` and no `duration` produces one
  anomaly, fires the banner, and the banner names that id and not the other
  eight;
- one dateless, durationless entry on its own still fires no banner, which is
  the half the old "more than one" threshold happened to get right and which
  must not regress.

## Out of scope

- **Reclassifying anything.** A dated, durationless video is still excluded as a
  Short. R1009 changes what is reported, and OD-14 rejected raising or moving
  the classification rule.
- **A listing Shorts marker.** OD-14 left it available to the plan "where
  present"; it is not present on the measured entries, so nothing is built
  against it.
- **`youtubetab:approximate_date`.** The approximate-date rough edge in
  `docs/architecture.md` is a separate matter and is not touched.
- **Halting.** The banner reports; `fetch`'s halt triggers (R24) are the only
  thing in the pipeline that stops a run, and they are not this plan's.
