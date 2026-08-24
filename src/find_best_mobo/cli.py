"""Command-line entry point: parse what is ours, forward the rest, dispatch.

Dispatch is by importing the module named after the subcommand from
`find_best_mobo.commands` — deliberately not a hand-maintained table, so each
later slice adds its own command module without ever editing this file.

The same reasoning governs flags. This dispatcher parses only what it owns
(`--config`, `--help`, and the command name) and forwards every other argument
to the invoked module, which owns its parsing and its errors (R1006, OD-10).
Read this file end to end and you will not learn that `--check` exists; that is
the property, not an omission. Before R1006 the top-level parser rejected
`--check` before dispatch ever happened, which made a stated deliverable
unreachable (BL-5).
"""

from __future__ import annotations

import importlib
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from pathlib import Path

from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import load_config


def main(argv: Sequence[str] | None = None) -> int:
    """Run one subcommand and return its exit code.

    `argv` is the arguments without the program name; None means `sys.argv`.
    """
    parser = _top_level_parser()
    args, leftover = parser.parse_known_args(argv if argv is None else list(argv))
    command: str | None = args.command

    if command is None:
        parser.print_help()
        return 0 if args.help else 2

    module_name = f"find_best_mobo.commands.{command}"
    if not command.isidentifier():
        print(f"find-best-mobo: unknown command {command!r}", file=sys.stderr)
        return 2
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name is not None and module_name == error.name:
            print(f"find-best-mobo: unknown command {command!r}", file=sys.stderr)
            return 2
        raise

    # `--help` after a command name belongs to that command: it is the only
    # place a stage's own flags are documented. The plan proposed this as a LOW
    # default; the oracle has since RULED it, as OD-18 on BL-19, so it is
    # settled rather than proceeded on. `find-best-mobo --help` is handled above
    # and is unchanged, exit code included.
    if args.help:
        leftover = [*leftover, "--help"]

    command_args = _parse_for(module, command, leftover)
    config = load_config(args.config)
    result: int = module.run(config, command_args)
    return result


def _top_level_parser() -> ArgumentParser:
    """The dispatcher's own surface, and nothing else.

    `add_help=False` with an explicit `--help` flag, because argparse's built-in
    help consumes the token before dispatch and would keep a subcommand's help
    unreachable. `command` is optional so that `find-best-mobo --help` is a help
    request rather than a missing-argument error. `allow_abbrev=False` because
    with abbreviation on, a future subcommand flag that is a prefix of
    `--config` would be *recognised* here and never forwarded — precisely the
    failure R1006 names.
    """
    parser = ArgumentParser(
        prog="find-best-mobo",
        description="Turn the Buildzoid back catalogue into a motherboard shortlist.",
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument("command", nargs="?", help="subcommand to run, e.g. `index`")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="path to the configuration file (default: config.toml)",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="show this help, or the named subcommand's help",
    )
    return parser


def _parse_for(module: object, command: str, leftover: list[str]) -> Namespace:
    """Hand the leftovers to the module, or reject them on its behalf.

    A module with no `parse_args` gets a parser that accepts nothing, so a typo
    is still an exit-2 error naming that subcommand rather than being silently
    swallowed. Forwarding without this would turn every mistyped flag into
    silence, which is a worse defect than the one R1006 fixes.
    """
    parse_args = getattr(module, "parse_args", None)
    if parse_args is not None:
        parsed: Namespace = parse_args(leftover)
        return parsed
    return subcommand_parser(command, "").parse_args(leftover)


if __name__ == "__main__":
    raise SystemExit(main())
