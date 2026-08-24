---
slug: json3-captions
status: draft
created: 2026-08-24
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1013]
---

# Captions come from json3, and the fallback says so — Plan

Implements **OD-24** (`docs/DESIGN.oracle.md`), which adds **R1013** from the
evidence in **BL-28**: 285 of 285 cached transcripts carry roughly three copies
of every spoken word — 38,767,230 characters stored against 13,645,734 of
speech, 2.84x — because YouTube's automatic captions are delivered as WebVTT in
**roll-up** form, one cue per display frame rather than per line of speech.

## A correction to OD-24's rationale, carried here because that ledger is append-only

OD-24 says `aAppend` events "carry real speech, and dropping them loses words".
**That is wrong, and it was measured wrong.** Every one of the 2,257 `aAppend`
events in the fetched track is **text-free**: each carries a single newline and
nothing else, and the 2,257-character difference is exactly those newlines.

R1013's rule is unchanged — include them — and its reason is stronger than the
one OD-24 gives. They are the **line break**. Dropping them does not shorten the
transcript, it FUSES it: `we'regoing` where the speaker said `we're going`. That
corrupts matching at every line boundary, which is worse than losing 2,257
characters would have been. The correction is recorded here because
`docs/DESIGN.oracle.md` may not be edited once a decision has landed, and this
is the document whoever builds R1013 reads.

## Summary

One format preference at the boundary, one new parser, one de-duplication in the
old parser, and a provenance field that makes the difference visible.

- **`json3` is requested and preferred; VTT is the fallback.** The boundary
  already runs one extraction per video and already picks a track from it; this
  changes which format of that track it takes, not how many requests it makes.
- **A json3 transcript is one cue per text-bearing event**, its text the
  concatenation of that event's segments and its start the event's own
  `tStartMs`. Per-segment `tOffsetMs` is carried no further than that: R5 cuts
  windows from a cue start, so an event-level cue is already the improvement —
  it is the moment those words were spoken rather than the moment a two-line
  frame containing them was drawn.
- **`aAppend` events are kept as the line break**, for the reason above.
- **The VTT fallback de-duplicates on parse, never stores duplicates.** R1013
  says no cached transcript may contain the same line three times whichever path
  produced it, so `parse_vtt` drops the roll-up frames rather than something
  downstream compensating for them.
- **Provenance is a field, not an inference.** `Transcript.source_format` is
  `"json3"` or `"vtt"`, written into the cache record, and the `fetch` summary
  reports how many videos took each path — prominently when any took the
  fallback.
- **It costs you a re-fetch**, and one re-fetch serves three things: the
  descriptions R1004 records, this de-duplication, and the better timestamps.
  Nothing here refetches automatically; a cache entry written before this plan
  keeps working and reports its format as unknown.
- **Not done here:** no change to excerpting, selection or the projection beyond
  what smaller transcripts do to their numbers; no per-word timestamps on
  `Mention`; no removal of `parse_vtt`; no retry or format negotiation beyond
  preferring one and falling back once.

Three slices, ~500 lines, **sequential** — slice 1 introduces the field slices 2
and 3 report on.

**What I need you to rule on:** nothing is unruled. Two things are listed
because they cost you something: **the re-fetch**, and **a cache that will
briefly hold two provenance classes** until it is re-fetched, which is exactly
why the field and the summary line exist.

## Uncertainties

**No uncertainties — every decision derived from the design.** Nothing here was
guessed, so nothing is filed as a `BL-<n>`. Three questions came close enough to
the line that showing the derivation is worth more than asserting it.

- **Cue granularity: per event or per segment?** Derived from R5 and R1013 read
  together. R1013 requires a cue's start to be "the moment its own words were
  spoken" rather than a display frame's; R5 cuts a window of minutes around that
  start. A per-segment cue would make every cue one word long, which multiplies
  the cue count by roughly seven for a precision R5's two-and-five-minute window
  cannot use, and it would make `count_cross_cue_candidates` (R1010) count a
  boundary between every pair of words. Per text-bearing event is the coarsest
  cue that satisfies R1013 and the only one that leaves R1010 meaning what it
  means.
- **Where the format is chosen.** Derived from what the boundary already does:
  `_caption_url` picks a track and returns its URL, so it is the one place that
  sees the available formats. It returns the chosen format alongside the URL
  rather than a second function re-deriving it, because two readers of one
  extraction result is the shape ESC-21 and BL-28 both punish.
- **What an old cache entry reports.** Derived from R1004's precedent, ruled one
  slice earlier for exactly this situation: a record written before a field
  existed reads with that field's default and is never a forced refetch. The
  default is `"unknown"` rather than `"vtt"` — guessing that an old entry came
  from the VTT path would be true today and a lie the moment anyone replays this
  reasoning, and `"unknown"` is what makes the summary's fallback count honest.

## The work, sliced

Three, each observable from the command line on its own. **Sequential**: slice 1
adds the field and the parser; slice 2 changes what the fallback stores; slice 3
reports what slices 1 and 2 recorded. They share `transcripts.py` and
`docs/architecture.md`, so they are not built in parallel.

## Slice 1 — A transcript comes from json3, and says so

- **Delivers:** `find-best-mobo fetch` requests json3 and parses it, so a newly cached transcript holds each spoken line once with the timing json3 supplies, and its record carries `source_format: "json3"`. A track offering no json3 still fetches, through the VTT path, and records `"vtt"`. A cache entry written before this plan loads unchanged and reports `"unknown"`. Covers R1013 in part.
- **Files:** `src/find_best_mobo/ytdlp.py`, `src/find_best_mobo/transcripts.py`, `tests/test_transcripts.py`, `tests/test_ytdlp_client_reuse.py`, `tests/fixtures/captions_json3.json`, `docs/architecture.md`
- **Estimate:** ~230 lines

### Signatures

```python
JSON3 = "json3"
VTT = "vtt"
UNKNOWN_FORMAT = "unknown"


@dataclass(frozen=True)
class CaptionTrack:
    url: str
    caption_format: str


@dataclass(frozen=True)
class VideoFetch:
    captions: str | None
    description: str
    caption_format: str


@dataclass(frozen=True)
class Transcript:
    video_id: str
    cues: tuple[Cue, ...]
    description: str = ""
    source_format: str = UNKNOWN_FORMAT


def parse_json3(raw: str) -> tuple[Cue, ...]: ...
```

Per **OD-12**, the module of every shared name this slice touches: `JSON3`,
`VTT`, `CaptionTrack` and `VideoFetch` live in `src/find_best_mobo/ytdlp.py` —
they describe what the network boundary offers and returns, and nothing above it
constructs one. `UNKNOWN_FORMAT`, `Transcript`, `Cue`, `parse_json3` and
`parse_vtt` live in `src/find_best_mobo/transcripts.py`, because a cached record
keeps its provenance after the boundary is gone. `Video` stays in
`src/find_best_mobo/index.py`; `FetchFailure` and `HaltTriggered` in
`src/find_best_mobo/ledger.py`. `fetch_video`, `fetch_transcript`, `fetch_all`,
`load_cached` and `cache_path` keep the signatures they have.

### Behaviour the signatures cannot carry

- **`_caption_url` becomes `_caption_track`**, returning a `CaptionTrack` or
  `None`. Manual subtitles still win over automatic ones; within either, `json3`
  wins, then `vtt`, and the first offered format is still the last resort — its
  `caption_format` is then whatever the entry advertises, or `UNKNOWN_FORMAT`
  when it advertises nothing.
- **`parse_json3` reads one cue per TEXT-BEARING event.** An event's text is the
  concatenation of its segments' `utf8` in order; its start is `tStartMs / 1000`.
  An event whose concatenated text is empty or whitespace contributes no cue —
  which is what an `aAppend` event is, and it is exactly why the line break must
  not be dropped from the TEXT: cue texts are joined with a single space
  downstream, so a break that becomes nothing fuses `we're` and `going`.
- **Whitespace inside a segment is preserved as it arrives.** json3 puts the
  leading space on the following word (`'Hey'`, `' guys,'`), so concatenating
  verbatim is what reproduces the sentence; stripping per segment would fuse
  every word in the event.
- **Anything unparseable is a `ValueError`, not a silent empty transcript.**
  `parse_vtt` tolerates a malformed cue because one bad cue in two hours is not
  worth losing a video; a json3 document that is not JSON at all is a different
  failure, and a transcript of zero cues from a video that has captions would be
  indistinguishable from a video with none. The caller's ledger already
  distinguishes "could not fetch" from "nothing to fetch" and this keeps that
  line drawn.
- **`fetch_transcript` chooses the parser from `VideoFetch.caption_format`**, not
  by sniffing the payload: the boundary knows what it asked for, and a sniffer is
  a second reader of one answer.
- **`load_cached` defaults a missing `source_format` to `UNKNOWN_FORMAT`**, for
  the same reason and by the same mechanism as R1004's description: a strict read
  would invalidate the owner's whole cache, which R1004 forbids and this plan
  does not revisit.
- **The fixture is a synthetic json3 document of the real shape**, in
  `tests/fixtures/captions_json3.json` — the roll-up pattern (a text event, then
  a text-free `aAppend` event, then the next text event), segments with and
  without `tOffsetMs`, an event with no `segs` key, and one whose text is only
  whitespace. R21 keeps the real corpus local, so the shape is reproduced and the
  words are invented.
- **What the tests must pin:** json3 is preferred when both formats are offered
  and vtt is taken when json3 is absent; a roll-up json3 document parses to one
  cue per line with no line repeated; `aAppend` events produce no cue but their
  break is not lost from the text of the cues around them; segment whitespace is
  preserved; `tStartMs` becomes the cue start; a malformed document raises; the
  cache round-trips `source_format`; and an old record without the key loads with
  `UNKNOWN_FORMAT` and its cues intact.

## Slice 2 — The VTT fallback stops storing the duplication

- **Delivers:** a roll-up WebVTT track parses to one cue per spoken line, so a video that falls back holds the same text a json3 video would rather than three copies of it. The shipped non-roll-up fixture parses exactly as it does today. Covers R1013 in part.
- **Files:** `src/find_best_mobo/transcripts.py`, `tests/test_transcripts.py`, `tests/fixtures/captions_rollup_vtt.txt`, `docs/architecture.md`
- **Estimate:** ~170 lines

### Signatures

```python
def parse_vtt(raw: str) -> tuple[Cue, ...]: ...
```

Unchanged, deliberately: this is a behaviour change inside a function every
caller already routes through, and giving it a flag would let the duplication
back in through the argument. Per **OD-12** this slice adds no shared type.

### Behaviour the signatures cannot carry

- **A cue that merely EXTENDS the previous one is a display frame and is
  dropped.** In roll-up VTT the sequence is `A`, `A B`, `B`, `B C`, `C`: the
  frame is the one whose text starts with the previous cue's text followed by a
  separator. Dropping those leaves `A`, `B`, `C` — the spoken lines, each with
  the start time it was actually displayed alone at, which is the timing the
  frames cannot give.
- **A cue that is wholly contained in the previous one is also dropped**, which
  is the same frame seen from the other side.
- **The last line is not lost.** If the final cue is a frame extending its
  predecessor, its new tail has no solo cue to follow it, so that tail is kept
  as its own cue. Without this the last line of every fallback transcript
  disappears, which is a silent loss and is the case the measurement flagged.
- **The rule is structural and is only ever applied to ADJACENT cues.** It never
  compares distant text, so genuinely repeated speech is untouched unless a
  speaker repeats exactly the words at a cue boundary — and the measurement
  behind this bound is that a conservative structural rule recovers all but
  0.008% of what an aggressive word-overlap merge does, so nothing needs the
  aggressive one.
- **A non-roll-up track is unchanged.** No cue in an ordinary WebVTT extends its
  predecessor, so every rule above is a no-op and the shipped fixture's parse is
  byte-identical to today's. That is asserted, not assumed.
- **The new fixture is a synthetic roll-up VTT** reproducing BL-28's measured
  shape: paired cues 0.01s apart, the second carrying the first's text plus the
  next line, ending on a frame so the last-line rule is exercised. Invented
  words, real geometry, per R21.
- **What the tests must pin:** a roll-up document yields one cue per line with
  each line appearing once; the cue starts are the solo frames' starts, not the
  0.01s twins'; the final line survives; the shipped non-roll-up fixture parses
  unchanged; and a transcript's total characters after parsing are within a few
  percent of the same content parsed from json3 — the two paths must agree, which
  is the property that makes the fallback trustworthy.

## Slice 3 — The run says which path every video took

- **Delivers:** `find-best-mobo fetch` ends with a line stating how many videos came from json3 and how many from the VTT fallback, printed on every run including when the fallback count is zero — and when it is not zero, prominently enough that nobody has to be told twice which cache they are looking at. Completes R1013.
- **Files:** `src/find_best_mobo/commands/fetch.py`, `tests/test_transcripts.py`, `docs/architecture.md`
- **Estimate:** ~100 lines

### Signatures

```python
def run(config: Config, args: Namespace) -> int: ...
```

No type or signature changes: the stage counts what `fetch_all` has already
written. Per **OD-12**: `Transcript` and `UNKNOWN_FORMAT` stay in
`src/find_best_mobo/transcripts.py`; `Ledger` and `HaltTriggered` in
`src/find_best_mobo/ledger.py`.

### Behaviour the signatures cannot carry

- **The counts come from the transcripts this run cached**, not from a walk of
  the whole cache directory: the summary describes the run, and a cache holding
  older entries in another format is what slice 1's `UNKNOWN_FORMAT` and this
  line exist to make visible rather than to average away.
- **Both counts print every run, zero included** — the same rule R1009, R1010 and
  R1012 already follow, and for the same reason: a count that appears only when
  it fired cannot be told from one that never ran.
- **A non-zero fallback count is called out, not merely counted.** R1013 requires
  the run to say so prominently; the shape is the one `index` already uses for
  the case it must not let pass unnoticed, and the message says what it means —
  those transcripts were reconstructed from roll-up frames rather than read
  verbatim, they are within a fraction of a percent of the json3 text, and the
  reason it matters is that a later question about one claim's timestamp has a
  different answer depending on which path produced it.
- **A halted run still reports what it cached before halting.** The R24 trigger
  path prints the ledger; this line goes with the counts that path already
  prints, so a halt does not hide the provenance of what did land.
- **What the tests must pin:** the counts on a mixed run; both lines at zero on
  an empty run; the prominent call-out present when the fallback was used and
  absent when it was not; and the counts surviving a halt.

## Out of scope

- **Re-fetching the existing cache.** R1004 already ruled that a stage never
  forces a refetch, and nothing here revisits it. The owner re-fetches when they
  choose, and one re-fetch serves this plan and R1004's descriptions together.
- **Per-word timestamps on `Mention`.** json3 carries `tOffsetMs` per segment and
  this plan deliberately stops at the event. Using it would change `Mention`,
  R5's window arithmetic and the report's links at once, and R1013 asks for none
  of that.
- **Removing `parse_vtt`.** OD-24 weighed and rejected it: json3 is undocumented
  and can change, and the fallback is what keeps that a degraded run rather than
  an outage.
- **Any change to excerpting, selection or the projection.** Their numbers move
  because the transcripts are smaller and their timestamps better; no rule of
  theirs changes, and nothing in this plan edits those modules.
- **Format negotiation beyond one preference and one fallback.** `srv1`, `srv3`
  and `ttml` were weighed in OD-24 and add a third parser for nothing.
