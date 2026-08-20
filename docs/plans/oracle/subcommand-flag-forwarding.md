---
slug: subcommand-flag-forwarding
status: draft
created: 2026-08-20
design: MVP — Corpus and the cost checkpoint (no inference)
covers: [R1006]
---

# Every subcommand flag is reachable from the CLI — Plan

Implements **OD-10** (`docs/DESIGN.oracle.md`), which adds **R1006** from the
evidence in **BL-5**. `uv run find-best-mobo aliases --check` is a stated
deliverable of `docs/plans/corpus-and-checkpoint.md` slice 3 and it does not
work: the top-level parser rejects `--check` before dispatch ever happens
(`error: unrecognized arguments: --check`), because the dispatcher deliberately
holds no subcommand table. The recall report is reachable only by calling
`aliases.run()` from Python, which is what `scripts/run.sh` does today behind a
comment naming BL-5.

## Summary

The dispatcher stops rejecting what it does not recognise and hands it to the
subcommand instead. Two slices, ~245 lines, **sequential**.

- **`parse_known_args`, not a subcommand table.** `cli.py` parses exactly the two
  things it documents — the command name and `--config`, and no abbreviations of
  either — and forwards everything else to the invoked subcommand. The property
  `corpus-and-checkpoint` slice 1 bought survives: a flagged subcommand added
  later needs no dispatcher edit.
- **Forwarded arguments travel as `args.extra`**, a tuple on the Namespace the
  command already receives, so `run(config, args)` keeps its signature and no
  test that calls a command directly changes.
- **Every subcommand parses its own flags** — including the four that take none,
  which therefore reject a stray argument instead of silently ignoring it.
  Silent ignoring is the one way this could be worse than the defect it fixes,
  so nothing lands without it.
- **`aliases --check` behaves exactly as it does today** when called directly:
  same usage text, same exit 2 for a missing flag (OD-17 asked for that), same
  guards.
- **`scripts/run.sh` loses its workaround** and calls `uv run find-best-mobo
  aliases --check` like every other stage.
- **Not done:** no per-subcommand `--help` (the open question), no subcommand
  able to define its own `--config`, no new flags anywhere, no `argparse`
  subparsers, no change to any stage's behaviour, and no revision of the plan
  this makes partly wrong.

**What this costs you.**

1. **`find-best-mobo aliases --help` prints the dispatcher's help, not the
   subcommand's** — the dispatcher still owns `-h/--help`. **BL-19**, proceeded
   on.
2. **`docs/plans/run-scripts.md` becomes partly wrong** — it says `aliases` is
   invoked through Python and gives fixing BL-5 to you. Revising it is a
   separate owner-reviewed pull request, not this one. (`corpus-and-checkpoint`
   slice 3 gets its stated deliverable back and needs no words changed.)
3. **Slice 2 is verified by running it**, as `run-scripts.md` established for
   shell: no bash harness exists and this adds none.

**What I need you to rule on:** BL-19 only, already proceeding on its default.

## Uncertainties

One, LOW, proceeded on and filed — `docs/BACKLOG.md`, in this commit.

- **Q:** After a subcommand name, does `-h/--help` belong to the dispatcher or to
  the subcommand? R1006 says every flag a subcommand *documents* is reachable,
  and no subcommand documents `--help` today — but `find-best-mobo aliases
  --help` printing the top-level help is a plausible surprise. — **risk:** LOW —
  it is one constructor argument (`add_help=False`) and one branch in `cli.py`:
  no slice boundary moves, no shared signature changes, no artifact on disk
  changes shape, and reversing it is restoring the default. — **proposed:** the
  dispatcher keeps `--help`. It is a documented top-level flag, so it is not an
  argument the dispatcher "does not recognise"; giving it away would mean
  `find-best-mobo --help` had to be special-cased on whether a command name was
  already seen, which is dispatcher complexity R1006 did not ask for. A
  subcommand's usage stays what it is today — printed by the subcommand when its
  arguments are wrong.
  **Ruling:** proceeded on the default (LOW), filed as **BL-19** for the
  oracle's next cycle.

### Derivations, not uncertainties

Places OD-10/R1006 fixes the behaviour and leaves the mechanism here. Shown
rather than asserted, because two of them look like decisions until you read the
decision that already made them.

- **`parse_known_args` is the mechanism.** OD-10 chose "forward unrecognised
  arguments to the subcommand" over a central table and over the status quo, and
  named its own property: "one small dispatcher change, each subcommand owns its
  own parsing, and the no-table property is preserved". `parse_known_args` is
  argparse's name for exactly that; nothing else in the standard library is.
- **Forwarding by attribute rather than by a third parameter.** R1006 fixes what
  must arrive, not how. `args.extra` leaves `run(config, args) -> int` alone, so
  `commands/fetch.py`, `commands/index.py`, `commands/select.py` and
  `commands/estimate.py` change only where they now guard, and every existing
  direct call in the suite keeps working. A third parameter would rewrite five
  signatures and their call sites to carry the same tuple.
- **Every command guards, not just the flagged one.** R1006's clause is "the
  invoked subcommand, which owns their parsing and their errors" — a command
  that owns its parsing and accepts anything is not parsing. Today
  `find-best-mobo index --oops` exits 2; after forwarding, a command with no
  guard would exit 0 having ignored it. That is a regression the requirement
  does not license, so it is prevented in the same slice that creates the
  possibility, and pinned by a test that enumerates the command modules.
- **`allow_abbrev=False` on the dispatcher.** With argparse's default, `--conf`
  is consumed as an abbreviation of `--config`, which means the set of arguments
  the dispatcher swallows is larger than the set it documents — and grows to
  collide with any future subcommand flag sharing a prefix. R1006 says the
  dispatcher forwards "arguments it does not recognise"; recognising exactly its
  own two spellings is that sentence read literally.
- **`aliases` keeps its hand-written `--check` requirement** rather than
  declaring `required=True` and letting argparse produce the error. OD-17 states
  "the `--check` usage error and its exit code 2 are untouched", and argparse's
  version of that error is different text on a different stream.
- **Parsing into the same Namespace preserves every direct call.**
  `parser.parse_args(extra, namespace=args)` only fills in a default for an
  attribute the namespace does not already have, so `run(config,
  Namespace(check=True))` — the shape a dozen tests in `tests/test_aliases.py`
  use — still reads `check=True` with no forwarded arguments present. This is
  the property that keeps `tests/test_aliases.py` out of slice 1's file list
  entirely; it is load-bearing, not incidental.
- **A parse failure returns 2 rather than escaping as `SystemExit`.**
  `main()` is typed `-> int` and the suite calls it that way; argparse's
  `error()` raises `SystemExit(2)` after printing to stderr. The helper catches
  it and reports the failure to the caller, so the exit code is unchanged and
  the type is honest.
- **`subcommand.py` imports nothing from this package.** It is the one module
  both the dispatcher and every command import; a dependency in the other
  direction would make the helper a second dispatcher. Same shape as
  `artifacts.py` in `docs/plans/oracle/refuse-on-missing-artifact.md`.
- **No `argparse` subparsers.** Subparsers *are* the central table OD-10
  rejected: every command would have to be registered in `cli.py`, which is the
  design property `corpus-and-checkpoint` slice 1 bought and OD-10 kept.
- **`scripts/run.sh` reverts rather than being left alone.** R1006 says so in as
  many words: "The `run-scripts` workaround (invoking `aliases` through Python)
  reverts to a plain CLI call."

## The work, sliced

Two, **sequential**. Slice 2 depends on slice 1 having landed — a `run.sh` that
calls `find-best-mobo aliases --check` before the dispatcher forwards it is a
broken script.

Two rather than three or more, deliberately. The mechanism cannot be split
without leaving a window in which a subcommand silently ignores arguments the
dispatcher used to reject (see the derivations), and splitting the dispatcher
from its first user would land a forwarding path with nothing to forward to.
A third slice here would be padding, and `run-scripts.md` is the local
precedent for saying so out loud rather than manufacturing one. Each slice is
observable without reading code: slice 1 is BL-5's defect gone, slice 2 is the
visible workaround gone.

## Slice 1 — The dispatcher forwards what it does not recognise

- **Delivers:** `uv run find-best-mobo aliases --check` runs the recall report instead of `error: unrecognized arguments: --check`, and `--check` may appear before or after `--config`. `find-best-mobo aliases` with no flag still prints its usage and exits 2. `find-best-mobo aliases --bogus` exits 2 naming `--bogus`, from the subcommand. `find-best-mobo index --oops` still exits 2 rather than ignoring the argument. A subcommand added later receives its own flags with no change to `cli.py`. Covers R1006 in full, bar the script.
- **Files:** `src/find_best_mobo/subcommand.py`, `src/find_best_mobo/cli.py`, `src/find_best_mobo/commands/aliases.py`, `src/find_best_mobo/commands/fetch.py`, `src/find_best_mobo/commands/index.py`, `src/find_best_mobo/commands/select.py`, `src/find_best_mobo/commands/estimate.py`, `tests/test_cli.py`, `docs/architecture.md`
- **Estimate:** ~230 lines

### Signatures

```python
FORWARDED_ATTR = "extra"


def flag_parser(command: str) -> ArgumentParser: ...
def parse_flags(parser: ArgumentParser, args: Namespace) -> Namespace | None: ...
```

Per **OD-12**, the module of every shared name this slice touches:
`FORWARDED_ATTR`, `flag_parser` and `parse_flags` are new and live in
`src/find_best_mobo/subcommand.py`, which imports from `argparse` and nothing
from this package. `main` stays in `src/find_best_mobo/cli.py` with the
signature it has today, `main(argv: Sequence[str] | None = None) -> int`. Each
`run(config: Config, args: Namespace) -> int` stays in its own module under
`src/find_best_mobo/commands/`. `Config` and `load_config` stay in
`src/find_best_mobo/config.py`; `Alias`, `Mention` and the matcher helpers in
`src/find_best_mobo/aliases.py`; `_Tally` stays private to
`src/find_best_mobo/commands/aliases.py`.

### Behaviour the signatures cannot carry

- **`flag_parser(command)` builds one shape**, so every subcommand's errors
  read alike: `ArgumentParser(prog=f"find-best-mobo {command}",
  add_help=False, allow_abbrev=False)`. `add_help=False` because `-h/--help` is
  consumed by the dispatcher and can never arrive here (BL-19) — advertising a
  flag that cannot be reached is worse than not having one.
- **`parse_flags(parser, args)` parses the forwarded arguments into `args` and
  returns it**, or returns `None` when argparse rejected them, having already
  printed usage and the reason to stderr. It reads `getattr(args,
  FORWARDED_ATTR, ())`, so a Namespace built by hand in a test — with no
  forwarded arguments at all — parses an empty list and keeps every attribute it
  was given. It never calls `sys.exit`, never raises `SystemExit`, and returns
  the *same* Namespace object rather than a copy.
- **The dispatcher's parse becomes `parse_known_args`**, and the leftovers are
  attached as a tuple: `setattr(args, FORWARDED_ATTR, tuple(extra))`, before the
  command module is imported. `--config` is consumed by the dispatcher and never
  appears in the tuple. The top-level parser gains `allow_abbrev=False`.
- **The unknown-command path is untouched.** A command name that is not an
  identifier, or names no module, still prints ``find-best-mobo: unknown command
  'x'`` and returns 2 — including when flags follow it, which now parse without
  complaint before the command is resolved. Configuration is still loaded after
  the module resolves, so an unknown command does not require a readable
  `config.toml`.
- **`commands/aliases.py` declares `--check` and parses it itself**:
  `parser = flag_parser("aliases")`, one `add_argument("--check",
  action="store_true", ...)`, then `if parse_flags(parser, args) is None: return
  2`. Its existing `if not args.check` branch, its `_USAGE` text and its exit 2
  stay exactly as they are, and the three artifact guards below them are
  untouched by this plan.
- **The four flagless commands guard in two lines each**: `if
  parse_flags(flag_parser("<name>"), args) is None: return 2`, first thing in
  `run`, before any work and before any network call. The module docstrings in
  `commands/select.py` and `commands/estimate.py` currently say `run` "takes no
  flags and reads nothing off `args`"; they now say the command accepts no flags
  and rejects any it is given, citing OD-10/R1006.
- **What the tests must pin** (all of it in `tests/test_cli.py`, driving
  `main()` with an explicit `--config` under `tmp_path`):
  - `main(["aliases", "--check", "--config", cfg])` reaches the command — with
    an empty data directory it returns 1 and prints the alias-table guard's
    message, which is only observable if `--check` arrived;
  - the same with `--config` first, and with `--check` last: same result;
  - `main(["aliases", "--config", cfg])` returns 2 and prints the `--check`
    usage line;
  - `main(["aliases", "--bogus", "--config", cfg])` returns 2, names `--bogus`
    on stderr, prints no traceback, and raises nothing;
  - `main(["index", "--oops", "--config", cfg])` returns 2 — the no-silent-
    ignoring property — and `main(["index", "--config", cfg])` is unaffected;
  - **every module in `find_best_mobo.commands` rejects an unrecognised
    argument**, enumerated with `pkgutil.iter_modules` so a command added later
    without a guard fails this test rather than shipping the regression. It must
    use a `--config` under `tmp_path`, so that a module that *does* leak past
    its guard cannot touch a real data directory;
  - a stub module injected at `sys.modules["find_best_mobo.commands.faux"]`
    receives `args.extra == ("--anything", "value")` from `main(["faux",
    "--anything", "value", "--config", cfg])`, and `--config` and its value are
    not in that tuple — this is R1006's "a future flagged subcommand requires no
    dispatcher edit", pinned;
  - `main(["nope", "--check"])` still returns 2 with the unknown-command
    message;
  - `main(["index", "--conf", cfg])` returns 2 rather than being accepted as an
    abbreviation of `--config`;
  - `parse_flags` unit cases: a namespace that already carries `check=True`
    still carries it after parsing no forwarded arguments; an unrecognised
    argument returns `None` with a message on stderr; a recognised one sets the
    attribute and returns the same object it was passed.
- **`docs/architecture.md`**: the CLI dispatcher row in Components says it
  forwards arguments it does not recognise to the subcommand, which declares and
  parses its own flags (OD-10/R1006), and that this is what keeps the no-table
  property compatible with flags; a Components row for `subcommand.py`; the
  "Inspecting the alias table" section loses the paragraph beginning **"This
  stage is not reachable from the command line yet"** and states the real
  invocation, `find-best-mobo aliases --check`; "Known rough edges" gains one
  entry — after a subcommand name, `--help` prints the dispatcher's help rather
  than the subcommand's, and a subcommand cannot define its own `--config`
  because the dispatcher consumes it (BL-19).

## Slice 2 — The `run-scripts` workaround reverts to a plain CLI call

- **Delivers:** `./scripts/run.sh aliases` runs `uv run find-best-mobo aliases --check` like every other stage, and the `run_aliases` Python block and the comment naming BL-5 are gone. The stage list, the ordering, the validation and the `--help` text are unchanged. Completes R1006.
- **Files:** `scripts/run.sh`
- **Estimate:** ~15 lines

### Signatures

No Python surface. The interface is the command line, and it does not move:

    ./scripts/run.sh aliases          the recall diagnostic, now through the CLI
    ./scripts/run.sh                  index → fetch → select → estimate
    ./scripts/run.sh <unknown>        2, names the unknown stage

### Behaviour the signatures cannot carry

- **`run_aliases` is deleted, not rewritten.** The `case` arm becomes the same
  `uv run find-best-mobo "$stage"` every other stage uses, plus `--check`; a
  one-arm case that only appends a flag is the last trace of the workaround. The
  surrounding comment keeps its first half — `aliases` is a diagnostic and
  produces no data the pipeline reads, which is why it is not in `ALL_STAGES` —
  and loses the half about BL-5, which no longer describes anything.
- **`aliases` stays out of `ALL_STAGES`.** This plan changes how the stage is
  invoked, not whether a bare `./scripts/run.sh` runs it.
- **Verified by running it**, not by a test: `run-scripts.md` ruled that a bash
  harness for 165 lines of glue is a bigger change than the glue, and that ruling
  stands. The pull request records `./scripts/run.sh aliases` and
  `./scripts/run.sh --help` having been run and what they printed.

## Out of scope

- **Per-subcommand `--help`.** BL-19, proceeded on: the dispatcher keeps
  `-h/--help`.
- **A subcommand flag named `--config`.** The dispatcher consumes it first.
  Nothing needs one; when something does, that is a decision about the
  dispatcher and it goes through the ledger like this one did.
- **New flags on any subcommand.** `--check` is the only flag in the tree, and
  this plan adds no others. `docs/plans/oracle/description-signal.md` notes that
  a `--refresh` flag would need this mechanism; it is that plan's to add, not
  this one's to anticipate.
- **`argparse` subparsers, a command registry, or a `--version` flag.**
- **Any stage's behaviour.** No guard, message, exit code or artifact changes
  outside the argument-parsing path — `aliases --check`'s three artifact guards
  in particular belong to `docs/plans/oracle/refuse-on-missing-artifact.md`.
- **Revising `docs/plans/run-scripts.md`**, whose summary and "Out of scope"
  both describe the workaround this removes. It is a `CODEOWNERS`-gated document
  and a change may not carry its own revision of one; it needs its own pull
  request.
- **The alias table's location (OD-11/R1007).** It touches
  `commands/aliases.py` too. Sequential with this plan; whichever lands second
  carries the rebase, and the two edits are in different parts of the file
  (`run`'s first lines here, the table path there).
- **A bash test harness for `scripts/run.sh`.**
