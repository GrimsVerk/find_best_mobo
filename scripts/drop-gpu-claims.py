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
from pathlib import Path

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


def is_about_a_graphics_card(claim: dict) -> bool:
    text = f"{claim['board']} {claim['snippet']}"
    return bool(
        GPU_VIDEO.search(claim["video_title"])
        and GPU_VOCAB.search(text)
        and not MOBO_TOKEN.search(text)
    )


def main() -> int:
    rows = [json.loads(line) for line in STORE.read_text(encoding="utf-8").splitlines() if line]
    dropped = [row for row in rows if is_about_a_graphics_card(row)]
    kept = [row for row in rows if not is_about_a_graphics_card(row)]

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
