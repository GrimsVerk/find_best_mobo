# Reading the claim store

For whoever reads `data/claims.jsonl` next — most likely a model. It says what
each field means, what the data is evidence OF, and the four ways it will
mislead you if you take it at face value. Nothing here is a plan; the plan that
produced this data is `docs/plans/oracle/stage-b-extraction.md`.

## Where the data is

| Path | What it is | Tracked? |
| --- | --- | --- |
| `data/claims.jsonl` | **The claim store.** One JSON object per line, append-only, batch-tagged. This is the artifact. | no — `data/` is gitignored (R21) |
| `data/claims/batch-<n>/bundle-<id>.json` | What the model actually SAID, written to disk before anything parsed it (R27). The store is derived from these. | no |
| `data/bundles/batch-<n>/bundle-<id>.xml` | What was SENT. Excerpts with video ids, titles and second offsets. | no |
| `data/selected.jsonl` | Which videos were chosen for excerpting, and why. | no |
| `data/transcripts/` | The cached caption tracks the excerpts were cut from. | no |
| `calibration/batch-<n>.json` | What a batch cost, measured rather than projected (R1011). | **yes** |

`data/` being gitignored is deliberate: it is a local cache that makes the
pipeline restartable, not a deliverable. Do not expect it in a fresh clone —
re-run `./scripts/run.sh` instead. The calibration records are the exception,
because R1011 requires committed evidence of spend.

## The shape of one claim

Eight fields, all required, all present on every row:

```json
{
  "board": "MSI Z890 Tomahawk Wifi II",
  "video_id": "wK9oe1xfmt0",
  "video_title": "mobo PCB Breakdown: MSI Z890 Tomahawk Wifi II",
  "timestamp_seconds": 1830.0,
  "snippet": "they do end up getting rather hot here at 96.4 degrees Celsius",
  "category": "tested",
  "subject": "vrm_capacity",
  "polarity": "mixed",
  "batch": 4
}
```

`batch` is added by the store, not by the model. Everything else is the model's.

### The three closed vocabularies

A value outside these lists is a schema fault and the whole file is refused, so
you may rely on them absolutely.

- **`category` — how he knows it.** `tested` (he put it on a bench and
  measured), `reasoned` (his own analysis from topology, part numbers, layout),
  `secondhand` (he is repeating a source he trusts), `warning` (he is telling
  people not to buy or not to run it). `warning` wins over the others when both
  would fit.
- **`subject` — what it is about.** `vrm_capacity`, `voltage_firmware_safety`,
  `memory`, `features`, `value`.
- **`polarity` — which way it cuts.** `positive`, `negative`, `mixed`.

`category` is the field that carries epistemic weight. A `tested` negative on
`voltage_firmware_safety` is a measurement that a board does something harmful.
A `reasoned` one is an expert's inference from the design. Do not average them.

## How to verify any claim yourself

Every claim is checkable, and checking is cheap. `video_id` plus
`timestamp_seconds` is a URL:

```
https://youtu.be/<video_id>?t=<timestamp_seconds as a whole number>
```

`snippet` is copied out of the caption track, not paraphrased, so it can be
found in `data/transcripts/`. A 40-claim random audit found 40 of 40 quotes
present in their source transcript; the one near-miss had two filler words
compressed at the start of the sentence and was otherwise verbatim.

**So: never restate a claim without its snippet and its link.** The snippet is
what makes this data evidence rather than assertion.

## The four ways this data will mislead you

**1. `board` is often a BRAND, not a model.** `ASUS` appears far more often than
any specific board, because the alias list that found these mentions carries
brand-level canonicals as well as model names. A row reading `board: "ASUS"` is
a claim about *some* ASUS board, or about ASUS boards in general, and grouping
by `board` will silently merge things that are not the same product. Read the
`snippet` and the `video_title` before treating a board name as an identifier.

**2. Some claims are about graphics cards.** The extraction prompt tells the
model to skip claims about CPUs, chipsets and the industry. It never mentions
GPUs, and Buildzoid reviews those too. `scripts/drop-gpu-claims.py` removed the
35 that were unambiguous, and it is deliberately conservative: a claim is
dropped only when the video is about a card, the claim's own text talks about a
card, AND nothing in it names a chipset, socket, BIOS or motherboard family.
Anything ambiguous was KEPT, because losing a real motherboard claim is the
worse error. About 90 claims still come from GPU-topic videos, and most of those
are genuine motherboard remarks made during a GPU video — but not all. Filter
again if precision matters more to you than recall.

**3. Nothing has been aggregated, ranked, or deduplicated.** This is Stage B
output: raw claims. Two rows may say the same thing about the same board from
two videos. That is not a bug — it is two pieces of evidence — but it means a
naive count of positives is a count of *sentences*, not of opinions.

**4. Absence is not disagreement.** A board with no claims was not judged badly;
it was not covered, or its mentions never cleared the selection threshold. See
`data/selected.jsonl` for which videos were excluded and why.

## Batches

Batch 1 is the calibration batch (12 bundles, fixed by ruling). Batches 2 upward
split the rest evenly, sized by `batch_count` in `config.toml`. Batch numbers say
nothing about content or quality — they are units of spend and of restartability.
A batch is either wholly in the store or wholly absent; `extract` refuses to
store one twice.

## The calibration records

`calibration/batch-<n>.json` records what a batch cost. Two numbers in it are
easy to misread:

- **`measured_chars_per_token` is a measurement.** Characters sent divided by
  tokens the batch's own calls reported. The subscription meter is not involved,
  so it is valid per batch regardless of what else was running. Seven batches
  measured 2.379–2.408, against a configured guess of 4.0.
- **`tokens_per_point` is an estimate, and its SCOPE is per batch.** It divides
  one batch's tokens by the movement of an account-wide meter. When batches run
  concurrently, each one sees every other one's spend, so each understates what a
  point buys by roughly the number of batches running. The fix is arithmetic, not
  data: sum the charged tokens of everything in the window and divide by the
  movement across it. Done that way over four concurrent batches, a weekly point
  is about 870,000 charged tokens.

"Charged tokens" means fresh input plus cache creation — the tokens this batch's
own text became. Cache reads are Claude Code's own re-served prefix and output is
not input. **Never sum the four components:** on this corpus cache reads exceed
fresh input by more than four orders of magnitude, so a total is dominated by the
one component that is not the batch's own text (R8).
