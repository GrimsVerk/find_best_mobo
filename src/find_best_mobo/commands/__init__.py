"""Subcommand modules, one per pipeline stage.

The CLI dispatches by importing the module named after the subcommand, so a
new stage adds one module here and never edits `cli.py`. Each module exposes
`run(config, args) -> int`.

**The dispatcher contract**, which every present and future command module is
written against (`docs/DESIGN.oracle.md` OD-10, R1006):

> A command module MAY define `parse_args(argv: Sequence[str]) -> Namespace`.
> The dispatcher calls it with exactly the arguments the top-level parser did
> not recognise, in the order they were given, and passes the result to `run`
> as `args`. A module that defines no `parse_args` is dispatched with a
> Namespace parsed by a parser that accepts no arguments, so anything left over
> is an error naming that subcommand.

That is the whole of it. `cli.py` holds no subcommand names and no flag names —
the table OD-10 rejected — so a stage that grows a flag needs no edit there.
Build the parser with `subcommand_parser` below rather than by hand, so every
stage's usage line and error text have one shape and the dispatcher's fallback
cannot drift from a stage's own parser.
"""

from __future__ import annotations

from argparse import ArgumentParser


def subcommand_parser(command: str, description: str) -> ArgumentParser:
    """An empty parser that names one subcommand in its usage and its errors.

    No arguments are added: what a stage accepts is the stage's to declare. The
    `prog` is what makes a bad flag report `find-best-mobo index` rather than
    `find-best-mobo`, which is the difference between an error a reader can act
    on and one that sends them to the wrong help screen.
    """
    return ArgumentParser(prog=f"find-best-mobo {command}", description=description)
