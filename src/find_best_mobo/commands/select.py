"""The `select` subcommand: narrow the corpus and show what the lever cost.

Reads the index and the alias table, selects over every pending video, and
writes `data/selected.jsonl` — excluded videos included, because the point of
the report below is to let the owner see what the threshold threw away before
deciding whether it is set right (`docs/DESIGN.md` R4, R17).

The what-if lines are phrased as deltas *and* resulting totals on purpose. A
bare "12" next to a threshold change is unreadable — nobody should have to work
out whether it is twelve more videos or twelve videos in all.

This stage declares no flags, so anything passed to it is an error naming the
stage (`find-best-mobo select --nonsense`). The dispatcher still holds no
subcommand table — what changed with R1006 is that it forwards what it does not
recognise rather than rejecting it, so a stage that grows a flag declares it
here and `cli.py` is untouched.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence

from find_best_mobo.artifacts import MissingArtifact
from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import Config
from find_best_mobo.select import ThresholdReport, select_all, threshold_report, write_selected


def parse_args(argv: Sequence[str]) -> Namespace:
    """This stage declares no flags, so anything left over is its error (R1006)."""
    return subcommand_parser(
        "select", "Narrow the corpus, and report what the threshold cost."
    ).parse_args(list(argv))


def run(config: Config, args: Namespace) -> int:
    """Select the corpus, write it, and print the threshold's effect."""
    try:
        selections = select_all(config)
    except FileNotFoundError as error:
        print(_missing(config, error))
        return 1

    path = config.data_dir / "selected.jsonl"
    written = write_selected(selections, path)
    report = threshold_report(selections, config)
    print(f"Wrote {written} selections to {path} (excluded videos included)")
    _print_report(report)
    return 0


def _missing(config: Config, error: FileNotFoundError) -> str:
    """Name the missing file and the command that produces it.

    A `MissingArtifact` already carries all three parts of the sentence, so it
    is asked. What remains is the alias table, which `load_aliases` raises a
    plain `FileNotFoundError` for and which no stage produces — R1005's "name
    the stage that produces it" has no answer for hand-authored input (R1007),
    so its wording stands as it is. It is recognised by the CONFIGURED path
    rather than a filename suffix: with `alias_table_path` a lever, a suffix
    test is a guess about a name the owner now chooses.
    """
    if isinstance(error, MissingArtifact):
        return error.message()
    filename = str(error.filename)
    if filename == str(config.alias_table_path):
        return f"No alias table at {filename}. It ships with the repository; restore it."
    return f"Missing file: {filename}. Run `find-best-mobo index` and `find-best-mobo fetch` first."


def _print_report(report: ThresholdReport) -> None:
    """Print the counts, then each what-if as a direction and a resulting total."""
    selected = report.title_hits + report.threshold_passes
    print(f"Threshold in force: {report.threshold} distinct canonicals in the body")
    print(f"  {report.title_hits} videos included on a title hit")
    print(f"  {report.threshold_passes} videos included on the mention threshold")
    print(f"  {selected} videos selected in total")
    print(f"  {report.excluded} videos excluded below the threshold")
    print(
        f"Lowering the threshold to {report.threshold - 1} would include "
        f"{report.would_include_at_minus_one} ADDITIONAL videos, "
        f"for {selected + report.would_include_at_minus_one} selected in total."
    )
    print(
        f"Raising the threshold to {report.threshold + 1} would DROP "
        f"{report.would_exclude_at_plus_one} of the {report.threshold_passes} "
        f"threshold passes, for {selected - report.would_exclude_at_plus_one} "
        "selected in total. Title hits are unaffected either way."
    )
