#!/usr/bin/env python3
"""Split data/claims.jsonl into worker prompt files for board resolution."""

import json
import pathlib
import sys

REPO = pathlib.Path("/home/loke/code/GrimsVerk/find_best_mobo")
OUT = pathlib.Path(__file__).parent
CHUNK_SIZE = 100

TEMPLATE = """You are a data-cleaning worker in a checkout of the find_best_mobo repo.

Task: for each input row at the bottom, identify the specific motherboard the
claim is about, and its CPU platform. Use only the row's own video_title and
snippet as context. The tracked file aliases.toml in the repo root maps mention
aliases to canonical board names; you may Read it to normalize spellings.

Each input row is one JSON object:
  {{"i": <id>, "board": <name as extracted>, "video_title": ..., "snippet": ...}}

The "board" field is often only a brand (e.g. "ASUS") or a bare family name
(e.g. "Taichi"). The video_title usually names the exact model and chipset.

Write the file analysis/brand-map/{name}.jsonl: one JSON object per input row,
same order, one per line:
  {{"i": <same id>, "canonical_board": "<Brand Chipset Model>" or null,
   "platform": "AM5"|"AM4"|"Intel"|"GPU"|"unknown",
   "confidence": "high"|"medium"|"low",
   "note": "<short reason; only when confidence is not high>"}}

Rules:
- canonical_board: the most specific full name you can justify from THIS row
  (brand + chipset + model, e.g. "ASRock X670E Taichi"). If you cannot name a
  specific model, set null. Never guess a model.
- platform by chipset: AM5 = X670/X670E, B650/B650E, X870/X870E, B850, B840,
  A620. Intel = Z690, Z790, Z890, B660, B760, B860, H610, H770, W790. AM4 =
  X570, B550, B450, A520. If the claim is about a graphics card, use "GPU".
  Use "unknown" only when the row truly does not tell.
- A row about a brand in general (no single board) gets canonical_board null
  and the platform the snippet/title supports.
- Every input row must appear exactly once in the output. Keep input order.
- Do not read data/ (it does not exist here). Do not modify any other file.

When done, run: git add analysis/brand-map/{name}.jsonl
then commit with message "{name}: board resolution". You must commit.

INPUT ROWS:
{rows}
"""


def main(test: bool):
    rows = [json.loads(ln) for ln in (REPO / "data/claims.jsonl").read_text().splitlines()]
    items = [
        {"i": i, "board": r["board"], "video_title": r["video_title"], "snippet": r["snippet"]}
        for i, r in enumerate(rows)
    ]
    if test:
        # stratified sample: brand-only, family-name, specific
        brands = {"ASUS", "MSI", "Gigabyte", "ASRock", "Asus", "Biostar", "EVGA"}
        brand_rows = [x for x in items if x["board"] in brands][:15]
        fam = {
            "Taichi",
            "Aorus Elite",
            "MAG Tomahawk",
            "Aorus Master",
            "ROG Strix",
            "ROG Crosshair",
            "Steel Legend",
            "B650",
            "B650E",
        }
        fam_rows = [x for x in items if x["board"] in fam][:15]
        used = {x["i"] for x in brand_rows + fam_rows}
        rest = [x for x in items if x["i"] not in used][:10]
        chunk = brand_rows + fam_rows + rest
        write_chunk("chunk-test", chunk)
        return
    for n, start in enumerate(range(0, len(items), CHUNK_SIZE)):
        write_chunk(f"chunk-{n:03d}", items[start : start + CHUNK_SIZE])


def write_chunk(name, chunk):
    body = "\n".join(json.dumps(x, ensure_ascii=False) for x in chunk)
    (OUT / f"prompt-{name}.md").write_text(TEMPLATE.format(name=name, rows=body))
    print(name, len(chunk))


main(test="--test" in sys.argv)
