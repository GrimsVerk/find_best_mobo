---
slug: subcommand-flag-forwarding
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1006]
---

# Every subcommand flag is reachable from the CLI — Plan

Implements **OD-10** (`docs/DESIGN.oracle.md`), which adds **R1006** from the
evidence in **BL-5**. `corpus-and-checkpoint` slice 3 promised
`uv run find-best-mobo aliases --check`, but the top-level parser rejects
`--check` before dispatch ever happens (`error: unrecognized arguments:
--check`), so the stage is reachable from Python only and `scripts/run.sh`
carries a `python -c` workaround that names BL-5 in a comment. R1006 fixes the
behaviour — *the top-level dispatcher forwards arguments it does not recognise
to the invoked subcommand, which owns their parsing and their errors* — while
keeping the design decision that caused the defect: the dispatcher holds no
subcommand table, so no two slices ever edit it.

## Summary

One dispatcher change, one hook each subcommand may implement, and the
workaround deleted.

- **The dispatcher forwards what it does not recognise.** `cli.py` parses with
  `parse_known_args` and hands the leftovers to the invoked module. It gains no
  table, no subparsers and no knowledge of any subcommand's flags — a later
  stage with flags needs no edit here, which is R1006's second sentence and the
  property OD-10 rejected a central table to keep.
- **A subcommand owns its parsing through one optional hook**,
  `parse_args(argv) -> Namespace`, and the Namespace it returns is what `run`
  receives. Only `commands/aliases.py` needs one today.
- **A module that declares no flags still rejects them.** The dispatcher parses
  the leftovers with a parser that accepts nothing, so `find-best-mobo index
  --nonsense` still exits 2 — now with a usage line naming `find-best-mobo
  index` instead of `find-best-mobo`. Nothing becomes silently accepted.
- **`--help` after a subcommand becomes the subcommand's**, so
  `find-best-mobo aliases --help` prints the help that documents `--check`
  rather than the top-level help that does not. This is a deliberate change to
  what the CLI does today and is filed as **BL-19** (LOW) for next cycle's
  review. `find-best-mobo --help` and `find-best-mobo` with no arguments are
  unchanged, exit codes included.
- **`scripts/run.sh` reverts to a plain CLI call** — R1006's last sentence. The
  `python -c` block and its BL-5 comment go, and a small test keeps them from
  coming back, because nothing else in the suite would notice.
- **Costs you a behaviour you may have relied on:** `find-best-mobo <stage>
  --help` no longer prints the top-level help. That is the only user-visible
  regression in the change; every existing exit code and message otherwise
  stands.
- **Not done here:** no new flag for any stage; no listing of available
  subcommands (that is the table OD-10 rejected); no move of the alias table
  (OD-11/R1007); no promise about flags written *before* the command name.

Three slices, ~530 lines, **sequential** — slice 1 introduces the hook and the
helper the other two rely on.

**What I need you to rule on** — one thing, and it is the `--help` change
above, filed as BL-19 and proceeded on. Everything else here is R1006 applied.

## Uncertainties

- **Q:** When `--help` follows a subcommand, whose help prints — the
  subcommand's or the dispatcher's? R1006 says every flag a subcommand
  *documents* is reachable and that the dispatcher forwards what it does not
  recognise, but `-h/--help` is the one token the top-level parser owns today
  and argparse consumes it before dispatch, so the rule and the current
  behaviour disagree on exactly this argument. — **risk:** LOW — it changes one
  console output and nothing else: no slice boundary, no Signatures block, no
  file format, and reversing it is deleting one branch in `cli.py`.
  — **proposed:** forward it, so `find-best-mobo aliases --help` prints the
  `aliases` parser's help, which is the only place `--check` is documented.
  **Ruling:** proceeded on the default (LOW), filed as **BL-19** in
  `docs/BACKLOG.md` in this same commit for the oracle's next cycle.

### Derivations, not uncertainties

Each is a place OD-10 fixes the behaviour and hands the mechanism to the plan —
its own **Alternatives considered** says the fix is "one small dispatcher
change, each subcommand owns its own parsing". Recorded so a reader sees the
derivation rather than a decision appearing from nowhere.

- **`parse_known_args`, not subparsers.** R1006 says the dispatcher *forwards
  arguments it does not recognise*, which is that function's contract in one
  call. `add_subparsers` would require every subcommand to register with the
  top-level parser, which is the hand-maintained table OD-10 rejected by name.
- **The hook is `parse_args(argv) -> Namespace`, defined by the subcommand.**
  R1006 puts parsing *and errors* on the subcommand, so the subcommand builds
  the parser; a dispatcher-built parser filled by an `add_arguments(parser)`
  hook would put the usage text, the prog name and the error handling back in
  `cli.py`. The hook is optional so a flagless stage stays a `run` and nothing
  more.
- **The subcommand's Namespace replaces the top-level one.** `run` keeps
  `(config, args)`, and `args` is now what the subcommand parsed — it no longer
  carries `command` or `config`. Nothing reads those: the settled contract
  already pinned in `tests/test_index.py` is `run(config, Namespace())` with no
  attributes at all, and the configuration reaches `run` as its first argument.
- **An unrecognised argument for a flagless subcommand is still an error.**
  Forwarding without this would turn every typo into silence — today the
  top-level parser catches `find-best-mobo index --nonsens`, and a fix for
  BL-5 that loses that is a worse defect than BL-5. Hence the fallback parser
  that accepts nothing.
- **The unknown-command error still wins.** `find-best-mobo bogus --check`
  prints today's `unknown command 'bogus'` and returns 2 without ever looking
  at `--check`: parsing flags for a command that does not exist names the
  smaller of two problems.
- **Arguments are parsed before the configuration is loaded.** A flag typo
  should not depend on a readable `config.toml`, and `load_config` already
  tolerates an absent file, so nothing is lost by moving it after the parse.
- **`allow_abbrev=False` on the top-level parser.** With abbreviation on, a
  future subcommand flag that is a prefix of `--config` would be *recognised*
  by the dispatcher and never forwarded — precisely the failure R1006 names.
  The cost is that `--conf` stops being accepted for `--config`; nothing
  documents or uses it.
- **Exit codes are argparse's, as they are today.** A bad flag reaches the
  subcommand's parser, which prints usage and raises `SystemExit(2)` out of
  `main` — the same shape today's top-level parse error already has, one prog
  name deeper.
- **`aliases` keeps its own missing-`--check` behaviour.** `--check` stays a
  `store_true`, not an argparse-required option, so `find-best-mobo aliases`
  still prints the stage's usage and returns 2 rather than exiting through
  argparse. That keeps `test_missing_check_flag_prints_usage_and_returns_two`
  passing untouched, and it keeps the friendlier message the stage already
  writes.

## The work, sliced

Three, each observable from the command line on its own. **Sequential**: slice
1 adds the dispatcher hook and the shared parser helper that slice 2 uses and
that slice 3's script depends on. The three touch disjoint source and test
files and share only `docs/architecture.md`; if any two are built in parallel,
whichever lands second carries that rebase.

A slice that shipped the dispatcher change with no subcommand using it would be
horizontal — a mechanism with nothing observing it — which is why slice 1
carries `aliases --check` end to end.

## Slice 1 — `find-best-mobo aliases --check` works

- **Delivers:** `uv run find-best-mobo aliases --check` runs the recall report
  from the command line and exits with the stage's own code — BL-5's blocked
  deliverable, reachable. `find-best-mobo aliases` (no flag) still prints the
  stage's usage and returns 2. `find-best-mobo index --nonsense` still fails
  with exit 2, now naming `find-best-mobo index`. `find-best-mobo aliases
  --help` prints the `aliases` parser's help, which documents `--check`.
  `find-best-mobo` with no arguments and `find-best-mobo --help` behave as they
  do today. `--config` is still accepted wherever it appears. Covers R1006 in
  part.
- **Files:** `src/find_best_mobo/cli.py`, `src/find_best_mobo/commands/__init__.py`, `src/find_best_mobo/commands/aliases.py`, `tests/test_cli.py`, `docs/architecture.md`
- **Estimate:** ~285 lines

### Signatures

```python
# src/find_best_mobo/commands/__init__.py
def subcommand_parser(command: str, description: str) -> ArgumentParser: ...


# src/find_best_mobo/commands/aliases.py
def parse_args(argv: Sequence[str]) -> Namespace: ...
def run(config: Config, args: Namespace) -> int: ...


# src/find_best_mobo/cli.py
def main(argv: Sequence[str] | None = None) -> int: ...
```

Per **OD-12**, the module of every shared name this slice touches:
`subcommand_parser` is new and lives in
`src/find_best_mobo/commands/__init__.py` — the package every command module
already imports through, so a command reaches it without importing the CLI it
is dispatched by. `parse_args` is a **per-module** function, one in each
command module that wants flags, never a shared import. `main` stays in
`src/find_best_mobo/cli.py`; `Config` and `load_config` in
`src/find_best_mobo/config.py`; `Alias`, `compile_matcher`, `find_mentions`
and `find_title_hits` in `src/find_best_mobo/aliases.py`; the private `_Tally`
stays in `src/find_best_mobo/commands/aliases.py`. **`run` keeps the signature
it has** in every command module — it is listed here to say that it does not
change.

### The dispatcher contract

Stated once, because it is what every present and future command module is
written against:

> A command module MAY define `parse_args(argv: Sequence[str]) -> Namespace`.
> The dispatcher calls it with exactly the arguments the top-level parser did
> not recognise, in the order they were given, and passes the result to `run`
> as `args`. A module that defines no `parse_args` is dispatched with a
> Namespace parsed by a parser that accepts no arguments, so anything left over
> is an error naming that subcommand.

`src/find_best_mobo/commands/__init__.py`'s docstring carries this text: it is
the file a new stage's author reads, and today's docstring there ("Each module
exposes `run(config, args) -> int`") is where the contract already lives.

### Behaviour the signatures cannot carry

- **The top-level parser keeps `--config` and loses nothing else.** It is built
  with `add_help=False` and `allow_abbrev=False`; `-h`/`--help` becomes an
  explicit `store_true`, and `command` becomes `nargs="?"` so that
  `find-best-mobo --help` is not a missing-argument error. These three changes
  exist only to let `--help` and the leftovers reach the subcommand; the
  recognised surface is otherwise exactly today's.
- **`main` in order:** parse with `parse_known_args`; if no command was named,
  print the top-level help and return 0 when `--help` was asked for or 2
  otherwise (today's exit code for a bare invocation); reject a non-identifier
  or unimportable command exactly as today, returning 2 before any leftover is
  looked at; if `--help` was asked for *and* a command was named, append
  `--help` to the leftovers so the subcommand's parser prints its own help;
  parse the leftovers through the module's `parse_args` or the no-argument
  fallback; then `load_config`, then `run`.
- **`subcommand_parser(command, description)`** returns an
  `ArgumentParser(prog=f"find-best-mobo {command}", description=description)`
  with no arguments added. One helper, so every stage's usage line and error
  text have one shape, and so the dispatcher's fallback and a stage's own
  parser cannot drift apart.
- **`commands/aliases.py` gains `parse_args`** building
  `subcommand_parser("aliases", …)` with
  `add_argument("--check", action="store_true", help=…)`. `run` is untouched:
  it still reads `getattr(args, "check", False)`, still prints `_USAGE` and
  returns 2 when the flag is absent, and still refuses on a missing table,
  index or cache with the messages it has today.
- **What is deliberately *not* in `cli.py`:** no subcommand names, no flag
  names, no mapping from either to the other. A reviewer should be able to read
  the whole dispatcher and not learn that `--check` exists.
- **What the tests must pin**, through the real `main` against `tmp_path` (a
  written `config.toml`, a small index, a cached transcript and an alias table,
  in the shapes `tests/test_aliases.py` already uses; the network boundary is
  never reached by any of these):
  - **BL-5's deliverable.** `main(["aliases", "--check", "--config", cfg])`
    returns the stage's code and prints the recall report — the canonical
    lines and the never-matched summary — where the same call without this
    slice fails to parse.
  - **The flag still reaches `run` when `--config` is written first**:
    `main(["aliases", "--config", cfg, "--check"])` behaves identically.
  - **The missing flag is the stage's error, not argparse's.**
    `main(["aliases", "--config", cfg])` returns 2 and prints the `--check`
    usage line the stage writes.
  - **An undeclared flag is rejected, naming the subcommand.**
    `main(["index", "--nonsense", "--config", cfg])` raises `SystemExit` with
    code 2, the message names `index` and `--nonsense`, and no
    `data/index.jsonl` is written — the stage never ran.
  - **The unknown command still wins.** `main(["bogus", "--check"])` returns 2
    and prints `unknown command 'bogus'`.
  - **Help.** `main(["aliases", "--help"])` exits 0 (through `SystemExit`) and
    its output names `--check`; `main(["--help"])` returns 0 printing the
    top-level help; `main([])` returns 2 and prints the top-level usage.
  - **Nothing else moves.** `tests/test_index.py`'s `TestRunAndCli` — `main(["index", "--config", …])` and `main(["index"])` — must keep passing
    **unedited**; it is the regression guard on the dispatch path this slice
    rewrites.
- **`docs/architecture.md`**: the paragraph under "Inspecting the alias table"
  that begins "**This stage is not reachable from the command line yet**" is
  replaced by what is now true — the stage runs as `uv run find-best-mobo
  aliases --check`, because the dispatcher forwards what it does not recognise
  to the subcommand, citing OD-10/R1006; the CLI-dispatcher row in the
  components table gains that clause and keeps its "holds no list of
  subcommands" sentence, which this change preserves rather than weakens.

## Slice 2 — every stage answers for itself

- **Delivers:** `find-best-mobo <stage> --help`, for each of `index`, `fetch`,
  `select` and `estimate`, prints a usage line naming that stage and a one-line
  description of what it does, instead of a bare usage line; an undeclared flag
  is rejected with the same stage-specific usage. The four stage docstrings
  stop claiming the CLI cannot carry flags. A guard test walks every module in
  `find_best_mobo.commands` and fails if any of them cannot answer `--help`, so
  a stage added later inherits R1006 rather than re-discovering BL-5. Completes
  R1006's dispatcher half.
- **Files:** `src/find_best_mobo/commands/index.py`, `src/find_best_mobo/commands/fetch.py`, `src/find_best_mobo/commands/select.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_cli_stages.py`, `docs/architecture.md`
- **Estimate:** ~190 lines

### Signatures

```python
# in each of commands/index.py, commands/fetch.py,
# commands/select.py, commands/estimate.py
def parse_args(argv: Sequence[str]) -> Namespace: ...
def run(config: Config, args: Namespace) -> int: ...
```

No type changes anywhere. Per **OD-12**: `subcommand_parser` comes from
`src/find_best_mobo/commands/__init__.py` (slice 1); `Video`,
`enumerate_channel` and `write_index` stay in `src/find_best_mobo/index.py`;
`Ledger`, `FetchFailure` and `HaltTriggered` in
`src/find_best_mobo/ledger.py`; `Selection`, `ThresholdReport` and
`select_all` in `src/find_best_mobo/select.py`; `Projection` and `project` in
`src/find_best_mobo/estimate.py`. Every `run` keeps the signature it has.

### Behaviour the signatures cannot carry

- **Each `parse_args` is three lines**: build `subcommand_parser(<name>,
  <one-line description>)` and parse `argv` through it. No flags are added —
  none of these stages has one, and inventing one here would be work R1006 does
  not authorise.
- **The descriptions come from what each module already says about itself**:
  the first line of its docstring, kept short enough for a usage screen —
  `index`: enumerate the channel into `data/index.jsonl`; `fetch`: cache every
  pending video's transcript; `select`: narrow the corpus and report what the
  threshold cost; `estimate`: cut, bundle, batch, project — and stop.
- **Four docstrings lose a sentence that is no longer true.**
  `commands/select.py` and `commands/estimate.py` both open with "This stage is
  reachable from Python only, by owner ruling: the top-level parser holds no
  subcommand table, so `run` takes no flags and reads nothing off `args`." The
  first clause is now false and the second is now a property of the stage's own
  parser, not of the dispatcher. Both are rewritten to say what holds after
  R1006: the stage declares no flags, so anything passed to it is an error, and
  the dispatcher still holds no subcommand table. `commands/index.py` and
  `commands/fetch.py` gain nothing beyond their `parse_args`.
- **The fallback stays in the dispatcher.** After this slice every shipped
  module defines `parse_args`, but the no-argument fallback is not deleted: it
  is what makes a *future* module correct before its author has thought about
  flags at all, and deleting it would turn an omission into a traceback.
- **What the tests must pin**, through the real `main` against `tmp_path`:
  - **Every command module answers `--help`.** Iterate the modules found in
    `find_best_mobo.commands` (by package inspection, not a hand-written list —
    a list here would be the table OD-10 rejected, one directory over): for
    each, `main([name, "--help"])` exits 0, the output's usage line reads
    `find-best-mobo <name>`, and the description is non-empty. This is the test
    a later stage's author will see fail if they break R1006.
  - **Each stage rejects what it does not declare.** `main([name,
    "--nonsense"])` raises `SystemExit(2)` and names both the stage and the
    flag, for each of the four; and the stage does no work — no
    `data/index.jsonl`, no `data/selected.jsonl`, no `data/bundles/`.
  - **Nothing else moves.** Every existing `run(config, Namespace())` call in
    `tests/test_index.py`, `tests/test_transcripts.py`, `tests/test_select.py`
    and `tests/test_estimate.py` keeps passing **unedited**: `parse_args` is a
    new entry point beside `run`, never a precondition of it.
- **`docs/architecture.md`**: the CLI-dispatcher row records that a stage
  declaring no flags rejects them through its own parser, so an argument the
  dispatcher forwards is never silently dropped.

## Slice 3 — the workaround is gone

- **Delivers:** `./scripts/run.sh aliases` runs `uv run find-best-mobo aliases
  --check` — the `python -c` block that reached into `find_best_mobo.commands`
  and hand-built a `Namespace` is deleted, along with the comment naming BL-5
  as the reason it existed. R1006's last sentence, done, and a test that fails
  if the workaround is reintroduced.
- **Files:** `scripts/run.sh`, `tests/test_run_script.py`, `docs/architecture.md`
- **Estimate:** ~55 lines

### Signatures

No Python surface changes. The interface is the script's command lines, which
do not move:

    ./scripts/run.sh                      index → fetch → select → estimate
    ./scripts/run.sh aliases              the recall diagnostic, now via the CLI
    ./scripts/run.sh --help               0, usage
    ./scripts/run.sh <unknown>            2, names the unknown stage

### Behaviour the signatures cannot carry

- **`run_aliases()` and its comment block are deleted.** The stage dispatch
  becomes a two-line `case`: `aliases` runs `uv run find-best-mobo aliases
  --check`, everything else runs `uv run find-best-mobo "$stage"`. The flag
  stays in the script because the diagnostic requires it; what goes is the
  Python invocation, which is what BL-5 called the workaround.
- **`aliases` stays out of `ALL_STAGES`** and stays labelled a diagnostic in
  `--help`. R1006 says nothing about the pipeline's shape, and
  `docs/plans/run-scripts.md`'s "four stages, not five" decision is the owner's
  and stands.
- **The test is a file-content guard, not a shell harness.**
  `tests/test_run_script.py` reads `scripts/run.sh` from the repository root
  and asserts it invokes `find-best-mobo aliases --check` and contains no
  `python -c`. `docs/plans/run-scripts.md` established that this repository
  does not test shell, and a bash harness for a four-line change would be
  larger than the change; but R1006's last sentence is otherwise observed by
  nothing at all, and the ratchet asks for the thing that notices. Two
  assertions is that thing. The script itself is verified by running it, and
  the output is recorded in the pull request.
- **`docs/architecture.md`**: "Inspecting the alias table" step 1 names the
  command the owner actually runs — `uv run find-best-mobo aliases --check`, or
  `./scripts/run.sh aliases` — rather than "the `aliases` stage with
  `--check`".

## Out of scope

- **Any new flag for any stage.** R1006 makes documented flags reachable; it
  documents none. A `--refresh` for the description cache
  (`docs/plans/oracle/description-signal.md` names it and rules it out), a
  threshold override for `select`, a `--force` anywhere: each is its own
  evidence and its own decision. This plan is what makes them *possible*
  without a dispatcher edit, which is the whole of R1006's second sentence.
- **Listing the available subcommands** in `find-best-mobo --help`. It reads
  like an obvious companion and it is not this decision's: OD-10 rejected a
  central subcommand table by name, and every way of producing that list —
  hand-written or discovered by import — is a new behaviour no requirement
  asks for. The guard test in slice 2 walks the package because a test may know
  things the shipped dispatcher must not.
- **argparse subparsers.** Same reason, one level down: `add_subparsers`
  requires every stage to register with the top-level parser at import time,
  which is the shared edit point slice 1 of `corpus-and-checkpoint` exists to
  avoid.
- **Flags written before the command name, and `--` as a separator.** The
  documented form is `find-best-mobo <command> [--config PATH] [flags…]`, which
  is what today's `main(["index", "--config", …])` already uses. Other orderings
  are whatever `parse_known_args` does with them; nothing pins them, and a
  future need is a `BL-<n>` rather than a guess made here.
- **A per-subcommand `--config`.** Configuration stays a top-level concern
  loaded once by the dispatcher, exactly as `docs/architecture.md` describes it.
- **OD-11/R1007's move of the alias table.** `commands/aliases.py` keeps
  reading the table from `config.data_dir / "aliases.toml"` — this plan changes
  how the command is invoked, never where it looks. That move edits the same
  file and is separately plannable; whichever lands second carries the rebase.
- **OD-9/R1005's refusals.** `docs/plans/oracle/refuse-on-missing-artifact.md`
  edits `commands/aliases.py`, `commands/estimate.py`, `commands/fetch.py` and
  `commands/select.py` — every command module this plan touches. Neither plan
  is built in parallel with the other, and the refusal messages are left
  exactly as they are here.
- **Revising `docs/plans/run-scripts.md`.** Its summary decision "`aliases` is
  invoked through Python, not the CLI" and its out-of-scope entry "Fixing BL-5"
  are what R1006 retires, and its 2026-08-15 ruling already anticipated this
  ("it reverts to a plain CLI call when BL-5 is ruled on"). That plan sits
  behind `CODEOWNERS`; the workaround is removed from the *script* here, and
  the plan's own text is the owner's edit.
- **Revising `docs/plans/corpus-and-checkpoint.md`.** BL-5 is a plan-rework
  item against its slice 3 — the file list that excluded `cli.py` while the
  deliverable needed it. **OD-12** already commissions that plan's revision,
  and this correction can ride alongside the ones `description-signal` and
  `caption-split-aliases` already owe it.
