---
slug: stage-b-extraction
status: draft
created: 2026-08-25
design: MVP — Extraction (Stage B)
covers: [R8, R9, R10, R26, R27, R1011]
---

# Stage B — one bundle in, one validated claims file out — Plan

Commissioned by **OD-22**, which added **R1011** and named this plan's scope:
one steward plan covering R1011 together with R8, R9, R10, R26 and R27,
elaborating the continue command R7 promises, and ending where **BL-23** ends —
a calibration batch extracted, validated, stored, its factor corrected, and its
record committed.

**This is the first work in the project that spends model budget.** Stage A is
complete: `index`, `fetch`, `select` and `estimate` all run, and `estimate`
stops at the projection exactly as R7 requires. Nothing consumes what it writes.
Until Stage B exists, every Stage A improvement sharpens an input to a stage
that is not there.

## What it is built on, and why now

OD-22's sequencing condition is met. It requires that extraction calibrate only
against bundles produced by the AMENDED Stage A — "R1000's re-cut and R1008's
routing built first — because a factor calibrated against inflated excerpts is
wrong by construction". Both landed on 2026-08-25, and the corpus was refetched
against them the same day. The projection the calibration batch will be measured
against is **1,830,123 tokens across 91 bundles**, down from 58,182,407 at the
start of the project.

The three questions this plan would otherwise have to guess at were ruled by the
owner on 2026-08-25 and are recorded in `docs/DECISIONS.md`: the subscription
pays, `Weekly (7-day)` governs the cap, and the calibration batch stays at 12
bundles.

## Uncertainties

- **Q:** R1011 requires the calibration record in a **git-tracked file outside
  the gitignored corpus directory**; BL-26's ruling names **`data/calibration.json`**,
  which is inside it. Both cannot hold. — **risk:** HIGH: it decides an external
  artifact path, what `acceptance/S3.sh` reads, and what `estimate` prefers.
  — **proposed:** ONE file, tracked, at `calibration/batch-<n>.json`, read
  directly by both `estimate` and `acceptance/S3.sh`. No `data/` copy is
  written. R1011's own words are the reason: "a restated number elsewhere is
  never a second source". BL-26's ruling settles the SEMANTICS — a measured
  factor that `estimate` prefers over `config.chars_per_token`, with the
  configuration key never rewritten by a stage — and every part of that survives
  the move; only the directory changes, and it changes because R1011 requires
  the record to be committed evidence rather than local scratch.
  **Ruling:** pending — attended, the owner rules before slices are built.

- **Q:** Which model extracts, and at what effort? §7 says "low effort, because
  this is reading comprehension, not reasoning". — **risk:** LOW: it is one
  configured string; reversing it is a config edit and a rerun of one batch.
  — **proposed:** a configured `extraction_model` with no default in code, set
  in `config.toml`, so the choice is data rather than a constant and the
  calibration record can state which model produced it. A factor measured
  against one model is not transferable to another, and a record that does not
  say which model it measured is not evidence.
  **Ruling:** proceeding on the default (LOW), left for review.

- **Q:** What happens to a bundle whose claims file fails validation twice?
  R9 says "reported and retried or set aside — never silently dropped".
  — **risk:** LOW: it is a policy inside one loop, and both branches are cheap.
  — **proposed:** one retry, then set aside — the bundle stays unconsumed, is
  named in the run's output, and the batch continues. A batch that halts on one
  malformed file would strand the eleven bundles already paid for, which is the
  waste R27 exists to prevent.
  **Ruling:** proceeding on the default (LOW), left for review.

## The slices

Four, and they are **sequential**: slice 2 writes files slice 1 validates, slice
3 drives slice 2 one batch at a time, and slice 4 measures what slice 3 spent.
Each updates `docs/architecture.md`, which is safe precisely because no two of
them run at once.

## Slice 1 — A claims file is validated and stored, or refused

- **Delivers:** `./scripts/run.sh ingest <file>` reads one claims file, validates
  it against the schema, and appends its claims to the append-only store tagged
  by batch. An invalid file is refused loudly with the reason, nothing is
  appended, and the bundle stays unconsumed. Nothing here invokes a model.
  Covers R9, R10.
- **Files:** `src/find_best_mobo/claims.py`, `src/find_best_mobo/claimstore.py`, `src/find_best_mobo/commands/ingest.py`, `src/find_best_mobo/cli.py`, `tests/test_claims.py`, `tests/test_claimstore.py`, `docs/architecture.md`
- **Estimate:** ~420 lines

### Signatures

Where every shared name lives, per **OD-12**: `Claim`, the three vocabularies
and `InvalidClaims` are new in `find_best_mobo.claims`; the store's functions
are new in `find_best_mobo.claimstore`; `Config` stays in
`find_best_mobo.config`.

```python
# find_best_mobo/claims.py — the schema, and nothing that touches the disk.

CATEGORIES: tuple[str, ...] = ("tested", "reasoned", "secondhand", "warning")
SUBJECTS: tuple[str, ...] = ("vrm_capacity", "voltage_firmware_safety", "memory", "features", "value")
POLARITIES: tuple[str, ...] = ("positive", "negative", "mixed")


class InvalidClaims(ValueError):
    """A claims file that does not meet the schema. Carries every fault, not the first."""

    def __init__(self, path: Path, faults: Sequence[str]) -> None: ...

    def message(self) -> str: ...


@dataclass(frozen=True)
class Claim:
    board: str
    video_id: str
    video_title: str
    timestamp_seconds: float
    snippet: str
    category: str
    subject: str
    polarity: str
    batch: int


def parse_claims(raw: str, path: Path, batch: int) -> tuple[Claim, ...]: ...


# find_best_mobo/claimstore.py — the append-only store, tagged by batch.


def store_path(config: Config) -> Path: ...
def append_claims(claims: Sequence[Claim], config: Config) -> int: ...
def read_claims(config: Config) -> Iterator[Claim]: ...
def batches_stored(config: Config) -> frozenset[int]: ...
```

### Behaviour the signatures cannot carry

- **The agent is never trusted to self-check.** BL-23 says so outright: Python
  validates, and the file is data until it passes. Every field in §9's Claim is
  required, every vocabulary field must be one of the tuples above, and an
  unknown key is a fault rather than something to ignore — a model that invents
  a field is a model that misunderstood the contract, and dropping the field
  hides that.
- **Every fault is reported, not the first.** A file with four bad rows produces
  four faults in one message. Reporting one at a time turns a malformed batch
  into four round trips, and each round trip is paid for.
- **Appending is atomic per FILE, not per claim.** Either every claim in a valid
  file lands or none does. A partial append would leave the store holding half a
  bundle's evidence with nothing recording which half, and R10's promise that a
  stop between batches "loses no work" would be false in the one case it exists
  for.
- **The store is append-only and re-ingesting the same batch is REFUSED**, not
  merged and not silently duplicated. R27's rule is that no completed work is
  lost to an overrun; the mirror of it is that no completed work is silently
  rewritten. `batches_stored` is what the refusal reads.
- **Nothing here reaches the network or a model**, and the module that would is
  not imported. Slice 1 is fully exercisable offline, which is what lets its
  blind tests be written without spending anything.

## Slice 2 — One bundle becomes one claims file

- **Delivers:** a single bundle is handed to the extraction agent and comes back
  as a claims file that slice 1's ingest accepts. The prompt lives in the
  repository, so the same bundle produces a comparable file twice. Covers R9.
- **Files:** `prompts/extract-claims.md`, `src/find_best_mobo/extract.py`, `tests/test_extract.py`, `docs/architecture.md`
- **Estimate:** ~330 lines

### Signatures

Per **OD-12**: `ExtractionResult` and the module's functions are new in
`find_best_mobo.extract`; `Claim` and `parse_claims` come from
`find_best_mobo.claims`; `Bundle` from `find_best_mobo.bundle`.

```python
# find_best_mobo/extract.py — the model boundary, and the ONLY module that
# invokes one. Structured like ytdlp.py for the same reason: one seam, so the
# rest of the tree is testable without a network or a subscription.


@dataclass(frozen=True)
class ExtractionResult:
    bundle_id: str
    claims_path: Path
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


def prompt_text() -> str: ...
def extract_bundle(bundle_path: Path, batch: int, config: Config) -> ExtractionResult: ...
```

### Behaviour the signatures cannot carry

- **The subscription pays, through `claude -p`** — the owner's ruling of
  2026-08-25 in `docs/DECISIONS.md`. An API call would never move the weekly
  meter R26's cap is written against, so slice 3's guard would read healthy
  while a card was charged without limit.
- **The four token components are returned separately and never summed.** R8 as
  amended requires it, and the reason is measured: on the owner's machine cache
  reads outnumber fresh input by more than four orders of magnitude, so a single
  total is dominated by the cheapest tokens in it and says nothing useful about
  cost.
- **The prompt is a file, not a string literal**, and `prompt_text` is the only
  way to reach it. R23's determinism claim needs the prompt to be a versioned
  artifact: "the same bundle produces a comparable file twice" is false the
  moment the prompt can change without a diff.
- **The result is written to disk before it is parsed**, always, including when
  parsing then fails. R27: every model output is written as it is produced. A
  file that fails validation is evidence of what the model actually said, and
  deleting it destroys the only record of a spend that already happened.
- **One seam, monkeypatched in tests.** No test in this slice invokes a model.
  The suite must run offline, free, and identically on a machine with no
  subscription at all.

## Slice 3 — One batch at a time, stopping before the line

- **Delivers:** `./scripts/run.sh extract --batch N` extracts exactly one batch,
  taking a real usage reading before it, part-way through it, and after it, and
  **stopping before the 10% cap rather than discovering the overrun afterwards**.
  This is the explicit continue command R7 promises and nothing has provided.
  Covers R26, R27.
- **Files:** `src/find_best_mobo/spend.py`, `src/find_best_mobo/commands/extract.py`, `src/find_best_mobo/cli.py`, `tests/test_spend.py`, `tests/test_extract_command.py`, `docs/architecture.md`
- **Estimate:** ~460 lines

### Signatures

Per **OD-12**: `Reading`, `CapExceeded` and the guard's functions are new in
`find_best_mobo.spend`; `ExtractionResult` comes from `find_best_mobo.extract`.

```python
# find_best_mobo/spend.py — the R26 guard. Reads a meter, never a projection.

WEEKLY_LABEL = "Weekly (7-day)"


class CapExceeded(RuntimeError):
    """The run stopped BEFORE crossing the line, and says what it read."""

    def __init__(self, reading: Reading, ceiling: float) -> None: ...

    def message(self) -> str: ...


@dataclass(frozen=True)
class Reading:
    label: str
    percent: float
    taken_at: str
    source: str


def take_reading(config: Config) -> Reading: ...
def ceiling(baseline: Reading, config: Config) -> float: ...
def check(reading: Reading, ceiling: float) -> None: ...
```

### Behaviour the signatures cannot carry

- **`Weekly (7-day)` governs**, per the owner's ruling. Not the model-scoped
  limit beside it, which ignores spend on every other model. The figure comes
  from Anthropic's own usage endpoint, so it counts every session on the
  subscription — other machines, web sessions and spawned workers included, a
  property measured on 2026-08-25 and the reason the cap means anything.
- **`omarchy-agent-usage-claude --limits-only --force` first, `claude -p "/usage"`
  as the fallback** (BL-24's ruling, R26 as amended). The fallback is a fallback
  because it starts a session and so spends against the very limit it reads —
  `Reading.source` records which one answered, because a reading that perturbed
  the meter is a different kind of evidence from one that did not.
- **The cap is 10% of the weekly limit, measured from the baseline reading taken
  before the batch** — `ceiling` is `baseline.percent + 0.10`, clamped at 1.0.
  R26 caps the extraction EFFORT, not the account, so a run beginning at 43%
  stops at 53% rather than refusing outright.
- **The reading is taken THREE times** — before, part-way, and after — and the
  part-way one is what makes the guard a guard rather than a receipt. The
  ordering is: read, extract one bundle, ingest it, read again if the batch is
  long enough to warrant it, and stop the moment a reading crosses the ceiling.
- **A stop is not a failure, and it is not a rollback.** Every bundle already
  extracted stays extracted and every claim already ingested stays ingested
  (R27). The command reports which bundles are done, which remain, and what the
  meter read, then exits non-zero so nothing downstream mistakes a partial batch
  for a whole one.
- **Before every UNATTENDED run the agent asks which limit governs and what
  value to use** — the owner's BL-24 ruling. **BL-29** files that rule for
  `AGENTS.md` and the template, where it belongs; this plan does not implement
  it, and says so rather than leaving the reader to wonder.
- **No test invokes the reader.** `take_reading` is a seam like slice 2's, and
  the suite pins the guard's ARITHMETIC and its refusals against constructed
  readings.

## Slice 4 — The calibration batch, measured and committed

- **Delivers:** the first batch runs, and the run's two quantities are recorded
  as committed evidence: the token projection against the tokens the calls
  actually reported, and the `Weekly (7-day)` points before and after, kept
  apart. The chars-per-token factor is corrected and `estimate` prefers the
  measurement over the guess, saying which it used. `acceptance/S3.sh` lands in
  the same change as the first real record. Covers R8, R1011, and closes S3.
- **Files:** `src/find_best_mobo/calibration.py`, `src/find_best_mobo/estimate.py`, `src/find_best_mobo/commands/extract.py`, `acceptance/S3.sh`, `tests/test_calibration.py`, `docs/architecture.md`
- **Estimate:** ~400 lines

### Signatures

Per **OD-12**: `CalibrationRecord`, `TokenActual` and the module's functions are
new in `find_best_mobo.calibration`; `Reading` comes from `find_best_mobo.spend`;
`Projection` stays in `find_best_mobo.estimate`.

```python
# find_best_mobo/calibration.py — the committed record, and the factor it yields.


@dataclass(frozen=True)
class TokenActual:
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


@dataclass(frozen=True)
class CalibrationRecord:
    batch: int
    model: str
    projected_tokens: int
    actual: TokenActual
    measured_chars_per_token: float
    points_before: Reading
    points_after: Reading
    points_delta: float
    tokens_per_point: float | None
    conversion_assumptions: tuple[str, ...]
    recorded_at: str


def record_path(batch: int) -> Path: ...
def write_record(record: CalibrationRecord) -> Path: ...
def load_latest() -> CalibrationRecord | None: ...
def measured_factor(record: CalibrationRecord) -> float: ...
```

### Behaviour the signatures cannot carry

- **Two quantities, kept apart** (R8 as amended). Tokens against tokens correct
  the factor, because both sides are tokens. Points against points say what the
  batch cost the weekly limit. Neither is derived from the other, and the
  conversion between them is recorded as a labelled ESTIMATE with every
  assumption behind it written out beside it — `conversion_assumptions` is that
  list, and nothing reads it as an input.
- **`tokens_per_point` is `None` when the meter did not move, and that is a
  RESULT.** The reader returns whole percentages, so a batch consuming less than
  one full point reads identically before and after. The owner's ruling of
  2026-08-25 keeps the batch at 12 bundles knowing this: the factor correction
  does not need the meter, and "unmeasurable at this batch size" is a finding
  worth committing rather than a failure worth spending more to avoid.
- **The record names the model.** A factor measured against one model does not
  transfer to another, and a record that does not say which model it measured is
  not evidence.
- **`estimate` prefers the measured factor and SAYS WHICH IT USED** (BL-26's
  ruling), printing whether the number is a measurement or a guess. The
  configuration key stays the fallback and is never rewritten by a stage — a
  stage that edits its own configuration makes R23's "same cache and
  configuration" unfalsifiable.
- **`acceptance/S3.sh` lands with the first real record and never before it**
  (R1011), so no pull request is ever red for a record that cannot yet exist.
- **The token actual is summed over the batch's own calls**, from the
  `ExtractionResult`s slice 2 returns — never from a usage tool's daily total.
  Measured on 2026-08-25: `todayTotalTokens` is a running total for the day that
  includes every other session on the machine, so attributing it to a batch
  would be wrong by whatever else the owner did that day.

## Measurement

`AGENTS.md`'s ratchet asks what notices this change. Four things do:

- **the committed calibration record**, which is R1011 and the only durable
  evidence that the projection was ever compared with reality;
- **`acceptance/S3.sh`**, which reads that record on every pull request rather
  than trusting a console line that scrolled away;
- **the claim store**, where a batch's contribution is visible and countable,
  and re-ingesting a stored batch is refused;
- **the suite**: the schema's refusals, the store's atomicity, the guard's
  arithmetic and its three readings, and the factor's preference over the guess.

## Out of scope

- **Stages C, D and E.** BL-23 draws the boundary and gives the reason: each
  later spending stage arrives with its own approval, exactly as this one did.
- **M2's minimal report generator** (R16, R14's partial). OD-22 puts it outside
  this plan deliberately — it consumes claims whose real shape the calibration
  batch is the instrument for measuring.
- **The design-text correction BL-25 implies**, which landed separately as the
  owner's own pull request (#185) on 2026-08-25.
- **BL-29's confirmation rule**, which belongs in `AGENTS.md` and the template.
