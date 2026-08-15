"""The `estimate` stage: cut, bundle, batch, project — and stop.

The last stage of the corpus milestone. It reads what `select` decided, cuts
windows around every mention in every included video, packs them into XML
bundles under `data/bundles/`, and prints what reading them would be projected
to cost. Then it returns.

**There is no continuation.** Nothing in this module, and nothing it imports,
can call a model: the stage that reads the bundles is a separate command that
has not been written. That is the design's central promise made structural — a
checkpoint that the pipeline could stride past on a flag would not be a
checkpoint, it would be a log line.

Videos are handled most-recent-first, one transcript at a time (R22). The
recency order matters downstream: it survives packing and batching, so the
calibration batch is drawn from the newest boards rather than the oldest, and a
run stopped after batch 2 has read the most currently-relevant material.

This stage is reachable from Python only, by owner ruling: the top-level parser
holds no subcommand table, so `run` takes no flags and reads nothing off `args`.
"""

from __future__ import annotations

from argparse import Namespace

from find_best_mobo.bundle import assign_batches, pack_bundles, write_bundles
from find_best_mobo.config import Config
from find_best_mobo.estimate import project, render_projection
from find_best_mobo.excerpt import Excerpt, cap_per_video, cut_windows, merge_overlapping
from find_best_mobo.select import EXCLUDED, Selection, read_selected
from find_best_mobo.transcripts import load_cached


def run(config: Config, args: Namespace) -> int:
    """Build the bundles, print the projection, and stop."""
    path = config.data_dir / "selected.jsonl"
    try:
        selections = tuple(read_selected(path))
    except FileNotFoundError:
        print(f"No selections at {path}. Run `find-best-mobo select` first.")
        return 1

    excerpts: list[Excerpt] = []
    for selection in _included_recent_first(selections):
        excerpts.extend(_excerpts_for(selection, config))

    bundles = assign_batches(pack_bundles(excerpts, config), config)
    written = write_bundles(bundles, config)
    print(f"Wrote {written} bundles to {config.data_dir / 'bundles'}")
    print(render_projection(project(bundles, selections, config)))
    return 0


def _included_recent_first(selections: tuple[Selection, ...]) -> list[Selection]:
    """The selections that were included, newest video first.

    Video id ascending breaks the tie, because several uploads share an upload
    date and an arbitrary order there would shuffle the batches between runs
    (R23) — the same corpus must produce the same calibration batch twice.
    """
    included = [selection for selection in selections if selection.reason != EXCLUDED]
    return sorted(included, key=lambda s: (-s.video.upload_date.toordinal(), s.video.video_id))


def _excerpts_for(selection: Selection, config: Config) -> tuple[Excerpt, ...]:
    """One video's excerpts, or none at all if its transcript is not cached.

    The transcript is loaded, cut, and dropped before the next video is read, so
    the run's memory holds excerpts rather than a channel's worth of cues (R22).

    A missing transcript is not an error here. A video can be selected on its
    title alone with no captions ever fetched, and it has simply nothing to
    excerpt — failing the whole run over it would mean one absent caption track
    costing the projection of the other nine hundred videos.
    """
    transcript = load_cached(selection.video.video_id, config)
    if transcript is None:
        return ()
    windows = cut_windows(transcript, selection.mentions, selection.video, config)
    return cap_per_video(merge_overlapping(windows), config)
