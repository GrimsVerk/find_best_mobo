---
slug: caption-split-aliases
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1002]
---

# An alias split across caption tokens still matches — Plan

Implements **OD-6** (`docs/DESIGN.oracle.md`), which adds **R1002** from the
evidence in **BL-8**: auto-captions split product names across tokens, and the
shipped matcher is blind to the result. Measured offline against the shipped
table, `toma hawk`, `aor us master` and `air us elite` matched nothing at all —
silent losses in the corpus every later stage is built from.

**OD-14** fixes this plan's scope: R1002's rule reads over the text handed to
the matcher, which is one cue at a time. A split straddling two cues is
**decided** out of scope, and this plan pins that boundary as a negative case.

## Summary

Two mechanical changes to the space the matcher works in, then BL-8's measured
variant set as a fixture, asserted where OD-6 says to measure it. Three slices,
~495 lines, **sequential**.

- **The hyphen stops being a kept character.** `normalize` folds it to a space,
  so `steel-legend` meets the table's `steel legend`. Only hyphens fold. Two
  shipped `normalize` tests assert the retired rule and are rewritten, visibly,
  with the reason in the commit message.
- **Each surface form compiles to a pattern with an optional space between
  adjacent characters and a required space where the form has one** —
  `tomahawk` matches `toma hawk`, `aorus master` matches `aor us master`. Still
  one compiled pattern, longest form first, so R22 and R23 are untouched.
- **A fused token is never matched into.** `b650` is not found in `theb650`, and
  `aorus master` does not match `aorusmaster`: the alias's own space requires a
  real token boundary. Pinned as negative cases.
- **Cross-cue splits stay unmatched, by decision (OD-14), not by omission.**
  `find_mentions` keeps its signature and its cue-at-a-time scan, and a two-cue
  transcript splitting `toma` / `hawk` is asserted to yield no mention.
- **The table gains `airus elite` and loses `pro-rs`.** `air us` for `aorus` is
  a mishearing no join recovers, and R1002 leaves those to the table — but only
  the *observed* forms, so the unobserved `airus master` is not added. `pro-rs`
  folds onto the `pro rs` beside it after slice 1, becoming a line the matcher
  can never use.
- **The 52-variant set is reconstructed, not recovered** — BL-8's list was never
  committed. This plan enumerates 52 from the shipped table by BL-8's own damage
  classes, with its named failures verbatim, plus a reject set. Five fail today.
- **The measurement is R4's selection counts**, as OD-6 names: a video titled
  with a split form is admitted on its title, and one whose only body evidence
  is split spellings passes the mention threshold. Both are red today.
- **Not done here:** OD-7/R1003's ITX rule, which lands in the same function;
  OD-11/R1007's move of the table; separators other than the hyphen.

**What I need you to rule on:**

1. **The reconstructed 52** — filed as **BL-16** (LOW) and proceeded on. If a
   fixture of only the five observed failures is honester, slice 3 shrinks.
2. **Merge order.** OD-7 edits the same matcher and OD-11 moves the same table
   file. Whichever plan lands second carries the rebase.

## Uncertainties

One filed, one ruled, the rest derived. The derivations are shown rather than
asserted, because the questions that came closest to the line are the ones a
reviewer would otherwise have to reconstruct.

- **Q:** What are BL-8's 52 variants? The backlog entry records the count, the
  three failures and the damage classes — not the list; nothing in the tree, the
  journal or `docs/runs/` holds it. — **risk:** LOW — fixture content; no
  signature, slice boundary or external format turns on it. — **proposed:**
  reconstruct 52 from the shipped table's own canonicals across BL-8's damage
  classes, with the named failures verbatim, and say in the fixture that it is a
  reconstruction.
  **Ruling:** proceeded on the default (LOW), filed as **BL-16** in
  `docs/BACKLOG.md` for the oracle's next cycle. Two facts worth seeing:
  BL-8's arithmetic (49 matched + 3 failures = 52) leaves no room for the
  hyphenated `steel-legend` it also reports failing, and this reconstruction has
  five failing variants, not three or four.

- **Q:** Do splits that straddle two cues have to match?
  **Ruling: OD-14** — no. `find_mentions` keeps its cue-at-a-time scan and its
  signature, a `Mention`'s timestamp stays its cue's start, and the boundary is
  pinned as a negative case in slice 2. This is a decision, not a gap: reversing
  it costs one ledger entry if the recall instrument ever measures a cue-spanning
  miss that cost a video.

Derived, with the citation that decides each:

- **Regex-per-form, not a token-scanning matcher.** OD-6's alternatives choose
  "token-join matching with boundary alignment" as the *behaviour* and leave the
  mechanism open; R22 (a two-hour transcript scanned once) and R23 (a
  byte-identical pattern for a given table) both point at the single compiled
  pattern the built system already has. So the rule lands inside the form's own
  pattern source and nothing above it changes.
- **A required space where the form has one.** R1002: "every space inside the
  alias aligns with a token boundary". An optional space there would let
  `aorusmaster` match, which the same sentence forbids.
- **Only the hyphen folds.** R1002 names hyphens and nothing else; a wider
  separator set is a fresh reading of R3 and is out of scope below.
- **The table gains `airus elite` and not `airus master`.** R1002: the table
  gains "the observed spoken forms". `air us elite` was observed; `air us
  master` was not, and inventing an unobserved form is data this decision does
  not authorise. `aor us master` needs no entry — the join rule recovers it.
- **The table is edited where it lives, `data/aliases.toml`.** R1007 (OD-11)
  states the destination and assigns the migration to one change of its own
  ("Migration moves the existing file and its config default in one change"), so
  moving it here would be that plan's work done twice.

## The slices

Three, and they are **sequential**: slice 2's join rule is stated over the space
slice 1 produces, and slice 3's variant set is green only once both have landed.
They share files for that reason, which is safe because none of them runs beside
another.

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
  joins now. `_SEPARATORS` collapses to a single space and may be simplified or
  removed at the coder's discretion, provided the fold cases here hold.
- **`normalize` stays pure, total and idempotent.** `normalize("")` is `""`, it
  never raises, and `normalize(normalize(t)) == normalize(t)` — the existing
  property tests hold unchanged, which is why it is worth stating.
- **The two tests that assert the retired rule are rewritten**, not deleted:
  `test_hyphen_survives_as_a_character` and
  `test_hyphenated_model_name_is_left_intact` become the assertions above, and
  the commit message says why (`AGENTS.md`, the blind-tests rule — an edit to a
  test is allowed and must be visible). `STRIPPED_PUNCTUATION`'s comment, which
  explains why the hyphen is absent from it, is corrected in the same edit: the
  hyphen is not stripped, it is folded to a space.
- **`tests/test_aliases.py` is listed only as a contingency.** Its hyphen cases
  (`the b650e-plus board`, the `X870E-Nova` surface form) normalize on both
  sides and are expected to pass untouched; if one does not, correcting it
  belongs to this slice with the reason stated.
- **The module docstring loses its "a hyphen is KEPT as a character" rule**, and
  **`docs/architecture.md`** loses the same claim in the components table's
  normalization row, citing OD-6.

## Slice 2 — A name the captions split in half is still one name

- **Delivers:** `mag tomahawk` matches `the mag toma hawk vrm`, `aorus master`
  matches `aor us master`, and `b650` still finds nothing in `theb650`. The
  `aliases --check` report shows the split spelling as the form that fired, and
  R4's selection counts move for every video whose only mentions were split.
  Covers R1002.
- **Files:** `src/find_best_mobo/aliases.py`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~230 lines

### Signatures

```python
def alias_pattern(form: str) -> str: ...
def compile_matcher(aliases: Sequence[Alias]) -> re.Pattern[str]: ...
```

`alias_pattern` is new and public, in `src/find_best_mobo/aliases.py` alongside
`compile_matcher`, so the rule has a unit the tests can reach without asserting
on the shape of the whole table's pattern. `load_aliases`, `find_mentions` and
`find_title_hits` keep the signatures they have — `find_mentions` by OD-14, not
by inertia.

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
- **What must not match:** `theb650` and `xb650e` (the alias would start inside
  a token); `b650ex` and `x870ese` (it would end inside one); `aorusmaster` and
  `steellegend` (the alias's own space has no boundary to land on); `verb 650`
  (`b650` would start mid-token). These are R1002's "never a proper substring of
  a fused token", and they are the assertions that make the rule safe rather
  than merely wide.
- **A split across two cues yields no mention, and it is asserted** —
  `test_a_split_across_two_cues_yields_no_mention`: a two-cue transcript where
  one cue ends `the mag toma` and the next begins `hawk is fine` produces zero
  mentions from `find_mentions`. The test names **OD-14** as the decision it
  pins, so a future change to the scope is a visible test edit rather than
  drift.
- **Longest-form-first is unchanged**, and still sorts on the length of the
  *normalized form*, not of its pattern — a stable sort on negated length, file
  order among equals. `mag tomahawk` therefore still wins over `tomahawk` at the
  same position, and the compiled pattern stays byte-identical for a given
  table (R23).
- **The pattern stays linear to scan.** Each inserted element is ` ?` on a
  single literal space, never nested and never over a group, so the alternation
  gains no backtracking behaviour it did not have; the source roughly doubles in
  length and the table still compiles to one pattern, which is what R22 rides
  on.
- **`matched_form` stays `match.group(0)`** — the text as the caption spelled
  it, so `aliases --check` reports `toma hawk` as the spelling that did the
  work. That report is R1002's stated measurement; it only measures anything if
  the split form survives into it.
- **Global de-duplication is unchanged.** Two canonicals claiming one normalized
  form still resolve to the first declared, and the loser still surfaces as a
  zero-match canonical in the report.
- **A form's own spaces are single spaces.** Normalized text has no runs and no
  tabs, so the pattern needs no `+` and gains none — one more thing that cannot
  drift between two runs.
- **`docs/architecture.md`**'s "Inspecting the alias table" section gains the
  join rule beside the longest-first rule, and the alias-table component row
  says the pattern tolerates caption splits within a cue, citing OD-6 and OD-14.

## Slice 3 — The measured recall is pinned, and a split-spelled video is selected

- **Delivers:** a fixture of the 52 mangled spellings BL-8 tested, each with the
  canonical it must reach, run against the shipped table; every one matches, the
  `air us` mishearing because the table now carries it. And the end of the path
  OD-6 names as its measurement: a video titled with a split form is selected on
  its title hit, and one whose only body evidence is split spellings passes the
  mention threshold instead of being excluded. Covers R1002.
- **Files:** `tests/fixtures/caption_variants.json`, `tests/test_aliases.py`, `tests/test_select.py`, `data/aliases.toml`, `docs/architecture.md`
- **Estimate:** ~195 lines

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
mid-sentence are both covered. `†` marks the five that fail against the shipped
table today.

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
  carrier sentence, and in `find_mentions` for a cue holding it;
- `len(variants) >= 52`, with the count's provenance in the test's docstring —
  a later addition is welcome, a loss is a regression;
- the five named failures are present by exact text, so no future tidy-up can
  drop the cases the evidence was written about;
- nothing in `never_match` yields a mention against the shipped table.

### The selection effect

In `tests/test_select.py`, against a table and transcripts written into
`tmp_path` as that module already does:

- a video titled `MSI MAG toma hawk MAX WIFI review` is selected with the
  title-hit reason, where the same video is excluded before this plan;
- a video whose body spells three distinct canonicals only in split forms
  passes the mention threshold and is counted as a threshold pass rather than an
  exclusion in the selection report.

These are the counts OD-6 names as the measurement. Nothing here changes
`select.py`; the slice asserts that the matcher change reaches the number the
checkpoint is spent against.

### The table changes

`Aorus Elite` gains `airus elite`. One form covers both spoken shapes: under
slice 2's rule `airus elite` matches `air us elite`, `airus elite` and (after
slice 1) `air-us elite`, so the split spelling needs no second entry. `air us`
for `aorus` is the observed mishearing; the unobserved `airus master` is
deliberately absent, per R1002's "the observed spoken forms" — the recall report
is where a second sighting would come from.

`Pro RS` loses `pro-rs`, and it is the only removal: after slice 1 it normalizes
to the `pro rs` sitting beside it, and global de-duplication drops the second
claimant silently. A line the matcher can never use is worse than absent — it
reads as coverage. The variant `pro-rs` stays in the fixture and still matches,
through `pro rs`. Every other form the join rule makes redundant — `cross hair`,
`giga byte`, `tai chi`, `bio star`, `a 620` — **stays**: those are distinct
normalized forms that still fire on their own, and deleting them would move
`aliases --check`'s per-form counts for reasons unrelated to this change.

`docs/architecture.md` needs no new flow here; the alias-table row already says
the table is hand-authored input. The recall fixture is named in the testing
section so a future reader finds the pinned set from the document rather than by
grep.

## Out of scope

- **Splits across a cue boundary.** Decided out of scope by **OD-14**, not
  merely unimplemented: `find_mentions` keeps its cue-at-a-time scan, and slice
  2 asserts the boundary. Reversing it needs a measured cue-spanning miss and a
  new decision.
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
- **Widening the table beyond the `air us` mishearing.** The table is data and
  the owner extends it from the recall report; this plan adds only what R1002
  names as observed.
- **Any change to `Mention`, `Excerpt`, the index, or the bundle format.**
  Nothing downstream of the matcher sees this change except as more mentions.
