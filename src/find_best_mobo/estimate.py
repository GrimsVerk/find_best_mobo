"""The cost checkpoint: what this corpus would cost to read, and then a full stop.

This is the last thing the milestone does (`docs/DESIGN.md` R7). It counts what
the earlier stages produced, multiplies it by an openly-stated guess about
characters per token, prints the result, and ends. The number is a projection,
not a bill — its whole purpose is to be looked at by the owner BEFORE any money
is committed, which is only meaningful if the pipeline genuinely cannot carry on
without a separate decision.

So the stop is structural rather than promised: there is no branch here, and no
import anywhere in this slice, that leads to a model being called. The stage that
reads the bundles is a different command, and it does not exist yet.

Every figure the projection prints is a count of something already on disk,
except the chars-per-token factor, which is a guess and is labelled as one. The
calibration batch exists to replace it with a measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from find_best_mobo.bundle import Bundle
from find_best_mobo.config import Config
from find_best_mobo.index import read_index
from find_best_mobo.select import EXCLUDED, Selection


@dataclass(frozen=True)
class Projection:
    videos_indexed: int
    videos_selected: int
    excerpt_characters: int
    bundle_count: int
    tokens_per_batch: tuple[int, ...]
    total_tokens: int
    chars_per_token: float


def project(
    bundles: Sequence[Bundle], selections: Sequence[Selection], config: Config
) -> Projection:
    """Count the corpus as it now stands, from the bundles and the selections.

    `videos_indexed` is read back off `data/index.jsonl` rather than derived from
    the selections, because the two answer different questions — how much there
    was, against how much survived — and a reader comparing them is doing exactly
    what the funnel is printed for. A missing index counts as zero rather than
    raising: by the time this runs the selections have already been read, and
    losing the whole projection over one absent denominator helps nobody.

    `tokens_per_batch` is positional, batch 1 first, and keeps a zero for every
    batch that got no bundles. A short tuple would make "batch 3 is empty" and
    "there is no batch 3" the same reading, which is the one thing the owner
    would misread when deciding what to pay for next.
    """
    index_path = config.data_dir / "index.jsonl"
    videos_indexed = (
        sum(1 for video in read_index(index_path) if video.inclusion == "pending")
        if index_path.exists()
        else 0
    )
    excerpts = [excerpt for bundle in bundles for excerpt in bundle.excerpts]

    batch_count = max(1 + max(config.batch_count, 0), *(bundle.batch for bundle in bundles), 1)
    tokens_per_batch = [0] * batch_count
    for bundle in bundles:
        if bundle.batch >= 1:
            tokens_per_batch[bundle.batch - 1] += bundle.projected_tokens

    return Projection(
        videos_indexed=videos_indexed,
        videos_selected=sum(1 for selection in selections if selection.reason != EXCLUDED),
        excerpt_characters=sum(len(excerpt.text) for excerpt in excerpts),
        bundle_count=len(bundles),
        tokens_per_batch=tuple(tokens_per_batch),
        total_tokens=sum(bundle.projected_tokens for bundle in bundles),
        chars_per_token=config.chars_per_token,
    )


def render_projection(projection: Projection) -> str:
    """The printable projection: the funnel, the batches, and the stop.

    Written to be read by someone deciding whether to spend, so it states the
    estimate's basis in the same breath as its result. A total presented without
    the assumption behind it invites the reader to treat it as measured, and this
    one is not measured — that is what the calibration batch is for.
    """
    lines = [
        "Cost projection (no model has been invoked)",
        f"  {projection.videos_indexed} videos indexed and pending",
        f"  {projection.videos_selected} videos selected for excerpting",
        f"  {projection.excerpt_characters} characters of excerpt text",
        f"  {projection.bundle_count} bundles written",
    ]
    for index, tokens in enumerate(projection.tokens_per_batch, start=1):
        label = " (calibration)" if index == 1 else ""
        lines.append(f"  batch {index}{label}: {tokens} projected tokens")
    lines.append(f"  {projection.total_tokens} projected tokens in total")
    lines.append(
        f"Projected at {projection.chars_per_token} characters per token. That factor is an "
        "ESTIMATE, not a measurement: the calibration batch exists to correct it, "
        "so treat the totals above as an order of magnitude rather than a price."
    )
    lines.append(
        "The pipeline STOPS here. No model has been or will be invoked by this "
        "command — reading the bundles is a separate, explicit decision, and the "
        "bundles are on disk waiting for it."
    )
    return "\n".join(lines)
