"""Which path a video's evidence takes to the model, and what that path costs.

A video whose excerpt windows have grown to cover most of it is not really being
excerpted any more. The windows overlap, the merge folds them back together, and
what comes out is the transcript with a few gaps in it — paid for as excerpts,
carrying excerpt structure, and missing the passages between the mentions for no
saving worth having. R28 draws the line at 80%: at or above that ratio the whole
transcript is sent instead.

**The path is decided by the ratio and by nothing else** (OD-13, R1008). An
earlier design capped the whole path at one bundle's token cap and bounced an
over-cap video back to excerpts; OD-13 superseded that. A transcript too large
for one bundle is now cut at CUE boundaries into consecutive parts and delivered
across sequential bundles. So a three-hour saturated stream takes the same path a
thirty-minute one does, and the cap decides only how many blocks it arrives in.

Nothing here invokes a model. This module decides what would be sent and what it
would be projected to cost; `docs/DESIGN.md` R7's checkpoint still stops the
pipeline before anything is spent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from find_best_mobo.bundle import estimate_tokens
from find_best_mobo.config import Config
from find_best_mobo.excerpt import Excerpt, transcript_characters
from find_best_mobo.index import Video
from find_best_mobo.transcripts import Cue, Transcript

# R28's threshold, "80% or more" — so the comparison is `>=` and exactly at the
# line takes the whole path. A named constant because the number is the owner's
# and the plan's readers look for it by name.
WHOLE_TRANSCRIPT_RATIO: float = 0.80

EXCERPTS = "excerpts"
WHOLE = "whole"


@dataclass(frozen=True)
class VideoSubmission:
    """One video's contribution, which path it took, and what that path cost."""

    video_id: str
    video_title: str
    path: str
    blocks: tuple[Excerpt, ...]
    excerpt_characters: int
    transcript_characters: int
    projected_tokens: int


def excerpt_ratio(excerpts: Sequence[Excerpt], transcript: Transcript) -> float:
    """How much of the transcript the excerpts already cover, 0.0 to 1.0.

    The excerpts must be the blocks that would ACTUALLY be sent — after
    `merge_overlapping` has re-cut them and after `cap_per_video` has thrown away
    what the budget cannot afford. Measuring before the merge counts every
    overlapping second twice and pushes nearly everything over the line;
    measuring before the cap routes a video whole on the strength of excerpts
    that were then discarded.

    A transcript with no text has no ratio to give: it returns 0.0 rather than
    dividing by zero, and `choose_submission` sends such a video down the excerpt
    path.
    """
    total = transcript_characters(transcript)
    if total == 0:
        return 0.0
    return sum(len(excerpt.text) for excerpt in excerpts) / total


def split_whole(
    video: Video,
    transcript: Transcript,
    canonicals: Sequence[str],
    config: Config,
) -> tuple[Excerpt, ...]:
    """The whole transcript as one block per bundle-sized part, in cue order.

    Cues are taken in order into a part while the part's projected tokens stay
    at or under `bundle_token_cap`; the first cue that would carry it over starts
    the next part. **A cue is never split.** One whose own projected tokens
    exceed the cap becomes a part on its own and exceeds it — `pack_bundles`
    already gives an over-cap block a bundle to itself, so it stays visible in
    the projection as the outsized thing it is, rather than being cut
    mid-sentence or dropped.

    The parts partition the cues, so no speech is lost and none is repeated, and
    the arithmetic says so exactly: the parts' texts sum to
    `transcript_characters(transcript) - (part_count - 1)`, one joining space
    being consumed at each split.

    A part's span runs from its first cue's start to its LAST CUE'S START — the
    convention `cut_windows` already uses, where a cue's end is not known.
    `canonicals` is repeated on every part, so each one carries its own
    provenance into whichever bundle it lands in.
    """
    parts: list[list[Cue]] = []
    current: list[Cue] = []

    for cue in transcript.cues:
        candidate = current + [cue]
        over = estimate_tokens(" ".join(item.text for item in candidate), config)
        if current and over > config.bundle_token_cap:
            parts.append(current)
            current = [cue]
            continue
        current = candidate
    if current:
        parts.append(current)

    shared = tuple(sorted(set(canonicals)))
    part_count = len(parts)
    return tuple(
        Excerpt(
            video_id=video.video_id,
            video_title=video.title,
            start_seconds=cues[0].start_seconds,
            end_seconds=cues[-1].start_seconds,
            text=" ".join(cue.text for cue in cues),
            canonicals=shared,
            form=WHOLE,
            part=index + 1,
            part_count=part_count,
        )
        for index, cues in enumerate(parts)
    )


def choose_submission(
    video: Video, transcript: Transcript, excerpts: Sequence[Excerpt], config: Config
) -> VideoSubmission:
    """Route one video, and report what its chosen blocks would cost.

    Size is never consulted. The ratio decides, `>=` so that exactly at the
    threshold takes the whole path, and a transcript with no text takes the
    excerpt path rather than dividing by zero. A video with no excerpts has ratio
    0.0 and contributes nothing, exactly as it does today.

    `projected_tokens` is the submission's OWN cost — `estimate_tokens` summed
    over the blocks it will actually contribute — so the projection does not
    re-derive it and a reader can check one video's routing against one number.
    """
    total = transcript_characters(transcript)
    ratio = excerpt_ratio(excerpts, transcript)
    whole = total > 0 and ratio >= WHOLE_TRANSCRIPT_RATIO

    if whole:
        canonicals = sorted({canonical for excerpt in excerpts for canonical in excerpt.canonicals})
        blocks = split_whole(video, transcript, canonicals, config)
        path = WHOLE
    else:
        blocks = tuple(excerpts)
        path = EXCERPTS

    return VideoSubmission(
        video_id=video.video_id,
        video_title=video.title,
        path=path,
        blocks=blocks,
        excerpt_characters=sum(len(excerpt.text) for excerpt in excerpts),
        transcript_characters=total,
        projected_tokens=sum(estimate_tokens(block.text, config) for block in blocks),
    )
