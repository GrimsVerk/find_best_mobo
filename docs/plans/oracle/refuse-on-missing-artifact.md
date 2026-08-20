---
slug: refuse-on-missing-artifact
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1005]
---

# A stage whose input is absent refuses instead of understating — Plan

Implements **OD-9** (`docs/DESIGN.oracle.md`), which adds **R1005** from the
evidence in **BL-7**. `project` counts `videos_indexed` as 0 when
`data/index.jsonl` is absent, so `estimate` still prints a projection whose
denominator reads as a real number rather than an absence — and that projection
is the number the owner is asked to spend against (R7). The same silence sits
one input over: with no `data/transcripts/` at all, the same command prints a
projection of zero excerpt characters and exit code 0.

## Summary

One guard module, and every stage checks its upstream artifacts before it does
any work. Three slices, ~490 lines, **sequential**.

- **The refusal is one mechanism, not four spellings.** A new
  `src/find_best_mobo/artifacts.py` names each artifact, its path, and the
  subcommand that produces it; stages ask it, and a missing one raises.
- **`estimate` refuses when the index is absent** — exit 1, no bundles written,
  message naming `data/index.jsonl` and `find-best-mobo index`. `project`'s
  forgiving-zero branch becomes a raise, so no later caller can restore it.
- **An empty index still prints a projection**, `0 videos indexed and pending`,
  exit 0. Absence and emptiness read differently, which is OD-9's point.
- **The transcript cache is an upstream artifact too.** With `data/transcripts/`
  absent, `estimate` and `select` refuse naming `fetch`, instead of quietly
  losing 100% of the excerpt characters and every body mention. So **`fetch`
  creates that directory even when it caches nothing** — otherwise absence and
  emptiness stay indistinguishable and a legitimate all-failed run is refused.
- **Nothing about the message or the exit changes**: today's wording, on stdout,
  exit 1 — now issued from one place. A hand-authored input (the alias table)
  names no producing stage and keeps its "restore it" remedy.
- **Not done:** no new config lever, no `--force` escape hatch, no move to
  stderr, no exit-code taxonomy, no repair or auto-run of the missing stage, no
  change to per-video transcript absence (the failure ledger still governs it,
  R2/R24), and nothing about corrupt artifacts — absence is the subject.

**What this costs you.**

1. **A workflow that used to print now refuses.** An `index` + `select` run with
   no transcripts fetched prints a zero-character projection today and exits 1
   after this. That is the defect, but it is a visible behaviour change.
2. **`aliases --check` relaxes in the other direction**: a present-but-empty
   cache reports every canonical as never matched instead of refusing. The one
   thing here R1005 does not settle — filed as **BL-18**, proceeded on.
3. **`docs/plans/corpus-and-checkpoint.md` slice 5 is now partly wrong** — its
   `project` contract says nothing about refusing, and that silence is what BL-7
   recorded. **OD-12** already commissions its revision; this rides it.

**What I need you to rule on:** BL-18 only, already proceeding on its default.

## Uncertainties

One, LOW, proceeded on and filed — `docs/BACKLOG.md`, in this commit.

- **Q:** Does R1005 bind `aliases --check`, which the repository calls a
  diagnostic rather than a pipeline stage (`scripts/run.sh`: "the pipeline is
  four stages, not five"), and which today refuses when the transcript cache
  directory exists but holds no files? — **risk:** LOW — it is one condition in
  one command: no slice boundary moves (slice 3 exists for `select` either way),
  no Signatures block changes, no artifact on disk changes shape, and reversing
  it is restoring one `if`. — **proposed:** yes, bind it. R1005's second
  sentence — "a present-but-empty artifact is a real value and is reported as
  what it is" — is the half that this command breaks, and an empty corpus
  reported as every-canonical-never-matched is a true report, loudly phrased.
  `docs/architecture.md` already calls it "the inspection stage".
  **Ruling:** proceeded on the default (LOW), filed as **BL-18** for the
  oracle's next cycle.

### Derivations, not uncertainties

Places R1005 fixes the behaviour and leaves the mechanism here. Shown rather
than asserted, because the two that came closest to the line are the ones a
reviewer would otherwise have to reconstruct.

- **The transcript cache counts as an upstream artifact of `estimate` and
  `select`.** R1005's rule is general — "a pipeline stage whose upstream
  artifact is missing refuses to run, naming the absent artifact and the stage
  that produces it" — and names the index case only as its "in particular".
  `data/transcripts/` is read by both stages and produced by `fetch`, so it fits
  the rule's shape exactly, including the clause about naming a producing stage.
  OD-9's rationale is the confirming half: "a projection the owner spends
  against must never understate itself because an input was absent". An absent
  cache understates the projection by every excerpt character there is, which is
  a larger understatement than the one BL-7 measured.
- **A per-video missing transcript stays a non-error**, as it is today. The
  artifact is the cache; a video inside it is not one. R1005's own
  absence-versus-emptiness line draws that boundary one level up, R2 and R24
  give per-video gaps to the failure ledger, and OD-8 restates it ("a
  description cannot conjure a transcript"). This plan changes nothing there.
- **`fetch` creates its output directory whether or not it caches anything.**
  Today the directory appears on the first successful write, so a run in which
  every video failed leaves no directory — and "fetch never ran" and "fetch ran
  and produced nothing" are the same fact on disk, which is precisely the
  conflation R1005 forbids. Creating it up front is the minimal mechanism that
  makes R1005's distinction true, and it is a mechanism rather than a decision:
  the requirement demands the two read differently, not any particular way of
  telling them apart.
- **The guard runs before the stage does any work.** "Refuses to run" is
  R1005's phrase; a check that fires after bundles are on disk would be a
  refusal to *finish*. The built system already has this shape for the missing
  `selected.jsonl` case, which writes no bundles.
- **`project` raises rather than trusting its caller.** The command guards up
  front, so `project` can never see an absent index in the shipped path; it
  still asks, because the swallowed zero lived in `project` and BL-7 is the
  record of what a defensive default costs when nothing above it checks.
- **The message keeps its wording, its stream and its exit code.** Every
  refusal in the tree today prints to stdout and returns 1; R1005 asks only that
  the refusal be observable "in the command's exit and message", not that either
  move. Changing the stream would rewrite passing assertions in three test files
  to buy nothing this decision asked for. One wording does change: `aliases
  --check` says "under `<dir>`" where the shared message says "at `<dir>`".
- **A hand-authored input names no producing stage.** The alias table has no
  stage that writes it, so `produced_by` is `None` and the message keeps today's
  remedy — "It ships with the repository; restore it." R1005's naming clause is
  satisfied by naming the artifact; inventing a command that does not exist
  would not be.
- **`artifacts.py` imports only `config`.** It is the one module that says where
  each artifact lives, so everything else imports it and it imports nothing back
  — a guard module that pulled in the network boundary to learn a directory name
  would invert the dependency it exists to simplify. `transcripts.cache_path` is
  rebuilt on top of it so the cache's location is stated once.
- **`index` is out of scope.** Its upstream is the channel listing, not an
  artifact on disk; a listing that fails is already the ledger's and the halt
  triggers' business (R24).
- **No new configuration lever.** R17 enumerates the cost-saving levers and this
  is not one of them; R1005 states the rule unconditionally.
- **`scripts/run.sh` needs no change.** It is `set -euo pipefail`, so a stage
  that exits 1 stops the run there — the refusal already propagates.

## The work, sliced

Three, **sequential**: slice 2 adds a guard to the command slice 1 rewrites, and
slice 3 reuses the module slice 1 introduces. They overlap on
`src/find_best_mobo/commands/estimate.py`, `tests/test_estimate.py` and
`docs/architecture.md`, so they are not parallel and are not written as if they
were. Each is observable without reading code: slice 1 is the BL-7 defect gone,
slice 2 is the same defect on the other input, slice 3 is every remaining stage
speaking with one voice.

## Slice 1 — The projection refuses instead of understating

- **Delivers:** `find-best-mobo estimate` with no `data/index.jsonl` prints ``No index at data/index.jsonl. Run `find-best-mobo index` first.``, exits 1, and writes no bundles and no `data/bundles/` directory. With an index present but empty it prints the projection as before, `0 videos indexed and pending`, exit 0. A missing `data/selected.jsonl` refuses with today's wording, now from the shared mechanism. Covers R1005 in part.
- **Files:** `src/find_best_mobo/artifacts.py`, `src/find_best_mobo/estimate.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_artifacts.py`, `tests/test_estimate.py`, `docs/architecture.md`
- **Estimate:** ~190 lines

### Signatures

```python
@dataclass(frozen=True)
class Artifact:
    label: str
    path: Path
    produced_by: str | None  # the subcommand that writes it; None for a tracked input


class MissingArtifact(Exception):
    def __init__(self, artifact: Artifact) -> None:
        self.artifact: Artifact


def require(artifact: Artifact) -> Path: ...
def index_artifact(config: Config) -> Artifact: ...
def selections_artifact(config: Config) -> Artifact: ...
def transcript_cache_artifact(config: Config) -> Artifact: ...
def alias_table_artifact(config: Config) -> Artifact: ...
```

Per **OD-12**, the module of every shared type this slice touches: `Artifact`,
`MissingArtifact` and all five functions are new and live in
`src/find_best_mobo/artifacts.py`, which imports `Config` from
`src/find_best_mobo/config.py` and nothing else from this package.
`Projection`, `project` and `render_projection` stay in
`src/find_best_mobo/estimate.py` with the signatures they have today;
`Bundle` in `src/find_best_mobo/bundle.py`; `Selection` and `EXCLUDED` in
`src/find_best_mobo/select.py`; `Config` in `src/find_best_mobo/config.py`.
`transcript_cache_artifact` and `alias_table_artifact` are declared here, with
the rest of the table, and are first used in slices 2 and 3.

### Behaviour the signatures cannot carry

- **`require` checks existence and nothing else.** `Path.exists()` is true for a
  file and for a directory, so one helper covers both artifact kinds. It never
  creates, never reads content, and returns the path so a caller can use it in
  place: `path = require(index_artifact(config))`. A present artifact of the
  wrong kind, or an unreadable one, is not this decision's subject and is left
  to fail where it fails today.
- **`MissingArtifact` is a deliberate stop, not a crash**, in the shape
  `HaltTriggered` already set in `ledger.py`: the command catches it, prints one
  line, and returns non-zero without a traceback reaching the owner. Its
  `str()` carries the same text as the printed line.
- **The message has exactly two forms**, built from the artifact:
  - with a producing stage — ``No {label} at {path}. Run `find-best-mobo {produced_by}` first.``
  - without one — `No {label} at {path}. It ships with the repository; restore it.`

  Labels are `index`, `selections`, `cached transcripts` and `alias table`, so
  the four printed lines are the four in the tree today, one wording aside (see
  the derivations). Paths print as configured, not resolved to absolute.
- **The artifact table is the only place that says where things live**:
  `index_artifact` → `config.data_dir / "index.jsonl"`, produced by `index`;
  `selections_artifact` → `config.data_dir / "selected.jsonl"`, produced by
  `select`; `transcript_cache_artifact` → `config.data_dir / "transcripts"`,
  produced by `fetch`; `alias_table_artifact` → `config.data_dir /
  "aliases.toml"`, produced by nobody. That last path is where the table lives
  **today**; **OD-11/R1007 moves it**, and this plan neither implements nor
  blocks that — it gives it one line to change instead of three call sites.
- **`commands/estimate.py` guards before it works.** `require` is called for the
  index and then the selections at the top of `run`, before `read_selected`,
  before any excerpt is cut and before `write_bundles` creates a directory. Both
  absent means one message, the index's, because it is the earlier stage and the
  operator's next command. The existing `FileNotFoundError` branch around
  `read_selected` goes away; `MissingArtifact` replaces it, caught once around
  the guard.
- **`project` stops swallowing.** The `if index_path.exists() else 0` expression
  becomes `require(index_artifact(config))`, and the docstring paragraph
  defending the forgiving zero is replaced by one citing OD-9/R1005 and BL-7 —
  the comment that justified the defect must not outlive it. The signature does
  not change and the return type does not change; the function now raises.
- **An empty index is a real value.** A zero-byte `index.jsonl`, and an index
  whose every record is excluded, both yield `videos_indexed=0` and a printed
  projection at exit 0. `test_nothing_at_all_projects_zeros` already pins this
  and must keep passing unchanged.
- **What the tests must pin:** `require` returns the path for a present file and
  for a present directory, and raises for an absent one; both message forms,
  including the exact command name in the first; `estimate` with no index exits
  1, names `index`, prints no projection line and leaves no `data/bundles/`;
  `estimate` with an empty index exits 0 and prints `0 videos indexed`;
  `estimate` with no selections still exits 1 naming `select`; with both absent
  only the index line is printed; `project` raises `MissingArtifact` rather than
  returning a `Projection` when the index is absent; no traceback reaches
  stdout in any of these.
- **`docs/architecture.md`**: a Components row for `artifacts.py` — "naming each
  artifact, where it lives, and the stage that produces it, so a stage refuses
  on an absent input instead of counting it as zero (OD-9/R1005)"; "Estimating
  the cost, and stopping" gains a step 1 for the guard, renumbering what
  follows; the `data/index.jsonl` entry under "State and storage" says an absent
  index is an error and an empty one is a corpus of no videos.

## Slice 2 — A projection with no transcripts refuses too

- **Delivers:** after `index` and `select` with `fetch` never run, `estimate` refuses naming `fetch`, exits 1 and writes no bundles, instead of printing a projection of zero excerpt characters at exit 0. After a `fetch` in which every video failed, `data/transcripts/` exists and is empty, `estimate` runs, and the projection prints zeros honestly with the reasons in `data/failures.jsonl`. One selected video whose transcript is missing is still not an error. Covers R1005 in part.
- **Files:** `src/find_best_mobo/transcripts.py`, `src/find_best_mobo/commands/fetch.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_transcripts.py`, `tests/test_estimate.py`, `docs/architecture.md`
- **Estimate:** ~150 lines

### Signatures

```python
def ensure_cache_dir(config: Config) -> Path: ...
def cache_path(video_id: str, config: Config) -> Path: ...
```

Per **OD-12**: `ensure_cache_dir` is new and lives in
`src/find_best_mobo/transcripts.py`, beside `cache_path`, because that module
owns the on-disk cache and is where "reruns never refetch" already lives.
`cache_path` keeps its signature and is rebuilt on
`transcript_cache_artifact(config).path` so the directory is named once.
`Transcript`, `Cue` and `NoCaptions` stay in
`src/find_best_mobo/transcripts.py`; `FetchFailure`, `HaltTriggered` and
`Ledger` in `src/find_best_mobo/ledger.py`, with today's `FetchFailure`
re-export from `transcripts.py` untouched; `Artifact`, `MissingArtifact`,
`require` and `transcript_cache_artifact` in
`src/find_best_mobo/artifacts.py` from slice 1.

### Behaviour the signatures cannot carry

- **`ensure_cache_dir` is `mkdir(parents=True, exist_ok=True)` and a returned
  path.** Idempotent, safe on every run, and it creates only the directory —
  never a placeholder file, which would make an empty cache indistinguishable
  from a cache with one junk entry.
- **`commands/fetch.py` calls it once**, after its own index guard and before
  the first fetch, so a run that halts on its first video still leaves the
  evidence that `fetch` ran. Its ad-hoc `index_path.exists()` check becomes
  `require(index_artifact(config))` with the shared message — the wording it
  prints today, so no output changes.
- **`_write_cache` keeps its own `mkdir`.** Belt and braces: it is what makes
  `fetch_transcript` → `_write_cache` usable without the command around it, and
  removing it would couple a library function to a stage's setup.
- **`commands/estimate.py` requires the cache between the index and the
  selections**, matching pipeline order — `index`, `fetch`, `select` — so the
  named remedy is always the earliest stage the operator still has to run.
- **A present-but-empty cache changes nothing downstream.** `estimate` proceeds,
  every selected video yields no excerpts, `write_bundles` writes none, and the
  projection prints its zeros. That path is already exercised by
  `test_a_selection_whose_transcript_is_missing_is_not_an_error`, which must
  keep passing once its fixture creates the directory.
- **Nothing backfills and nothing refetches.** This slice adds a `mkdir` and two
  guards; the cache-hit skip, the ledger, and the halt triggers are untouched.
- **What the tests must pin:** `fetch` creates `data/transcripts/` when every
  video fails and when the pending list is empty, and when it halts on the first
  video; `fetch` with no index refuses with the shared message and exit 1;
  `cache_path` still resolves to `<data_dir>/transcripts/<video_id>.json` for a
  configured `data_dir`; `estimate` with no transcripts directory exits 1,
  names `fetch`, and leaves no `data/bundles/`; `estimate` with an empty
  transcripts directory exits 0 and prints `0 characters of excerpt text`;
  `estimate` with one video's transcript deleted still exits 0 and bundles the
  rest; with the index and the cache both absent, only the index line prints.
- **`docs/architecture.md`**: "Fetching transcripts" says the stage creates the
  cache directory before fetching, and that its absence therefore means the
  stage never ran; the `data/transcripts/<video_id>.json` entry under "State and
  storage" gains that distinction; "Estimating the cost, and stopping" names the
  cache in its guard step.

## Slice 3 — Every remaining stage refuses through the same mechanism

- **Delivers:** `select` refuses on an absent index, alias table or transcript cache — same wording, same exit code, one message per run — instead of a hand-built `FileNotFoundError` and a private message table. `aliases --check` does the same, and stops refusing when the cache directory is present but empty: it reports every canonical as never matched, which is what an empty corpus is. Completes R1005.
- **Files:** `src/find_best_mobo/select.py`, `src/find_best_mobo/commands/select.py`, `src/find_best_mobo/commands/aliases.py`, `tests/test_select.py`, `tests/test_aliases.py`, `docs/architecture.md`
- **Estimate:** ~150 lines

### Signatures

```python
def select_all(config: Config) -> tuple[Selection, ...]: ...
def run(config: Config, args: Namespace) -> int: ...
```

Per **OD-12**: both keep their modules and their signatures —
`select_all` in `src/find_best_mobo/select.py`, `run` in each of
`src/find_best_mobo/commands/select.py` and
`src/find_best_mobo/commands/aliases.py`. What changes is the exception
`select_all` raises: `MissingArtifact` from `src/find_best_mobo/artifacts.py`,
never a synthesized `FileNotFoundError`, so `errno` and `os` leave
`select.py`'s imports. `Selection`, `ThresholdReport`, `TITLE_HIT`, `THRESHOLD`
and `EXCLUDED` stay in `src/find_best_mobo/select.py`; `Alias` and `Mention` in
`src/find_best_mobo/aliases.py`; `Video` in `src/find_best_mobo/index.py`.

### Behaviour the signatures cannot carry

- **`select_all` requires index, alias table and cache, in that order**, before
  it reads anything. The order is pipeline order, so the remedy named is the
  earliest stage still outstanding.
- **`commands/select.py` loses `_missing`.** Its three-branch filename sniffing
  is what the shared message replaces; the command catches `MissingArtifact`,
  prints, and returns 1. The alias-table line keeps today's "restore it" text.
- **`commands/aliases.py` keeps its guards but stops owning their wording**, and
  its `not any(cache_dir.glob("*.json"))` test becomes `require`, which is the
  behaviour change: the directory's *absence* refuses, its *emptiness* does not.
  The `--check` usage message and its exit code 2 are untouched — a missing flag
  is not a missing artifact.
- **An empty cache produces the report, loudly.** Every canonical lands under
  `NEVER MATCHED` and the closing summary says so for all of them. That reads as
  alarming because it is, and it is true; the previous refusal said the same
  thing while looking like a setup error. **This is BL-18**, filed and
  proceeded on.
- **No stage acquires a guard it does not need.** `select` does not require
  `selected.jsonl` (it writes it), `aliases --check` does not require the
  selections (it never reads them), and `index` gains nothing at all.
- **What the tests must pin:** `select` with no index, with no alias table, and
  with no transcripts directory each exit 1 with the artifact named and the
  right remedy — `index`, "restore it", `fetch` — and write no
  `data/selected.jsonl`; with several absent, only the earliest prints;
  `select_all` raises `MissingArtifact` and not `FileNotFoundError`; `select`
  over a present-but-empty cache exits 0 and selects title hits only;
  `aliases --check` with an absent cache directory exits 1 naming `fetch`;
  `aliases --check` with a present-but-empty one exits 0 and lists every
  canonical as never matched; `aliases` without `--check` still exits 2 with the
  usage line.
- **`docs/architecture.md`**: the `aliases` and `select` rows in Components say
  each stage refuses on an absent input and reports an empty one, citing
  OD-9/R1005; "Known rough edges" gains one entry — an empty transcript cache
  makes every canonical read as never matched, which is honest and looks like a
  broken table, and the remedy is `find-best-mobo fetch`.

## Out of scope

- **The `index` stage.** Its upstream is the channel listing, not an artifact on
  disk; R24's ledger and halt triggers already govern a listing that fails.
- **Corrupt or malformed artifacts.** A damaged cache entry still reads as
  absent, a bad index line still fails where it fails today. OD-9 is about
  absence; corruption is a different decision and nobody has logged it.
- **Per-video transcript absence.** Unchanged, and deliberately: R2 and R24 give
  it to the failure ledger.
- **Any escape hatch.** No `--force`, no `--allow-missing`, no config key that
  restores the forgiving zero. R1005 says refuse.
- **Repairing or running the missing stage.** The message names the command; the
  operator runs it.
- **Moving the refusal to stderr, or giving refusals their own exit code.**
  Today's stdout and exit 1 are kept.
- **The alias table's location (OD-11/R1007)** and **the dispatcher's flag
  forwarding (OD-10/R1006)**. This plan touches `commands/aliases.py` and the
  alias table's path exactly once each, and leaves both decisions to their own
  plans; whichever lands second edits one line here.
- **Revising `docs/plans/corpus-and-checkpoint.md`**, whose slice 5 contract is
  silent on refusal and whose `project` signature no longer tells the whole
  story. **OD-12** commissions that revision; this plan does not carry it.
- **`data/failures.jsonl` and `data/bundles/`.** Outputs of the stages that
  write them, never upstream inputs, so no stage guards them.
