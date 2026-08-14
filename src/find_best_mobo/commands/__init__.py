"""Subcommand modules, one per pipeline stage.

The CLI dispatches by importing the module named after the subcommand, so a
new stage adds one module here and never edits `cli.py`. Each module exposes
`run(config, args) -> int`.
"""
