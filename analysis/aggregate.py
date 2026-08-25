#!/usr/bin/env python3
"""Steps 2-5: filter, grade, verdict table, ranking.

Reads: data/claims.jsonl, data/index.jsonl, board-map.jsonl (worker output).
Writes: report.md (full verdict table + top-5) and boards.json (machine form).
"""

import collections
import json
import pathlib
import re

REPO = pathlib.Path("/home/loke/code/GrimsVerk/find_best_mobo")
HERE = pathlib.Path(__file__).parent


def load(path):
    return [json.loads(ln) for ln in path.read_text().splitlines()]


claims = load(REPO / "data/claims.jsonl")
idx = {r["video_id"]: r for r in load(REPO / "data/index.jsonl")}
bmap = {r["i"]: r for r in load(HERE / "board-map.jsonl")}

# ---- name folding ----------------------------------------------------------
BRANDS = ["ASROCK", "ASUS", "GIGABYTE", "MSI", "BIOSTAR", "NZXT"]
CHIPSETS = ["X870E", "X870", "X670E", "X670", "B650E", "B650", "B850", "B840", "A620"]
FAMILIES = [  # longest first so multi-word families win
    "TAICHI LITE",
    "TAICHI OCF",
    "AORUS MASTER",
    "AORUS XTREME",
    "AORUS ELITE",
    "AORUS PRO",
    "AORUS TACHYON",
    "CROSSHAIR HERO",
    "CROSSHAIR GENE",
    "CROSSHAIR EXTREME",
    "CROSSHAIR APEX",
    "STEEL LEGEND",
    "PG LIGHTNING",
    "PG RIPTIDE",
    "PG SONIC",
    "PRO RS",
    "LIVEMIXER",
    "TAICHI",
    "TOMAHAWK",
    "CARBON",
    "EDGE",
    "NOVA",
    "HDV",
    "PROART",
    "STRIX",
    "PRIME",
    "TUF",
    "GAMING PLUS",
    "MORTAR",
    "BAZOOKA",
    "APEX",
    "GENE",
    "HERO",
    "FORCE",
    "ELITE ICE",
    "PRO ICE",
    "CREATOR",
    "PHANTOM",
]


def fold(name):
    """canonical worker name -> (brand, chipset|None, family|None, form) key"""
    u = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    u = re.sub(r"\s+", " ", u).strip()
    brand = next((b for b in BRANDS if b in u), None)
    chip = next((c for c in CHIPSETS if re.search(rf"\b{c}[IM]?\b", u)), None)
    itx = (
        bool(re.search(r"\b(X870I|B650I|B850I|X670EI|ITX|X870 I|B650 I)\b", u))
        or " I GAMING" in u
        or "-I " in name.upper()
    )
    fam = next((f for f in FAMILIES if f in u), None)
    # CROSSHAIR without HERO/GENE/etc: keep as CROSSHAIR
    if fam is None and "CROSSHAIR" in u:
        fam = "CROSSHAIR"
    # bare sub-names are the same board as their full family name
    FAM_FOLD = {
        "GENE": "CROSSHAIR GENE",
        "HERO": "CROSSHAIR HERO",
        "APEX": "CROSSHAIR APEX",
        "HDV": "HDV",
        "CROSSHAIR": "CROSSHAIR HERO",
    }
    fam = FAM_FOLD.get(fam, fam)
    if fam == "HDV":
        chip = chip or "B650"  # B650M-HDV is the only AM5 HDV
    if fam == "STRIX":
        # Strix letter variant matters (-E/-F/-A/-I)
        m = re.search(r"STRIX.*?\b([EFAI])\b", u)
        if m and m.group(1) == "I":
            itx = True
        fam = "STRIX " + m.group(1) if m else "STRIX"
    return (brand, chip, fam, itx)


def label(key):
    b, c, f, i = key
    parts = [p for p in (b, c, f) if p]
    return " ".join(parts) + (" (ITX)" if i else "")


# ---- CPU transfer grade ----------------------------------------------------
CPU_PATTERNS = [
    (r"\b(9950X3D|7950X3D)\b", 1.00, "16-core X3D (target CPU)"),
    (r"\b(9950X|7950X)\b", 0.95, "16-core"),
    (r"\b(9900X3?D?|7900X3?D?|7900X)\b", 0.85, "12-core"),
    (r"\b(9800X3D|7800X3D)\b", 0.80, "8-core X3D"),
    (r"\b(9700X|7700X?|8700G)\b", 0.65, "8-core"),
    (r"\b(9600X?|7600X?|8600G)\b", 0.55, "6-core"),
]


def cpu_grade(text):
    t = text.upper().replace(" ", "")
    for pat, w, name in CPU_PATTERNS:
        if re.search(pat, t):
            return w, name
    return 0.70, None  # CPU not named: mid transfer weight


CAT_W = {"tested": 3.0, "reasoned": 1.5, "secondhand": 0.75, "warning": 3.0}
SUBJ_W = {
    "voltage_firmware_safety": 3.0,
    "vrm_capacity": 2.5,
    "memory": 0.75,
    "features": 0.5,
    "value": 0.5,
}
POL_S = {"positive": 1.0, "negative": -1.0, "mixed": -0.15}


def year_w(d):
    y = int(d[:4]) if d and d[:4].isdigit() else 0
    return {2023: 0.8, 2024: 0.9, 2025: 1.0, 2026: 1.1}.get(y, 0.0)


CONF_W = {"high": 1.0, "medium": 0.8, "low": 0.5}

# ---- build graded AM5 claim set -------------------------------------------
boards = collections.defaultdict(
    lambda: {"claims": [], "safety": 0.0, "safety_n": 0, "warn": 0, "videos": collections.Counter()}
)
dropped_old = dropped_notam5 = 0

for i, c in enumerate(claims):
    m = bmap[i]
    if m["platform"] != "AM5":
        dropped_notam5 += 1
        continue
    if not m["canonical_board"]:
        continue  # brand-level AM5 talk: context only, never scores a board
    vid = idx.get(c["video_id"], {})
    date = vid.get("upload_date", "")
    if date and date < "2023-01-01" and date > "2000":
        dropped_old += 1
        continue
    key = fold(m["canonical_board"])
    if key[0] is None and key[1] is None:
        continue
    # chipset missing: let the claim's own video title supply it, but only
    # when the title also names the same family (so we never borrow a chipset
    # from a video about a different board)
    if key[1] is None and key[2]:
        tu = re.sub(r"[^A-Z0-9 ]", " ", c["video_title"].upper())
        tu = re.sub(r"\s+", " ", tu)
        if key[2].split()[0] in tu or (key[2] == "CROSSHAIR HERO" and "CROSSHAIR" in tu):
            tchip = next((x for x in CHIPSETS if re.search(rf"\b{x}[IM]?\b", tu)), None)
            if tchip:
                key = (key[0], tchip, key[2], key[3])
    cw, cpu_name = cpu_grade(c["snippet"] + " " + c["video_title"])
    is_safety = c["subject"] in ("voltage_firmware_safety", "vrm_capacity")
    w = (
        CAT_W[c["category"]]
        * SUBJ_W[c["subject"]]
        * POL_S[c["polarity"]]
        * cw
        * (year_w(date) or 0.7)
        * CONF_W[m["confidence"]]
    )
    if c["category"] == "warning":
        w = -abs(w) or -1.0
    b = boards[key]
    b["claims"].append(
        {
            "board": m["canonical_board"],
            "score": round(w, 2),
            "cat": c["category"],
            "subj": c["subject"],
            "pol": c["polarity"],
            "cpu": cpu_name,
            "date": date,
            "conf": m["confidence"],
            "snippet": c["snippet"],
            "video_id": c["video_id"],
            "t": int(c["timestamp_seconds"]),
            "title": c["video_title"],
        }
    )
    b["videos"][c["video_id"]] += SUBJ_W[c["subject"]]
    if is_safety:
        b["safety"] += w
        b["safety_n"] += 1
    if c["category"] == "warning":
        b["warn"] += 1


# ---- merge chipset-less family buckets into their board --------------------
# and STRIX-I letter variants into the ITX bucket, by shared source videos.
def vids(b):
    return set(c["video_id"] for c in b["claims"])


merged = True
while merged:
    merged = False
    for key in list(boards):
        brand, chip, fam, itx = key
        if key not in boards:
            continue
        cands = [
            k
            for k in boards
            if k != key
            and k[0] == brand
            and (k[2] == fam or (fam and k[2] and fam in k[2]))
            and (chip is None or k[1] is None or k[1] == chip)
        ]
        cands = [k for k in cands if vids(boards[k]) & vids(boards[key])]

        # merge the LESS specific key into the MORE specific one
        def spec(k):
            return (k[1] is not None) + (k[2] is not None) + k[3]

        for k in cands:
            a, b = (key, k) if spec(key) < spec(k) else (k, key)
            if a == b or a not in boards or b not in boards:
                continue
            if vids(boards[a]) <= vids(boards[b]) or len(cands) == 1:
                boards[b]["claims"] += boards[a]["claims"]
                boards[b]["safety"] += boards[a]["safety"]
                boards[b]["safety_n"] += boards[a]["safety_n"]
                boards[b]["warn"] += boards[a]["warn"]
                boards[b]["videos"] += boards[a]["videos"]
                del boards[a]
                merged = True
        if merged:
            break

# ---- rank ------------------------------------------------------------------
ranked = sorted(boards.items(), key=lambda kv: (kv[1]["safety"], kv[1]["safety_n"]), reverse=True)

out = {"summary": [], "dropped_old": dropped_old, "dropped_notam5": dropped_notam5}
for key, b in ranked:
    out["summary"].append(
        {
            "board": label(key),
            "safety_score": round(b["safety"], 1),
            "safety_claims": b["safety_n"],
            "warnings": b["warn"],
            "total_claims": len(b["claims"]),
            "top_videos": b["videos"].most_common(3),
        }
    )
(HERE / "boards.json").write_text(json.dumps(out, indent=1))

print(f"dropped: pre-2023={dropped_old}, non-AM5={dropped_notam5}")
print(f"scored boards: {len(ranked)}")
print(f"{'BOARD':44} {'SAFETY':>7} {'#saf':>4} {'warn':>4} {'tot':>4}")
for key, b in ranked[:14]:
    print(
        f"{label(key):44} {b['safety']:7.1f} {b['safety_n']:4} {b['warn']:4} {len(b['claims']):4}"
    )
print("...")
for key, b in ranked[-6:]:
    print(
        f"{label(key):44} {b['safety']:7.1f} {b['safety_n']:4} {b['warn']:4} {len(b['claims']):4}"
    )
