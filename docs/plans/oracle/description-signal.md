---
slug: description-signal
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1004]
---

# The video description is recorded at fetch and matched at selection — Plan

Implements **OD-8** (`docs/DESIGN.oracle.md`), which adds **R1004** from the
evidence in **BL-11**. The pipeline reads titles and transcripts and nothing
else, and the one real video measured so far — a review of the MSI MPG B850I
Edge TI — names its chipset in neither: the title spells it `B850i` and the
spoken audio never lands a clean `B850`. Its description carries
`#AMD #ryzen #MSI #B850 #ITX`. `fetch_caption_track` already receives that
description in the per-video extraction it runs today, and throws it away.

## Summary

The fetch stage stops discarding the description, selection reads it as a third
include rule, and the checkpoint counts what it added. Three slices, ~415 lines,
**sequential**.

- **The description is stored in the transcript cache record**, as a field on
  `Transcript` defaulting to `""` — the only durable thing a successful fetch
  writes, and the record selection already loads. A separate
  `data/descriptions/` artifact would buy only the no-caption case, which R1004
  hands to the failure ledger anyway.
- **The network boundary is renamed** `fetch_caption_track` → `fetch_video`,
  returning captions *and* description from the extraction it already runs. No
  additional request — OD-8's whole answer to BL-11's cost objection.
- **A description hit is an automatic include, after the title and before the
  threshold**, written to `data/selected.jsonl` under a new reason
  `description_hit`. It produces no `Mention` and does not move
  `distinct_canonicals`: a description has no cue, and R5 cuts every window from
  a timestamp.
- **The select report gains two numbers, not one**: videos admitted on a
  description, and how many of those no other rule would have admitted. Only the
  second is R1004's "how many videos the signal added", now that one video can
  satisfy two rules.
- **Not done here:** no `data/index.jsonl` change, no description text in
  `selected.jsonl`, no description forms in the `aliases --check` recall report,
  no refresh flag, no description contribution to the mention threshold.

**What I need you to rule on** — all three are already ruled by OD-8, and are
here because they cost you something.

1. **The cache you already have gains nothing.** R1004 forbids a forced
   refetch, so the measured B850I case stays invisible until those entries are
   deleted and `fetch` is re-run, at one extraction each. Documented as an
   operator action, never automated.
2. **The whole description is matched**, boilerplate and links included — R1004
   says so, unqualified. A footer naming a vendor auto-includes every video
   carrying it; the two new counts make that visible on the first real run, and
   narrowing the rule is a fresh ruling on that evidence.
3. **The rename makes a merged plan partly wrong.** `corpus-and-checkpoint`'s
   slice 2 declares `fetch_caption_track`, which stops existing. **OD-12**
   already commissions that plan's revision; this rides it.

## Uncertainties

**None: every decision derived from the design.** R1004 fixes the behaviour at
both ends of the field and answers the three questions that would otherwise have
been guesses — where a pre-existing cache entry stands ("simply has no
description signal — never an error, and no forced refetch"), what a description
hit counts as ("an automatic include, like a title hit"), and what happens when
the description is the only signal on a video with no captions ("the failure
ledger still governs"). Nothing is filed to `docs/BACKLOG.md` by this plan.

### Derivations, not uncertainties

Each is a place the design layer fixes the behaviour and leaves the mechanism to
the plan. Shown rather than asserted, because the ones that came closest to the
line are the ones a reviewer would otherwise have to reconstruct.

- **The description lives in the transcript cache record.** Three grounds, in
  order of weight. (1) R1004's "a video cached before descriptions were
  recorded simply has no description signal" ties the field's presence to a
  cache entry's vintage, which is a property of the record, not of the video.
  (2) The fetch stage's only durable output on success is that record — the
  ledger records failures — so recording "at the fetch boundary", OD-8's own
  phrase, has exactly one home that costs no new artifact. (3) R1004 accepts
  losing the description precisely when there is no transcript, which is what
  storing it beside the cues does by construction.
- **`Transcript` gains the field rather than `select_video` gaining a
  parameter.** Everything that already loads a cache entry then sees the
  description, and `select_video`'s signature — the contract two blind authors
  share — does not move. The tension is worth naming: §9's Transcript is "video
  id, ordered cues … plus the normalized form used for matching", and a
  description is none of those. §9's Video would be the better home by entity
  and cannot be one by sequencing — `data/index.jsonl` is written by a stage
  that runs before any description exists.
- **The new reason lives on `Selection`, not on `Video`.** R1004's measurement
  clause names "the inclusion reason in the index (R1/§9)"; §9's four inclusion
  reasons (title hit, threshold pass, excluded, transcript unavailable) are
  selection outcomes, and the built system already implements them as
  `Selection.reason` in `data/selected.jsonl`, while `Video.inclusion` carries
  the index stage's own three values. Putting one reason in a different file
  from its three siblings would make R1004's count harder to read, not easier.
- **Title before description before threshold.** R1004 makes a description hit
  an automatic include "like a title hit", which puts it above the threshold.
  The title stays first because it is the stronger signal and because keeping it
  first leaves every existing title-hit count untouched by this change.
- **"How many videos the signal added" is computed, not read off the reason.**
  Once two rules can fire on one video, counting `description_hit` records
  overstates the addition by however many of them the threshold would have
  admitted anyway. Both numbers are cheap — `distinct_canonicals` is already on
  every record — so the report carries the honest one beside the raw one.
- **A description hit yields no mentions.** `Mention` carries `start_seconds`,
  R5 cuts every excerpt window from it, and R14's links are built on it. A
  description has no cue, so a description-derived mention would have to invent
  that number. A selected video with no body mentions therefore yields no
  excerpts — the same shape a title hit with no body mentions already has today,
  not a property this plan introduces.
- **The description is matched as one normalized string.** `normalize` collapses
  newlines with all other whitespace, and `#` is not alphanumeric, so `#B850`
  lands as `#b850` and the matcher's `(?<![a-z0-9])` left boundary is satisfied.
  BL-11's measured case works with no hashtag-specific rule and no change to
  `normalize`.
- **No new configuration lever.** R17 lists the cost-saving levers and this is
  not one of them; R1004 states the rule unconditionally.

## The work, sliced

Three, and they are **sequential** — slice 2 decides on what slice 1 records,
slice 3 reads what slice 2 counts, and slices 1 and 2 share
`docs/architecture.md`. Each is vertical and observable by a person without
reading code: slice 1 is a field on disk after a fetch, slice 2 is a video whose
fate changed, slice 3 is the checkpoint's own printed output, which is where
OD-8's measurement is actually read.

## Slice 1 — The fetch stage stops throwing the description away

- **Delivers:** after `find-best-mobo fetch`, each newly cached `data/transcripts/<video_id>.json` carries the video's description beside its cues, from the same per-video extraction that fetched the captions — no additional request, and one client for the run as before. A cache file written before this slice still loads, with an empty description and no refetch. A video with no caption track is still a ledger row and caches nothing. Covers R1004 in part.
- **Files:** `src/find_best_mobo/ytdlp.py`, `src/find_best_mobo/transcripts.py`, `tests/test_transcripts.py`, `tests/test_ytdlp_client_reuse.py`, `docs/architecture.md`
- **Estimate:** ~150 lines

### Signatures

```python
@dataclass(frozen=True)
class VideoFetch:
    captions: str | None
    description: str


def fetch_video(video_id: str, config: Config) -> VideoFetch: ...


@dataclass(frozen=True)
class Transcript:
    video_id: str
    cues: tuple[Cue, ...]
    description: str = ""


def fetch_transcript(video: Video, config: Config) -> Transcript: ...
def load_cached(video_id: str, config: Config) -> Transcript | None: ...
```

Per **OD-12**, the module of every shared type this slice touches: `VideoFetch`
is new and lives in `src/find_best_mobo/ytdlp.py`, because it is what the
network boundary returns and nothing above the boundary constructs one;
`Transcript` and `Cue` stay in `src/find_best_mobo/transcripts.py`, as does the
`NoCaptions` exception; `Video` in `src/find_best_mobo/index.py`; `FetchFailure`
and `HaltTriggered` in `src/find_best_mobo/ledger.py`, with today's re-export of
`FetchFailure` from `transcripts.py` kept. `fetch_all`, `cache_path` and
`parse_vtt` keep the signatures they have; `fetch_transcript` and `load_cached`
are listed only to say that theirs do not change.

### Behaviour the signatures cannot carry

- **`fetch_video` replaces `fetch_caption_track` and is the same call.** One
  `extract_info` on the watch URL, on the same lazily built shared client, then
  the same English-track selection. `VideoFetch.captions` is exactly what
  `fetch_caption_track` returned — raw WebVTT, or `None` when the video offers
  no English track — and anything that goes wrong reaching YouTube still raises
  rather than returning a value, because the caller owns the ledger.
- **`VideoFetch.description` is a plain string, never `None`.** A missing key, a
  null, or a non-string in the extraction result all become `""`. The text is
  taken verbatim: no stripping, no truncation, no parsing of hashtags or links.
  Whatever normalization matching needs is matching's business, one stage later.
- **`fetch_transcript` carries it onto the `Transcript`.** `NoCaptions` is still
  raised when `captions is None`, before the description is used for anything —
  a description cannot conjure a transcript, and the ledger governs that video.
- **The cache record gains one key.** `_write_cache` writes `description`
  alongside `video_id` and `cues`, still `sort_keys=True` and one trailing
  newline, so two runs over the same video produce byte-identical files (R23).
- **`load_cached` must tolerate a record with no `description` key**, defaulting
  it to `""`. This is the load-bearing line of the slice: today a `KeyError` is
  caught and read as "no usable cache entry", so a strict read would silently
  invalidate every entry the owner already has and refetch the whole corpus —
  the exact opposite of R1004's "no forced refetch". A `description` present but
  not a string is coerced with `str`, matching how `video_id` is already read.
- **Nothing backfills.** `fetch_all` still skips a video whose cache entry
  exists, so an old entry is never refetched to acquire a description. R1004
  states that outcome; the mechanism is the cache-hit skip that already exists,
  and no code is added to preserve it.
- **`data/transcripts/` stays local-only** (R21). A description is corpus in the
  same way the cues are: never redistributed, never committed.
- **What the tests must pin:** an extraction carrying a description writes it
  into the cache file and reads back out of `load_cached`; an extraction
  carrying none yields `""` rather than failing; a cache file in the pre-slice
  shape (`video_id` and `cues` only) still loads, with `""`, and `fetch_all`
  still skips it without a fetch; a video with no caption track writes no cache
  file and lands in the ledger as `no_captions`, description or not; the
  one-client-per-run assertion in `tests/test_ytdlp_client_reuse.py` holds
  against `fetch_video`; and the cache file is byte-identical across two runs.
- **`docs/architecture.md`**: the network-boundary and transcript rows of the
  components table say the per-video extraction yields captions *and* the
  description; "Fetching transcripts" gains the description in step 3; the
  `data/transcripts/<video_id>.json` entry under "State and storage" says the
  record carries the description and that entries written before this change
  simply do not — citing OD-8/R1004, so the next agent reads an empty field as a
  decision rather than a bug.

## Slice 2 — A board named only in the description brings its video in

- **Delivers:** a video whose description names a board, and whose title and body name none, is selected instead of excluded, recorded under the reason `description_hit`; a video hitting on both title and description stays a `title_hit`; the threshold report carries how many videos came in on a description and how many of those nothing else would have admitted. A corpus with no descriptions selects exactly as it does today. Covers R1004.
- **Files:** `src/find_best_mobo/aliases.py`, `src/find_best_mobo/select.py`, `src/find_best_mobo/commands/select.py`, `tests/test_aliases.py`, `tests/test_select.py`, `docs/architecture.md`
- **Estimate:** ~170 lines

### Signatures

```python
def find_description_hits(description: str, matcher: re.Pattern[str]) -> frozenset[str]: ...


DESCRIPTION_HIT = "description_hit"


@dataclass(frozen=True)
class Selection:
    video: Video
    reason: str  # "title_hit" | "description_hit" | "threshold" | "excluded_below_threshold"
    mentions: tuple[Mention, ...]
    distinct_canonicals: int


@dataclass(frozen=True)
class ThresholdReport:
    threshold: int
    title_hits: int
    description_hits: int
    description_only_includes: int
    threshold_passes: int
    excluded: int
    would_include_at_minus_one: int
    would_exclude_at_plus_one: int
```

Per **OD-12**: `find_description_hits` is new and lives in
`src/find_best_mobo/aliases.py` beside `find_title_hits`, because it is the same
matching stage over the same compiled pattern and needs the same private
canonical-recovery helper. It takes the description as a plain `str` rather than
a `Transcript`, so it is testable without a cache entry and the alias module
stays ignorant of where the field is stored. `DESCRIPTION_HIT`, `Selection` and
`ThresholdReport` stay in `src/find_best_mobo/select.py` beside `TITLE_HIT`,
`THRESHOLD` and `EXCLUDED`; `Mention` and `Alias` in
`src/find_best_mobo/aliases.py`; `Transcript` and `Cue` in
`src/find_best_mobo/transcripts.py`; `Video` in `src/find_best_mobo/index.py`.
`select_video`, `select_all`, `threshold_report`, `write_selected` and
`read_selected` keep the signatures they have — `select_video` reads the
description off the `Transcript` it is already handed, which is why slice 1 put
it there.

### Behaviour the signatures cannot carry

- **`find_description_hits` is `find_title_hits` over another string**: the
  canonicals whose forms the matcher finds in `normalize(description)`, as a
  frozenset, empty for an empty description. Pure, total, no I/O. The boundary
  rule is not relaxed for descriptions — `theb850` still matches nothing.
- **The order in `select_video` is title, description, threshold, excluded.** A
  title hit is decided first and its record is unchanged. Otherwise a non-empty
  description-hit set is `DESCRIPTION_HIT`. Otherwise the distinct count against
  the threshold, exactly as today.
- **`mentions` and `distinct_canonicals` are computed exactly as today** — body
  mentions, in cue order — for every reason, `description_hit` included. No
  `Mention` is ever constructed from a description and no `start_seconds` is
  invented. This is the load-bearing negative of the slice.
- **`threshold_report` counts both new numbers.** `description_hits` is the
  count of `DESCRIPTION_HIT` selections; `description_only_includes` is how many
  of those have `distinct_canonicals < threshold` — the videos no other rule
  would have admitted, which is R1004's "how many videos the signal added". The
  two are equal only when no description-hit video also passes the threshold.
- **The what-if deltas keep their definitions and shift in value.**
  `would_include_at_minus_one` still counts excluded videos and
  `would_exclude_at_plus_one` still counts threshold passes — a video that used
  to be a threshold pass and now reads `description_hit` has left that
  population, which is correct, because the threshold no longer decides it.
- **`_print_report` gains two lines, printed always, zero included**, after the
  title-hit line and before the total: a count that prints only when it fired
  cannot be told from one that never ran. `selected` becomes title hits plus
  description hits plus threshold passes, and the closing clause of the
  raise-the-threshold line becomes "Title and description hits are unaffected
  either way." The exact wording is pinned in slice 3, not here.
- **`selected.jsonl` gains no field.** The new value appears in the existing
  `reason` string; the description text is not copied into the record — it is
  already on disk in the cache, it can be long, and nothing downstream reads it.
  `read_selected` needs no change and still reads records written before this.
- **What the tests must pin**, through the real `select_all` path against a
  table and cache entries written into `tmp_path`, as `tests/test_select.py`
  already does: a description-only video is selected with reason
  `description_hit` where the same video with its description removed is
  excluded; a title-and-description video is a `title_hit` and is counted in
  neither new number; a description hit that also passes the threshold is
  counted in `description_hits` and **not** in `description_only_includes`; a
  description-hit video whose body names nothing has `mentions == ()` and
  `distinct_canonicals == 0`; and a corpus with no descriptions produces the
  same selections and the same record shapes as before, with both new counts
  zero. In `tests/test_aliases.py`, `find_description_hits` directly: the
  hashtag form `#b850`, a plain sentence naming a board, a multi-line
  description with the name on its own line, an empty string, and the fused
  `theb850` that must yield nothing.
- **`docs/architecture.md`**: "Narrowing the corpus" gains the description rule
  as a numbered step between the title rule and the threshold, with why hashtags
  are strong evidence and the note that a description hit adds no mentions; the
  selection row of the components table and the `data/selected.jsonl` entry
  under "State and storage" name the new reason. Citing OD-8.

## Slice 3 — The measured video appears in the checkpoint the owner reads

- **Delivers:** OD-8's stated measurement, at the surface it is actually read. `find-best-mobo select`, over a cache holding BL-11's measured video, prints that one video came in on a description and that one of those would not have been selected any other way, and writes its `description_hit` record; over a cache written before this change, it prints both counts as zero, selects exactly as it did before, and fetches nothing. Covers R1004.
- **Files:** `tests/test_description_signal.py`, `docs/architecture.md`
- **Estimate:** ~95 lines

### Signatures

None. No production code changes: this slice asserts that slice 2's decision
reaches `data/selected.jsonl` and the printed report, which is where R4's
selection counts and R1004's inclusion reason are read.

### Behaviour the signatures cannot carry

- **The BL-11 case is built from what BL-11 records**, and nothing else: the
  description line `#AMD #ryzen #MSI #B850 #ITX`, verbatim, on a video whose
  cues name no canonical. Its provenance is stated in the test's docstring,
  citing BL-11.
- **The title is deliberately neutral**, not the real video's `B850i`. Two
  reasons: the title is not in the repository (the same gap **BL-17** records
  for R1003, ruled by **OD-16**), and once `itx-chipset-variant` lands a `B850i`
  title would auto-include on the title rule, which would make this test's
  result depend on merge order. A neutral title is what proves the description
  did the work.
- **The table is written into `tmp_path`** carrying `B850` as a chipset, as the
  selection tests already do — the shipped table has no B850 entry and BL-11's
  evidence is about B850.
- **The pre-description case reuses the same corpus** with the cache entries
  rewritten in the old two-key shape. Both counts print zero, the same videos
  are selected as before the plan, and no fetch is attempted — the offline
  fixture in `tests/conftest.py` fails the test if one is.
- **Both printed reports are asserted as text**, including the two new lines and
  the "Title and description hits are unaffected either way" clause, because the
  checkpoint's output is what the owner spends against.
- **`docs/architecture.md`**: "Known rough edges" records that the signal is
  absent from every cache entry written before this change, and states the
  operator action once — delete the entry and re-run `fetch`, at one extraction
  per video — citing OD-8/R1004.

## Out of scope

- **Backfilling descriptions into existing cache entries**, and any flag that
  would. R1004 rules out a forced refetch; deleting a cache file and re-running
  `fetch` is the deliberate path, documented rather than automated. A
  `--refresh` flag would also need OD-10/R1006's dispatcher forwarding, which is
  not built on this branch.
- **Keeping the description of a video with no caption track.** R1004 hands that
  video to the failure ledger; storing its description would mean a second
  artifact for a video that can never be excerpted.
- **Description hits counting toward the mention threshold**, or appearing in
  `data/selected.jsonl` as `Mention`s. R1004 makes a description hit an include,
  not evidence with a timestamp.
- **Narrowing what counts as a description hit** — hashtags only, or ignoring
  links and boilerplate. R1004 says "a normalized alias hit in the description".
  If the first real run's counts show boilerplate admitting the channel
  wholesale, that is logged evidence for a `BL-<n>`, not a narrowing taken here.
- **Description forms in the `aliases --check` recall report.** OD-8's stated
  measurement is the inclusion reason and R4's selection report; the recall
  report reads cached transcripts and is left reading bodies only.
- **`data/index.jsonl` and `index.py`.** The index stage runs before any
  description exists; the new reason lives where the other three selection
  reasons already live.
- **OD-11/R1007's move of the alias table** to a tracked root path. No plan
  covers it on this branch yet; this plan reads the table wherever `select_all`
  reads it today.
- **Revising `docs/plans/corpus-and-checkpoint.md`**, whose slice 2 Signatures
  block names `fetch_caption_track`. That plan is `CODEOWNERS`-owned and
  **OD-12** already commissions its revision; this rename rides it.
- **Merge order.** `caption-split-aliases` (OD-6) and `itx-chipset-variant`
  (OD-7) both edit `src/find_best_mobo/aliases.py` and `tests/test_aliases.py`,
  and `caption-split-aliases` slice 3 also edits `tests/test_select.py`. None of
  the three is built in parallel with this one; whichever lands second carries
  the rebase, and nothing here depends on either landing first.
