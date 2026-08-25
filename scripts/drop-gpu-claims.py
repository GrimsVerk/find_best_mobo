#!/usr/bin/env python3
"""Remove claims that are about a GRAPHICS CARD rather than a motherboard.

Why they are there. The extraction prompt tells the model that "a claim about a
CPU, a chipset in general, or the industry is not a claim about a board" and to
skip it. It never says the same about graphics cards, and Buildzoid reviews
those too -- so a GPU PCB breakdown produces perfectly well-formed claims about
a product this project is not about. The fix in the prompt belongs in the next
extraction; this removes what the current corpus already holds.

The rule needs THREE signals to agree, because the cheap ones are wrong on their
own. Dropping by video throws away the real motherboard claims that GPU videos
contain -- Buildzoid talks about the board he is testing on. Dropping by board
name misfires the other way: `MSI 970 Gaming Krait` is a motherboard, and the
ambiguous names (`MSI`, `ASUS`, `ROG Strix`) name both kinds of product.

So a claim is dropped only when ALL of:

  1. the source video is about a graphics card or a power connector, AND
  2. the claim's own text positively talks about a card, AND
  3. nothing in it names a chipset, a socket, a BIOS, or a motherboard family.

Deliberately conservative: anything ambiguous is KEPT. That leaves some genuine
GPU claims behind -- a card claim that happens to mention a chipset code stays
-- and that is the intended direction of the error. Over-keeping is a filtering
problem for a later stage; over-deleting destroys evidence that cost money.

Usage:  uv run python scripts/drop-gpu-claims.py [--apply]
Without --apply it only reports. The original is copied to claims.jsonl.bak.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

STORE = Path("data/claims.jsonl")

GPU_VIDEO = re.compile(
    r"\bGPU\b|graphics card|RTX|GTX|RX ?90[0-9]{2}|melting power connector|power balancing", re.I
)
GPU_VOCAB = re.compile(
    r"\b(card|cards|gpu|vram|nvidia|geforce|radeon|rtx|gtx|\d{3,4}\s?ti|4090|4080|4070|3080|"
    r"3090|980|970|960|760|9070|5090|die|shunt|12vhpwr|12vt)\b",
    re.I,
)
MOBO_TOKEN = re.compile(
    r"([XZBHA]\d{2,3}[A-Z]?\b|AM[45]\b|LGA\s?\d{3,4}|\b(socket|chipset|motherboard|mobo|boards|bios|"
    r"dimm|rampage|maximus|crosshair|apex|taichi|tomahawk|aorus|godlike|livemixer|steel legend|"
    r"gene|"
    r"encore|hero|formula|unify|carbon|krait|designare|itx)\b)",
    re.I,
)


# The owner ruled in chat on 2026-08-25, twice: "it is way more important to
# include motherboards than to exclude gpus", and "make sure that you dont drop
# any motherboards in the filtering, that is the bigger error". So the error
# budget is asymmetric BY INSTRUCTION. These two guards are that ruling made
# mechanical, rather than a promise in a docstring that the next widened regex
# quietly breaks.

# No plausible reading of this corpus makes graphics-card claims a large slice of
# it. If a rule change ever says otherwise, the rule is wrong, not the corpus.
MAX_DROPPED_FRACTION = 0.05

# A video whose title says it is about a motherboard is never a source of
# droppable claims, whatever the text of an individual claim looks like. This is
# the belt to the three-signal rule's braces: it cannot be defeated by widening
# GPU_VOCAB, because it never consults it.
MOBO_VIDEO = re.compile(r"\b(mobo|motherboard|mainboard)\b", re.I)


class RefusedToDrop(RuntimeError):
    """The drop set is too large to be believable. Nothing was written."""


def refuse_if_too_much_is_dropped(dropped: Sequence[Mapping[str, object]], total: int) -> None:
    """Fail loudly rather than delete, when the rule suddenly matches far more.

    Over-deletion is the unacceptable error here, and it is the one that looks
    like success: a script that removes a third of the corpus and reports it
    cheerfully is indistinguishable, in its output, from one that worked.
    """
    if not total:
        return
    fraction = len(dropped) / total
    if fraction > MAX_DROPPED_FRACTION:
        raise RefusedToDrop(
            f"the rule matched {len(dropped)} of {total} claims ({fraction:.1%}), over the "
            f"{MAX_DROPPED_FRACTION:.0%} ceiling. Motherboard claims are the thing that must "
            "not be lost, so this refuses to write rather than delete on a rule it cannot "
            "believe. Widen nothing until the drop set has been read row by row."
        )


def is_about_a_graphics_card(claim: Mapping[str, Any]) -> bool:
    """True only when all three signals agree. Unsure means False, which KEEPS."""
    title = str(claim["video_title"])
    if MOBO_VIDEO.search(title):
        return False
    text = f"{claim['board']} {claim['snippet']}"
    return bool(GPU_VIDEO.search(title) and GPU_VOCAB.search(text) and not MOBO_TOKEN.search(text))


def main() -> int:
    rows = [json.loads(line) for line in STORE.read_text(encoding="utf-8").splitlines() if line]
    dropped = [row for row in rows if is_about_a_graphics_card(row)]
    kept = [row for row in rows if not is_about_a_graphics_card(row)]

    refuse_if_too_much_is_dropped(dropped, len(rows))
    print(f"{len(rows)} claims, {len(dropped)} about a graphics card, {len(kept)} kept")
    for row in dropped:
        print(f"  drop [{row['board']}] {row['video_id']} @{row['timestamp_seconds']}s")

    if "--apply" not in sys.argv:
        print("\nreport only. Pass --apply to rewrite the store.")
        return 0

    shutil.copy2(STORE, STORE.with_suffix(".jsonl.bak"))
    STORE.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in kept), encoding="utf-8"
    )
    print(f"\nwrote {len(kept)} claims to {STORE}; original kept at {STORE}.bak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
