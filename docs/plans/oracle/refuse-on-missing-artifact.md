---
slug: refuse-on-missing-artifact
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1005]
---

# A stage with a missing upstream artifact refuses to run — Plan

Implements **OD-9** (`docs/DESIGN.oracle.md`), which adds **R1005** from the
evidence in **BL-7**. `project` counts `videos_indexed` as 0 when
`data/index.jsonl` is absent, so `estimate` prints a full projection whose
denominator reads as a real number rather than an absence — on the one number
the checkpoint (R7) exists to make trustworthy, against which the owner decides
what to spend. R1005 generalises the fix: *a pipeline stage whose upstream
artifact is missing refuses to run, naming the absent artifact and the stage
that produces it*, while *a present-but-empty artifact is a real value and is
reported as what it is*.

## Summary

One rule, applied at every stage boundary the built pipeline has, and one
forgiving branch deleted.

- **One helper, one message shape.** A new `artifacts.py` holds
  `MissingArtifact` plus `require_file` / `require_directory`. It **subclasses
  `FileNotFoundError`**, so every existing `except` and every existing refusal
  keeps working and no caller learns a new exception.
- **`estimate` stops reading a missing index as zero** (BL-7's defect) and
  checks all three of its upstream artifacts *before* it cuts anything, so a
  refusal never leaves bundles on disk. `project` keeps its signature; the
  `if index_path.exists() else 0` branch is deleted, not moved.
- **The transcript cache is an artifact, so `fetch` starts creating
  `data/transcripts/`** even when it caches nothing. Today it appears only on
  the first successful write, which makes "fetch never ran" and "fetch ran and
  everything failed" one state on disk — the conflation R1005 forbids.
- **This costs you a workflow.** `select` and `estimate` now exit 1 before
  `fetch` has ever run, where `select` used to print a title-hits-only threshold
  report — the same understatement BL-7 found one stage over: it reads as a
  measurement of the lever and is really one of the missing corpus.
- **Present-but-empty is a real value, and one refusal is retired.**
  `aliases --check` against an empty-but-present cache prints an all-zeros
  recall report and exits **0**, where today it exits 1; its check moves from
  "no `*.json` files" to "no directory".
- **The alias table is deliberately not covered.** No stage produces it (R1007
  calls it hand-authored input), so R1005's "name the stage that produces it"
  has no answer for it; its message stays as it is.
- **It edits existing tests.** Five across `tests/test_estimate.py` and
  `tests/test_select.py` gain one line creating the empty cache directory a
  `fetch` run would have left; one in `tests/test_aliases.py` is renamed,
  because its name claims "empty" for a case that is "absent". Each edit states
  its reason in its commit, per `AGENTS.md`'s blind-test rule.
- **Not done here:** no flag overriding a refusal; no detection of a *partial*
  cache left by a halted `fetch` (present-but-incomplete is not absence);
  nothing about `data/failures.jsonl`; no change to `scripts/run.sh`, whose
  stage order is already index → fetch → select → estimate.

Three slices, ~495 lines, **sequential** — slice 1 introduces the module the
other two import.

**What I need you to rule on** — nothing here is unruled; both items are R1005
applied, and they are here because they cost you something. **The workflow:**
running `select` on a fresh index without fetching now fails instead of printing
a partial report. **The exit-code flip:** `aliases --check` on an empty cache
now succeeds with a report of zeros instead of telling you to run `fetch`.

## Uncertainties

**None: every decision derived from the design.** R1005 fixes the behaviour
(refuse, name the artifact and its producing stage, treat emptiness as a value)
and leaves the mechanism to the plan. Nothing is filed to `docs/BACKLOG.md` by
this plan.

### Derivations, not uncertainties

Each is a place the design layer fixes the behaviour and delegates the
mechanism. Recorded so a reader sees the derivation rather than a decision
appearing from nowhere.

- **The rule reaches every stage, not only `estimate`.** R1005's first sentence
  is unqualified — "*A pipeline stage* whose upstream artifact is missing" — and
  the `estimate` clause opens with "in particular", which highlights BL-7's
  measured case without narrowing the rule. So the plan enumerates the stages
  and their upstream artifacts rather than patching one function.
- **What counts as an upstream artifact.** R1005 supplies the criterion in its
  own message clause: an artifact has *a stage that produces it*. That gives,
  for the built tree: `index` — none, it reads the channel; `fetch` —
  `data/index.jsonl`; `select` — `data/index.jsonl` and `data/transcripts/`;
  `aliases --check` — the same two; `estimate` — `data/index.jsonl`,
  `data/transcripts/` and `data/selected.jsonl`. `data/failures.jsonl` is
  fetch's own prior state, read by nothing downstream, so it is not upstream of
  anything.
- **The alias table is outside the rule.** OD-11/R1007 makes it a hand-authored,
  git-tracked input; no stage produces it, so R1005's message shape cannot be
  formed for it and its absence is a different fact ("restore it" rather than
  "run the stage"). The existing wording in `commands/select.py` and
  `commands/aliases.py` is left alone.
- **`select` refuses on an absent cache, and the counter-reading is answered.**
  It could be read that R2 and R24 — a video with no caption track is an
  ordinary outcome and the run continues — mean `select` must tolerate a missing
  cache. They do, per video: a title hit with no transcript is a real selection
  and stays one. They say nothing about the *artifact* being absent, which is
  the state where every threshold pass is impossible by construction and R4's
  lever report understates itself exactly as BL-7's projection did.
  `aliases --check` already refuses on this artifact today, so refusing is the
  consistent reading rather than a new posture.
- **`fetch` creates `data/transcripts/` unconditionally.** Without it, absence
  is ambiguous — the directory appears on the first successful cache write, so a
  fetch run where every video failed leaves no directory, and a downstream stage
  would tell the owner to run a stage they have already run. Creating it is what
  makes R1005's third sentence true of this artifact: present-and-empty means
  "fetch ran and cached nothing", absent means "fetch has not run".
- **`MissingArtifact` subclasses `FileNotFoundError`.** `select_all` already
  raises `FileNotFoundError` with `errno` and `filename` set so its command can
  name the file, and `load_aliases` raises the plain one. Subclassing keeps both
  callers, both tests that assert `pytest.raises(FileNotFoundError)`, and the
  alias-table fallback working unchanged, while carrying the two fields the
  message needs. A fresh exception hierarchy would have bought nothing and
  rewritten three call sites.
- **The stage checks first; the library function refuses second.** R1005 asks a
  stage to *refuse to run*, which must happen before it does its work — today
  `commands/estimate.py` writes the bundles before `project` is ever called, so
  a refusal raised inside `project` would arrive after the writing. Hence the
  up-front check in the command. `project` separately loses its `else 0`
  branch, because a function that reads a file must not substitute a value when
  the read fails; that is not the same duty and it is the one BL-7 recorded.
- **Checks run in pipeline order.** `index.jsonl`, then `data/transcripts/`,
  then `selected.jsonl` — so an owner who has run nothing is told to run
  `index`, not the last stage in the chain. The one exception is inside
  `select_all`, where the existing alias-table check keeps its current position
  ahead of the new one, so a stage missing both still names the table.
- **Exit code 1 and a plain printed message**, matching every refusal the built
  commands already have, and satisfying R1005's "observable directly in the
  command's exit and message".

## The work, sliced

Three, one per stage that gains behaviour, each observable on its own from the
command line. **Sequential**: slice 1 introduces `artifacts.py`, which slices 2
and 3 import. Slices 2 and 3 touch disjoint source and test files and differ
only in sharing `docs/architecture.md`; if they are built in parallel, whichever
lands second carries that rebase. A slice that built the helper alone would be
horizontal — a mechanism with nothing observing it.

## Slice 1 — `estimate` refuses instead of understating

- **Delivers:** `find-best-mobo estimate` with no `data/index.jsonl` exits 1
  saying which artifact is absent and that `index` produces it, prints no
  projection, and writes no bundles — BL-7's measured defect, gone. The same for
  an absent `data/transcripts/` (naming `fetch`) and an absent
  `data/selected.jsonl` (naming `select`, as today). `find-best-mobo fetch`
  creates `data/transcripts/` whether or not it caches anything, so the
  directory's absence means fetch has not run. An index, cache or selection file
  that is present but empty still projects real zeros and exits 0. Covers R1005
  in part.
- **Files:** `src/find_best_mobo/artifacts.py`, `src/find_best_mobo/estimate.py`, `src/find_best_mobo/commands/estimate.py`, `src/find_best_mobo/commands/fetch.py`, `tests/test_artifacts.py`, `tests/test_estimate.py`, `tests/test_transcripts.py`, `docs/architecture.md`
- **Estimate:** ~270 lines

### Signatures

```python
class MissingArtifact(FileNotFoundError):
    path: Path
    description: str
    produced_by: str

    def __init__(self, path: Path, description: str, produced_by: str) -> None: ...
    def message(self) -> str: ...


def require_file(path: Path, description: str, produced_by: str) -> Path: ...
def require_directory(path: Path, description: str, produced_by: str) -> Path: ...
```

Per **OD-12**, the module of every shared type this slice touches:
`MissingArtifact`, `require_file` and `require_directory` are new and live in
`src/find_best_mobo/artifacts.py` — a module of its own rather than
`config.py`, because every stage imports it and it must not drag configuration
into anything that only needs a path check. `Projection` and `project` stay in
`src/find_best_mobo/estimate.py`; `Video` and `read_index` in
`src/find_best_mobo/index.py`; `Selection` and `read_selected` in
`src/find_best_mobo/select.py`; `Transcript` and `Cue` in
`src/find_best_mobo/transcripts.py`; `FetchFailure` and `HaltTriggered` in
`src/find_best_mobo/ledger.py`. **`project`, `render_projection`, `fetch_all`
and both `run` functions keep the signatures they have** — they are listed here
only to say that theirs do not change.

### Behaviour the signatures cannot carry

- **`MissingArtifact` is constructed as a `FileNotFoundError` would be**:
  `super().__init__(errno.ENOENT, os.strerror(errno.ENOENT), str(path))`, so
  `.errno` and `.filename` carry what every existing handler already reads, and
  the three named attributes ride alongside. Nothing catches it as anything
  narrower than `FileNotFoundError` in this slice; the point of the subclass is
  that it does not have to.
- **`message()` is the one shape**, and it is the sentence R1005 asks for:
  `No {description} at {path}. Run \`find-best-mobo {produced_by}\` first.`
  Descriptions used by this plan: `index`, `cached transcripts`, `selections`.
  `require_directory` uses the same word "at" as `require_file` — one shape is
  worth more than a preposition, and nothing asserts on the exact string.
- **`require_file` raises on a path that is not an existing file**;
  `require_directory` raises on a path that is not an existing directory. Both
  return the path on success, so a caller can write
  `path = require_file(...)`. A path of the wrong kind — a file where a
  directory is expected — is treated as absent rather than as a separate error
  class: the owner's remedy is the same, and inventing a second message for a
  state nobody has hit is speculative.
- **`project` loses its forgiving branch.** `videos_indexed` is counted from
  `read_index` after `require_file(index_path, "index", "index")`, with the
  `if index_path.exists() else 0` deleted. Its docstring's second paragraph,
  which currently *argues for* the zero ("losing the whole projection over one
  absent denominator helps nobody"), is replaced with R1005's reasoning: a
  projection the owner spends against must never understate itself because an
  input was absent. Everything else in `project` is untouched, so the
  blind-written `TestProject` suite that pins every other projected number keeps
  passing unedited.
- **`commands/estimate.py` checks before it works.** At the top of `run`, in
  pipeline order: `require_file(data_dir / "index.jsonl", "index", "index")`,
  `require_directory(data_dir / "transcripts", "cached transcripts", "fetch")`,
  `require_file(data_dir / "selected.jsonl", "selections", "select")`, all
  inside one `try` that catches `MissingArtifact`, prints `message()` and
  returns 1. The existing `try`/`except FileNotFoundError` around
  `read_selected` is retired: the check above it now covers that case, and the
  hand-written message it printed becomes `message()`'s.
- **Nothing is written on a refusal.** No bundles directory, no bundle files —
  the checks run before `pack_bundles`. The existing
  `test_a_missing_selected_file_writes_no_bundles` already pins this for one
  artifact; the slice extends it to the other two.
- **`_excerpts_for` keeps tolerating a per-video missing transcript.** A video
  selected on its title with no caption track has nothing to excerpt and is not
  an error (R2, R24). This slice changes only what happens when the *cache
  itself* is absent, and a reviewer should check that the per-video tolerance
  survives.
- **`commands/fetch.py` creates the cache directory** with
  `(config.data_dir / "transcripts").mkdir(parents=True, exist_ok=True)` after
  the index check and before `fetch_all`, so it also exists when the run halts
  (R24) part-way — fetch *ran*, and the artifact reflects that. Its own index
  refusal is rewritten to use `require_file`, so all four stages print the same
  shape. `fetch_all` and `_write_cache` are untouched; the `mkdir` in
  `_write_cache` stays, because `transcripts.py` must not depend on a command
  having run first.
- **What the tests must pin.** In `tests/test_artifacts.py`, against real
  `tmp_path` files: `require_file` returns the path for a file that exists and
  raises for one that does not; `require_directory` likewise, and specifically
  that an **empty directory passes** — the R1005 sentence this module exists to
  encode; the raised object `isinstance`s as `FileNotFoundError`, carries
  `filename` and `errno`, and its `message()` contains the path, the description
  and the producing command's name; a path of the wrong kind raises.
  In `tests/test_estimate.py`, through the real `run`: with no index, exit 1, a
  message naming `index`, no `Traceback`, and no `data/bundles/` on disk; the
  same for an absent `data/transcripts/` naming `fetch`; `project` called
  directly with no index raises `MissingArtifact`; an **empty** index file still
  projects `videos_indexed=0` and exits 0 (the existing
  `test_nothing_at_all_projects_zeros` and
  `test_no_selections_at_all_still_returns_zero_and_prints`, unchanged in
  intent); and a state with all three artifacts present behaves exactly as it
  does today. In `tests/test_transcripts.py`, through the real fetch command:
  a run that caches nothing still leaves `data/transcripts/` on disk, and so
  does a run that halts.
- **The existing tests that move, and why.** In `tests/test_estimate.py`,
  `test_a_missing_selected_file_returns_one_naming_what_to_run_first` and
  `test_a_missing_selected_file_writes_no_bundles` build an index but no cache,
  so under pipeline-order checking they would now be told to run `fetch`. Both
  gain a line creating the empty cache directory, which restores exactly the
  state each is about; neither assertion is weakened.
  `test_no_selections_at_all_still_returns_zero_and_prints` gains the same line
  and keeps expecting 0 — an empty corpus is a real value, and this test is the
  one that says so. The commit making these edits states that reason, per
  `AGENTS.md`.
- **`docs/architecture.md`**: the components table gains a row for
  `artifacts.py` (the shared refusal: what each stage requires of the one before
  it); "Estimating the cost, and stopping" gains a step 0 — the stage checks its
  three upstream artifacts and refuses before cutting anything, citing
  OD-9/R1005; "Fetching transcripts" records that the stage creates
  `data/transcripts/` whether or not it caches anything; the
  `data/transcripts/<video_id>.json` entry under "State and storage" says the
  directory's presence means fetch has run and its absence means it has not; and
  "Known rough edges" loses nothing but gains the distinction R1005 draws —
  absence is an error, emptiness is a value — stated once, where the next agent
  reading a zero will need it.

## Slice 2 — `select` refuses before `fetch` has run

- **Delivers:** `find-best-mobo select` with an index but no
  `data/transcripts/` exits 1, names the cache and the `fetch` stage, and writes
  no `data/selected.jsonl` — instead of printing a threshold report in which no
  video could possibly have passed the threshold. With the cache present and
  empty it runs normally and reports what that really is: title hits only, every
  other video excluded at zero distinct canonicals. A missing index or alias
  table refuses exactly as it does today. Covers R1005 in part.
- **Files:** `src/find_best_mobo/select.py`, `src/find_best_mobo/commands/select.py`, `tests/test_select.py`, `docs/architecture.md`
- **Estimate:** ~130 lines

### Signatures

```python
def select_all(config: Config) -> tuple[Selection, ...]: ...
```

No type changes. Per **OD-12**: `Selection`, `ThresholdReport`, `TITLE_HIT`,
`THRESHOLD` and `EXCLUDED` stay in `src/find_best_mobo/select.py`;
`MissingArtifact`, `require_file` and `require_directory` in
`src/find_best_mobo/artifacts.py` (slice 1); `Video` in
`src/find_best_mobo/index.py`; `Transcript` in
`src/find_best_mobo/transcripts.py`. `select_video`, `threshold_report`,
`write_selected`, `read_selected` and `run` all keep the signatures they have.

### Behaviour the signatures cannot carry

- **`select_all` gains one check, in this order:** the index (now via
  `require_file`, replacing the hand-built `FileNotFoundError` that exists only
  to carry `filename`), then `load_aliases` as today, then
  `require_directory(config.data_dir / "transcripts", "cached transcripts",
  "fetch")`. The cache check goes last on purpose: the alias-table refusal
  already exists and this plan is not reordering it, so a stage missing both the
  table and the cache still names the table, and
  `test_a_missing_alias_table_returns_one_naming_it` keeps passing untouched.
- **`select_all`'s docstring is corrected.** Its "a missing transcript cache is
  not an error" sentence becomes the distinction R1005 draws: a missing
  transcript *for a video* is not an error, because a video with no captions can
  still be selected on its title; a missing *cache directory* is, because fetch
  has not run and no video could pass the threshold. Getting this sentence
  wrong is how the tolerance gets restored by accident later.
- **`commands/select.py`'s `_missing` shrinks.** It prints
  `error.message()` when the error is a `MissingArtifact`, and keeps exactly
  today's alias-table wording for the plain `FileNotFoundError` that
  `load_aliases` raises. The generic trailing fallback stays as the last
  resort. Nothing else in the command changes: the same `except
  FileNotFoundError` catches both, which is what the subclass bought.
- **Per-video tolerance is unchanged and is the load-bearing negative.** With
  the cache present, a video with no cached transcript is still selected on its
  title, still yields no mentions, and still lands in `selected.jsonl` — the
  existing `test_a_video_with_no_cached_transcript_is_still_selected` and
  `test_a_title_hit_survives_a_missing_transcript` are the tests that must not
  change meaning.
- **What the tests must pin**, through the real `run` and `select_all` against
  `tmp_path`:
  - **The refusal.** An index and an alias table with no `data/transcripts/`
    directory: `run` returns 1, the message names `fetch`, there is no
    `Traceback`, and `data/selected.jsonl` does not exist afterwards.
    `select_all` raises `MissingArtifact` in the same state.
  - **Emptiness is a value.** The same corpus with an empty `data/transcripts/`
    directory returns 0, writes a record for every pending video, and reports
    the title hits as includes and everything else as excluded at zero distinct
    canonicals. This is the test that separates R1005's two sentences.
  - **Order.** Missing index and missing cache together names the index;
    missing table and missing cache together names the table.
  - **Nothing else moves.** The nine-video `build_corpus` selections, records
    and printed report are byte-for-byte what they are today.
- **The existing tests that move, and why.** Three `TestSelectAll` tests build
  an index with no transcripts at all —
  `test_a_title_hit_survives_a_missing_transcript`,
  `test_order_follows_the_index_file` and
  `test_the_selection_carries_the_full_video_record` — as do the two
  `test_a_missing_index_*` command tests, which are unaffected because the index
  is checked first. Each of the three gains one line creating the empty cache
  directory, which is the state a real `fetch` would have left and is not what
  any of them is testing. The commit says so.
- **`docs/architecture.md`**: "Narrowing the corpus" gains the refusal as its
  first step, with the reason — a threshold report built with no corpus
  understates the lever it exists to measure — citing OD-9/R1005; the selection
  row in the components table says the stage requires the index, the alias table
  and the transcript cache before it decides anything.

## Slice 3 — `aliases --check` stops calling an empty cache a missing one

- **Delivers:** `find-best-mobo aliases --check` against a present-but-empty
  `data/transcripts/` prints its normal report — every canonical at zero videos,
  zero mentions, `NEVER MATCHED`, and the closing summary naming all of them —
  and exits **0**, where today it exits 1 and tells the owner to run `fetch`.
  Against an absent directory it still refuses, now through the shared helper
  and with the shared message. The alias-table and index refusals are unchanged.
  Completes R1005.
- **Files:** `src/find_best_mobo/commands/aliases.py`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~95 lines

### Signatures

```python
def run(config: Config, args: Namespace) -> int: ...
```

No type or signature changes: the slice replaces one predicate and one message.
Per **OD-12**: `Alias`, `Mention`, `compile_matcher`, `find_mentions` and
`find_title_hits` stay in `src/find_best_mobo/aliases.py`; the private `_Tally`
stays in `src/find_best_mobo/commands/aliases.py`; `MissingArtifact` and
`require_directory` come from `src/find_best_mobo/artifacts.py` (slice 1).

### Behaviour the signatures cannot carry

- **The predicate changes from contents to existence.**
  `if not any(cache_dir.glob("*.json"))` becomes
  `require_directory(cache_dir, "cached transcripts", "fetch")`, inside a `try`
  that catches `MissingArtifact`, prints `message()` and returns 1 — the same
  handler shape as the other two stages. The index check becomes `require_file`
  in the same motion. The alias-table check keeps its own wording and its
  position first, for the reason slice 2 gives.
- **An empty cache produces a real report, not a special case.** `_scan` already
  handles a video with no cached transcript (`mentions = ()`), so an empty cache
  needs no new branch anywhere: every tally stays at zero, every canonical sorts
  into the `NEVER MATCHED` list, and the closing "Either the spelling is wrong
  or nobody says it" line prints. That the report is *useless* in that state is
  not a reason to hide it — R1005's point is that it is not a *lie*, and the
  numbers say plainly that nothing was scanned.
- **What the tests must pin**, through the real `run` against `tmp_path`:
  - **Emptiness is a value.** A table, an index with pending videos, and an
    empty `data/transcripts/` directory: exit 0, every canonical listed at
    `videos=0 titles=0 mentions=0 forms: none`, marked `NEVER MATCHED`, and the
    summary naming all of them.
  - **Absence is an error.** The same state with no directory at all: exit 1,
    the message names `fetch`, no `Traceback`.
  - **Nothing else moves.** The missing-table and missing-index refusals return
    1 and name what they name today; the populated-corpus report is what it is
    today.
- **The existing test that moves, and why.**
  `test_empty_transcript_cache_returns_one_naming_what_to_run` sets up an
  *absent* directory while calling it empty. It is renamed to say "absent" and
  keeps every assertion; the new empty-directory test above takes the name it
  was using. The commit records that the rename is R1005 making two states
  distinct that the test's name conflated.
- **`docs/architecture.md`**: "Inspecting the alias table" records that the
  stage requires the table, the index and the transcript cache *directory*, and
  that an empty cache yields a report of zeros rather than a refusal, citing
  OD-9/R1005; the `aliases` row in the components table says the same in one
  clause.

## Out of scope

- **Any flag or configuration key that overrides a refusal.** R1005 makes
  absence an error; a lever that turns the error back into a zero would restore
  BL-7 behind an option, and the checkpoint's whole value is that the number
  cannot be quietly understated.
- **Detecting a partial or stale cache.** A `fetch` halted by R24 leaves a real
  but incomplete `data/transcripts/`, and a later stage will project from it
  without complaint. That is present-but-incomplete, which is neither of the two
  states R1005 distinguishes, and R24's halt plus the failure ledger are what
  make it visible. If a run is later found to have spent against a silently
  partial corpus, that is logged evidence for a `BL-<n>`, not a check taken
  here.
- **`data/failures.jsonl`.** BL-1's stale-ledger objection is a different
  defect — a present artifact that is out of date — and no stage reads the
  ledger as an upstream input. Untouched.
- **`config.toml`.** Its absence is deliberately not an error: `config.py`
  supplies in-code defaults so an absent file is never a crash, and nothing
  produces it.
- **`data/bundles/`.** Produced by `estimate` and read by a stage that does not
  exist yet. When it does, R1005 applies to it by the same rule.
- **OD-10/R1006's dispatcher forwarding and OD-11/R1007's move of the alias
  table.** Both touch the same command modules and both are separately planned
  or plannable; this plan reads the table wherever each stage reads it today and
  adds no flag that would need forwarding.
- **`scripts/run.sh`.** Its `ALL_STAGES` order is already
  index → fetch → select → estimate and it runs under `set -e`, so a refusal
  stops the pipeline loudly with no change. Running a later stage alone against
  a `data/` that never had the earlier ones is precisely the case R1005 wants to
  fail.
- **Revising `docs/plans/corpus-and-checkpoint.md`.** Its slice 5 text and
  contract are what BL-7 says were silent on this case; that plan sits behind
  `CODEOWNERS` and **OD-12** already commissions its revision, which this
  change can ride alongside the renames `description-signal` and
  `caption-split-aliases` already owe it.
