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

import math
from collections.abc import Sequence
from dataclasses import dataclass

from find_best_mobo.artifacts import require_file
from find_best_mobo.bundle import Bundle, estimate_tokens
from find_best_mobo.config import Config
from find_best_mobo.index import read_index
from find_best_mobo.select import (
    EXCLUDED,
    Coverage,
    Selection,
    render_coverage,
    transcript_coverage,
)
from find_best_mobo.submission import WHOLE, VideoSubmission


@dataclass(frozen=True)
class Projection:
    videos_indexed: int
    videos_selected: int
    excerpt_characters: int
    bundle_count: int
    tokens_per_batch: tuple[int, ...]
    total_tokens: int
    chars_per_token: float
    # How much of the transcript cache the excerpted videos actually had. It
    # sits on the projection because R1012 requires it printed beside the
    # character count: a projection read without it says nothing about what
    # fraction of the corpus produced it.
    coverage: Coverage
    # R1008's routing figures. Every count here counts VIDEOS, never blocks and
    # never bundles, so `videos_whole + videos_excerpted` is the number of
    # submissions and nothing else.
    videos_whole: int
    videos_excerpted: int
    whole_characters: int
    whole_tokens: int
    excerpt_tokens: int
    videos_over_bundle_cap: int
    # (video_id, bundles) for every whole-path video occupying more than one
    # bundle, in submission order — newest first, and the same order twice for
    # the same corpus (R23).
    bundles_spanned: tuple[tuple[str, int], ...]
    # The bound the split was made against, carried on the projection so the
    # rendered spans can state it without reaching for the config again.
    bundle_token_cap: int


def project(
    bundles: Sequence[Bundle],
    selections: Sequence[Selection],
    submissions: Sequence[VideoSubmission],
    config: Config,
) -> Projection:
    """Count the corpus as it now stands, from the bundles and the selections.

    `videos_indexed` is read back off `data/index.jsonl` rather than derived from
    the selections, because the two answer different questions — how much there
    was, against how much survived — and a reader comparing them is doing exactly
    what the funnel is printed for. A missing index RAISES (R1005, OD-9): this
    number is the denominator of the one figure the owner spends against, and a
    projection must never understate itself because an input was absent. An
    index that is present and empty is a real value — a channel with nothing in
    range — and projects a real zero. That distinction is the whole point; the
    forgiving branch that used to sit here erased it.

    `tokens_per_batch` is positional, batch 1 first, and keeps a zero for every
    batch that got no bundles. A short tuple would make "batch 3 is empty" and
    "there is no batch 3" the same reading, which is the one thing the owner
    would misread when deciding what to pay for next.

    **The path figures come from the SUBMISSIONS; the span figures come from the
    BUNDLES** (R1008). A bundle cannot say why a video is on the excerpt path,
    and a part count cannot say what actually happened to the parts — so
    `bundles_spanned` counts the distinct bundles holding a whole-form block of
    that video, which is what the transcript SPANS rather than what the router
    intended.

    The two are cross-checked rather than merely described.
    `videos_over_bundle_cap` is derived from the submissions and must equal
    `len(bundles_spanned)`, derived from the bundles. Intent and outcome
    agreeing is the whole claim of slice 2's ordering invariant; a run where
    they disagree is a defect the projection should surface rather than smooth
    over, so the suite asserts the equality instead of a comment promising it.

    No submissions is a real value: zeroes on every path and an empty span
    list. R1005's absent-index refusal above is a different condition and is
    unweakened by that.
    """
    index_path = require_file(config.data_dir / "index.jsonl", "index", "index")
    videos_indexed = sum(1 for video in read_index(index_path) if video.inclusion == "pending")
    excerpts = [excerpt for bundle in bundles for excerpt in bundle.excerpts]

    batch_count = max(1 + max(config.batch_count, 0), *(bundle.batch for bundle in bundles), 1)
    tokens_per_batch = [0] * batch_count
    for bundle in bundles:
        if bundle.batch >= 1:
            tokens_per_batch[bundle.batch - 1] += bundle.projected_tokens

    included = [s for s in selections if s.reason != EXCLUDED]
    excerpt_blocks = [block for block in excerpts if block.form != WHOLE]
    whole_blocks = [block for block in excerpts if block.form == WHOLE]

    # Distinct bundles per whole-path video, walked over the bundles rather than
    # read off `part_count`: what the transcript actually spans, not what the
    # split intended. Submission order is preserved, so the list is newest first
    # and identical between two runs over the same corpus (R23).
    spanned: dict[str, set[int]] = {}
    for index, bundle in enumerate(bundles):
        for block in bundle.excerpts:
            if block.form == WHOLE:
                spanned.setdefault(block.video_id, set()).add(index)
    whole_submissions = [s for s in submissions if s.path == WHOLE]
    bundles_spanned = tuple(
        (s.video_id, len(spanned[s.video_id]))
        for s in whole_submissions
        if len(spanned.get(s.video_id, ())) > 1
    )

    return Projection(
        videos_indexed=videos_indexed,
        videos_selected=len(included),
        excerpt_characters=sum(len(block.text) for block in excerpt_blocks),
        bundle_count=len(bundles),
        tokens_per_batch=tuple(tokens_per_batch),
        total_tokens=sum(bundle.projected_tokens for bundle in bundles),
        chars_per_token=config.chars_per_token,
        # The INCLUDED selections, matching the line it is printed beside:
        # `excerpt_characters` is summed over the videos that were
        # excerpted, and a coverage figure over a different set than the
        # number it annotates is worse than none. Read off the selections,
        # never re-derived from the cache — see R1012.
        coverage=transcript_coverage(included),
        videos_whole=len(whole_submissions),
        videos_excerpted=len(submissions) - len(whole_submissions),
        whole_characters=sum(len(block.text) for block in whole_blocks),
        whole_tokens=sum(estimate_tokens(block.text, config) for block in whole_blocks),
        excerpt_tokens=sum(estimate_tokens(block.text, config) for block in excerpt_blocks),
        videos_over_bundle_cap=sum(
            1 for s in whole_submissions if _transcript_tokens(s, config) > config.bundle_token_cap
        ),
        bundles_spanned=bundles_spanned,
        bundle_token_cap=config.bundle_token_cap,
    )


def _transcript_tokens(submission: VideoSubmission, config: Config) -> int:
    """`estimate_tokens` over the whole transcript, from the length it recorded.

    The projection holds no transcripts — R22 drops each one as soon as its
    blocks are cut — so the token figure is taken from the character count the
    submission carries. `estimate_tokens` depends on nothing but that length, so
    this is the same number, not an approximation of it; it is written as a
    named function rather than inline so the equality is somewhere a reader can
    check it.
    """
    return math.ceil(submission.transcript_characters / config.chars_per_token)


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
        f"  {render_coverage(projection.coverage, 'selected videos')}",
        f"  {projection.bundle_count} bundles written",
        f"  {projection.videos_excerpted} videos sent as excerpts: "
        f"{projection.excerpt_characters} characters, {projection.excerpt_tokens} projected tokens",
        f"  {projection.videos_whole} videos sent whole: "
        f"{projection.whole_characters} characters, {projection.whole_tokens} projected tokens",
    ]
    # The cap is stated in the same breath as the spans, for the same reason the
    # chars-per-token factor is stated beside the totals: a span reported without
    # the bound that produced it invites the reader to treat it as a property of
    # the corpus rather than of the configuration (R1008).
    lines.append(
        f"  {projection.videos_over_bundle_cap} whole transcripts exceed one bundle's "
        f"{projection.bundle_token_cap}-token cap and are split across sequential bundles"
    )
    for video_id, spanned in projection.bundles_spanned:
        lines.append(f"    {video_id} spans {spanned} bundles")
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
