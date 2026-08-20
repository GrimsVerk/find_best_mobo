---
slug: caption-split-aliases
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1002, R1010]
---

# An alias split across caption tokens still matches — Plan

Implements **OD-6** (`docs/DESIGN.oracle.md`), which adds **R1002** from the
evidence in **BL-8**, together with **OD-15**, which adds **R1010** and rules
the scope question BL-16 filed. Auto-captions split product names across tokens
and the shipped matcher is blind to the result: measured offline against the
shipped table, `toma hawk`, `aor us master` and `air us elite` matched nothing
at all — silent losses in the corpus every later stage is built from. OD-15
fixes the text the join rule runs over: **one cue at a time**, with the
cue-spanning case counted rather than matched.

This plan is re-cut from `docs/oracle/od-6-plan-draft.md` — the draft the review
gate blocked for self-ruling on BL-16 — used as raw material, not as authority,
exactly as that file's header instructs.

## Summary

Two mechanical changes to the space the matcher works in, BL-8's measured
variants as a fixture, and the boundary counter OD-15 requires so the case it
scoped out is measured instead of assumed.

- **The hyphen stops being a kept character.** `normalize` folds it to a space,
  so `steel-legend` meets the table's `steel legend`. Two shipped `normalize`
  tests assert the retired rule and are rewritten. Only hyphens fold.
- **Each surface form compiles to a pattern with an optional space between
  adjacent characters and a required space where the form has one** —
  `tomahawk` matches `toma hawk`, `aorus master` matches `aor us master`. Still
  one compiled pattern, longest form first, so R22 and R23 are untouched.
- **A fused token is never matched into.** `b650` is not in `theb650`, and
  `aorus master` does not match `aorusmaster`: R1002 makes the alias's own space
  require a real token boundary. Pinned as negative cases.
- **A split across a cue boundary is counted, never matched (R1010).**
  `find_mentions` keeps its one-cue-at-a-time shape, so every mention's
  `start_seconds` stays the start of the one cue holding it. A new per-video
  count of matches that exist only across an adjacent-cue join rides `Selection`
  into the threshold report and prints on every run, zero included.
- **`Selection` and `selected.jsonl` gain one integer field.** A record written
  before this plan reads back as 0 rather than failing — no refetch, no
  re-select.
- **The table gains `airus elite`, and loses `pro-rs`.** `air us` for `aorus` is
  a mishearing no join recovers; `pro-rs` folds onto the `pro rs` beside it
  after slice 1, so it becomes a line the matcher can never use. **Departing
  from the draft:** `airus master` is *not* added — R1002 says the table gains
  the *observed* spoken forms and only the Elite spelling was ever heard.
- **The 52-variant set is reconstructed, not recovered** — BL-8's list was never
  committed. Filed as **BL-17**, proceeding on the default.
- **The measurement is R4's selection counts and the selection report**, as OD-6
  and OD-15 name: both already land in `docs/runs/`; no new collection mechanism.
- **Not done here:** OD-7/R1003's ITX rule, OD-11/R1007's table move,
  OD-8/R1004's descriptions, and cross-cue *matching* of any kind.

Four slices, ~670 lines, **sequential**. One open uncertainty, LOW, filed as
BL-17 and proceeded on.

**What I need you to rule on:**

1. **The reconstructed 52 (BL-17).** R1002 asks for BL-8's set by that number
   and the set is not in the repository. If a fixture of the observed failures
   alone is honester, slice 3 shrinks to those.
2. **`airus master`.** The draft would have added it beside `airus elite`; I
   read R1002 as authorising only observed forms. Adding it later is one line
   of data.
3. **Merge order.** OD-7 edits the same matcher and OD-11 moves the same table
   file. Whichever lands second carries the rebase.

## Uncertainties

One, LOW, filed and proceeded on. The question that stopped the previous
attempt is now ruled, and is recorded here with its ids rather than re-argued.

- **Q:** What are BL-8's 52 variants? The backlog entry records the count, the
  three failures and the damage classes, not the list; nothing in the tree, the
  journal or `docs/runs/` holds it. — **risk:** LOW — fixture content; no
  signature, slice boundary or external format turns on it. — **proposed:**
  reconstruct 52 from the shipped table's own canonicals across BL-8's damage
  classes, with the named failures verbatim, and say in the fixture that it is
  a reconstruction.
  **Ruling:** proceeded on the default (LOW), filed as **BL-17** under
  "Uncertainties awaiting oracle ruling" in the same commit as this plan. Two
  facts the reviewer should see: BL-8's arithmetic (49 matched + 3 failures =
  52) leaves no room for the hyphenated `steel-legend` it also reports failing,
  and the draft's reconstruction had five failing variants rather than three.

- **Q (ruled, recorded):** Does the join rule have to recover an alias split
  across a **cue boundary**? — **HIGH**, filed by the previous steward as
  **BL-16**. **Ruling: OD-15 / R1010.** No: the rule applies within one cue's
  normalized text, no mention is ever synthesized across a boundary, and every
  mention's `start_seconds` is the start of the single cue containing it. The
  scoped-out case is detected and counted per run in the selection report, and
  never emitted. Slice 4 is that counter.

### Derivations, not uncertainties

Recorded because each is a place the design hands the choice to the plan, and a
reader should see the derivation rather than a decision appearing from nowhere.

- **What text the counter joins.** R1010 says "the normalized concatenation of
  adjacent cues". Resolved as `normalize(a.text) + " " + normalize(b.text)`, not
  `normalize(a.text + " " + b.text)`: the first leaves the boundary at a known
  offset, so "starts in one cue's text and ends in the next's" is exactly
  decidable, and it still catches spacing damage across the break (`x 670` |
  `e board` → `x670 e board`, which slice 2's rule matches as `x670e`). The
  second fuses tokens across the boundary and makes the attribution a guess.
- **Where the count is carried.** R1010 fixes the observable — a per-run count
  in the selection report — and leaves the mechanism to the plan. `select_all`
  loads and releases one transcript at a time (R22), so the count must be taken
  inside that loop, and `Selection` is the only thing that survives it. Carrying
  it per video is also what lets the first real run say *which* videos the
  scoped-out case costs, which is the evidence OD-15 says would supersede it.
- **Which report.** The selection report only. R1010 names it; the
  `aliases --check` recall report is R1002's measurement and gains nothing here.
- **What is counted.** Matches, per adjacent-pair occurrence, not distinct
  canonicals and not videos — R1010 says "the count". A canonical found
  elsewhere in the same video does not suppress it.
- **Which path the table edits go to.** `data/aliases.toml`, where the table
  lives today. OD-11/R1007 moves it and re-homes the loaders; that is its plan's
  work and this content rides along.
- **The required-space reading** of "every space inside the alias aligns with a
  token boundary", and the **hyphen-only fold** (R1002 names hyphens and nothing
  else). Both are R1002 read literally.
- **One regex per form over a token-scanning matcher.** R22 and R23 both point
  at the single compiled pattern the built system already has.

## The work, sliced

Four, and they are **sequential**: slice 2's join rule is stated over the space
slice 1 produces, slice 3's variant set is green only once both have landed, and
slice 4's counter scans with the pattern slice 2 compiles. They share files for
that reason, which is safe because none of them runs beside another.

## Slice 1 — A hyphen no longer hides a family name

- **Delivers:** `steel-legend` in a caption or a title matches the table's
  `Steel Legend`, and `x670e-plus` still matches `X670E`. Observable in
  `find-best-mobo aliases --check`, where the hyphenated spelling appears in a
  canonical's `forms:` list instead of being absent. Covers R1002 in part.
- **Files:** `src/find_best_mobo/normalize.py`, `tests/test_normalize.py`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~70 lines

### Signatures

```python
def normalize(text: str) -> str: ...
```

Unchanged, and deliberately: this is a behaviour change inside a pure function
every caller already routes through. Nothing else in the module is public, and
per **OD-12** there is no shared type to place — `src/find_best_mobo/normalize.py`
defines none and this slice adds none.

### Behaviour the signature cannot carry

- **A hyphen becomes a space** during cleaning, before the joining pass —
  `normalize("steel-legend") == "steel legend"`, `normalize("The X670E-PLUS
  board") == "the x670e plus board"`.
- **The joining rule is unaffected.** `x-670-e` still folds to `x670e`: the
  hyphen was already a member of `_SEPARATORS`, so a gap that joined before
  joins now. `_SEPARATORS` collapses to a single space and can be simplified or
  removed at the coder's discretion, provided the fold cases here hold.
- **`normalize` stays pure, total and idempotent.** `normalize("")` is `""`, it
  never raises, and `normalize(normalize(t)) == normalize(t)` — the existing
  property tests hold unchanged and are the reason to state it.
- **The two tests that assert the retired rule are rewritten**, not deleted:
  `test_hyphen_survives_as_a_character` and
  `test_hyphenated_model_name_is_left_intact` become the assertions above, and
  the commit message says why (`AGENTS.md`, blind-tests rule — an edit to a test
  is allowed and must be visible).
- **The module docstring is now false and is corrected here.** It states "a
  hyphen is KEPT as a character" as the one rule worth stating twice; it becomes
  the fold rule, citing OD-6.
- **`tests/test_aliases.py` is listed only as a contingency.** The hyphen cases
  there (`the b650e-plus board`, the `X870E-Nova` surface form) normalize on both
  sides and are expected to pass untouched; if one does not, correcting it
  belongs to this slice with the reason stated.
- **`docs/architecture.md`**'s normalization row in the components table gains
  the fold, citing OD-6.

## Slice 2 — A name the captions split in half is still one name

- **Delivers:** `mag tomahawk` matches `the mag toma hawk vrm`, `aorus master`
  matches `aor us master`, and `b650` still finds nothing in `theb650`. The
  `aliases --check` report shows the split spelling as the form that fired, and
  R4's selection counts move for every video whose only mentions were split.
  Covers R1002.
- **Files:** `src/find_best_mobo/aliases.py`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~220 lines

### Signatures

```python
def alias_pattern(form: str) -> str: ...
def compile_matcher(aliases: Sequence[Alias]) -> re.Pattern[str]: ...
```

`alias_pattern` is new and public, in `src/find_best_mobo/aliases.py` alongside
`compile_matcher`, so the rule has a unit the tests can reach without asserting
on the shape of the whole table's pattern. `load_aliases`, `find_mentions` and
`find_title_hits` keep the signatures they have.

Per **OD-12**, the module of every shared type this slice touches, none of which
changes shape: `Alias` and `Mention` in `src/find_best_mobo/aliases.py`;
`Transcript` and `Cue` in `src/find_best_mobo/transcripts.py`; `Video` in
`src/find_best_mobo/index.py`.

### Behaviour the signatures cannot carry

- **`alias_pattern` takes an already-normalized form** and returns regex source
  for it — no group wrapper, no lookarounds, both of which stay
  `compile_matcher`'s. Between every pair of adjacent characters inside one word
  of the form it emits an optional single space; where the form itself has a
  space it emits a required single space. Every literal character goes through
  `re.escape`.
- **`alias_pattern("")` raises `ValueError`.** `compile_matcher` already drops
  forms that normalize to empty, so it is unreachable from there; an empty
  pattern would match at every position, which is the failure worth naming.
- **Tests exercise it by compiling and matching, never by string equality with
  the regex source.** The source is an implementation detail; the language it
  accepts is the contract.
- **What must match**, over normalized text: `toma hawk` → `MAG Tomahawk`;
  `aor us master` → `Aorus Master`; `tom a hawk` → `MAG Tomahawk` (a split may
  fall anywhere); `steel leg end` → `Steel Legend` (the alias's space lands on
  the boundary between `steel` and `leg`); and every form that matched before,
  unchanged.
- **What must not match:** `theb650` and `xb650e` (the alias would start inside a
  token); `b650ex` and `x870ese` (it would end inside one); `aorusmaster` and
  `steellegend` (the alias's own space has no boundary to land on); `verb 650`
  (`b650` would start mid-token). These are R1002's "never a proper substring of
  a fused token", and they are the assertions that make the rule safe rather than
  merely wide.
- **Longest-form-first is unchanged**, and still sorts on the length of the
  *normalized form*, not of its pattern — a stable sort on negated length, file
  order among equals. `mag tomahawk` therefore still wins over `tomahawk` at the
  same position, and the compiled pattern stays byte-identical for a given table
  (R23).
- **`matched_form` stays `match.group(0)`** — the text as the caption spelled it,
  so `aliases --check` reports `toma hawk` as the spelling that did the work.
  That report is R1002's stated measurement; it only measures anything if the
  split form survives into it.
- **Global de-duplication is unchanged.** Two canonicals claiming one normalized
  form still resolve to the first declared, and the loser still surfaces as a
  zero-match canonical in the report.
- **A form's own spaces are single spaces.** Normalized text has no runs and no
  tabs, so the pattern needs no `+` and gains none — one more thing that cannot
  drift between two runs.
- **`docs/architecture.md`**'s "Inspecting the alias table" section gains the
  join rule beside the longest-first rule, and the alias-table component row says
  the pattern tolerates caption splits, citing OD-6.

## Slice 3 — The measured recall is pinned, and a split-spelled video is selected

- **Delivers:** a fixture of the 52 mangled spellings BL-8 tested, each with the
  canonical it must reach, run against the shipped table; every one matches, the
  `air us` mishearing because the table now carries it. And the end of the path
  OD-6 names as its measurement: a video titled with a split form is selected on
  its title hit, and one whose only body evidence is split spellings passes the
  mention threshold instead of being excluded. Covers R1002.
- **Files:** `tests/fixtures/caption_variants.json`, `tests/test_aliases.py`, `tests/test_select.py`, `data/aliases.toml`, `docs/architecture.md`
- **Estimate:** ~200 lines

### The fixture

`tests/fixtures/caption_variants.json`, one object:

```json
{
  "note": "Reconstructed from BL-8 (OD-6/R1002); see docs/plans/oracle/caption-split-aliases.md",
  "variants": [{"text": "toma hawk", "canonical": "MAG Tomahawk", "damage": "split"}],
  "never_match": ["theb650"]
}
```

`damage` is one of `spacing`, `digit-split`, `hyphen`, `split`, `spelled-out`,
`mishearing`, `plural`, `partial` — descriptive, not asserted on, and there so a
future reader can tell which class a regression belongs to.

**The 52 variants, verbatim.** Each is matched inside a carrier sentence (`the
<text> board`) as well as bare, so a match at a text boundary and a match
mid-sentence are both covered. `†` marks the five the draft recorded as failing
against the shipped table (unverified in this planning session — the fixture
author confirms them by running the suite before the fix, which is the point of
the slice).

Chipsets (15): `x 870 e`→X870E, `x870 e`→X870E, `x-870-e`→X870E,
`x 8 70 e`→X870E, `x 870`→X870, `b 850`→B850, `b 840`→B840, `x 670 e`→X670E,
`x 6 70 e`→X670E, `670 e`→X670E, `x 670`→X670, `b 650 e`→B650E,
`b650 e`→B650E, `b 650`→B650, `a 620`→A620.

Vendors (10): `as rock`→ASRock, `az rock`→ASRock, `ass rock`→ASRock,
`as-rock`†→ASRock, `a sus`→ASUS, `assus`→ASUS, `giga byte`→Gigabyte,
`m s i`→MSI, `em es eye`→MSI, `bio star`→Biostar.

Families (22): `tai chi`→Taichi, `ty chi`→Taichi, `steel legends`→Steel Legend,
`steal legend`→Steel Legend, `steel-legend`†→Steel Legend,
`cross hair`→ROG Crosshair, `r o g crosshair`→ROG Crosshair, `stryx`→ROG Strix,
`r o g strix`→ROG Strix, `tough gaming`→TUF Gaming, `orus master`→Aorus Master,
`aorus masters`→Aorus Master, `aor us master`†→Aorus Master,
`orus elite`→Aorus Elite, `air us elite`†→Aorus Elite,
`m p g carbon`→MPG Carbon, `carbon wifi`→MPG Carbon,
`m a g tomahawk`→MAG Tomahawk, `tomohawk`→MAG Tomahawk, `toma hawk`†→MAG
Tomahawk, `pro r s`→Pro RS, `pro-rs`→Pro RS.

CPUs (5): `7800 x 3 d`→7800X3D, `78 00 x 3 d`→7800X3D, `9800 x 3 d`→9800X3D,
`9950 x 3 d`→9950X3D, `7950 x`→7950X.

`never_match` (6): `theb650`, `verb 650 watts`, `steellegend`, `aorusmaster`,
`x870ese`, `b650ex` — none of them may produce any mention at all, not merely
not the obvious one.

### Assertions

- every variant's canonical is in `find_title_hits` for a video titled with the
  carrier sentence, and in `find_mentions` for a single cue holding it;
- `len(variants) >= 52`, with the count's provenance in the test's docstring — a
  later addition is welcome, a loss is a regression;
- the five marked failures are present by exact text, so no future tidy-up can
  drop the cases the evidence was written about;
- nothing in `never_match` yields a mention against the shipped table.

### The selection effect

In `tests/test_select.py`, against a table and transcripts written into
`tmp_path` as that module already does:

- a video titled `MSI MAG toma hawk MAX WIFI review` is selected with the
  title-hit reason, where the same video is excluded before this plan;
- a video whose body spells three distinct canonicals only in split forms passes
  the mention threshold and is counted as a threshold pass rather than an
  exclusion in the selection report.

These are the counts OD-6 names as the measurement. Nothing here changes
`select.py`; the slice asserts that the matcher change reaches the number the
checkpoint is spent against.

### The table changes

`Aorus Elite` gains `airus elite`. Under slice 2's rule that one form covers
`air us elite`, `airus elite` and (after slice 1) `air-us elite`, so the split
spelling needs no second entry. `air us` for `aorus` is the mishearing BL-8
observed, and R1002 leaves exactly that class to the table. `Aorus Master` gains
nothing: `air us master` was never heard, and the table is the owner's to extend
from the recall report.

`Pro RS` loses `pro-rs`, and it is the only removal: after slice 1 it normalizes
to the `pro rs` sitting beside it, and global de-duplication drops the second
claimant silently. A line the matcher can never use is worse than absent — it
reads as coverage. The variant `pro-rs` stays in the fixture and still matches,
through `pro rs`. Every other form the join rule makes redundant — `cross hair`,
`giga byte`, `tai chi`, `bio star`, `a 620` — **stays**: those are distinct
normalized forms that still fire on their own, and deleting them would move
`aliases --check`'s per-form counts for reasons unrelated to this change.

`docs/architecture.md` needs no new flow here; the alias-table row already says
the table is hand-authored input.

## Slice 4 — A split the captions broke across two cues is counted, not lost

- **Delivers:** `find-best-mobo select` prints, on every run and including zero,
  how many alias matches existed only across an adjacent-cue join and were
  therefore not counted as mentions. `data/selected.jsonl` carries the count per
  video, so the first real corpus run says which videos the scoping costs.
  `find_mentions` is unchanged: no mention is ever synthesized across a cue
  boundary, and every mention's `start_seconds` is still the start of the one cue
  holding it. Covers R1010.
- **Files:** `src/find_best_mobo/aliases.py`, `src/find_best_mobo/select.py`, `src/find_best_mobo/commands/select.py`, `tests/test_aliases.py`, `tests/test_select.py`, `docs/architecture.md`
- **Estimate:** ~180 lines

### Signatures

```python
@dataclass(frozen=True)
class Selection:
    video: Video
    reason: str  # "title_hit" | "threshold" | "excluded_below_threshold"
    mentions: tuple[Mention, ...]
    distinct_canonicals: int
    cross_cue_candidates: int = 0


@dataclass(frozen=True)
class ThresholdReport:
    threshold: int
    title_hits: int
    threshold_passes: int
    excluded: int
    would_include_at_minus_one: int
    would_exclude_at_plus_one: int
    cross_cue_candidates: int


def count_cross_cue_candidates(transcript: Transcript, matcher: re.Pattern[str]) -> int: ...
```

`select_video`, `select_all`, `threshold_report`, `write_selected` and
`read_selected` keep the signatures they have; only the two records above gain a
field. Per **OD-12**: `count_cross_cue_candidates` lives in
`src/find_best_mobo/aliases.py`, beside `find_mentions`, because it is the same
matching stage R1010 assigns the detection to and it shares the normalization
rule; `Selection` and `ThresholdReport` stay in `src/find_best_mobo/select.py`;
`Transcript` and `Cue` in `src/find_best_mobo/transcripts.py`; `Mention` and
`Alias` in `src/find_best_mobo/aliases.py`; `Video` in
`src/find_best_mobo/index.py`.

`Selection.cross_cue_candidates` defaults to 0 for two reasons, both stated so
the default is not read as laziness: a video with no cached transcript genuinely
has none, and `read_selected` must be able to read a record written before this
slice without failing.

### Behaviour the signatures cannot carry

- **The join is per adjacent pair, in cue order:** for each `(cues[i],
  cues[i + 1])`, the scanned text is `normalize(a.text) + " " +
  normalize(b.text)`. A pair where either side normalizes to empty is skipped, and
  a transcript with fewer than two cues is 0. Adjacency is list order; a silent
  gap between two cues does not disqualify a pair, because R1010 says adjacent
  cues and nothing about time.
- **A match counts only if it spans the join.** With `boundary = len(norm_a)`, a
  match counts when `match.start() < boundary and match.end() > boundary + 1` —
  a match ending at or before the boundary lies wholly in the first cue and one
  starting after the separator lies wholly in the second, and both are already
  the matcher's business.
- **Nothing is ever emitted.** `find_mentions` is not touched by this slice, no
  `Mention` is constructed here, and no `start_seconds` is invented. This is the
  whole of OD-15's scoping and the reviewer should check it as such.
- **The count is a floor, not a certified total**, and the docstring says so: the
  scan is one left-to-right non-overlapping `finditer`, so a match lying wholly
  inside the first cue can consume characters a crossing match would have used.
  R1010 asks for an observable that tells a zero from a material number; "at
  least N" does that and a certified total would cost an overlapping scan for no
  decision it would change.
- **Pure, offline, deterministic, and one transcript at a time.** No I/O, no
  clock, no token spend — one extra linear scan per adjacent pair over text
  already in memory, inside the loop that already loads and releases one
  transcript (R22). Two runs over one cache print identically (R23).
- **`select_video` fills the field** from the transcript it already has; it
  changes no decision — reason, mentions and `distinct_canonicals` are computed
  exactly as today, and a video is never selected or excluded because of this
  count.
- **`threshold_report` sums it** across the selections it is given.
- **`_print_report` prints one line, always, zero included**, after the
  in/out counts and before the what-if lines — a line the run report captures
  whether or not it fired, because a counter that prints only when non-zero
  cannot be told from a counter that was never run:
  `  N alias matches spanned a cue boundary and were NOT counted as mentions`,
  with the reason stated in the same line or the one below it.
- **`read_selected` defaults a missing key to 0**; `write_selected` writes the
  field, which `_record`'s `asdict` picks up with no change.
- **The distinguishing pair R1010 demands**, in `tests/test_select.py` and
  `tests/test_aliases.py`: a transcript whose cues are `("the mag toma", "hawk
  has a twelve phase vrm")` yields **no** `MAG Tomahawk` mention and increments
  the counter by one; a transcript whose single cue is `"the mag toma hawk has a
  twelve phase vrm"` yields the mention and leaves the counter at zero. The
  `select` command's printed line is asserted for both a zero and a non-zero
  corpus.
- **`docs/architecture.md`**'s "Narrowing the corpus" section gains the counter
  as a numbered step and the report line, and the alias-matching description
  states the within-one-cue scope, citing OD-15 and R1010. The scoped-out case
  is described as counted-not-matched, so the next agent does not read the
  absence of cross-cue matching as an oversight.

## Out of scope

- **Cross-cue *matching* of any kind.** OD-15 rules it out and its handoff says
  so twice: the counter observes the boundary, the matcher does not cross it. If
  a real run's count is material, that is new logged evidence for a future
  ruling — file it, do not build ahead of it.
- **OD-7 / R1003, the ITX variant rule.** A chipset matching `b850i` is a
  different decision with its own requirement, and it lands in the same
  `compile_matcher`. Nothing here relaxes the right boundary, which is the rule
  that decision has to work with.
- **Separators other than the hyphen.** `x670e/plus` and `steel+legend` still
  block a join. R1002 names hyphens; anything wider is a fresh reading of R3.
- **OD-11 / R1007's move of the alias table** to a tracked root path, and the
  configured-path loading that goes with it. This plan edits the table where it
  currently lives.
- **OD-8 / R1004's description matching.** A new field to match against is
  independent of how a form is matched, and the two meet only in the selection
  report.
- **Widening the table beyond the `air us elite` mishearing.** The table is data
  and the owner extends it from the recall report; this plan adds only what
  R1002 names as observed.
- **Any change to `Mention`, `Excerpt`, the index, or the bundle format.**
  Nothing downstream of the matcher sees this change except as more mentions and
  one more integer on a selection record.
- **Revising `docs/plans/corpus-and-checkpoint.md`.** Its slice 3 and 4
  Signatures blocks no longer describe the built matcher and selection records
  once this lands. It is a plan behind `CODEOWNERS`, revised on its own pull
  request — OD-12 already commissions that revision, and these additions can
  ride it.
