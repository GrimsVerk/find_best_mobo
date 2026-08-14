"""The `aliases` subcommand: show what the alias table actually catches.

The table decides which videos enter the corpus, so its recall has to be
inspectable before it is trusted (`docs/DESIGN.md` R3). `--check` walks the
cached transcripts once and reports, per canonical, how many videos name it, how
often, and which spellings did the work.

The report's most important line is the one for a canonical that matched
nothing. An alias that never fires is either a spelling nobody uses or a mistake
in the table, and it is invisible unless something says so out loud — so
zero-match canonicals are both listed in the main table and called out again at
the end.

Transcripts are loaded and released one at a time (R22): a channel's worth of
captions never sits in memory together.
"""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path

from find_best_mobo.aliases import (
    Alias,
    compile_matcher,
    find_mentions,
    find_title_hits,
    load_aliases,
)
from find_best_mobo.config import Config
from find_best_mobo.index import read_index
from find_best_mobo.transcripts import load_cached

_USAGE = "usage: find-best-mobo aliases --check"


@dataclass
class _Tally:
    """Running totals for one canonical, accumulated across the corpus."""

    videos: int = 0
    title_videos: int = 0
    mentions: int = 0
    forms: set[str] = field(default_factory=set)


def run(config: Config, args: Namespace) -> int:
    """Report the alias table's recall over the cached corpus."""
    if not getattr(args, "check", False):
        print(_USAGE)
        print("  --check  report how many videos mention each canonical (required)")
        return 2

    table_path = config.data_dir / "aliases.toml"
    if not table_path.exists():
        print(f"No alias table at {table_path}. It ships with the repository; restore it.")
        return 1
    index_path = config.data_dir / "index.jsonl"
    if not index_path.exists():
        print(f"No index at {index_path}. Run `find-best-mobo index` first.")
        return 1
    cache_dir = config.data_dir / "transcripts"
    if not any(cache_dir.glob("*.json")):
        print(f"No cached transcripts under {cache_dir}. Run `find-best-mobo fetch` first.")
        return 1

    aliases = load_aliases(table_path)
    tallies = _scan(config, index_path, aliases)
    _report(table_path, aliases, tallies)
    return 0


def _scan(config: Config, index_path: Path, aliases: tuple[Alias, ...]) -> dict[str, _Tally]:
    """Walk the corpus once, tallying every canonical as it goes.

    Only videos the index left `pending` are scanned: those are the corpus the
    later slices work from, and an excluded Short's title should not inflate a
    canonical's reach. Each transcript is dropped before the next is read.
    """
    matcher = compile_matcher(aliases)
    tallies = {alias.canonical: _Tally() for alias in aliases}
    for video in read_index(index_path):
        if video.inclusion != "pending":
            continue
        title_hits = find_title_hits(video, matcher)
        transcript = load_cached(video.video_id, config)
        mentions = find_mentions(transcript, matcher) if transcript is not None else ()
        for mention in mentions:
            tally = tallies[mention.canonical]
            tally.mentions += 1
            tally.forms.add(mention.matched_form)
        for canonical in title_hits:
            tallies[canonical].title_videos += 1
        for canonical in title_hits | {mention.canonical for mention in mentions}:
            tallies[canonical].videos += 1
    return tallies


def _report(table_path: Path, aliases: tuple[Alias, ...], tallies: dict[str, _Tally]) -> None:
    """Print the tallies in a fixed order (R23), zero-match entries called out.

    Descending video count, then canonical ascending — so a canonical that
    matched nothing sorts to the bottom, where the summary picks it up again.
    """
    print(f"Alias table: {table_path}")
    print(f"{len(aliases)} canonicals")
    print("")
    ordered = sorted(aliases, key=lambda alias: (-tallies[alias.canonical].videos, alias.canonical))
    for alias in ordered:
        tally = tallies[alias.canonical]
        forms = ", ".join(sorted(tally.forms)) if tally.forms else "none"
        line = (
            f"{alias.canonical} ({alias.kind})  videos={tally.videos}  "
            f"titles={tally.title_videos}  mentions={tally.mentions}  forms: {forms}"
        )
        if tally.videos == 0:
            line = f"{line}  <- NEVER MATCHED"
        print(line)

    never = [alias for alias in ordered if tallies[alias.canonical].videos == 0]
    print("")
    if not never:
        print("Every canonical matched at least one video.")
        return
    print(f"{len(never)} of {len(aliases)} canonicals never matched anything:")
    for alias in never:
        print(f"  {alias.canonical} ({alias.kind})")
    print("Either the spelling is wrong or nobody says it. Fix the table and re-run.")
