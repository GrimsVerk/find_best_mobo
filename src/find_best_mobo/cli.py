"""Command-line entry point: parse arguments, load config, dispatch.

Dispatch is by importing the module named after the subcommand from
`find_best_mobo.commands` — deliberately not a hand-maintained table, so each
later slice adds its own command module without ever editing this file.
"""

from __future__ import annotations

import importlib
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from find_best_mobo.config import load_config


def main(argv: Sequence[str] | None = None) -> int:
    """Run one subcommand and return its exit code.

    `argv` is the arguments without the program name; None means `sys.argv`.
    """
    parser = ArgumentParser(
        prog="find-best-mobo",
        description="Turn the Buildzoid back catalogue into a motherboard shortlist.",
    )
    parser.add_argument("command", help="subcommand to run, e.g. `index`")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="path to the configuration file (default: config.toml)",
    )
    args = parser.parse_args(argv if argv is None else list(argv))
    command: str = args.command
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
    config = load_config(args.config)
    result: int = module.run(config, args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
