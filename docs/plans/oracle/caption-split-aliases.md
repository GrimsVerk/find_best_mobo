---
slug: caption-split-aliases
status: draft
created: 2026-08-19
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1002]
---

# An alias split across caption tokens still matches — Plan

Implements **OD-6** (`docs/DESIGN.oracle.md`), which adds **R1002** from the
evidence in **BL-8**: auto-captions split product names across tokens, and the
folding rule in `normalize` only joins letter-to-digit transitions, so
`toma hawk`, `aor us master` and `air us elite` match nothing at all. Of the 52
mangled variants the audit put through the shipped table, 49 matched and those
three did not — silent losses, in the corpus the whole product is built from.

## Summary

Compile the split tolerance **into the pattern the table already becomes**: a
surface form's characters may be separated by optional whitespace, a space
*inside* a form still demands a real one, the alphanumeric lookarounds stay. That
is R1002 verbatim — whole tokens at both ends, alias spaces on token boundaries.

- **No public signature moves.** `compile_matcher` still returns one compiled
  `re.Pattern`, `find_mentions` and `find_title_hits` keep their arguments, and
  `select`, `aliases --check` and every test holding a matcher are untouched. The
  alternative — a token-join pass beside the regex — changes the matcher's type
  and reaches into three modules to buy the same behaviour.
- **`normalize` folds hyphens to spaces**, because R1002 says it does, so
  `steel-legend` meets the table's `steel legend`. Two shipped `normalize` tests
  assert the opposite and are rewritten, with the reason in the commit — the
  visible test edit `AGENTS.md` asks to be declared. `x670e-plus` still matches:
  table forms fold the same way.
- **A multi-word alias will not match its fused spelling.** `steel legend` never
  matches `steellegend` — R1002 wants the alias's space on a token boundary, and
  one token has none. Captions split words; they do not weld them. It is the same
  clause that keeps `b650` out of `theb650`.
- **The table gains the mishearings no join can recover** — `air us elite`, and
  its sibling `air us master`, which was *not* measured (see below). The
  now-redundant `pro-rs` form goes, since it folds onto `pro rs`.
- **The 52-variant set is reconstructed, not recovered.** BL-8 recorded the count
  and the three failures, not the list, and it is nowhere in the tree. The fixture
  is one mangled variant per canonical plus more of the shapes the audit stressed,
  to 52, the three failures verbatim — with a reject set pinning what R1002 forbids.
- **Not done here: OD-7's ITX rule and OD-8's descriptions.** Separate decisions,
  separate plans; OD-7 edits these same files, so the two are sequenced.
- **What it costs the owner:** recall rises, so more videos are selected and the
  projection rises with them — R1002's whole point, and both numbers are already
  reported by `aliases --check` and R4's in/out counts.

Two slices, ~515 lines, sequential — the second measures what the first does.

**What I need you to rule on:** (1) `air us master` is added by symmetry with the
measured `air us elite`; delete the line if you would rather the table carried
only what was heard. (2) The 52-variant fixture is a reconstruction of BL-8's
set, not the set itself — say if a fixture that cannot be the original is worth
less to you than a smaller one that names only what was measured.

## Uncertainties

Two guesses, both filed here and in the steward's report; neither changes a
slice boundary or a signature, so both are **LOW** and proceed on the recorded
default for the oracle to review next cycle. Nothing here stopped for a ruling —
this plan was written unattended and cannot.

- **Q:** Which 52 variants? BL-8's measured set is not in the repository — the
  entry records the count and the three failures only, and no run report,
  journal entry or fixture carries the list. — **risk:** LOW; it is the content
  of one test fixture, and the slice, its files and its signatures are the same
  whichever set is used. — **proposed:** reconstruct 52 by the composition rule
  in slice 2, with `toma hawk`, `aor us master` and `air us elite` carried
  verbatim as the entries that must match, and record in the fixture's header
  that it is a reconstruction.
  **Ruling:** proceeded on the default (LOW), left for review.
- **Q:** Does the table gain `air us master` as well as the measured
  `air us elite`? R1002 says "the table gains the observed spoken forms", and
  only the Elite spelling was observed. — **risk:** LOW; one line of data, and
  deleting it is the whole reversal. — **proposed:** add it. The mishearing is
  of `aorus`, the token both family names share, so a table that recovers the
  Elite and not the Master is inconsistent in a way nothing in the pipeline
  would ever report.
  **Ruling:** proceeded on the default (LOW), left for review.

Four more questions came close enough to the line that showing the derivation is
worth more than asserting there was none.

- **The mechanism.** R1002 fixes the behaviour and not the implementation, and
  OD-4 set the precedent that a mechanism the decision does not name is the
  plan's to choose, not a gap to route back to the oracle. It resolves to the
  pattern rather than a token-join pass on the design's own stated grounds:
  `aliases.py` compiles the whole table to ONE regex so a two-hour transcript is
  scanned once, and a second pass over token windows would either scan twice or
  retire that property. The equivalence argument is in slice 1.
- **Whether hyphen folding is this plan's to do.** It is: R1002 states it in the
  requirement text ("Normalization folds hyphens to spaces"), so it is design,
  not scope this plan widened into — even though `normalize.py`'s docstring
  currently argues the opposite in bold.
- **Whether the fixture runs against the shipped table.** Yes — the shipped table
  is what BL-8 measured and what decides the real corpus, and `tests/test_aliases.py`
  already holds a `SHIPPED_TABLE` constant for exactly this. OD-11/R1007 moves
  that file to the repository root; whichever of the two plans lands second
  updates the constant, and this is named in Out of scope so it is not a surprise.
- **Whether split tolerance applies to every form or only to compound ones.**
  Every form. R1002 says "an alias", without qualification, and a rule that
  applied to some entries of a data table and not others would have to be
  explained in the table itself.

## The work, sliced

Two slices, and deliberately not three. The change is one rule in the matcher
plus the recall measurement that proves it on the evidence that produced it;
cutting the normalization change out as its own slice would be horizontal — a
slice whose only observable is a function nothing user-facing calls yet.

**They are sequential.** Slice 2 asserts against the behaviour slice 1 delivers,
so it is built after slice 1 has landed, not beside it.

## Slice 1 — A product name split by the captions is found anyway

- **Delivers:** `uv run find-best-mobo aliases --check` reports `MAG Tomahawk`
  and `Aorus Master` matching in videos where the captions wrote `toma hawk` and
  `aor us master`, with those spellings named in the report's `forms:` column —
  today they match nothing and the canonicals can read as NEVER MATCHED. A video
  titled with a split form is admitted by `select` on its title hit. Covers R1002.
- **Files:** `src/find_best_mobo/normalize.py`, `src/find_best_mobo/aliases.py`, `data/aliases.toml`, `tests/test_normalize.py`, `tests/test_aliases.py`, `docs/architecture.md`
  <!-- One line deliberately: `.github/scripts/plan-parse.sh` reads the file
  list off this single line, so a wrapped continuation is invisible to the
  reviewer's scope check. -->
- **Estimate:** ~250 lines

### Signatures

```python
def normalize(text: str) -> str: ...
def compile_matcher(aliases: Sequence[Alias]) -> re.Pattern[str]: ...
def find_mentions(transcript: Transcript, matcher: re.Pattern[str]) -> tuple[Mention, ...]: ...
def find_title_hits(video: Video, matcher: re.Pattern[str]) -> frozenset[str]: ...
def _split_tolerant(form: str) -> str: ...
```

**Every public signature above is unchanged from what is in the tree today** —
they are restated because they are the contract the blind test author works
from, not because anything moved. `_split_tolerant` is new and private: it takes
one already-normalized surface form and returns the regex source for it.

Per OD-12, the module of every shared type: `Alias` and `Mention` in
`src/find_best_mobo/aliases.py`; `Transcript` and `Cue` in
`src/find_best_mobo/transcripts.py`; `Video` in `src/find_best_mobo/index.py`.
None of them changes shape here.

### Behaviour the signatures cannot carry

- **`_split_tolerant` is the whole rule.** For a normalized form, emit
  `re.escape` of each character joined by `\s*` within a word, and join the
  words with `\s+`. `tomahawk` becomes `t\s*o\s*m\s*a\s*h\s*a\s*w\s*k`;
  `aorus master` becomes `a\s*o\s*r\s*u\s*s\s+m\s*a\s*s\s*t\s*e\s*r`. The
  alternation, the group naming, the longest-form-first sort and the
  `(?<![a-z0-9]) … (?![a-z0-9])` lookarounds around the whole alternation are
  untouched.
- **Why that is exactly R1002.** Normalized text separates tokens by single
  spaces, so within a match `\s*` can only ever consume a whole token boundary.
  The lookarounds force the match to begin and end at a token edge, so the
  matched span is a run of adjacent whole tokens whose concatenation is the form
  with its spaces removed; `\s+` forces every space inside the form onto one of
  those boundaries. Both halves of R1002 fall out of that, including the one it
  states as a prohibition — `b650` cannot be found inside `theb650`, because the
  left lookaround sees `e`.
- **`normalize` folds `-` to a space** before whitespace is collapsed, so
  `x-670-e` still joins to `x670e` and `steel-legend` becomes `steel legend`.
  With the hyphen gone from the text, `_SEPARATORS` reduces to a single space;
  an em dash still separates, which is the distinction that comment was making.
  The module docstring's "a hyphen is KEPT as a character" paragraph is now
  false and is rewritten in this slice, citing OD-6.
- **Two shipped tests assert the old rule** —
  `test_hyphen_survives_as_a_character` and
  `test_hyphenated_model_name_is_left_intact` in `tests/test_normalize.py`. They
  are rewritten to assert the fold, and the commit says why: R1002 changed the
  contract they pin. Under `AGENTS.md` this is an allowed but visible test edit,
  not a weakening — the new assertions are as strict as the old ones.
- **The table changes are three lines.** `air us elite` on `Aorus Elite`,
  `air us master` on `Aorus Master`, and `pro-rs` deleted from `Pro RS` because
  it now normalizes onto the `pro rs` already there, where global de-duplication
  would silently drop it anyway. `aor us master` and `toma hawk` get **no** table
  entry: they are what the rule recovers, and adding them would hide whether it
  works.
- **Determinism holds (R23).** Pattern construction is a pure function of the
  table's file order and form lengths, as it is today, so a given table still
  compiles to a byte-identical pattern and the same run produces the same
  mentions.
- **One regex, one scan (R22).** The pattern roughly doubles in source length
  and gains no alternation; `\s*` over single-space text cannot backtrack
  quadratically, so a two-hour transcript is still one pass per cue.
- **`matched_form` reports what the captions actually wrote** — `toma hawk`, not
  `tomahawk` — because it is `match.group(0)`, unchanged. That is what makes the
  `aliases --check` report evidence rather than a restatement of the table.
- **`docs/architecture.md` is corrected in this slice.** Its normalization row
  and its "the fix for one kind of caption damage" note describe a matcher that
  cannot see a split compound; the new rule and its boundary guarantee replace
  them, citing OD-6 and R1002.

## Slice 2 — The recall the audit measured is pinned in the suite

- **Delivers:** the 52-variant recall set as a fixture, run against the shipped
  table: every variant matches its canonical, the three BL-8 failures included.
  A reject set beside it holds the spellings that must **not** match, so the
  slice measures the boundary as well as the recall. And the end-to-end
  observation: a video whose only alias evidence is split spellings is selected
  rather than excluded. Covers R1002.
- **Files:** `tests/fixtures/alias_variants.toml`, `tests/test_alias_variants.py`, `tests/test_select.py`
- **Estimate:** ~265 lines

### Signatures

```python
@dataclass(frozen=True)
class Variant:
    text: str
    canonical: str


def load_variants(path: Path) -> tuple[Variant, ...]: ...
def load_rejects(path: Path) -> tuple[Variant, ...]: ...
```

Both live in `tests/test_alias_variants.py`; nothing under `src/` is touched by
this slice.

### The fixture

`tests/fixtures/alias_variants.toml` — TOML rather than JSON because the header
has to carry the provenance, and a fixture that cannot say where its numbers
came from is how BL-8's list got lost in the first place:

```toml
[[variant]]
text = "the msi mag toma hawk max wifi"
canonical = "MAG Tomahawk"

[[reject]]
text = "theb650 board"
canonical = "B650"
```

**Composition — 52 variants, by this rule:**

- one mangled variant for each of the 29 canonicals in the shipped table, so a
  canonical the table cannot reach is impossible to miss;
- the remainder made of the shapes the audit stressed — split compounds
  (`toma hawk`, `aor us master`, `cross hair`, `tai chi`), hyphenated forms
  (`steel-legend`, `x-670-e`), digit-split part numbers (`x 6 70 e`,
  `78 00 x 3 d`), and mishearings (`air us elite`, `steal legend`);
- the three BL-8 failures verbatim, marked in the file as the measured ones.

**The reject set is separate and is not part of the 52.** It pins what R1002
forbids: `theb650` yields no `B650`, `st eellegend` yields no `Steel Legend`
(the alias's space does not land on a token boundary), `steellegend` likewise,
and `b650ex` stays unmatched. A recall fixture with no reject set passes just as
well against a matcher that matches everything.

Each variant is asserted through `compile_matcher(load_aliases(SHIPPED_TABLE))`
and `find_mentions` over a one-cue transcript, so the assertion runs the same
path the corpus does. The failure message names the variant and its canonical:
this test is read when the table is extended, and "assert False" would waste
that.

### The end-to-end observation

In `tests/test_select.py`, against a table and transcripts written into
`tmp_path` as that module already does:

- a video titled `MSI MAG toma hawk MAX WIFI review` is selected with reason
  `title_hit`, where the same video is excluded before this plan;
- a video whose body spells three different canonicals only in split forms
  passes the mention threshold, and `ThresholdReport` counts it under
  `threshold_passes` rather than `excluded`.

That second case is R1002's effect on the number the checkpoint spends against,
which is the reason OD-6 names R4's selection counts as its measurement.

## Out of scope

- **OD-7 / R1003, the ITX variant rule.** `b850i` counting as `B850` is its own
  decision and its own plan. It lands in `aliases.py`, the same file, so the two
  pull requests are sequenced rather than parallel — whichever is second rebases.
  Nothing here anticipates it: this plan's rule joins what captions split and
  says nothing about a trailing letter.
- **OD-8 / R1004, matching the video description.** A different signal, a
  different stage, its own plan.
- **OD-11 / R1007, moving the alias table to the repository root.** This plan
  reads the table where it is today. When that migration lands, the
  `SHIPPED_TABLE` constant in the tests moves with it, in that plan's diff.
- **Extending the alias table with boards the corpus turns out to name.** The
  table is data (§9) and widening it is a run-time activity, not this plan's.
  What lands here is only the mishearings R1002 names.
- **The excerpt, bundle and estimate stages.** More mentions mean more windows
  and a larger projection; nothing about how a window is cut, merged or costed
  changes here.
- **Any change to `Mention`, `Alias`, or `data/selected.jsonl`'s shape.**
  Downstream slices read those, and this rule needs none of them different.
</content>
</invoke>
