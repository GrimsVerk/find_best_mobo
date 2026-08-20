---
slug: itx-chipset-variant
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1003]
---

# A chipset's ITX variant counts as the chipset — Plan

Implements **OD-7** (`docs/DESIGN.oracle.md`), which adds **R1003** from the
evidence in **BL-9**. ITX boards are named `<chipset>I`, and the matcher's right
boundary `(?![a-z0-9])` refuses to find `b850` inside `b850i`. Measured against
a real 33-minute review of the MSI MPG B850I Edge TI, **`B850` matched zero
times** — in the title and in the body both, so even the automatic title include
missed it. Every ITX review in the corpus is affected, and ITX is exactly where
one-DIMM-per-channel memory behaviour lives.

## Summary

One rule, in the one place the alias table becomes a pattern: a chipset
contributes its ITX form alongside the forms the table declares.

- **A derived form, not a relaxed boundary.** For every `kind = "chipset"`
  alias, each normalized surface form enters the pattern a second time with a
  trailing `i`. The right boundary is untouched, which is what R1003 requires of
  everything else: `b850ix` and `theb850i` still match nothing, and `asrocki` is
  still not ASRock.
- **Derived from every declared form, not from the canonical alone.** A spelling
  the owner adds later gets its ITX variant with no code change — the
  self-maintaining property OD-7 rejected hand-listed `b850i` entries for.
- **Explicit beats derived.** Declared forms are enumerated before any derived
  one, so a hand-added `b850i` wins the existing first-declared-wins
  de-duplication and the derived form drops out silently. A form already ending
  in `i` derives nothing.
- **Chipsets only** — families, boards, vendors and CPUs derive nothing. R1003
  names the chipset.
- **No table entry and no signature change downstream.** `data/aliases.toml`
  gains a header comment and no new forms; `compile_matcher`, `find_mentions`,
  `find_title_hits`, `Mention` and `selected.jsonl` keep their shapes.
  `matched_form` reports `b850i`, so the `aliases --check` recall report names
  the spelling that fired.
- **The threshold still gates bodies** (OD-7 says so): an ITX video naming one
  chipset in its body is one distinct canonical and stays excluded at N=3. The
  title hit is what rescues the measured case.
- **The regression is a labelled reconstruction.** The real review's title is in
  no commit, journal entry or run record — only BL-9's verbatim board name is.
  Filed as **BL-18**, proceeding on the default.
- **Not done here:** OD-6/R1002's caption-split join (which is what makes
  `b850-i` and `b850 i` match), OD-11/R1007's table move, OD-8/R1004's
  descriptions, and any suffix beyond R1003's single trailing `i`.

Two slices, ~300 lines, **sequential**. One open uncertainty, LOW, filed as
BL-18 and proceeded on.

**Merge order**, unchanged from the OD-6 plan's note: `caption-split-aliases`
edits the same `compile_matcher` and OD-11 moves the same table file, so these
must not be built in parallel and whichever lands second carries the rebase.
Deriving at the form-string level is what keeps that rebase to one call site.

**What I need you to rule on:**

1. **The reconstructed title (BL-18).** R1003 asks for the *real* B850I review's
   title and the tree does not hold it. If asserting on the board-name token
   alone is honester, slice 2 loses one string.
2. **Whether `aliases --check` should mark a form as derived.** It will print
   `b850i` under B850 while the table shows no such form. Left alone here — see
   Out of scope — because a new marker is an observable nobody ruled on.
3. **Merge order** against `caption-split-aliases` and OD-11's table move.

## Uncertainties

One, LOW, filed and proceeded on.

- **Q:** What is the real B850I review's title? R1003 names the regression as
  "the real B850I review's title auto-includes on its chipset", and the title
  string is nowhere in the repository: BL-9 records the board
  (`MSI MPG B850I Edge TI`), the 33-minute duration and the measured zero
  matches, but not the title as YouTube spells it, and `data/index.jsonl` is
  gitignored and absent from a fresh clone. — **risk:** LOW — test-fixture
  content; no signature, slice boundary or external format turns on it. —
  **proposed:** carry BL-9's board name verbatim inside a plainly-labelled
  reconstructed title, with the test's docstring stating that the original is
  unrecoverable and that only the board name has measured provenance.
  **Ruling:** proceeded on the default (LOW), filed as **BL-18** under
  "Uncertainties awaiting oracle ruling" in the same commit as this plan. The
  provenance rule is not invented here — **OD-16** already settled it for
  R1002's fixture: a reconstruction declares itself, and only what was actually
  observed claims measured provenance.

### Derivations, not uncertainties

Each is a place the design layer hands the choice to the plan. Recorded so a
reader sees the derivation rather than a decision appearing from nowhere.

- **Derived forms rather than a suffix-aware pattern.** OD-7 states it in terms:
  "A derived ITX form for chipset aliases (surface forms generated from the
  canonical, or an equivalent suffix-aware rule) — chosen; which mechanism is
  the plan's choice, the behaviour is fixed here." Resolved to a form-string
  derivation because the whole change then lives before pattern compilation:
  the lookarounds, the group naming and the longest-first sort are untouched,
  and — the reason it matters beyond tidiness — `caption-split-aliases` rewrites
  exactly how a form becomes regex source, so a rule stated over *forms* is
  carried by whichever plan lands second at no cost, where a rule stated over
  *pattern source* would have to be re-derived.
- **Which chipset text is suffixed.** Every declared surface form, not the
  canonical alone. Both are inside the mechanism OD-7 delegates, and the
  tie-breaker is OD-7's own argument against hand-listing: "every chipset needs
  remembering, including future ones". Suffixing the declared forms means a
  spelling added to the table tomorrow brings its ITX variant with it. The
  shipped table makes the two nearly identical anyway — each chipset's canonical
  normalizes onto a form it already declares.
- **Explicit-before-derived precedence.** Derived from the module's existing
  global de-duplication rule ("if two canonicals claim the same normalized form,
  the one declared first wins"), which needs an order to be meaningful once a
  second source of forms exists. Two passes over the same alias sequence answers
  it without a new rule: a form somebody wrote down always beats one the code
  inferred, whatever order the table is in.
- **Kind, not spelling, decides.** R1003 says "a chipset alias"; the table
  carries `kind` per entry (§9, `KINDS` in `aliases.py`), so the rule reads it
  rather than guessing from the shape of a form.
- **A form already ending in `i` derives nothing.** R1003's variant of `b850i`
  is `b850i`. Emitting `b850ii` would add an alternative no text can reach,
  which is a pattern that lies about what it covers.
- **The mention threshold is not re-tuned.** OD-7: "The mention threshold still
  gates body matches." Recovered mentions raise counts and therefore admit
  videos; whether N=3 is still right is a question for the numbers this change
  moves (R4/R17), not a change to make alongside it.

## The work, sliced

Two, and deliberately not three: R1003 is one rule in one function plus the
corpus-level regression the requirement names. A third would be horizontal — a
slice of code with nothing observing it, then a slice of observation. **They are
sequential:** slice 2 asserts against the behaviour slice 1 delivers, so it is
built after slice 1 has landed, not beside it.

## Slice 1 — A chipset's ITX token is the chipset

- **Delivers:** a cue saying "the b850i is a tiny board" yields a **B850**
  mention, and a title saying it is a title hit. `find-best-mobo aliases --check`
  reports `b850i` as one of the forms that carried B850. The boundary is
  visibly unchanged: `theb850i`, `b850ix` and `asrocki` still yield nothing.
  Covers R1003 in part.
- **Files:** `src/find_best_mobo/aliases.py`, `data/aliases.toml`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~170 lines

### Signatures

```python
ITX_SUFFIX = "i"


def itx_forms(alias: Alias) -> tuple[str, ...]: ...
def compile_matcher(aliases: Sequence[Alias]) -> re.Pattern[str]: ...
```

`itx_forms` is new and public, in `src/find_best_mobo/aliases.py` beside
`compile_matcher`, so the rule has a unit the tests can reach without asserting
on the shape of the whole table's pattern. `load_aliases`, `find_mentions` and
`find_title_hits` keep the signatures they have, and `compile_matcher`'s is
listed only to say it does not change.

Per **OD-12**, the module of every shared type this slice touches, none of which
changes shape: `Alias` and `Mention` in `src/find_best_mobo/aliases.py`;
`Transcript` and `Cue` in `src/find_best_mobo/transcripts.py`; `Video` in
`src/find_best_mobo/index.py`. This slice adds no type and no exception —
`ITX_SUFFIX` and `itx_forms` live in `src/find_best_mobo/aliases.py`.

### Behaviour the signatures cannot carry

- **`itx_forms` returns `()` for any alias whose `kind` is not `"chipset"`.**
  For a chipset it returns, in the alias's declaration order,
  `normalize(form) + ITX_SUFFIX` for each surface form, skipping any form that
  normalizes to empty and any that already ends in `ITX_SUFFIX`, de-duplicated
  within the alias with the first occurrence kept. It is pure and never raises;
  an alias with no forms yields `()`.
- **`compile_matcher` makes two passes over the same alias sequence**: every
  alias's declared forms first, then every alias's `itx_forms`, both feeding the
  `seen` set that already exists. So an explicit form always wins a collision —
  a hand-added `b850i`, or another canonical's declared form — and the derived
  one is dropped exactly as a duplicate declared form is today.
- **Nothing else about compilation changes.** The `(?<![a-z0-9])` /
  `(?![a-z0-9])` lookarounds, the stable longest-normalized-form-first sort,
  `_group_name`'s hex encoding, and the empty-table `_MATCHES_NOTHING` are all
  untouched. The pattern stays byte-identical for a given table across runs
  (R23), because the derived pass walks the same table in the same order.
- **What must match**, over normalized text, in bodies (`find_mentions`) and
  titles (`find_title_hits`) alike, and bare, mid-sentence and at either end of
  the text: `b850i` → B850; `x870i` → X870; `b650i` → B650; `a620i` → A620;
  `x670ei` → X670E (ASUS's X670E-I is a real board, so the rule must not be
  restricted to forms ending in a digit).
- **What must not match:** `theb850i` and `xb850i` (the form would start inside
  a token); `b850ix`, `b850i7` and `b850ie` (it would end inside one); `b850ii`
  (nothing derives it); `asrocki` and `taichii` (a vendor and a family derive
  nothing). Every negative the suite already pins — `theb650`, `b650ex`,
  `xb650e` — is unchanged, and this is R1003's "the right-boundary rule stays in
  force for everything else".
- **Precedence is pinned, not assumed.** With a synthetic table declaring both
  `B650` (`b650`) and `B650I` (`b650i`) as chipsets, the text `b650i` yields
  **B650I**, in either declaration order, and B650's derived form never fires.
- **`matched_form` is still `match.group(0)`** — the spelling the text used — so
  `b850i` reaches the recall report as the form that did the work. That report
  is OD-7's stated measurement, and it measures nothing if the ITX spelling does
  not survive into it.
- **The module docstring gains the rule.** `aliases.py` opens by naming the two
  things that are deliberate about it; the ITX derivation is a third, and it
  says which kinds it applies to and that explicit forms win, citing OD-7 and
  R1003.
- **`data/aliases.toml` gains a header comment and no forms.** It states that a
  chipset entry also matches its ITX token, that the variant is derived in code
  rather than listed, and that hand-adding `b850i` is unnecessary. Comment-only
  is deliberate: OD-11's move of this file and `caption-split-aliases`'s content
  edits then rebase without touching each other's lines.
- **`docs/architecture.md`**: the alias-table row in the components table says
  chipset forms also match their ITX token, and step 3 of "Inspecting the alias
  table" — the one compiled pattern, longest first — gains the derived ITX form
  beside it. Both cite OD-7/R1003, so the next agent reads the derivation as a
  decision rather than as a bug in the table.

## Slice 2 — The ITX review comes into the corpus

- **Delivers:** the regression R1003 names, end to end. An index whose pending
  video is titled with the measured board name is selected with the `title_hit`
  reason where the same video is excluded before this plan; a video whose body
  names three chipsets only in ITX spellings passes the mention threshold, while
  one naming a single chipset that way stays excluded; and the `aliases --check`
  report lists the ITX spelling among the forms that fired. Covers R1003.
- **Files:** `tests/test_select.py`, `tests/test_aliases.py`
- **Estimate:** ~130 lines

### The regression, and what it may claim

In `tests/test_aliases.py::TestShippedTable`, against the real shipped table:
a video titled with BL-9's board name yields `B850` from `find_title_hits`, and
a one-cue transcript of the same text yields a `B850` mention whose
`matched_form` is the ITX spelling.

The title is a **reconstruction**, and the test says so in its docstring:

- **`MSI MPG B850I Edge TI` is verbatim from BL-9** and is the only part with
  measured provenance;
- the surrounding title wording is invented, because the real title is in no
  commit, journal entry or run record (**BL-18**), and `data/index.jsonl` is
  gitignored;
- the docstring records what BL-9 *did* measure — zero `B850` matches in title
  and body on a 33-minute review — as the provenance of the case, not of the
  string.

Nothing asserts on the invented wording: the assertions are the canonical and
the matched form. This is OD-16's rule for R1002's fixture applied one file
over — a reconstruction declares itself, and a failing-today claim is
demonstrated rather than asserted. The test is written blind, before the code,
so it is observed red against the pre-fix matcher and green after, which is the
demonstration.

### The selection effect

In `tests/test_select.py`, against a table and transcripts written into
`tmp_path` as that module already does, through the real `select_all` path:

- the ITX-titled video is selected with the `title_hit` reason, and appears in
  the threshold report's title-hit count;
- a video whose body names `b850i`, `x870i` and `b650i` reaches
  `distinct_canonicals == 3` and is selected as a threshold pass at N=3;
- a video whose body says `b850i` three times reaches `distinct_canonicals == 1`
  and is **excluded** at N=3 — the mention threshold still gates body matches,
  which OD-7 states and which a rule that only ever adds mentions could
  otherwise be assumed to have loosened;
- every mention's `matched_form` is the ITX spelling, so `selected.jsonl`
  records what the caption actually said.

Nothing in `select.py` changes; the slice asserts that the matcher change
reaches the counts the checkpoint is spent against, which is the second half of
OD-7's stated measurement.

### The recall report

In `tests/test_aliases.py::TestAliasesCommand`, using that class's existing
`STANDARD_TABLE` corpus so the assertion is about the report rather than about
the shipped table: a cue naming a chipset's ITX token makes that canonical's
line count the video, and lists the ITX spelling among its `forms:`. This is the
`aliases --check` half of OD-7's measurement, asserted on the printed report
rather than assumed from the matcher.

## Out of scope

- **Marking a derived form as derived in `aliases --check`.** The report will
  print `b850i` under B850 while the table declares no such form. R1003's stated
  measurement is that report as it stands, and a new marker is an observable
  nobody ruled on; the table's header comment and `docs/architecture.md` carry
  the fact instead. If a real run shows the report misleading someone extending
  the table, that is logged evidence for a `BL-<n>`, not a widening here.
- **Any suffix but a single trailing `i`.** No `itx`, no `-itx`, no plural, no
  `im`/`ix` board-suffix guessing. R1003 names one letter.
- **The hyphenated and space-broken ITX spellings.** Today `normalize` keeps the
  hyphen and refuses to join a standalone `i` (`_STANDALONE_WORDS`), so `x870-i`
  and `x870 i` still match nothing after this plan. `caption-split-aliases`
  delivers both — its hyphen fold turns `x870-i` into `x870 i`, and its
  optional-space join lets the derived `x870i` meet it — with no further change
  here, which is the point of deriving a form rather than a pattern. That
  composition can only ever re-label a mention the base form already produced:
  where the join lets `b850i` consume the "I" of "the B850, I think", `b850`
  matched that text already, so the canonical and the count are the same and
  only `matched_form` differs.
- **A *board* whose own name ends in `I`.** Boards enter the table as data (§9);
  nothing here derives forms for `kind = "board"`.
- **OD-11/R1007's move of the alias table** to a tracked root path, and the
  configured-path loading with it. This plan edits the table where it lives
  today, and only its header comment.
- **OD-8/R1004's description matching.** A new field to match against is
  independent of how a form is matched; the two meet only in the selection
  report.
- **Re-tuning the mention threshold (R4/R17).** More matched chipsets move the
  in/out counts; whether N=3 is still right is a question for those numbers.
- **Revising `docs/plans/corpus-and-checkpoint.md`.** Its slice 3 Signatures
  block will not name `itx_forms` once this lands. It is a plan behind
  `CODEOWNERS`, revised on its own pull request — **OD-12** already commissions
  that revision, and this addition can ride it alongside
  `caption-split-aliases`'s.
