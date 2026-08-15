"""Packing excerpts into work units, and writing them out as XML.

A bundle is one unit of reading work: as much excerpt text as fits under a token
cap, tagged with enough provenance that whoever reads it can say which video and
which minute a statement came from (`docs/DESIGN.md` R6). Bundles are then
grouped into batches — a small CALIBRATION batch first, then the rest — so that
the run's real cost is measured on a fraction of it before the whole corpus is
committed to.

XML carries the structure, by the owner's ruling, with the transcript sitting
inside the tags as plain prose. The reason is attention, not size: tagged
boundaries are read reliably, whereas markdown headings blur into the transcript
they are meant to delimit. Closing tags cost MORE tokens than headings, and that
was accepted knowingly.

Nothing here invokes a model, and nothing here can: the milestone ends at the
projection, and the bundles are written to disk for a separate, later, explicit
command that does not exist yet.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from xml.sax.saxutils import escape

from find_best_mobo.config import Config
from find_best_mobo.excerpt import Excerpt

# `escape` handles `&`, `<` and `>`; attribute values additionally need the
# quote that delimits them. Auto-captions really do contain `<` and `>`, so this
# is the difference between a valid bundle and an unparseable one.
_ATTRIBUTE_EXTRAS = {'"': "&quot;"}


@dataclass(frozen=True)
class Bundle:
    bundle_id: str
    batch: int
    excerpts: tuple[Excerpt, ...]
    projected_tokens: int


def estimate_tokens(text: str, config: Config) -> int:
    """Characters divided by the configured factor, rounded up.

    The factor is a GUESS — four characters per token — and it is configuration
    rather than a constant precisely because it is a guess. Nothing here pretends
    otherwise; the projection prints the number it used so that the calibration
    batch can replace it with a measurement (R7).
    """
    if not text:
        return 0
    return math.ceil(len(text) / config.chars_per_token)


def pack_bundles(excerpts: Sequence[Excerpt], config: Config) -> tuple[Bundle, ...]:
    """Fill bundles greedily, in the order given, under `bundle_token_cap` (R6).

    The order given is meaningful — the caller supplies most-recent video first —
    so packing never reorders to fit more in. A tighter fit is worth less than
    batches that stay in recency order all the way to the projection.

    An excerpt bigger than the whole cap gets a bundle to ITSELF rather than
    being dropped or split. Splitting would cut a passage mid-argument, and
    dropping would lose evidence silently; an over-cap bundle is at least
    visible in the projection as the outsized thing it is.
    """
    bundles: list[Bundle] = []
    current: list[Excerpt] = []
    current_tokens = 0

    def close() -> None:
        nonlocal current, current_tokens
        bundles.append(
            Bundle(
                bundle_id=f"bundle-{len(bundles) + 1:03d}",
                batch=0,
                excerpts=tuple(current),
                projected_tokens=current_tokens,
            )
        )
        current = []
        current_tokens = 0

    for excerpt in excerpts:
        tokens = estimate_tokens(excerpt.text, config)
        if current and current_tokens + tokens > config.bundle_token_cap:
            close()
        current.append(excerpt)
        current_tokens += tokens
        # Only reachable with a single excerpt in hand: anything that would have
        # pushed a non-empty bundle over the cap closed it just above. So this
        # is the over-cap excerpt getting its own bundle, alone.
        if current_tokens > config.bundle_token_cap:
            close()
    if current:
        close()
    return tuple(bundles)


def assign_batches(bundles: Sequence[Bundle], config: Config) -> tuple[Bundle, ...]:
    """Number each bundle's batch: 1 is calibration, then `batch_count` more (R6).

    Batch 1 exists to be paid for first and looked at before anything else is
    paid for at all — it is where the chars-per-token guess gets replaced by a
    measurement, and where the excerpts get read by a human deciding whether the
    window and the threshold are set right.

    The remainder is split as evenly as the count allows, with leftovers going to
    the EARLIER batches, so no earlier batch is ever smaller than a later one —
    a run stopped halfway has then done the larger share of the work it planned.
    Order is preserved rather than sorted: the caller hands over the bundles
    most-recent-video-first, and recency is the property the batching exists to
    respect.
    """
    if not bundles:
        return ()
    calibration = list(bundles[: config.calibration_batch_size])
    rest = list(bundles[config.calibration_batch_size :])

    assigned = [replace(bundle, batch=1) for bundle in calibration]
    for batch, chunk in enumerate(_split_evenly(rest, config.batch_count), start=2):
        assigned.extend(replace(bundle, batch=batch) for bundle in chunk)
    return tuple(assigned)


def render_bundle(bundle: Bundle) -> str:
    """Render one bundle as the XML a reader is given.

    Timestamps are whole seconds, rounded down: sub-second precision on a
    two-minute window is noise, and a stable integer is what makes two runs
    render byte-identically (R23). Every piece of text is escaped, because
    auto-captions contain `<` often enough that an unescaped bundle would be
    invalid XML on a real corpus rather than on a contrived one.
    """
    lines = [f'<bundle id="{_attribute(bundle.bundle_id)}" batch="{bundle.batch}">']
    for excerpt in bundle.excerpts:
        lines.append(
            f'  <excerpt video_id="{_attribute(excerpt.video_id)}"'
            f' start="{math.floor(excerpt.start_seconds)}"'
            f' end="{math.floor(excerpt.end_seconds)}">'
        )
        lines.append(f"    <video_title>{escape(excerpt.video_title)}</video_title>")
        lines.append(f"    <boards>{escape(', '.join(excerpt.canonicals))}</boards>")
        lines.append(f"    <transcript>{escape(excerpt.text)}</transcript>")
        lines.append("  </excerpt>")
    lines.append("</bundle>")
    return "\n".join(lines) + "\n"


def write_bundles(bundles: Iterable[Bundle], config: Config) -> int:
    """Write each bundle under `data/bundles/batch-N/`, returning how many.

    Foldered by batch because the batch is the unit the owner acts on: reading
    the calibration batch means reading one directory, and paying for batch 2
    means pointing a later command at another. UTF-8 with `\\n` newlines
    throughout, so the same bundles produce byte-identical files every run (R23).
    """
    root = config.data_dir / "bundles"
    written = 0
    for bundle in bundles:
        directory = root / f"batch-{bundle.batch}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{bundle.bundle_id}.xml"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_bundle(bundle))
        written += 1
    return written


def _split_evenly(bundles: Sequence[Bundle], parts: int) -> list[Sequence[Bundle]]:
    """Cut `bundles` into `parts` contiguous chunks, remainders to the front.

    A `parts` of zero or less would have nowhere to put the remainder, so the
    whole remainder stays as one chunk rather than being silently discarded —
    losing bundles to a misconfigured lever is the one outcome worth ruling out.
    """
    if parts <= 0:
        return [bundles] if bundles else []
    size, remainder = divmod(len(bundles), parts)
    chunks: list[Sequence[Bundle]] = []
    cursor = 0
    for index in range(parts):
        take = size + (1 if index < remainder else 0)
        chunks.append(bundles[cursor : cursor + take])
        cursor += take
    return chunks


def _attribute(value: str) -> str:
    """Escape a value for use inside a double-quoted XML attribute."""
    return escape(value, _ATTRIBUTE_EXTRAS)
