---
slug: description-signal
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1004]
---

# The video description is recorded at fetch and matched at selection — Plan

Implements **OD-8** (`docs/DESIGN.oracle.md`), which adds **R1004** from the
evidence in **BL-11**. The pipeline matches titles and transcripts only, and the
one real video measured so far — a review of the MSI MPG B850I Edge TI — names
its chipset in neither: the title spells it `B850i` and the spoken audio never
lands a clean `B850`. Its description carries `#AMD #ryzen #MSI #B850 #ITX`.
Hashtags are author-written, short, and unmangled by speech-to-text, and
`fetch_caption_track` already receives the description in the per-video
extraction it runs today and throws it away.

## Summary

Two changes, one at each end of the field's life: the fetch stage stops
discarding the description, and selection reads it as a third include rule.

- **The description is stored in the transcript cache record**, as a field on
  `Transcript` defaulting to `""` — the only durable thing the fetch stage
  writes on success, and the record selection already loads. The alternative, a
  separate descriptions artifact, buys only the no-caption case R1004 hands to
  the failure ledger anyway.
- **The network boundary returns both from the extraction it already runs**:
  `fetch_caption_track` becomes `fetch_video` returning captions *and*
  description. No additional request — OD-8's whole answer to BL-11's cost
  objection.
- **A description hit is an automatic include, after the title and before the
  threshold**, recorded as a new reason `description_hit` in
  `data/selected.jsonl`. It yields no `Mention`s and does not move
  `distinct_canonicals`: a description has no cue, and R5 cuts every excerpt
  window from a timestamp.
- **The select report gains two numbers, not one**: videos included on a
  description, and how many of those no other rule would have admitted. Only the
  second reads as R1004's "how many videos the signal added" once a video can
  satisfy two rules at once.
- **This does not reach the cache you already have.** R1004 forbids a forced
  refetch, so the measured B850I case stays invisible on the existing 285-video
  cache until those entries are deleted and refetched, at one extraction each.
  Documented as an operator action, not automated.
- **The whole description is matched**, boilerplate and links included — R1004
  says "a normalized alias hit in the description", unqualified. If boilerplate
  names a vendor, that video auto-includes, and the two new counts are what make
  it visible at the checkpoint on the first real run.
- **Not done here:** no `data/index.jsonl` change (it is written before any
  description exists), no description text in `selected.jsonl`, no description
  forms in the `aliases --check` report, no refresh flag, no description
  contribution to the mention threshold.

Two slices, ~340 lines, **sequential** — slice 2 decides on the field slice 1
records. No uncertainties: every decision derives from the design layer, and the
derivations are recorded below. **Merge order:** `caption-split-aliases` (OD-15)
adds its own field to `Selection` and `ThresholdReport` and a line to the same
report, and this plan adds a function to `aliases.py`, which that plan and
`itx-chipset-variant` both edit — none of the three is built in parallel with
this one, and whichever lands second carries the rebase.

**What I need you to rule on** — both are already ruled by OD-8, and are here
because they cost you something. **The stale cache:** the signal reaches only
videos fetched after this lands, and recovering the measured case now means
deleting `data/transcripts/` and re-running `fetch`. **Whole-description
matching:** if the first run shows boilerplate admitting the channel wholesale,
narrowing it (hashtags only, vendors excluded) is a fresh ruling on that
evidence, not a change to make here.

## Uncertainties

**None: every decision derived from the design.** R1004 fixes the behaviour at
both ends of the field and answers the three questions that would otherwise have
been guesses — where a pre-existing cache entry stands ("simply has no
description signal — never an error, and no forced refetch"), what a description
hit counts as ("an automatic include, like a title hit"), and what happens when
the description is the only signal on a video with no captions ("the failure
ledger still governs"). Nothing is filed to `docs/BACKLOG.md` by this plan.

### Derivations, not uncertainties

Each is a place the design layer fixes the behaviour and leaves the mechanism
to the plan. Recorded so a reader sees the derivation rather than a decision
appearing from nowhere.

- **The description lives in the transcript cache record.** Three grounds, in
  order of weight. (1) R1004's "A video cached before descriptions were
  recorded simply has no description signal" ties the field's presence to a
  cache entry's vintage, which is a property of the record, not of the video.
  (2) The fetch stage's only durable output on success is that record — the
  ledger records failures — so recording "at the fetch boundary" (OD-8's own
  phrase) has one home that costs no new artifact. (3) R1004 accepts losing the
  description exactly when there is no transcript, which is precisely what
  storing it beside the cues does. The alternative, a `data/descriptions/`
  artifact, would keep a no-caption video's description — the one case R1004
  hands back to the failure ledger — at the price of a second file per video, a
  second reader, and a second thing to keep deterministic.
- **`Transcript` gains the field rather than `select_video` gaining a
  parameter.** Everything that already loads a cache entry then sees the
  description, and `select_video`'s signature — the contract two blind authors
  share — is unchanged. The field is last and defaults to `""`, so every
  existing construction, positional ones included, still compiles. The tension
  is real and worth naming: §9's Transcript is "video id, ordered cues … plus
  the normalized form used for matching", and a description is none of those.
  §9's Video would be the better home by entity, and cannot be one by
  sequencing — `data/index.jsonl` is written by a stage that runs before any
  description exists.
- **The boundary function is renamed.** A function returning a description is
  not `fetch_caption_track`, and this name is not incidental: it is the one
  surface the tests are permitted to fake, so it is read as a contract. Renamed
  once, in the slice that changes what it returns.
- **The new reason lives on `Selection`, not on `Video`.** R1004's measurement
  clause names "the inclusion reason in the index (R1/§9)"; §9's four inclusion
  reasons (title hit, threshold pass, excluded, transcript unavailable) are
  selection outcomes, and the built system implements them as `Selection.reason`
  in `data/selected.jsonl`, while `Video.inclusion` carries the index stage's own
  three values. The index file cannot carry this reason at all: it is written
  before `fetch`, so at index time no description exists.
- **Title before description before threshold.** R1004 says a description hit is
  an automatic include "like a title hit", which puts it above the threshold;
  the title stays first because it is the stronger signal and because keeping it
  first leaves every existing title-hit count untouched by this change.
- **"How many videos the signal added" is computed, not inferred from the
  reason.** Once two rules can fire on one video, the count of description-hit
  records overstates what the signal added by however many of them the threshold
  would have admitted anyway. Both numbers are cheap — `distinct_canonicals` is
  already on every record — so the report carries the honest one beside the raw
  one rather than choosing which lie to tell.
- **A description hit yields no mentions.** `Mention` carries `start_seconds`,
  R5 cuts every excerpt window from it and R14's links are built on it. A
  description has no cue, so a description-derived mention would have to invent
  that number. A selected video with no body mentions therefore yields no
  excerpts — the same shape a title hit with no body mentions already has today,
  and not a property this plan introduces.
- **The description is matched as one normalized string.** `normalize` collapses
  newlines with all other whitespace, and a leading `#` is not alphanumeric, so
  `#B850` lands as `#b850` and the matcher's `(?<![a-z0-9])` boundary is
  satisfied — BL-11's measured case works with no hashtag-specific rule. Nothing
  is truncated: one linear scan over text already in memory, offline, no spend.

## The work, sliced

Two, and each is observable on its own: slice 1 is a field on disk after a
fetch, slice 2 is a video in the corpus that was not there before. **Sequential**
— slice 2 decides on what slice 1 records — so slice 2 is built after slice 1
has landed, not beside it. A third slice would be horizontal: a rule with
nothing observing it, then the observation.

## Slice 1 — The fetch stage stops throwing the description away

- **Delivers:** after `find-best-mobo fetch`, each newly cached
  `data/transcripts/<video_id>.json` carries the video's description text
  alongside its cues, taken from the same per-video extraction that fetched the
  captions — no additional request, and the one-client-per-run property is
  unchanged. A cache file written before this slice still loads, with an empty
  description and no refetch. A video with no caption track is still a ledger
  row and caches nothing. Covers R1004 in part.
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
is new and lives in `src/find_best_mobo/ytdlp.py`, because it is what the network
boundary returns and nothing above the boundary constructs one; `Transcript` and
`Cue` stay in `src/find_best_mobo/transcripts.py`; `Video` in
`src/find_best_mobo/index.py`; `FetchFailure` and `HaltTriggered` in
`src/find_best_mobo/ledger.py` (`transcripts.py` keeps today's re-export).
`NoCaptions` stays in `src/find_best_mobo/transcripts.py`. `fetch_all`,
`cache_path` and `parse_vtt` keep the signatures they have; `fetch_transcript`
and `load_cached` are listed only to say that theirs do not change.

### Behaviour the signatures cannot carry

- **`fetch_video` replaces `fetch_caption_track` and is the same call.** One
  `extract_info` on the watch URL, on the same lazily-built shared client, then
  the same caption-track selection. `VideoFetch.captions` is exactly what
  `fetch_caption_track` returned — the raw WebVTT, or `None` when the video
  offers no English track — and everything that goes wrong reaching YouTube
  still raises rather than returning a value.
- **`VideoFetch.description` is a plain string, never `None`.** A missing key, a
  null, or a non-string in the extraction result all become `""`. The
  description is taken verbatim: no stripping, no truncation, no parsing of
  hashtags or links. Whatever normalization matching needs is matching's
  business, one stage later.
- **`fetch_transcript` carries it onto the `Transcript`.** `NoCaptions` is still
  raised when `captions is None`, before the description is used for anything —
  R1004: a description cannot conjure a transcript, and the failure ledger
  governs that video.
- **The cache record gains one key.** `_write_cache` writes `description`
  alongside `video_id` and `cues`, still `sort_keys=True`, still one trailing
  newline: two runs over the same video produce byte-identical files (R23).
- **`load_cached` must tolerate a record with no `description` key**, defaulting
  it to `""`. This is the single most important line in the slice: today a
  `KeyError` is caught and read as "no usable cache entry", so a strict read
  would silently invalidate every cache entry the owner already has and refetch
  the whole corpus — the opposite of R1004's "no forced refetch". A record whose
  `description` is present but not a string is coerced with `str`, matching how
  `video_id` is already read.
- **Nothing backfills.** `fetch_all` still skips a video whose cache entry
  exists, so an old entry is never refetched to acquire a description. R1004
  states this outcome; the mechanism is the cache-hit skip that already exists,
  and no code is added to preserve it.
- **`data/transcripts/` stays local-only** (R21). A description is corpus like
  the cues are: never redistributed, never committed.
- **What the tests must pin:** a fetch whose extraction carries a description
  writes it into the cache file and back out of `load_cached`; a fetch whose
  extraction carries none yields `""` rather than failing; a cache file written
  in the pre-slice shape (`video_id` and `cues` only) still loads, with `""`, and
  `fetch_all` still skips it; a video with no caption track writes no cache file
  and lands in the ledger as `no_captions`, description or not; the
  one-client-per-run assertion in `tests/test_ytdlp_client_reuse.py` holds
  against `fetch_video`; and the cache file is byte-identical across two runs.
- **`docs/architecture.md`**: the network-boundary and transcript rows in the
  components table say the per-video extraction yields captions *and* the
  description; "Fetching transcripts" gains the description as part of step 3;
  the `data/transcripts/<video_id>.json` entry under "State and storage" says
  the record carries the description and that entries written before this
  change simply do not, citing OD-8/R1004 so the next agent reads the empty
  field as a decision rather than a bug.

## Slice 2 — A board named only in the description brings its video in

- **Delivers:** `find-best-mobo select` includes a video whose description names
  a board — BL-11's `#AMD #ryzen #MSI #B850 #ITX` is the measured case — where
  its title and body name none, recording it in `data/selected.jsonl` under the
  reason `description_hit`. The printed report says how many videos came in that
  way and how many of them nothing else would have admitted. A video whose title
  also hits stays a `title_hit`; a cache entry with no description behaves
  exactly as it does today. Covers R1004.
- **Files:** `src/find_best_mobo/aliases.py`, `src/find_best_mobo/select.py`, `src/find_best_mobo/commands/select.py`, `tests/test_select.py`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~190 lines

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
matching stage over the same compiled pattern and it must reach the same private
canonical-recovery helper. It takes the description as a plain `str` rather than
a `Transcript`, so it is testable without a cache entry and does not tie the
alias module to where the field happens to be stored. `DESCRIPTION_HIT`,
`Selection` and `ThresholdReport` stay in `src/find_best_mobo/select.py` with
`TITLE_HIT`, `THRESHOLD` and `EXCLUDED`; `Mention` and `Alias` in
`src/find_best_mobo/aliases.py`; `Transcript` and `Cue` in
`src/find_best_mobo/transcripts.py`; `Video` in `src/find_best_mobo/index.py`.
`select_video`, `select_all`, `threshold_report`, `write_selected` and
`read_selected` keep the signatures they have — `select_video` reads the
description off the `Transcript` it is already given, which is why slice 1 put
it there.

### Behaviour the signatures cannot carry

- **`find_description_hits` is `find_title_hits` over another string**: the
  canonicals whose forms the matcher finds in `normalize(description)`, as a
  frozenset, empty for an empty description. Pure, total, no I/O.
- **The order in `select_video` is title, description, threshold, excluded.**
  A title hit is still decided first and its record is unchanged. Otherwise a
  non-empty description-hit set is `DESCRIPTION_HIT`. Otherwise the distinct
  count against the threshold, exactly as today.
- **`mentions` and `distinct_canonicals` are computed exactly as today** — body
  mentions, in cue order — for every reason including `description_hit`. No
  `Mention` is ever constructed from a description, and no `start_seconds` is
  invented. A reviewer should check this as the load-bearing negative of the
  slice.
- **`threshold_report` counts both numbers.** `description_hits` is the count of
  `DESCRIPTION_HIT` selections. `description_only_includes` is how many of those
  have `distinct_canonicals < threshold` — the videos no other rule would have
  admitted, which is R1004's "how many videos the signal added". The two are
  equal only when no description-hit video also passes the threshold.
- **The what-if deltas are unchanged in definition and shift in value.**
  `would_include_at_minus_one` still counts excluded videos, and
  `would_exclude_at_plus_one` still counts threshold passes — but a video that
  used to be a threshold pass and now reads `description_hit` has left that
  population, which is correct: the threshold no longer decides it.
- **`_print_report` prints two new lines, always, zero included**, after the
  title-hit line and before the total, because a count that prints only when it
  fired cannot be told from one that never ran:
  `  N videos included on a description hit` and
  `  M of them would not have been selected any other way`. The `selected` total
  becomes title hits plus description hits plus threshold passes, and the
  closing sentence of the raise-the-threshold line becomes "Title and
  description hits are unaffected either way."
- **`selected.jsonl` gains no field.** The new value appears in the existing
  `reason` string; the description text itself is not copied into the record —
  it is already on disk in the cache, it can be long, and nothing downstream
  reads it. `read_selected` needs no change and still reads records written
  before this slice.
- **What the tests must pin**, through the real `select_all` path against a
  table and cache entries written into `tmp_path` as `tests/test_select.py`
  already does:
  - **The BL-11 regression.** A video whose title and cues name no canonical,
    and whose cached description is the measured hashtag line
    `#AMD #ryzen #MSI #B850 #ITX`, is selected with reason `description_hit` and
    appears in both new counts. The same video with the description removed from
    its cache entry is excluded — which is the state of the world before this
    plan, and the demonstration that the description is what admitted it.
  - **Precedence.** A video hitting on both title and description is a
    `title_hit`, and is counted in neither new number. A video hitting on the
    description that also reaches the threshold is a `description_hit`, counted
    in `description_hits` and **not** in `description_only_includes`.
  - **No mentions are conjured.** A description-hit video whose body names
    nothing has `mentions == ()` and `distinct_canonicals == 0`, and its
    `selected.jsonl` record carries no mention.
  - **Nothing else moves.** A corpus with no descriptions at all produces the
    same selections, the same record shapes and the same report as before, with
    both new lines reading zero.
  - **The printed report** is asserted for a corpus with a description hit and
    for one without, including the "Title and description hits are unaffected"
    wording, so the checkpoint's own output is pinned rather than assumed.
  - In `tests/test_aliases.py`, `find_description_hits` directly: the hashtag
    form `#b850`, a plain sentence naming a board, a multi-line description
    where the name sits on its own line, an empty string, and a fused token
    (`theb850`) that must yield nothing — the boundary rule is not relaxed for
    descriptions.
- **`docs/architecture.md`**: "Narrowing the corpus" gains the description rule
  as a numbered step between the title rule and the threshold, with the reason
  hashtags are strong evidence and the note that a description hit adds no
  mentions; the selection row in the components table and the
  `data/selected.jsonl` entry under "State and storage" name the new reason;
  and "Known rough edges" records that the signal is absent from every cache
  entry written before this change, with the operator action (delete the entry
  and refetch) stated once, citing OD-8/R1004.

## Out of scope

- **Backfilling descriptions into existing cache entries**, and any flag that
  would. R1004 rules out a forced refetch; deleting a cache file and re-running
  `fetch` is the deliberate path and is documented in `docs/architecture.md`
  rather than automated. A `--refresh` flag would also need OD-10/R1006's
  dispatcher forwarding, which is not built.
- **Keeping the description of a video with no caption track.** R1004 hands that
  video to the failure ledger; storing its description would mean a second
  artifact for a video that can never be excerpted.
- **Description mentions counting toward the mention threshold**, or appearing
  in `data/selected.jsonl` as `Mention`s. R1004 makes a description hit an
  include, not evidence with a timestamp.
- **Narrowing what counts as a description hit** — hashtags only, or ignoring
  links and boilerplate. R1004 says "a normalized alias hit in the description".
  If the first real run's `description_hits` shows boilerplate admitting the
  channel wholesale, that is logged evidence for a `BL-<n>`, not a narrowing
  taken here.
- **Description forms in the `aliases --check` recall report.** OD-8's stated
  measurement is the inclusion reason and R4's selection report; the recall
  report reads cached transcripts and is left reading bodies only.
- **`data/index.jsonl`.** The index stage runs before any description exists;
  the new reason lives where the other three selection reasons already live.
- **OD-11/R1007's move of the alias table** and the configured-path loading with
  it. This plan reads the table wherever `select_all` reads it today.
- **Revising `docs/plans/corpus-and-checkpoint.md`.** Its slice 2 Signatures
  block names `fetch_caption_track`, which will not exist once this lands. That
  plan sits behind `CODEOWNERS` and **OD-12** already commissions its revision;
  this rename rides it alongside `caption-split-aliases`'s and
  `itx-chipset-variant`'s additions.
