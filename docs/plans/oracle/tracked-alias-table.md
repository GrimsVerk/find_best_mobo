---
slug: tracked-alias-table
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1007]
---

# The alias table is a tracked input at a configured path — Plan

Implements **OD-11** (`docs/DESIGN.oracle.md`), which adds **R1007** from the
evidence in **BL-4** and **BL-6**. The alias table is hand-authored input, not
cached corpus, but it sits at `data/aliases.toml` inside the tree `.gitignore`
excludes because the corpus never enters git (R21) — surviving in the repository
only by a `git add -f` that every ignore-respecting tool misreads (BL-4). And no
plan ever said where it is loaded from, so two blind authors each guessed
`config.data_dir / "aliases.toml"` (BL-6). R1007 fixes both with one rule: *the
table is a git-tracked, hand-authored input living outside the gitignored corpus
directory — default `aliases.toml` at the repository root — and every loader
takes its path from configuration rather than assuming a location*.

## Summary

One new configuration key, one `git mv`, and the `git add -f` exception retired.

- **The path becomes a lever: `alias_table_path`**, a flat key in `config.toml`
  named after its `Config` field like every other, holding a **full path to the
  file** rather than a directory. Both loaders read it; neither builds a path.
- **The table stops following `data_dir`.** Today both loaders read
  `config.data_dir / "aliases.toml"`, so pointing `data_dir` at another cache
  silently moves the table with it. After this it does not — the table is input,
  the cache is not, and R1007's whole point is that they are different things.
- **The file moves with `git mv`, byte-identical**, from `data/aliases.toml` to
  `aliases.toml` at the repository root, and the default moves with it in the
  same slice. A fresh clone carries the table; nothing is force-added.
- **No fallback to the old path.** A configured table that is absent refuses
  exactly as it does today ("It ships with the repository; restore it"); nothing
  ever looks in `data/` again. Two homes is the ambiguity BL-6 recorded.
- **A new test shells out to `git`** to prove the table is tracked and not
  ignored, with `data/` as its negative control, skipping with a stated reason
  where the tree is not a git checkout. This is the ratchet: no existing check
  would notice the table falling back out of git, which is the defect itself.
- **It costs you:** one line in `config.toml`; two edited assertions in a
  blind-written config test, because slice 2 flips the default slice 1 pins; and
  a test that runs `git` as a subprocess, which the offline suite has none of
  today.
- **Not done here:** no repository-root discovery (every path in this CLI is
  relative to the working directory, `config.toml` included); no `--aliases`
  flag; no change to the missing-table wording; no `.gitignore` edit — `data/`
  stays ignored and there is no negation rule to remove; the table is not
  packaged under `src/`, which OD-11 rejected by name.

Two slices, ~225 lines, **sequential** — slice 1 introduces the key, slice 2
moves the file and flips its default. Slice 1 shares `commands/aliases.py`,
`commands/select.py` or `select.py` with three other oracle plans; none of them
is built in parallel with this one.

**What I need you to rule on** — nothing here is unruled. Two things are in the
list above because they cost you something rather than because they are open:
the **`data_dir` decoupling**, and the **`git` subprocess** in a suite that has
run on fixtures alone until now.

## Uncertainties

**None: every decision derived from the design.** R1007 fixes the behaviour —
tracked, outside `data/`, default `aliases.toml` at the root, path from
configuration, migration in one change — and leaves the mechanism to the plan.
Nothing is filed to `docs/BACKLOG.md` by this plan.

### Derivations, not uncertainties

Each is a place the design layer fixes the behaviour and delegates the
mechanism, recorded so a reader sees the derivation rather than a decision
appearing from nowhere.

- **The key is named `alias_table_path`, after its field.** `config.toml`'s own
  header states the convention — "flat top-level keys named after the `Config`
  fields" — and `load_config` reads every value by its field name. The name is
  not free-standing style; picking anything else breaks the one rule that file
  states about itself.
- **The path is relative to the working directory**, exactly as `data_dir` and
  `--config`'s own `config.toml` default already are. R1007 says "at the
  repository root", and the repository root is where this CLI is run from:
  `scripts/run.sh` opens with `cd "$(dirname "$0")/.."`. Inventing root
  discovery for one key while `config.toml` and `data_dir` keep the existing
  convention would leave three paths resolving three ways.
- **The key holds a full path, not a directory.** R1007 names a file
  (`aliases.toml`), and a directory key would re-create exactly the "assume the
  filename" half of BL-6 one level up.
- **`Config` carries an in-code default for the new field.** Every other default
  lives only in `load_config`, and this one lives in both — as one module
  constant used twice, with a test pinning them equal. The reason is blast
  radius: `Config` is frozen with no defaults, so a required field would edit
  the ten `make_config` test helpers across ten files, several of which other
  in-flight plans are already editing, for a field eight of them never read. The
  contract `config.py` states about itself ("a missing key is never a crash") is
  unchanged.
- **The move and the default flip are one slice.** R1007's own sentence:
  "Migration moves the existing file and its config default in one change." It
  does not require the key's *introduction* to be in that change, which is what
  lets slice 1 land the lever with today's location as its default and leaves no
  broken intermediate state.
- **No fallback to `data/aliases.toml`.** OD-11's rationale asks for "one
  authoritative way to find it"; a fallback keeps two homes alive, which is the
  condition BL-6 measured, and it would let the retired location keep working
  unnoticed after the move.
- **`.gitignore` is untouched.** The table was tracked by `git add -f`, not by a
  negation rule, so retiring the exception means adding nothing and removing
  nothing there — the file simply leaves the ignored tree. That is worth stating
  because "retire the exception" reads like an ignore-file edit and is not one.
- **The `git mv` is content-free.** `caption-split-aliases` (slice 3) and
  `itx-chipset-variant` (slice 1) both edit this file's contents and both already
  say they expect this move; a pure rename rebases against a content edit
  without touching its lines.
- **The tracked-and-not-ignored check is part of the change, not a follow-up.**
  `AGENTS.md`: when a decision alters behaviour nothing measures, adding the
  thing that notices it is part of the change. The suite today would pass with
  the table untracked, ignored, or force-added — the exact state BL-4 filed — so
  the guard is what makes R1007 observable rather than merely asserted.
- **That check skips rather than fails outside a git checkout**, with the reason
  stated, per R20 and `AGENTS.md`'s optional-resource rule.
- **The `aliases --check` observable runs through `scripts/run.sh` today.**
  R1007's "observable by `aliases --check` running from a clean checkout" is
  reachable now as `./scripts/run.sh aliases`, which invokes the command through
  Python because the dispatcher cannot yet forward `--check` (BL-5). The literal
  `uv run find-best-mobo aliases --check` becomes reachable when
  `docs/plans/oracle/subcommand-flag-forwarding.md` (OD-10/R1006) is built. This
  plan neither waits on that nor does any part of it.

## The work, sliced

Two, split at the one seam R1007 leaves: the *lever* and the *location*. Each is
observable on its own from the command line, and neither leaves the tree in a
state where a stage cannot find the table. **Sequential**: slice 2 changes the
default value of the constant slice 1 introduces, and both touch `config.py`,
`config.toml`, `tests/test_config.py` and `docs/architecture.md`. A cut that
moved the file first and re-homed the loaders afterwards was rejected: it breaks
both stages in between, and R1007 requires the move and the default to land
together anyway.

## Slice 1 — Every loader reads the alias table's path from configuration

- **Delivers:** `alias_table_path` is a configuration key. Setting it to any
  file makes both `find-best-mobo select` and the `aliases` recall report read
  *that* file — the report names it on its first line — and setting it to a
  missing file makes each refuse with the message it prints today, naming the
  configured path. Nothing else moves: with the key absent, both stages read
  `data/aliases.toml`, where the table still is. Covers R1007 in part (BL-6's
  half).
- **Files:** `src/find_best_mobo/config.py`, `config.toml`, `src/find_best_mobo/aliases.py`, `src/find_best_mobo/select.py`, `src/find_best_mobo/commands/select.py`, `src/find_best_mobo/commands/aliases.py`, `tests/test_config.py`, `tests/test_aliases.py`, `tests/test_select.py`, `docs/architecture.md`
- **Estimate:** ~130 lines

### Signatures

```python
DEFAULT_ALIAS_TABLE = Path("data/aliases.toml")


@dataclass(frozen=True)
class Config:
    # every field it has today, in today's order, unchanged — then, last,
    # because a defaulted field may not precede an undefaulted one:
    alias_table_path: Path = DEFAULT_ALIAS_TABLE


def load_config(path: Path) -> Config: ...
def select_all(config: Config) -> tuple[Selection, ...]: ...
def _missing(config: Config, filename: str) -> str: ...
```

Per **OD-12**, the module of every shared name this slice touches:
`DEFAULT_ALIAS_TABLE` is new and lives in `src/find_best_mobo/config.py`, beside
`Config` and `load_config`, because it is a configuration default and nothing
else. `Alias`, `Mention`, `load_aliases`, `compile_matcher`, `find_mentions` and
`find_title_hits` stay in `src/find_best_mobo/aliases.py`; `Selection` and
`ThresholdReport` in `src/find_best_mobo/select.py`; `Video` in
`src/find_best_mobo/index.py`; `Transcript` and `Cue` in
`src/find_best_mobo/transcripts.py`. `load_aliases`, `select_all`,
`threshold_report` and both `run` functions keep the signatures they have —
`_missing` is the one exception, and it is private to
`src/find_best_mobo/commands/select.py`.

### Behaviour the signatures cannot carry

- **`load_config` reads the key by field name**, `Path(str(raw.get(
  "alias_table_path", DEFAULT_ALIAS_TABLE)))`, in the same shape as `data_dir`
  one line above it. The constant is used both here and as the field default, so
  the two can never drift.
- **`config.toml` gains the key** with the default's value and a comment saying
  what it is: the hand-authored alias table, input rather than cache, which is
  why it is a path of its own rather than something under `data_dir`. It goes
  next to `data_dir`, where a reader comparing the two will be.
- **`select.py`**: `load_aliases(config.data_dir / "aliases.toml")` becomes
  `load_aliases(config.alias_table_path)`. `select_all`'s docstring already says
  it raises `FileNotFoundError` when the table is missing; it gains no new
  behaviour, only a path it no longer builds.
- **`commands/aliases.py`**: `table_path = config.data_dir / "aliases.toml"`
  becomes `table_path = config.alias_table_path`. The existence check, the
  message and the exit code are untouched, and `_report` keeps printing
  `Alias table: {table_path}` — which is how a run says out loud which file it
  read, and is the slice's observable.
- **`commands/select.py`'s `_missing` takes the config** and compares the
  reported filename against `str(config.alias_table_path)` instead of asking
  whether it ends in `aliases.toml`. With the path configurable, a suffix test is
  a guess about a name the owner now chooses; the index branch keeps its
  `endswith` because nothing configures that filename. The wording of all three
  messages is unchanged.
- **`aliases.py`'s module docstring** stops naming `data/aliases.toml` as the
  table's location and says instead that the table is data, not code, and that
  its path comes from configuration (`alias_table_path`), citing OD-11 and
  R1007. The file it names today is about to stop existing.
- **The two `make_config` test helpers set the field explicitly.**
  `tests/test_aliases.py` and `tests/test_select.py` both build a `Config` with
  `data_dir=tmp_path` and write the table to `data_dir / "aliases.toml"`; both
  set `alias_table_path=data_dir / "aliases.toml"` so every existing test body
  stays valid — and, because the default is no longer `data_dir`-relative, those
  suites now exercise a *configured, non-default* path throughout, which is the
  clause of R1007 they are best placed to pin. The other eight `make_config`
  helpers are untouched: they never load the table, and the field's default is
  what keeps their `Config(...)` calls valid. The commit records both reasons,
  per `AGENTS.md`'s blind-test rule.
- **What the tests must pin.** In `tests/test_config.py`: a `config.toml`
  carrying `alias_table_path` yields that `Path` (the full-file case gains the
  key and the expected `Config` gains the field); a file omitting it yields
  `Path("data/aliases.toml")`; an empty file yields the same; and the field
  default equals what `load_config` supplies for an absent key — the assertion
  that stops the two defaults drifting. In `tests/test_aliases.py`, through the
  real `run`: a table written at a path nothing else would guess (not under
  `data_dir`, not named `aliases.toml`) is found, reported, and named in the
  first line of the report; a configured path that does not exist returns 1 and
  the message names *that* path. In `tests/test_select.py`, through the real
  `run` and `select_all`: the same two cases, and the missing-table message
  names the configured path rather than falling through to the generic one; the
  existing nine-video corpus report is byte-for-byte what it is today.
- **`docs/architecture.md`**: the configuration row in the components table
  gains the alias table's path as one of the levers it declares; the alias-table
  row says the loaders take the path from configuration and never build one; and
  the `data/aliases.toml` line under "State and storage" records, for now, that
  the path is configurable — slice 2 is what rewrites that entry properly.

## Slice 2 — The table leaves the gitignored corpus directory

- **Delivers:** `aliases.toml` sits at the repository root, tracked, with no
  `git add -f` anywhere in its history from here on, and the default path points
  at it. A clean clone with no `data/` directory at all runs
  `./scripts/run.sh aliases` and gets the recall report, where today it gets
  "No alias table at data/aliases.toml". The suite fails if the table is ever
  untracked, ignored, or moved back under `data/`. Completes R1007.
- **Files:** `aliases.toml`, `src/find_best_mobo/config.py`, `config.toml`, `tests/test_config.py`, `tests/test_alias_table_location.py`, `docs/architecture.md`
- **Estimate:** ~95 lines

### Signatures

```python
DEFAULT_ALIAS_TABLE = Path("aliases.toml")
```

No type or signature changes: one constant's value, one file's location, and one
new test module. Per **OD-12**: `DEFAULT_ALIAS_TABLE` and `Config` stay in
`src/find_best_mobo/config.py` (slice 1); `load_aliases` and `Alias` in
`src/find_best_mobo/aliases.py`. The new `tests/test_alias_table_location.py`
declares no types.

### Behaviour the signatures cannot carry

- **The move is `git mv data/aliases.toml aliases.toml`**, contents byte-
  identical — not a delete and an add, so the file's history survives and the
  two plans queued to edit its contents rebase against a rename rather than a
  rewrite. The estimate above excludes the rename's line count for the same
  reason: nothing in it is authored.
- **`DEFAULT_ALIAS_TABLE` becomes `Path("aliases.toml")` and `config.toml`'s
  value follows it**, in this commit, because R1007 requires the file and its
  config default to move together.
- **`.gitignore` is not edited.** `data/` stays ignored, as R21 requires; the
  table simply is not under it any more. The `git add -f` exception retires by
  becoming unnecessary, which is the only way an exception like it can retire.
- **`SHIPPED_TABLE` in `tests/test_aliases.py` follows the constant.** It is
  currently the literal `REPO_ROOT / "data" / "aliases.toml"`; it becomes
  `REPO_ROOT / DEFAULT_ALIAS_TABLE`, which is what "the table this repository
  ships" now means, and which is why that file is not in this slice's list — the
  edit belongs to slice 1, where the constant arrives. If slice 1's author reads
  this before writing that line, it costs slice 2 nothing.
- **The location guard is a module of its own** — the new
  `tests/test_alias_table_location.py`, rather than another class in
  `tests/test_aliases.py`, because three in-flight plans edit that file, and
  this test shares nothing with it but the subject. It asserts, against the real
  checkout:
  - **The default resolves to a real file.** `REPO_ROOT / DEFAULT_ALIAS_TABLE`
    exists, is a file, and `load_aliases` parses it — the property a fresh clone
    needs and the one BL-4 says is currently bought with `git add -f`.
  - **git tracks it.** `git ls-files --error-unmatch <path>` exits 0.
  - **git does not ignore it.** `git check-ignore -q <path>` exits non-zero.
  - **The negative control**: `git check-ignore -q data` exits 0. Without it the
    ignore assertion passes vacuously anywhere `.gitignore` is missing or git is
    misconfigured, and a guard that cannot fail is worse than none.
  - **Nothing is under `data/`.** The default path's parts do not begin with the
    configured `data_dir`, stated as its own assertion so the failure message
    says which rule broke.
- **The guard skips, with a reason, where it cannot run**: `git` not on the
  path, or `REPO_ROOT` not inside a work tree (`git rev-parse
  --is-inside-work-tree`). Per R20, an unavailable optional resource is a skip
  with a stated reason, never a failure — the suite must stay green from an
  unpacked source tree. The subprocess calls run with `cwd=REPO_ROOT` and no
  network, so `tests/conftest.py`'s offline guard is untouched.
- **`tests/test_config.py`'s default assertions flip** from
  `Path("data/aliases.toml")` to `Path("aliases.toml")` — two lines, and they
  are the assertion this slice exists to change. The commit says exactly that,
  per `AGENTS.md`'s blind-test rule; nothing is weakened, and the
  defaults-agree test is untouched.
- **`docs/architecture.md`**: the `data/aliases.toml` entry under "State and
  storage" moves out of the `data/` group to sit beside `config.toml` as a
  tracked repository-root input, and loses both the "forced past the ignore
  rule" clause and the "That it lives here at all is an open plan question"
  sentence — the question is answered, and the answer cites OD-11/R1007. The
  data-flow line `data/aliases.toml --(canonical entities…)-->` and the
  alias-table row in the components table both take the new path.

## Out of scope

- **Repository-root discovery.** Every path this CLI resolves — `config.toml`,
  `data_dir`, and now the table — is relative to the working directory, and
  `scripts/run.sh` supplies that by `cd`-ing to the root. Making one key smarter
  than the other two is a change to how the whole CLI finds its files, which
  R1007 does not ask for and no evidence has been filed against.
- **A `--aliases` command-line flag.** R1007 says configuration, and a flag
  would need the dispatcher forwarding that OD-10/R1006 is separately planning.
- **Any change to the missing-table message.** "It ships with the repository;
  restore it" is wrong today and true after this plan; the sentence itself
  stands.
- **Packaging the table under `src/`.** OD-11 weighed and rejected it: the table
  is owner-editable input, not code.
- **Validating the shipped table's contents.** `tests/test_aliases.py` already
  pins its kinds, its duplicate canonicals and the chipsets it must carry; this
  plan moves the file and touches no entry in it.
- **`data/` and R21.** The corpus stays local-only and gitignored. Nothing here
  tracks anything that was ever cache.
- **Revising `docs/plans/corpus-and-checkpoint.md`.** Its slice 3 is what BL-4
  and BL-6 were filed against, and its file list still names
  `data/aliases.toml`. That plan sits behind `CODEOWNERS`, and **OD-12** already
  commissions its revision, which this correction can ride alongside the ones
  `description-signal` and `caption-split-aliases` already owe it.
- **The other plans' file lists.** `caption-split-aliases` (slice 3) and
  `itx-chipset-variant` (slice 1) both name `data/aliases.toml`; both already
  record that this move is coming and that whichever lands second carries the
  rebase. Neither is re-cut by this plan, and neither is edited by it.
- **Building in parallel with the three plans that share slice 1's files.**
  `refuse-on-missing-artifact` (slice 3) rewrites `select.py`,
  `commands/select.py` and `commands/aliases.py` — it deletes `_missing`
  outright, so if it lands first this plan's `_missing` edit becomes the same
  one-line path change inside the shared `require`/`MissingArtifact` path
  instead. `description-signal` (slice 2) rewrites `select.py`,
  `commands/select.py` and `aliases.py`; `subcommand-flag-forwarding` (slice 1)
  rewrites `commands/aliases.py` and `commands/select.py`. Whichever lands
  second carries the rebase, and one pipeline pull request in flight at a time
  makes that a sequencing note rather than a risk.
