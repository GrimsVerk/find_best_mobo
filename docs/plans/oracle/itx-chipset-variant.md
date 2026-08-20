---
slug: itx-chipset-variant
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1003]
---

# A chipset's ITX variant counts as the chipset — Plan

Implements **OD-7** (`docs/DESIGN.oracle.md`), which adds **R1003** from the
evidence in **BL-9**: ITX boards are named `<chipset>I`, the matcher's right
boundary refuses to match `b850` inside `b850i`, and a real 33-minute review of
the MSI MPG B850I Edge TI matched `B850` **zero times** — in its title and in
its body both, so even the automatic title include missed it.

## Summary

One rule added to the alias matcher, then the two measurements OD-7 names
asserted at the far end of the path they run through. Three slices, ~325 lines,
**sequential**.

- **A chipset alias gains a derived ITX form: its normalized form plus a
  trailing `i`.** `b850` yields `b850i`, `x870` yields `x870i`, `670e` yields
  `670ei`. OD-7 leaves the mechanism to this plan and fixes the behaviour;
  derived forms keep the table free of per-chipset hand maintenance, including
  for chipsets that do not exist yet.
- **Only `kind = "chipset"` derives one, and only one trailing `i`.** `taichii`,
  `msii` and `7800x3di` match nothing, and nothing else about the right
  boundary moves: `b650ex` and `theb850i` still match nothing.
- **Derived forms are added after every declared form**, so a form the owner
  wrote always wins de-duplication, and the compiled pattern stays
  byte-identical for a given table (R23).
- **No change to the alias table's data, to `find_mentions`, or to any
  signature that exists today.** One new public helper, `itx_forms`, so the
  rule has a unit the tests can reach.
- **Slices 2 and 3 add no production code**, because R1003's two measurements —
  the `aliases --check` recall report and R4's selection counts — run through
  stages that already exist. They are the end of this change's vertical path,
  not a test layer bolted on after it.
- **Not done here:** OD-6/R1002's caption-split rule and OD-11/R1007's move of
  the table, both of which touch the same function or the same file; hyphenated
  ITX spellings (`b650e-i` already matches today); ITX as a *family* signal.

**What I need you to rule on:**

1. **The B850I regression title.** R1003 says "the real B850I review's title
   auto-includes on its chipset", and that title is not in the repository —
   BL-9 records the board, not the video. Filed as **BL-17** (LOW) and
   proceeded on: a declared reconstruction, asserted on the canonical rather
   than on the string.
2. **Merge order.** `caption-split-aliases` (OD-6) edits the same function and
   `run-scripts`/`corpus-and-checkpoint` do not, but OD-11 moves the table file.
   Whichever plan lands second carries the rebase; they cannot be built in
   parallel.

## Uncertainties

One filed, the rest derived. The derivations are shown rather than asserted,
because the questions that came closest to the line are the ones a reviewer
would otherwise have to reconstruct.

- **Q:** What title does R1003's regression case use? The requirement names "the
  real B850I review's title", and the tree does not hold it — BL-9 records the
  board (MSI MPG B850I Edge TI) and the duration, and no index, fixture,
  journal entry or `docs/runs/` artifact carries the video's id or title. —
  **risk:** LOW — it is fixture text; no signature, slice boundary or external
  format turns on it, and swapping in the real title later is a one-line edit.
  — **proposed:** a declared reconstruction, `MSI MPG B850I Edge TI review`,
  with a docstring naming BL-9 as its provenance and saying it is rebuilt;
  the assertion is that the video is admitted on `B850` by its title, never
  that the string is the original.
  **Ruling:** proceeded on the default (LOW), filed as **BL-17** in
  `docs/BACKLOG.md` for the oracle's next cycle. OD-15 ruled the same shape of
  question the same way for R1002's fixture, which is why the default is a
  *declared* reconstruction rather than a quiet one.

Derived, with the citation that decides each:

- **Derived forms, not hand-listed ones.** OD-7's alternatives weigh
  hand-listed `b850i`-style forms against "a derived ITX form for chipset
  aliases (surface forms generated from the canonical, or an equivalent
  suffix-aware rule) — chosen; which mechanism is the plan's choice, the
  behaviour is fixed here." The mechanism is therefore delegated, and OD-7's own
  objection to the hand-listed shape ("every chipset needs remembering,
  including future ones") decides which way.
- **Chipsets only.** R1003 says "A chipset alias also matches its ITX variant
  token". `kind == "chipset"`, and every other kind is untouched.
- **Exactly one trailing `i`.** R1003 names "the chipset followed by a trailing
  `i` (`b850i`, `x870i`, `b650i`)", and all three examples are single fused
  tokens. A wider suffix rule is a fresh reading of R3 and is out of scope below.
- **A form already ending in `i` derives nothing.** R1003's variant *is* the
  chipset plus a trailing `i`, so a declared form that already carries one is
  already the variant; deriving from it would add `b850ii`, a pattern
  alternative no board name can ever reach.
- **The right boundary stays exactly as it is.** OD-7 rejects "relaxing the
  right boundary generally", and OD-6's plan states that nothing in its own work
  relaxes it either. The ITX form is a longer literal behind the same
  lookaround, not a weaker lookaround.
- **The table is edited where it lives, and only its header comment.**
  R1007 (OD-11) states the destination and assigns the migration to one change
  of its own, so moving `data/aliases.toml` here would be that plan's work done
  twice. The comment edit is required by the "docs never lag the code" rule:
  the file tells its reader which spellings need listing, and after this slice
  chipset ITX forms do not.
- **Cross-cue scope is untouched.** OD-14 fixed R1002's scope at one cue at a
  time and this plan does not go near `find_mentions`, whose signature and scan
  both stay.

## The slices

Three, and they are **sequential**: slices 2 and 3 assert behaviour slice 1
delivers, and slice 2 shares `tests/test_aliases.py` with slice 1. They are
vertical in the sense that matters here — slice 1 goes text to mention, slice 2
goes a cached corpus to a printed report, slice 3 goes an index and a transcript
to one selection decision — and each is observable by a person without reading
code.

## Slice 1 — A fused ITX token is its chipset

- **Delivers:** `the b850i is a fine board` yields a `B850` mention, and a video
  titled `MSI MPG B850I Edge TI review` yields a `B850` title hit, where both
  yield nothing today. Everything that did not match before still does not:
  `theb850i`, `b850ix`, `b650ex`, `taichii`, `7800x3di`. Covers R1003.
- **Files:** `src/find_best_mobo/aliases.py`, `tests/test_aliases.py`, `data/aliases.toml`, `docs/architecture.md`
- **Estimate:** ~170 lines

### Signatures

```python
def itx_forms(alias: Alias) -> tuple[str, ...]: ...
def compile_matcher(aliases: Sequence[Alias]) -> re.Pattern[str]: ...
```

`itx_forms` is new and public, in `src/find_best_mobo/aliases.py` beside
`compile_matcher`, so the rule has a unit the tests can reach without asserting
on the shape of the whole table's compiled pattern. `compile_matcher` keeps its
signature. `load_aliases`, `find_mentions` and `find_title_hits` keep theirs
too, and `find_mentions` keeps its cue-at-a-time scan (**OD-14**).

Per **OD-12**, the module of every shared type this slice touches, none of which
changes shape: `Alias` and `Mention` in `src/find_best_mobo/aliases.py`;
`Transcript` and `Cue` in `src/find_best_mobo/transcripts.py`; `Video` in
`src/find_best_mobo/index.py`. This slice adds no type and no exception.

### Behaviour the signatures cannot carry

- **`itx_forms(alias)` returns the ITX variant of each of the alias's surface
  forms**, in the alias's own form order: each form is `normalize`d, and the
  variant is that normalized text with `i` appended. It returns an empty tuple
  for any alias whose `kind` is not `"chipset"`, and it skips a form that
  normalizes to empty or that already ends in `i`. Duplicates within one alias
  are dropped, keeping the first — `b850` and `b 850` both normalize to `b850`
  and yield one `b850i`.
- **Every form it returns is already normalized** — `normalize(f) == f` — which
  holds because appending `i` to a normalized form leaves one alphanumeric
  token. Worth a property test; it is what lets `compile_matcher` treat declared
  and derived forms identically.
- **`compile_matcher` collects forms in two passes**: every alias's declared
  forms first, in table order, then every alias's `itx_forms`, in table order.
  The existing global `seen` de-duplication spans both, so a declared form
  always beats a derived one that collides with it, whichever alias declared it.
- **Nothing else in `compile_matcher` moves.** The stable sort on negated
  normalized-form length, the per-form group naming, the lookarounds and the
  single compiled pattern all stay, so the pattern remains byte-identical for a
  given table (R23) and a two-hour transcript is still scanned once (R22).
- **The rule lands on the form list, not on the pattern source.** Each form is
  handed to whatever turns a form into regex source at the time — `re.escape`
  today, `alias_pattern` once `caption-split-aliases` lands. That is what makes
  the two plans safe to merge in either order.
- **What must match**, over normalized text, for the shipped table: `b850i` →
  B850; `x870i` → X870; `b650i` → B650; `a620i` → A620; `x670i` → X670;
  `x870ei` → X870E; `670ei` → X670E. Bare, at the start of the text, at the end
  of the text, and inside a carrier sentence (`the <text> board`).
- **What must not match:** `theb850i` and `xb850i` (the alias would start inside
  a token); `b850ix`, `b850ie` and `b850ii` (it would end inside one); and the
  existing negatives, unchanged — `b650ex`, `xb650e`, `9b650e`, `b650e1`.
- **Non-chipset kinds derive nothing**, asserted against the shipped table's own
  entries: `taichii`, `msii`, `tomahawki`, `7800x3di` and `stryxi` yield no
  mention at all, not merely not the obvious one.
- **A split ITX spelling is asserted by canonical only, never by
  `matched_form`.** `b 850 i` normalizes to `b850 i`, which matches `B850`
  today through the plain `b850` form and would match it through the ITX form
  once `caption-split-aliases` lands. Both give the same canonical and a
  different matched text, so asserting the text would make this slice's tests
  depend on merge order. The canonical is the contract.
- **The invariant worth stating**, because it is what makes the rule safe rather
  than merely wide: a derived form starts with the form it was derived from, so
  it can only add a match where the base form was blocked by the right
  boundary — that is, at a fused `<chipset>i` token. It can never introduce a
  canonical the base form could not already reach elsewhere in the same text.
- **`data/aliases.toml`'s header comment** gains one paragraph beside the
  existing note about which variants are worth listing: ITX forms are derived
  for every chipset entry, so `b850i` and its siblings must not be hand-added.
  Cites OD-7.
- **`docs/architecture.md`**: the alias-table row of the components table and
  the "Inspecting the alias table" section say that a chipset also matches its
  ITX token, beside the longest-first rule, citing OD-7. The
  known-limitations note about the table's recall being a human judgement
  stays true and is not touched.

## Slice 2 — The recall report shows the chipset firing on its ITX spelling

- **Delivers:** `find-best-mobo aliases --check`, over a cached corpus holding
  one ITX review, reports that chipset with a non-zero video count and shows
  `b850i` as a form that matched — where today the same corpus reports it in the
  zero-match callout. This is the first of the two measurements OD-7 names.
  Covers R1003.
- **Files:** `tests/test_aliases.py`
- **Estimate:** ~45 lines

### Signatures

None. `commands/aliases.py` needs no change: `_scan` already reports
`matched_form` per canonical, and the ITX spelling arrives there as the text the
transcript actually used.

### Behaviour the signatures cannot carry

- The corpus is built with the module's existing `setup_corpus` shape — a table
  written into `tmp_path`, an index, and cached transcripts — extended with one
  chipset entry whose only evidence in the corpus is an ITX token.
- Three assertions: that chipset's line shows a video count of one; the ITX
  spelling appears on it as a matched form; and the chipset is absent from the
  zero-match callout that a canonical matching nothing lands in.
- The existing report tests are not touched. Their corpus contains no ITX token,
  so their counts, their tie-break ordering and their byte-identical-rerun
  assertion are all unaffected — and if one does move, correcting it belongs to
  this slice with the reason stated in the commit message (`AGENTS.md`, the
  blind-tests rule).

## Slice 3 — The ITX review is selected

- **Delivers:** the regression R1003 names. A video titled with a B850I board is
  admitted with the `title_hit` reason, where the same video is excluded today;
  and a video whose only body evidence is ITX tokens for three distinct chipsets
  passes the mention threshold and is counted as a threshold pass rather than an
  exclusion in the selection report. Covers R1003.
- **Files:** `tests/test_select.py`, `docs/architecture.md`
- **Estimate:** ~110 lines

### Signatures

None. `select.py` is untouched: this slice asserts that the matcher change
reaches the numbers the checkpoint is spent against (R4, R7).

### Behaviour the signatures cannot carry

- Both cases use a table written into `tmp_path`, as the module already does,
  carrying `B850` as a chipset alongside the module's standard canonicals — the
  shipped `STANDARD_TABLE` has no B850, and BL-9's evidence is about B850.
- **The title case:** a video titled `MSI MPG B850I Edge TI review` with a
  transcript that names no board at all is selected, with reason `title_hit`.
  The test's docstring records that the title is a **reconstruction** from BL-9,
  not the real video's title, and cites BL-17 — so a later correction is an edit
  to a declared stand-in rather than a silent replacement.
- **The body case:** a video with a neutral title whose cues name three distinct
  chipsets only as ITX tokens passes the default threshold of three distinct
  canonicals, with reason `threshold`, and appears in the threshold report's
  included count rather than its excluded count.
- **The counts are asserted as counts**, not as report prose. The report's
  wording is already pinned by the existing marker-vocabulary tests, and this
  slice must not restate them.
- **`docs/architecture.md`**'s selection walkthrough gains one sentence: an ITX
  board's title carries its chipset, so an ITX review is admitted on the title
  rule like any other. Citing OD-7.

## Out of scope

- **OD-6 / R1002's caption-split matching.** It lands in the same
  `compile_matcher` and has its own plan (`caption-split-aliases`). Nothing here
  depends on it, and nothing here blocks it; the two are sequential, and
  whichever lands second rebases.
- **OD-11 / R1007's move of the alias table** to a tracked root path, and the
  configured-path loading with it. This plan edits the table's comment where the
  file currently lives.
- **Suffixes other than a single trailing `i`.** No `-i`, no `itx`, no `wifi`
  and no plural. R1003 names one trailing `i`; anything wider is a fresh reading
  of R3.
- **Hyphenated ITX spellings.** `b650e-i` normalizes to `b650e i`, which the
  plain `b650e` form already matches on the boundary before the hyphen. Nothing
  here changes that, and nothing here depends on the hyphen rule
  `caption-split-aliases` changes.
- **ITX as a signal in its own right.** The word `itx` in a title says the board
  is small, not which chipset it uses, and R1003 adds no canonical for it.
- **Deriving forms for any kind but `chipset`.** A board or family whose name
  ends in `I` is data the owner adds to the table, per §9.
- **Any change to `Mention`, `Excerpt`, `Selection`, the index, or the bundle
  format.** Nothing downstream of the matcher sees this change except as more
  mentions and more admitted videos.
