"""Turning mentions into the passages a reader would actually need to see.

A mention is a timestamp, and a timestamp on its own is worthless evidence: the
sentence containing "X670E" is rarely the sentence that says whether it is any
good. So each mention becomes a WINDOW of surrounding speech, and the window is
deliberately asymmetric — two minutes before, five after (`docs/DESIGN.md` R5).
He names a board, works through its VRM, its topology, its firmware, and only
then delivers the verdict, so the useful material sits mostly AFTER the mention.
A symmetric window would cut the conclusion off and keep the preamble.

Three steps, in order, and they are separate because each one is a different
kind of judgement. `cut_windows` is arithmetic on timestamps. `merge_overlapping`
is about not paying twice for the same speech. `cap_per_video` is a budget
decision — which passages survive when one video has more than the run can
afford (R17).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from find_best_mobo.aliases import Mention
from find_best_mobo.config import Config
from find_best_mobo.index import Video
from find_best_mobo.transcripts import Transcript


@dataclass(frozen=True)
class Excerpt:
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    text: str
    canonicals: tuple[str, ...]


def cut_windows(
    transcript: Transcript, mentions: Sequence[Mention], video: Video, config: Config
) -> tuple[Excerpt, ...]:
    """One window per mention, in the order the mentions were given.

    The start is clamped at zero — a mention ninety seconds in cannot reach back
    before the video began — but the END is deliberately NOT clamped to the
    transcript's length. Nothing here knows how long the video really is, and a
    window running past the last cue simply collects no further cues, which is
    the same outcome as clamping with none of the guessing.

    Overlap between neighbouring windows is expected and is left alone: merging
    is `merge_overlapping`'s job, and doing it here would mean deciding what to
    merge before knowing what the full set of windows is.
    """
    excerpts: list[Excerpt] = []
    for mention in mentions:
        start = max(0.0, mention.start_seconds - config.window_before_seconds)
        end = mention.start_seconds + config.window_after_seconds
        excerpts.append(
            Excerpt(
                video_id=video.video_id,
                video_title=video.title,
                start_seconds=start,
                end_seconds=end,
                text=_text_between(transcript, start, end),
                canonicals=(mention.canonical,),
            )
        )
    return tuple(excerpts)


def merge_overlapping(excerpts: Sequence[Excerpt]) -> tuple[Excerpt, ...]:
    """Fold windows of the same video that overlap or touch into single excerpts.

    Touching exactly counts as overlapping: a zero-second gap between two windows
    is not worth a second excerpt, a second XML block and a second copy of the
    provenance. Excerpts from different videos never merge, whatever their
    timestamps say — the timestamps are only comparable within one video.

    The merged TEXT is assembled from the two texts rather than re-cut from cues,
    because this function has no cues to re-cut from. When the later window sits
    wholly inside the earlier one its text adds nothing and is dropped; otherwise
    the two are joined and the speech in the overlap is counted twice. That is a
    known imprecision and it is accepted deliberately: it OVER-states the token
    count, which is the safe direction for a projection the owner spends money
    against. The alternative — trimming the duplicate by matching prose strings —
    is guesswork on auto-caption text, and a wrong guess silently deletes
    evidence instead of visibly inflating a number.
    """
    ordered = sorted(excerpts, key=lambda e: (e.start_seconds, e.end_seconds, e.video_id))
    merged: list[Excerpt] = []
    # Per video, the index in `merged` of the excerpt still open for merging.
    # Only the most recent one per video can ever merge, since `ordered` is
    # ascending by start and merging only extends an excerpt to the right.
    open_index: dict[str, int] = {}
    for excerpt in ordered:
        index = open_index.get(excerpt.video_id)
        if index is not None and excerpt.start_seconds <= merged[index].end_seconds:
            merged[index] = _merge_pair(merged[index], excerpt)
            continue
        open_index[excerpt.video_id] = len(merged)
        merged.append(
            Excerpt(
                video_id=excerpt.video_id,
                video_title=excerpt.video_title,
                start_seconds=excerpt.start_seconds,
                end_seconds=excerpt.end_seconds,
                text=excerpt.text,
                canonicals=_distinct_sorted(excerpt.canonicals),
            )
        )
    return tuple(merged)


def cap_per_video(excerpts: Sequence[Excerpt], config: Config) -> tuple[Excerpt, ...]:
    """Keep at most `per_video_excerpt_cap` excerpts from any one video (R17).

    Ranked by how many DISTINCT canonicals the excerpt carries, most first. A
    passage naming four boards is a comparison; a passage naming one is a board
    being described. When the budget forces a choice, the comparison is the thing
    worth paying to read, and mention density is the only proxy available before
    a model has read anything.

    Ties break by the earlier start, then by video id, so a rerun makes the same
    cut (R23). The survivors are returned in chronological order per video rather
    than in ranked order — whoever reads them is reading a timeline, and ranked
    order would present the video's ending before its middle.
    """
    cap = config.per_video_excerpt_cap
    order: dict[str, int] = {}
    grouped: dict[str, list[Excerpt]] = {}
    for excerpt in excerpts:
        order.setdefault(excerpt.video_id, len(order))
        grouped.setdefault(excerpt.video_id, []).append(excerpt)

    kept: list[Excerpt] = []
    for video_id in sorted(grouped, key=lambda key: order[key]):
        group = grouped[video_id]
        if len(group) > cap:
            group = sorted(
                group,
                key=lambda e: (-len(e.canonicals), e.start_seconds, e.video_id),
            )[:cap]
        kept.extend(sorted(group, key=lambda e: (e.start_seconds, e.end_seconds)))
    return tuple(kept)


def _merge_pair(earlier: Excerpt, later: Excerpt) -> Excerpt:
    """Combine two overlapping excerpts of the same video into one.

    `later` starts at or after `earlier` because the caller sorted; the span is
    therefore `earlier.start` to whichever end is further out.
    """
    contained = later.end_seconds <= earlier.end_seconds
    return Excerpt(
        video_id=earlier.video_id,
        video_title=earlier.video_title,
        start_seconds=earlier.start_seconds,
        end_seconds=max(earlier.end_seconds, later.end_seconds),
        text=earlier.text if contained else f"{earlier.text} {later.text}",
        canonicals=_distinct_sorted(earlier.canonicals + later.canonicals),
    )


def _distinct_sorted(canonicals: Sequence[str]) -> tuple[str, ...]:
    """Distinct canonicals, alphabetically, so the same input renders the same (R23)."""
    return tuple(sorted(set(canonicals)))


def _text_between(transcript: Transcript, start: float, end: float) -> str:
    """Every cue starting inside `[start, end]`, in cue order, as one line.

    Membership is decided on the cue's START alone. A cue is a couple of seconds
    of speech, so where its end falls is noise next to the two-and-seven-minute
    window around it, and testing one endpoint keeps the rule statable.
    """
    return " ".join(cue.text for cue in transcript.cues if start <= cue.start_seconds <= end)
