# Extract claims from one bundle

You are reading one bundle of transcript material from the YouTube channel
*Actually Hardcore Overclocking* (Buildzoid), who reviews and tears down PC
motherboards. The bundle follows these instructions, as XML.

Your whole job is to write down every claim he makes about a specific
motherboard, as JSON. Answer with the JSON and nothing else. Do not use tools,
do not read or write files, do not search the web, and do not ask questions —
everything you need is in the bundle below.

## What the bundle looks like

```xml
<bundle id="bundle-007" batch="1">
  <excerpt video_id="dQw4w9WgXcQ" start="120" end="420" form="excerpts" part="1" parts="1">
    <video_title>ASRock B850 Steel Legend VRM analysis</video_title>
    <boards>B850, ASRock Steel Legend</boards>
    <transcript>so the vrm on this thing is eight phases of ...</transcript>
  </excerpt>
  <excerpt ...>...</excerpt>
</bundle>
```

- `video_id` and `<video_title>` identify the video the speech came from. Every
  claim you write carries them, copied exactly as they appear.
- `start` and `end` are **seconds from the start of the video**, not clock times.
- `<boards>` lists the canonical names that were matched inside this block. Use
  these spellings for the `board` field whenever the board you are recording is
  one of them, so that claims about the same board from different videos group
  together later. If he clearly discusses a board that is not listed, use the
  name as he says it.
- `<transcript>` is an automatic caption track: lower case, no punctuation, with
  words occasionally mangled. Read it as speech. XML escapes (`&amp;`, `&lt;`,
  `&gt;`, `&quot;`) stand for the characters they name.
- `form="excerpts"` means the block is a window cut around a mention, so speech
  before and after it is **missing**, and two excerpts from the same video are
  not continuous. `form="whole"` means the block is a full transcript;
  `part`/`parts` say which piece of it you are holding when it was too long to
  send at once.

## What counts as a claim

One board, one thing said about it, in one category, about one subject, with one
polarity. A single passage often produces several claims: split it, one claim per
board and subject. Two claims about the same board and the same subject are
right when he says two different things about it.

Record only what he actually says.

- **Never infer and never fill gaps.** Your own knowledge of this hardware is not
  evidence and must not appear in the output. If an excerpt cuts off before the
  verdict, there is no claim in it — that is an expected outcome, not a problem
  to solve.
- **A board named in passing, with nothing said about it, produces no claim.**
- **A claim about a CPU, a chipset in general, or the industry is not a claim
  about a board.** Skip it. `<boards>` may list a chipset because that is how
  the board was found; record a claim against the chipset only when what he says
  is genuinely about the chipset itself.
- **Do not repeat yourself.** Two rows identical in every field are rejected as a
  duplicate, and the whole file is refused with them.

## The fields

Every claim is a JSON object with **exactly these eight keys**, all of them
required. An extra key of your own invention — `confidence`, `notes`, `batch`,
anything — is a fault that refuses the entire file, so do not add one.

| Key | Type | What it holds |
| --- | --- | --- |
| `board` | string | The board this claim is about, spelled as `<boards>` spells it where possible. |
| `video_id` | string | The `video_id` of the excerpt the claim came from, copied exactly. |
| `video_title` | string | That excerpt's `<video_title>`, copied exactly. |
| `timestamp_seconds` | number | The second, from the start of the video, where he says it. |
| `snippet` | string | A short verbatim quote from `<transcript>`. |
| `category` | string | One of `tested`, `reasoned`, `secondhand`, `warning`. |
| `subject` | string | One of `vrm_capacity`, `voltage_firmware_safety`, `memory`, `features`, `value`. |
| `polarity` | string | One of `positive`, `negative`, `mixed`. |

`timestamp_seconds` is a **JSON number, never a string**: `184`, not `"184"`,
and not `"3:04"`. It must fall between that excerpt's `start` and `end`. If you
cannot place the sentence within the window, use the excerpt's `start`.

`snippet` is **copied out of the transcript, not paraphrased and not tidied
up** — it is what a reader clicks through to verify, so it has to be findable in
the captions as written. One or two sentences of the speech that carries the
claim is right. Never leave it empty: a claim you cannot quote is a claim you
should not be recording.

### `category` — how he knows

- `tested` — he measured, probed, thermal-imaged or otherwise put the board on a
  bench himself.
- `reasoned` — his own analysis from the design: VRM topology, component part
  numbers, layout, trace routing, spec sheets.
- `secondhand` — he is repeating something from a source he trusts: another
  reviewer, a vendor engineer, a viewer report.
- `warning` — he is telling people not to buy or not to run something, because
  it can damage hardware or behaves dangerously. `warning` wins over the other
  three when both would fit: a tested statement that a board kills CPUs is a
  `warning`.

### `subject` — what it is about

- `vrm_capacity` — the VRM and its ability to feed the CPU: phase count, stage
  ratings, thermals under load, how much CPU the board can actually carry.
- `voltage_firmware_safety` — what the board DOES to the CPU: voltages it
  applies, SoC and memory rail behaviour, BIOS defaults, firmware bugs,
  degradation risk.
- `memory` — DRAM behaviour: trace layout, achievable speeds, stability, memory
  training.
- `features` — everything the board carries: slots, ports, headers, connectivity,
  build quality, heatsinks, layout convenience.
- `value` — price against what it delivers, and comparisons of the two.

Pick the ONE subject the statement is really about. When a sentence covers two,
write two claims with the same snippet and different subjects.

### `polarity` — which way it cuts

- `positive` — the statement is in the board's favour.
- `negative` — it counts against the board. Every `warning` is `negative` unless
  he is explicitly retracting one.
- `mixed` — he says both in the same breath: good for the price, bad above it.

## Output format

A single JSON array, written directly, with nothing around it:

- **No markdown code fence of any kind**, no language marker, no explanation
  before or after, no summary of what you found. The first character of your
  answer is `[` and the last is `]`.
- All eight keys on every object. All vocabulary values in lower case, exactly as
  spelled above.
- **If the bundle contains no claim about any board, answer `[]`.** That is a
  valid and expected result for a bundle that only mentions boards in passing,
  and it is far better than an invented claim.

A worked example, for a bundle containing the excerpt shown at the top:

```json
[
  {
    "board": "ASRock Steel Legend",
    "video_id": "dQw4w9WgXcQ",
    "video_title": "ASRock B850 Steel Legend VRM analysis",
    "timestamp_seconds": 184,
    "snippet": "so the vrm on this thing is eight phases of 60 amp power stages which is way more than any ryzen 9 is ever going to pull",
    "category": "reasoned",
    "subject": "vrm_capacity",
    "polarity": "positive"
  },
  {
    "board": "ASRock Steel Legend",
    "video_id": "dQw4w9WgXcQ",
    "video_title": "ASRock B850 Steel Legend VRM analysis",
    "timestamp_seconds": 291,
    "snippet": "do not run this bios it will push 1.3 volts into the soc rail and that is how you kill a 7800x3d",
    "category": "warning",
    "subject": "voltage_firmware_safety",
    "polarity": "negative"
  }
]
```

Your answer is validated by a program that reports every fault at once and
refuses the file if it finds any. It does not correct anything for you, and a
refused bundle has to be read again from scratch, so spend the care here.

The bundle follows.
