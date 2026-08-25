---
slug: claim-store-hygiene
status: draft
created: 2026-08-25
design: MVP — Extraction (Stage B)
covers: [R27]
---

# Claim-store hygiene — what the store holds, and what it should not — Plan

## Summary

The extraction prompt tells the model to skip claims about CPUs, chipsets and the
industry, and never mentions **graphics cards**. Buildzoid reviews those too, so
the first full extraction produced 35 well-formed claims about a product this
project is not about, out of 2771. **ESC-29** records it and names the gap: the
prompt is a committed artifact that no gate reads.

Three things, in this order: the prompt excludes graphics cards, as a rule about
non-motherboard components rather than a list of the ones someone thought of,
with a test that goes red if it is deleted — ESC-29's ratchet; a committed,
idempotent script removes the 35 already in the store; and
`docs/reading-the-claims.md` tells the next reader what the store holds and how
to verify a claim against its video.

**The decision expensive to reverse, already ruled.** Where does a motherboard
claim end and a graphics-card claim begin, when the two share brands (`MSI`,
`ASUS`, `ROG Strix`), a reviewer, and often a video? The owner ruled in chat on
2026-08-25, twice and unprompted the second time: *"it is way more important to
include motherboards than to exclude gpus"*. So **recall of motherboard claims is
the constraint; precision against graphics cards is only the objective** — a rule
that is unsure keeps the claim. That asymmetry is built as two mechanical guards
with tests, never as a note in a docstring.

**Deliberately not done.** No filtering, ranking, aggregation or deduplication —
Stage C. No bundle re-extracted, so nothing is paid for twice. The alias list is
untouched: it is what makes GPU videos reach the corpus, and it is right to.
Roughly 90 claims from GPU-topic videos are knowingly left, because removing them
would cost motherboard claims.

**What it costs the owner: nothing.** No gate change, no new required check, no
money, no manual step. It deletes 1.26% of a derived artifact, the original kept
beside it and the raw output R27 preserves untouched.

**Open questions: none.** Both Uncertainties below are ruled — the first by the
owner in chat, the second on R27's own wording. Merging this plan is the ruling.

## What it is built on

Stage B is complete. `run.sh` runs the whole pipeline, 91 of 91 bundles
extracted with none set aside, and the chars-per-token factor is measured at
2.379–2.408 across seven batches. `data/claims.jsonl` holds 2736 claims. None of
that changes here.

## Uncertainties

- **Q:** Where is the line between a claim about a MOTHERBOARD and a claim about
  a GRAPHICS CARD, when the two share brand names (`MSI`, `ASUS`, `ROG Strix`),
  share a reviewer, and often share a video? — **risk:** HIGH: it decides what is
  deleted from an artifact that cost real subscription spend, and a deletion is
  not recoverable from the store itself.
  — **proposed:** three signals must AGREE before a claim is dropped: the source
  video is about a card, the claim's own text talks about a card, and nothing in
  it names a chipset, socket, BIOS or motherboard family. Neither cheap signal
  works alone. Dropping by video destroys the real motherboard claims GPU videos
  contain, because Buildzoid discusses the board he is testing on. Dropping by
  board name misfires the other way: `MSI 970 Gaming Krait` is a motherboard.
  **Ruling:** the owner ruled in chat on 2026-08-25, twice and unprompted the
  second time: **"it is way more important to include motherboards than to
  exclude gpus"** and "I will accept including gpus by mistake … make sure you
  are not removing motherboard claims, that is the bigger error." So the error
  budget is asymmetric BY INSTRUCTION, not by taste: **recall of motherboard
  claims is the constraint; precision against graphics cards is the objective.**
  A rule that is unsure keeps the claim. That is not a note in a docstring — it
  is a mechanical guard in slice 2, and a test that fails if the guard is
  loosened.

- **Q:** Does removing rows from the claim store conflict with **R27**, which
  keeps what the model said? — **risk:** LOW, but worth stating so the next
  reader does not have to re-derive it. — **proposed:** no. R27 governs the
  RAW model output, which is written to `data/claims/batch-<n>/bundle-<id>.json`
  before anything parses it and is not touched here. The store is a derived
  artifact. Nothing is destroyed that cannot be rebuilt from what R27 preserved,
  and the removal is a committed script rather than a hand edit, so it is
  reproducible and reviewable rather than a one-off nobody can audit.

## The slices

Three, ordered. Slice 1 is the root-cause fix and its check; it must land before
slice 2, because cleaning the corpus while the prompt still produces the mess is
the shape ESC-29 exists to stop being repeated.

## Slice 1 — The prompt excludes what the project is not about

- **Delivers:** `prompts/extract-claims.md` excludes graphics cards in the same
  sentence that already excludes CPUs and chipsets, stated as a RULE about
  components that are not motherboards rather than an enumeration. A test asserts
  the exclusion is present and names graphics cards, so deleting it goes red.
  This is ESC-29's ratchet: the defect does not get fixed without a check that
  would have caught it. Covers R27's mirror — nothing is extracted twice, so a
  prompt defect is only ever fixed forward.
- **Files:** `prompts/extract-claims.md`, `tests/test_extract.py`
- **Estimate:** ~40 lines

### Signatures

No new names. The prompt is reached only through `find_best_mobo.extract.prompt_text()`,
which already exists and already raises a named failure when the file is absent.
The test asserts over `prompt_text()`'s return value, not over the file path, so
it exercises the same loader the extraction uses.

## Slice 2 — The graphics-card claims already in the store are removed

- **Delivers:** `scripts/drop-gpu-claims.py`, reporting by default and rewriting
  the store only under `--apply`, keeping the original at `claims.jsonl.bak`.
  It implements the three-signal rule the first Uncertainty rules on, and it
  carries the owner's asymmetry as a MECHANICAL guard: it refuses to run if the
  drop set exceeds a stated fraction of the store, and it never drops a claim
  whose source video is a motherboard-topic video. Idempotent — a second run
  finds nothing.
- **Files:** `scripts/drop-gpu-claims.py`, `tests/test_drop_gpu_claims.py`
- **Estimate:** ~200 lines

### Signatures

```python
# scripts/drop-gpu-claims.py — a rule over one claim, and a guard over the set.

def is_about_a_graphics_card(claim: Mapping[str, object]) -> bool:
    """True only when all three signals agree. Unsure means False (keep)."""

def refuse_if_too_much_is_dropped(dropped: Sequence[Mapping[str, object]],
                                  total: int) -> None:
    """Raise rather than delete when the drop set is implausibly large.

    The owner's ruling makes over-deletion the unacceptable error, so the script
    must fail loudly rather than quietly remove a large slice of the corpus if a
    regex is ever widened by accident.
    """
```

## Slice 3 — The store is documented for whoever reads it next

- **Delivers:** `docs/reading-the-claims.md` — the fields, the three closed
  vocabularies, how to verify any claim from `video_id` and `timestamp_seconds`,
  and the ways the data misleads a careless reader: brand-level board names,
  the graphics-card claims slice 2 deliberately did NOT remove, nothing
  aggregated or deduplicated, and absence meaning absence of coverage. Also how
  to read a calibration record, including that `tokens_per_point` is scope-wrong
  under concurrent batches and recoverable by summing.
- **Files:** `docs/reading-the-claims.md`
- **Estimate:** ~140 lines

## Measurement

Slice 1: the test goes red when the exclusion sentence is deleted. Slice 2: the
script's report on the current store, and the drop set read row by row before
`--apply` — the owner's ruling makes a sample insufficient. Slice 3: a reader
with no prior context can verify a claim against its video using only the
document.

## Out of scope

Elaborating the Summary's list, not adding to it. Filtering, ranking, aggregating
or deduplicating claims — Stage C. Re-extracting any bundle: the prompt fix
applies to the next extraction and nothing is paid for twice. Changing the alias
list, which is what makes GPU videos reach the corpus at all and is doing its job
correctly. Removing every graphics-card claim: the owner's ruling makes the
remaining ~90 the acceptable cost of not losing motherboard claims.

## Open questions

**None.** Both Uncertainties above are ruled: the first by the owner in chat on
2026-08-25, the second on R27's own wording. `covers: [R27]` is listed because
`coverage.sh` reads that field and R27 is the requirement this work must not
violate; the second Uncertainty is where it is shown not to. Nothing in this plan
is waiting on a decision.
