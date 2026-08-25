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
from dataclasses import dataclass, replace

from find_best_mobo.aliases import Mention
from find_best_mobo.config import Config
from find_best_mobo.index import Video
from find_best_mobo.transcripts import Transcript


@dataclass(frozen=True)
class Excerpt:
    """One block of speech a bundle will carry, however it was chosen.

    The last three fields are R1008's, and they are DEFAULTED on purpose. An
    excerpt-path block is the common case and keeps every existing construction
    site working untouched; only `submission.split_whole` sets them to anything
    else. `form` says which path produced the block, and `part`/`part_count`
    say where it sits when a whole transcript was too big for one bundle and
    was delivered across several.
    """

    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    text: str
    canonicals: tuple[str, ...]
    form: str = "excerpts"
    part: int = 1
    part_count: int = 1


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


def merge_overlapping(excerpts: Sequence[Excerpt], transcript: Transcript) -> tuple[Excerpt, ...]:
    """Fold windows that overlap or touch into single excerpts, RE-CUT from the cues.

    Touching exactly counts as overlapping: a zero-second gap between two windows
    is not worth a second excerpt, a second XML block and a second copy of the
    provenance. Merging on touch is also what makes the surviving spans strictly
    disjoint, which is half the proof of the bound below — do not relax it to a
    strict `<`.

    **The merged text is re-cut from the transcript, never assembled from the two
    window texts** (OD-4, R1000). The old behaviour concatenated on partial
    overlap, so every character in the overlap was paid for once per window
    instead of once. BL-10 measured a 28,438-character transcript producing a
    single 137,246-character excerpt — 4.8x the whole transcript — and the cost
    projection, which is the one number the checkpoint exists to produce, was
    wrong by that factor. Re-running the real corpus on 2026-08-24 made the same
    defect much larger: one 91-minute video's 213,000-character transcript
    became a 12,166,000-character excerpt.

    **The bound is a property, not an estimate.** Merged spans are disjoint and
    cue membership is decided on the cue's START alone, so each cue's text lands
    in at most one excerpt and a video's summed excerpt characters can never
    exceed `transcript_characters(transcript)`.

    Every excerpt must belong to `transcript`; a foreign one is a `ValueError`
    rather than a silent pass-through. The only caller already passes one
    video's windows and R22 forbids holding a channel at once, so "never merge
    across videos" becomes unaskable rather than enforced.
    """
    for excerpt in excerpts:
        if excerpt.video_id != transcript.video_id:
            raise ValueError(
                f"excerpt for {excerpt.video_id!r} cannot be merged against "
                f"the transcript of {transcript.video_id!r}"
            )
    ordered = sorted(excerpts, key=lambda e: (e.start_seconds, e.end_seconds))
    merged: list[Excerpt] = []
    for excerpt in ordered:
        if merged and excerpt.start_seconds <= merged[-1].end_seconds:
            previous = merged[-1]
            merged[-1] = replace(
                previous,
                end_seconds=max(previous.end_seconds, excerpt.end_seconds),
                canonicals=_distinct_sorted(previous.canonicals + excerpt.canonicals),
            )
            continue
        merged.append(replace(excerpt, canonicals=_distinct_sorted(excerpt.canonicals)))
    # Re-cut once, after every span is final: cutting during the fold would
    # re-read the same cues for every merge and produce the same answer.
    return tuple(
        replace(span, text=_text_between(transcript, span.start_seconds, span.end_seconds))
        for span in merged
    )


def transcript_text(transcript: Transcript) -> str:
    """The whole transcript as one line, joined the way an excerpt is.

    ONE definition of that join, in one place (R1008). `_text_between` performs
    the same single-space join over a span, and R28's saturation ratio measures
    excerpt characters against this text — so if the two were computed
    separately they would drift by a space per cue, and the ratio's denominator
    and the whole path's own text would disagree about the same transcript.
    Zero cues is the empty string.
    """
    return " ".join(cue.text for cue in transcript.cues)


def transcript_characters(transcript: Transcript) -> int:
    """The characters of a whole transcript, joined the way an excerpt is.

    Exactly `len(transcript_text(transcript))`, and defined that way rather than
    re-joining, so R1000's bound is exact rather than approximate — an excerpt's
    own text carries the separators between its cues, and a denominator that
    omitted them would make the bound false. Zero cues is 0.
    """
    return len(transcript_text(transcript))


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
