"""The `extract` subcommand: one batch, watched by the meter, stopped before the line.

This is the explicit continue command R7 promises and nothing has provided.
`estimate` prints a projection and stops, saying that continuing is a separate
decision; until this module existed there was no command that decision could
invoke, and the projection was a number with nothing on the other side of it.

**One batch, named on the command line.** Never "the rest of the corpus": R10's
stop between batches is what makes the spend inspectable, and a command that
took a bundle count or a `--all` would have made the batch boundary advisory.

**Three readings, and the middle one is the point** (R26). A reading before the
batch fixes the ceiling, a reading part-way through is what turns the guard into
a guard, and a reading after is the receipt. Take only the first and the last and
the command discovers an overrun instead of preventing one, which is the exact
failure R26 is written against.

**A stop is not a rollback** (R27). Every bundle already extracted stays
extracted and every claim already validated is still appended; the command names
what is done, what remains and what the meter read, and exits non-zero so
nothing downstream mistakes a partial batch for a whole one.

**A malformed claims file costs its bundle, not the batch.** One retry, then the
bundle is set aside — named in the output, left unconsumed, and the batch
carries on (R9, and the plan's third uncertainty). Halting on the first bad file
would strand the bundles already paid for, which is the waste R27 exists to
prevent.

**What the batch cost is written down, not narrated** (R1011). At the end of a
batch the run knows two things nothing else can reconstruct afterwards: what its
OWN calls reported, and what the meter read either side of them. Both go into
`calibration/batch-<n>.json` as committed evidence, kept apart (R8) — tokens
correct the chars-per-token factor, points say what the weekly limit paid, and
the conversion between them is stored as a labelled estimate with its
assumptions. A console line scrolls away; the record is what `acceptance/S3.sh`
reads on every pull request afterwards.

This is the first command in the project that spends anything. Everything it
spends goes through `find_best_mobo.extract`; everything it is allowed to spend
goes through `find_best_mobo.spend`; everything it did spend goes into
`find_best_mobo.calibration`.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from find_best_mobo import calibration, spend
from find_best_mobo.artifacts import MissingArtifact, require_directory
from find_best_mobo.bundle import estimate_tokens
from find_best_mobo.calibration import CalibrationRecord, TokenActual
from find_best_mobo.claims import Claim, InvalidClaims, parse_claims
from find_best_mobo.claimstore import BatchAlreadyStored, append_claims, batches_stored, store_path
from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import Config
from find_best_mobo.extract import ExtractionResult, extract_bundle
from find_best_mobo.spend import CapExceeded, Reading, UsageUnreadable

# What `--batches` takes instead of a number. A word rather than a sentinel like
# -1, because the owner types it.
ALL = "all"

# How many attempts one bundle gets before it is set aside. Two, not more: a
# claims file that fails the schema twice is a prompt or a bundle that needs
# looking at, and a third attempt would pay for the same misunderstanding again.
_ATTEMPTS = 2


def parse_args(argv: Sequence[str]) -> Namespace:
    """Which batch, or how many of them.

    **`--batch` and `--batches` are different questions and both are kept.**
    `--batch 3` names ONE batch and refuses if it is already stored: naming a
    batch that is done is a mistake worth reporting. `--batches 3` says how many
    PENDING batches to work through and skips stored ones without comment:
    skipping what is done is the whole point of asking for a count. Giving both
    is an error rather than a precedence rule, because a precedence rule is a
    thing readers guess at.

    Neither one means `--batches 1`. One, because that is the state the owner
    starts in — the numbers are unfamiliar until the calibration batch reports.
    Defaulting to `all` would make the first run the largest one, which is the
    opposite of what the calibration batch exists for.

    Both are declared optional to argparse for the reason `commands/ingest.py`
    records: argparse reports a MISSING required argument before an UNRECOGNISED
    one, so a required form would let `find-best-mobo extract --nonsense`
    complain about the absent batch and never name the flag, which R1006
    forbids.
    """
    parser = subcommand_parser(
        "extract",
        "Extract bundles into claims, stopping before the R26 spend cap.",
    )
    parser.add_argument("--batch", type=int, help="extract exactly this batch, e.g. 1")
    parser.add_argument(
        "--batches",
        help="how many PENDING batches to work through: a count, or `all` (default: 1)",
    )
    args = parser.parse_args(list(argv))
    if args.batch is not None and args.batches is not None:
        parser.error(
            "--batch and --batches ask different questions: --batch names one batch, "
            "--batches says how many pending ones to work through. Give one, not both."
        )
    if args.batches is not None and args.batches != ALL and not _is_count(args.batches):
        parser.error(f"--batches takes a positive whole number or `{ALL}`, not {args.batches!r}")
    return args


def pending_batches(config: Config) -> tuple[int, ...]:
    """The batches that have bundles on disk and are not yet in the claim store.

    Both halves matter. A batch with no bundle directory was never packed and is
    not work waiting to be done; a batch already in the store is work already
    paid for, and R27's mirror is that it is never silently redone. Ascending,
    because the batches are recency-ordered and batch 1 is the calibration one.
    """
    root = config.data_dir / "bundles"
    if not root.is_dir():
        return ()
    stored = batches_stored(config)
    found: list[int] = []
    for directory in root.iterdir():
        if not directory.is_dir() or not directory.name.startswith("batch-"):
            continue
        number = directory.name.removeprefix("batch-")
        if not number.isdigit() or not any(directory.glob("*.xml")):
            continue
        if int(number) not in stored:
            found.append(int(number))
    return tuple(sorted(found))


def batches_to_run(requested: str | None, config: Config) -> tuple[int, ...]:
    """The pending batches this run should do, in order.

    `None` means one — see `parse_args`. Asking for more batches than are
    pending is not an error: it means "as many as there are", which is what a
    reader means by `--batches 5` on a corpus with three left.
    """
    pending = pending_batches(config)
    if requested == ALL:
        return pending
    count = 1 if requested is None else int(requested)
    return pending[:count]


def _is_count(value: str) -> bool:
    return value.isdigit() and int(value) > 0


def run(config: Config, args: Namespace) -> int:
    """Extract the batches asked for, under the cap, and say what remains.

    `--batch N` is one batch and keeps its old behaviour exactly, refusal
    included. Otherwise this works through the pending batches, and **a ceiling
    stop ends the LOOP, not just the batch**: a run that has reached R26's line
    must not start another batch to discover the same thing again.

    Completing the requested count exits 0 even with batches still pending.
    Stopping because you asked for one batch is not a failure, and an exit code
    that said otherwise would make a normal continuation read as a recovery.
    """
    if args.batch is not None:
        return _run_one(config, args.batch)

    batches = batches_to_run(args.batches, config)
    if not batches:
        print("No pending batches. Every batch with bundles is already in the claim store.")
        return 0

    for batch in batches:
        code = _run_one(config, batch)
        if code != 0:
            print()
            print(f"Stopped after batch {batch}. Batches still pending: {_listed(config)}")
            return code

    remaining = pending_batches(config)
    print()
    if remaining:
        print(f"Ran {len(batches)} batch(es). Batches still pending: {_listed(config)}")
        print("  Run again to continue, or `--batches all` to work through the rest.")
    else:
        print(f"Ran {len(batches)} batch(es). Every batch with bundles is now extracted.")
    return 0


def _listed(config: Config) -> str:
    pending = pending_batches(config)
    return ", ".join(str(batch) for batch in pending) if pending else "none"


def _run_one(config: Config, batch: int) -> int:
    """One batch, exactly as this command has always done it."""
    directory = config.data_dir / "bundles" / f"batch-{batch}"
    try:
        require_directory(directory, f"bundle directory for batch {batch}", "estimate")
    except MissingArtifact as error:
        print(error.message())
        return 1

    # Sorted by name, which is the order `bundle.py` numbers them in, which is
    # recency order. A batch stopped part-way has then done the most useful
    # bundles in it rather than an arbitrary subset.
    bundles = sorted(directory.glob("*.xml"))
    if not bundles:
        # A real value, not a missing artifact: the batch exists and holds
        # nothing (OD-9, R1005). Nothing to spend, so nothing is spent.
        print(f"No bundles in {directory}. Nothing to extract.")
        return 0

    if batch in batches_stored(config):
        print(_already_stored(batch, config))
        return 1

    try:
        baseline = spend.take_reading(config)
    except UsageUnreadable as error:
        print(error.message())
        return 1

    limit = spend.ceiling(baseline, config)
    print(f"Extracting batch {batch}: {len(bundles)} bundles from {directory}")
    _print_reading("before the batch", baseline)
    print(f"  Ceiling for this effort: {_points(limit)} (R26: 10% above where the batch began)")

    run_state = _Run(batch=batch, bundles=bundles, config=config, limit=limit)
    run_state.execute(baseline)
    return run_state.report(baseline)


class _Run:
    """One batch's progress: what landed, what was paid for, and why it stopped.

    A class rather than a pile of locals because the stop can happen at three
    points — the baseline check, a part-way reading, and a broken extraction —
    and every one of them has to leave the same story behind: which bundles are
    done, which remain, what was spent, and what the meter said.
    """

    def __init__(self, batch: int, bundles: Sequence[Path], config: Config, limit: float) -> None:
        self.batch = batch
        self.bundles = tuple(bundles)
        self.config = config
        self.limit = limit
        self.done: list[str] = []
        self.set_aside: list[str] = []
        self.claims: list[Claim] = []
        self.results: list[ExtractionResult] = []
        self.readings: list[Reading] = []
        self.stopped: str | None = None
        # What this batch actually SENT, counted per call rather than per bundle
        # (R8). A bundle extracted twice was paid for twice and its characters
        # went over the wire twice, so a factor measured against one copy of them
        # would credit the model with reading half of what it read.
        self.characters_sent = 0
        self.projected_tokens = 0
        # Bundles whose own size could not be read back. They make the batch
        # unmeasurable rather than merely smaller: a projection missing one
        # bundle's characters, divided by tokens that include that bundle's, is
        # a factor that is wrong in a direction nobody would notice.
        self.unmeasured: list[str] = []

    def execute(self, baseline: Reading) -> None:
        """Extract each bundle in turn, reading the meter on the way through."""
        # The baseline is checked too, and only the clamp in `ceiling` can make
        # it fail: an account already at its weekly limit has no headroom to
        # spend, and the run should say so before paying for a bundle to find
        # out.
        try:
            spend.check(baseline, self.limit)
        except CapExceeded as error:
            self.stopped = error.message()
            return

        # Once, at the halfway bundle. A one-bundle batch has no part-way point
        # and gets two readings rather than a repeated one — R26 asks for a
        # reading part-way through a LONG batch, and the calibration batch of 12
        # is what that clause is written for.
        midpoint = len(self.bundles) // 2 if len(self.bundles) > 1 else 0

        for position, path in enumerate(self.bundles, start=1):
            if not self._extract(path):
                return
            if position == midpoint and not self._read_partway():
                return

    def report(self, baseline: Reading) -> int:
        """Append what was validated, print what happened, and pick the exit code."""
        after = self._final_reading()
        appended, refused = self._append()

        print()
        if self.stopped is not None:
            # The reason first, then the accounting, the way a halt reads in
            # `commands/fetch.py`: the owner needs to know the run stopped
            # before they read numbers that would otherwise look like a whole
            # batch's.
            print(self.stopped)
            print()
        print(f"Batch {self.batch}: {len(self.done)} of {len(self.bundles)} bundles extracted")
        _print_ids("done", self.done)
        _print_ids("set aside", self.set_aside)
        _print_ids("remaining", list(self._remaining()))
        if self.set_aside:
            print(
                "  A set-aside bundle stays unconsumed and was reported above with its "
                "faults (R9). Re-run this batch once the cause is understood."
            )
        print(f"  Appended {appended} claims to {store_path(self.config)} as batch {self.batch}")
        self._print_tokens()
        self._print_points(baseline, after)
        recorded = self._record(baseline, after)

        # Non-zero unless the whole batch landed. A stop, a set-aside bundle and
        # a store that refused the append all leave a batch that is partial, and
        # the exit code is the only signal a caller reads without parsing this
        # output (R27). A record that could not be WRITTEN counts too: R1011
        # makes the measurement part of what this command delivers, and a spend
        # whose evidence never reached the disk is the failure it exists for.
        complete = self.stopped is None and not self.set_aside and not refused and recorded
        return 0 if complete and not self._remaining() else 1

    def _extract(self, path: Path) -> bool:
        """Extract and validate one bundle. False stops the batch entirely.

        A file that fails VALIDATION twice sets its own bundle aside and the
        batch continues. An extraction that RAISES stops the batch: a boundary
        that is broken will be broken for the next bundle too, and eleven more
        failed calls would spend eleven more times to learn the same thing.
        """
        try:
            results, claims = self._extract_once_or_twice(path)
        # Broad on purpose. Whatever the model boundary raises, the owner gets a
        # named message and an exit code rather than a traceback with a half-run
        # batch behind it.
        except Exception as error:
            self.stopped = (
                f"Extraction failed on {path.name}: {error}\n"
                "Stopping the batch: the bundles after it stay unconsumed, and everything "
                "already extracted stays extracted (R27)."
            )
            return False

        # Both attempts' token counts are kept, valid or not. A call that
        # produced a malformed file is still a call that was paid for, and a
        # record counting only the successful ones would understate the batch
        # (R8).
        self.results.extend(results)
        self._count_sent(path, len(results))
        bundle_id = path.stem
        if claims is None:
            self.set_aside.append(bundle_id)
            return True
        self.claims.extend(claims)
        self.done.append(bundle_id)
        print(f"  {bundle_id}  {len(claims)} claims")
        return True

    def _extract_once_or_twice(
        self, path: Path
    ) -> tuple[list[ExtractionResult], tuple[Claim, ...] | None]:
        """One bundle's claims, after at most one retry, or None if set aside."""
        results: list[ExtractionResult] = []
        for attempt in range(1, _ATTEMPTS + 1):
            result = extract_bundle(path, self.batch, self.config)
            results.append(result)
            try:
                raw = result.claims_path.read_text(encoding="utf-8")
            except OSError as error:
                # Slice 2 writes the model's output before parsing it (R27), so
                # a file that cannot be read is a disk problem rather than a
                # model that misbehaved. Reported the same way regardless: the
                # bundle has no usable claims either way.
                print(f"  {result.claims_path} could not be read: {error}")
            else:
                try:
                    return results, parse_claims(raw, result.claims_path, self.batch)
                except InvalidClaims as error:
                    # Every fault at once, so a malformed file costs one round
                    # trip rather than one per bad row.
                    print(error.message())
            if attempt < _ATTEMPTS:
                print(f"  Retrying {path.name} once; a second bad file sets the bundle aside (R9).")
        return results, None

    def _read_partway(self) -> bool:
        """The reading that makes this a guard. False stops the batch."""
        try:
            partway = spend.take_reading(self.config)
        except UsageUnreadable as error:
            # A batch that carried on here would be running unwatched, which is
            # the state R26 forbids — and it would do so silently, since the
            # only sign is a reading that was never printed.
            self.stopped = (
                f"{error.message()}\nStopping the batch part-way rather than running it unwatched."
            )
            return False
        self.readings.append(partway)
        _print_reading("part-way through the batch", partway)
        try:
            spend.check(partway, self.limit)
        except CapExceeded as error:
            self.stopped = error.message()
            return False
        return True

    def _final_reading(self) -> Reading | None:
        """The receipt. Its absence is reported and never invents a number."""
        try:
            after = spend.take_reading(self.config)
        except UsageUnreadable as error:
            print(error.message())
            print("The batch's closing reading is missing; the work above is unaffected.")
            return None
        self.readings.append(after)
        return after

    def _append(self) -> tuple[int, bool]:
        """Append every validated claim in one call, returning what landed.

        One call for the whole batch, not one per bundle: the store refuses a
        batch it already holds (`claimstore.py`), so a second append tagged with
        the same batch would be refused however honest it was. The claims files
        themselves are already on disk whatever happens here — slice 2 writes
        each one as it is produced (R27) — so a stop costs the store's copy of
        the run and never the model output that was paid for.
        """
        if not self.claims:
            return 0, False
        try:
            return append_claims(self.claims, self.config), False
        except BatchAlreadyStored as error:
            print(error.message())
            return 0, True

    def _remaining(self) -> tuple[str, ...]:
        """The bundles this run never reached, in the order it would have."""
        attempted = set(self.done) | set(self.set_aside)
        return tuple(path.stem for path in self.bundles if path.stem not in attempted)

    def _print_tokens(self) -> None:
        """The four components this batch's calls reported, never summed (R8).

        A single total is dominated by cache reads — on the owner's machine they
        outnumber fresh input by more than four orders of magnitude — so the sum
        of the four is the cheapest number in the batch wearing the name of all
        of them. Every component prints, zero included, because a component that
        appeared only when it was non-zero could not be told from one that was
        never measured.
        """
        print(f"  {len(self.results)} model calls made for {len(self.bundles)} bundles")
        print(f"    fresh input    {sum(r.input_tokens for r in self.results)}")
        print(f"    output         {sum(r.output_tokens for r in self.results)}")
        print(f"    cache creation {sum(r.cache_creation_tokens for r in self.results)}")
        print(f"    cache read     {sum(r.cache_read_tokens for r in self.results)}")

    def _print_points(self, baseline: Reading, after: Reading | None) -> None:
        """Every reading this run took, and the difference across the batch.

        Points are printed beside the tokens and never folded into them (R8):
        they are different quantities measured by different instruments, and the
        conversion between them is slice 4's labelled estimate rather than
        something to do silently in a summary line.
        """
        print(f"  {baseline.label}: {_points(baseline.percent)} before the batch")
        for reading in self.readings:
            print(f"    then {_points(reading.percent)} via `{reading.source}`")
        if after is None:
            print("    no closing reading was taken")
            return
        delta = after.percent - baseline.percent
        print(f"    a difference of {_points(delta)} across the batch")

    def _count_sent(self, path: Path, calls: int) -> None:
        """Add one bundle's size, once per call that was made against it.

        The projection is a figure about text, so the comparison has to be
        against the same text. Read back off the bundle rather than carried
        forward from `estimate`: the two commands are separate runs, and a
        number passed between them through anything but the bundles themselves
        would be a second source that nothing keeps in step (R1011).
        """
        measured = _bundle_size(path, self.config)
        if measured is None:
            self.unmeasured.append(path.stem)
            return
        characters, projected = measured
        self.characters_sent += characters * calls
        self.projected_tokens += projected * calls

    def _record(self, baseline: Reading, after: Reading | None) -> bool:
        """Write this batch's calibration record, or say why there is none.

        **Two quantities, kept apart** (R8). The tokens are summed over THIS
        BATCH's own calls — retries included — and never taken from a usage
        tool's daily figure, which is a running total for the machine and would
        attribute to this batch whatever else the owner did today. They correct
        the chars-per-token factor, because both sides of that comparison are
        tokens. The points are the two meter readings, and they say what the
        batch took out of the weekly limit. Neither is derived from the other;
        the conversion between them is stored as a labelled estimate with its
        assumptions written out beside it.

        False only when a record that should have existed could not be written.
        A batch with nothing to measure is not a failure — it is a batch that
        spent nothing — but the reason is printed either way, because a missing
        record with no explanation reads as a step somebody forgot.
        """
        if after is None:
            self._no_record(
                "the closing reading is missing, so the points half of R8 would have to be "
                "written from a reading nobody took"
            )
            return True
        # Fresh input plus cache creation: the tokens this batch's own text
        # became. Cache reads are excluded because they are Claude Code's cached
        # prefix being re-served rather than bundle text — on this machine they
        # outnumber fresh input by more than four orders of magnitude, so
        # including them would put the factor off by that ratio — and output
        # tokens are excluded because they are not input at all. The four
        # components are still recorded separately below; this sum is the
        # divisor of one derived figure, not a total anything is reported as.
        tokens_read = sum(r.input_tokens + r.cache_creation_tokens for r in self.results)
        unmeasurable = self._unmeasurable(tokens_read)
        if unmeasurable is not None:
            self._no_record(unmeasurable)
            return True

        # Rounded to six decimals, which is four more than the meter reports.
        # Subtracting two floats leaves binary noise — 0.45 - 0.43 is not 0.02 —
        # and a record that stated the difference to seventeen places would be
        # claiming precision the instrument does not have, in the one file a
        # person reads to decide whether a spend was reasonable.
        delta = round(after.percent - baseline.percent, 6)
        record = CalibrationRecord(
            batch=self.batch,
            model=self.config.extraction_model.strip(),
            projected_tokens=self.projected_tokens,
            actual=TokenActual(
                input_tokens=sum(result.input_tokens for result in self.results),
                output_tokens=sum(result.output_tokens for result in self.results),
                cache_creation_tokens=sum(result.cache_creation_tokens for result in self.results),
                cache_read_tokens=sum(result.cache_read_tokens for result in self.results),
            ),
            measured_chars_per_token=self.characters_sent / tokens_read,
            points_before=baseline,
            points_after=after,
            points_delta=delta,
            # None when the meter did not move, and that is the RESULT rather
            # than a failure: the reader returns whole percentages, so a batch
            # costing less than one full point reads identically either side of
            # itself. A negative delta means the weekly window rolled over
            # mid-batch and is no more measurable than a flat one.
            tokens_per_point=round(tokens_read / (delta * 100.0), 3) if delta > 0 else None,
            conversion_assumptions=self._assumptions(after),
            recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        try:
            path = calibration.write_record(record)
        except OSError as error:
            print(f"  The calibration record for batch {self.batch} could not be written: {error}")
            print("    The batch's own numbers are printed above, but R1011's evidence is not")
            print("    on disk, and a console line is what R1011 exists to replace.")
            return False
        self._print_record(record, path, tokens_read)
        return True

    def _unmeasurable(self, tokens_read: int) -> str | None:
        """Why this batch cannot be calibrated, or None when it can be.

        Each of these makes the FACTOR wrong rather than merely absent, which is
        why none of them is worked around. A record is evidence, and evidence
        that is quietly missing a term is worse than no record: the projection
        would then be corrected towards a number nothing measured.
        """
        if not self.results:
            return "no model call was made, so there is nothing this batch measured"
        if self.unmeasured:
            return (
                f"the text of {', '.join(self.unmeasured)} could not be read back, so the "
                "projection to compare against is missing what those bundles held"
            )
        if not self.config.extraction_model.strip():
            return (
                "no `extraction_model` is set in config.toml, and a factor that cannot name "
                "the model it was measured against does not transfer to any other"
            )
        if tokens_read <= 0:
            return "the calls reported no input tokens, so there is nothing to divide by"
        if self.characters_sent <= 0:
            return "the bundles carry no transcript text, so there is nothing that was read"
        return None

    def _assumptions(self, after: Reading) -> tuple[str, ...]:
        """Everything the token-to-points conversion rests on, written out (R8).

        Written out rather than implied, because an estimate whose assumptions
        are not stored beside it cannot be corrected later, only replaced. They
        are assembled per run rather than kept as a constant: which reader
        answered and how many calls were made are facts about THIS batch, and an
        assumption list that stated them generically would be describing some
        other run.

        Nothing reads this list as an input. It is for the person who later asks
        why the number is what it is.
        """
        return (
            f"The token figures are summed over this batch's own {len(self.results)} calls, "
            "retries included, from what each `claude -p` call reported. They are never "
            "taken from a usage tool's daily total, which counts every other session on "
            "the machine that day.",
            "The tokens divided into the points are fresh input plus cache creation — the "
            "tokens this batch's own text became. Cache reads are excluded as Claude Code's "
            "own re-served prefix, and output tokens as not being input; if the weekly limit "
            "is charged on all four, this understates what a point buys.",
            f"The points are the {after.label} percentage read before and after the batch via "
            f"`{after.source}`. That figure is account-wide, so any other session on the "
            "subscription during the batch is counted in it and attributed here to this batch.",
            "The reader reports whole percentage points, so a delta of one point is anything "
            "from just over zero to just under two. The conversion is accurate to no better "
            "than the point it is measured in.",
            "The conversion assumes the whole movement of the meter was this batch's. It is "
            "an estimate in the direction tokens-to-points only; the chars-per-token factor "
            "beside it is a measurement and is not derived from any of this (R8).",
        )

    def _no_record(self, reason: str) -> None:
        print(f"  No calibration record written for batch {self.batch}: {reason}.")

    def _print_record(self, record: CalibrationRecord, path: Path, tokens_read: int) -> None:
        """What landed in the record, so the console and the file agree.

        Printed as well as written because the owner is reading this run now and
        the record is for everyone reading it later — but the file is the
        evidence, and this is the notice that it exists (R1011).
        """
        print(f"  Calibration record for batch {self.batch} written to {path}")
        print(
            f"    {record.projected_tokens} projected tokens against {tokens_read} read "
            f"({record.actual.input_tokens} fresh input, "
            f"{record.actual.cache_creation_tokens} cache creation)"
        )
        print(
            f"    corrected factor: {record.measured_chars_per_token:.4g} characters per token, "
            f"against the configured {self.config.chars_per_token}"
        )
        if record.tokens_per_point is None:
            print(
                "    tokens per weekly point: unmeasurable at this batch size — the meter "
                "reads whole percentages and did not move. That is a result, not a failure."
            )
        else:
            print(
                f"    tokens per weekly point: {record.tokens_per_point:.0f}, an ESTIMATE — "
                "the assumptions it rests on are written out in the record."
            )


def _print_reading(when: str, reading: Reading) -> None:
    """One reading, with the reader that gave it.

    The source is printed every time rather than only for the fallback: a
    reading taken by `claude -p "/usage"` started a session and so moved the
    meter it reported, and that is a property of the evidence, not a footnote.
    """
    print(f"  {reading.label} reads {_points(reading.percent)} {when} (`{reading.source}`)")


def _print_ids(label: str, ids: Sequence[str]) -> None:
    """Name the bundles in a group, always — an empty group prints as none.

    A line that appeared only when it was non-empty could not be told from a run
    that never counted, which is the rule R1009 and R1012 already follow.
    """
    print(f"  {label}: {', '.join(ids) if ids else 'none'}")


def _already_stored(batch: int, config: Config) -> str:
    """Refuse before spending, when the store already holds this batch.

    The store refuses a second append for a batch it holds, so extracting one
    again would pay for claims that could never land. Better to find that out
    for nothing than for twelve bundles.
    """
    return (
        f"Batch {batch} is already in {store_path(config)}. Extracting it again would spend "
        "on claims the append-only store would then refuse, so nothing was extracted. "
        "If the batch really must be redone, move the store aside first — deliberately, "
        "and with the old one kept."
    )


def _bundle_size(path: Path, config: Config) -> tuple[int, int] | None:
    """One bundle's transcript characters and the tokens the projection gave it.

    The TRANSCRIPT text only, not the file: `estimate` projects the text it cut,
    and a factor measured against the XML around it would be measuring the
    renderer. The token figure is the projection's own arithmetic — the same
    per-block rounding `bundle.estimate_tokens` does, so the number here is the
    number the projection printed rather than a second estimate of it.

    None when the bundle cannot be read or parsed. The caller treats that as a
    batch it cannot calibrate rather than as a bundle worth zero, because zero
    would be a real-looking number that shifts the factor.
    """
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    texts = [element.text or "" for element in root.iter("transcript")]
    return sum(len(text) for text in texts), sum(estimate_tokens(text, config) for text in texts)


def _points(fraction: float) -> str:
    """A fraction rendered as the percentage points the meter is read in."""
    return f"{fraction * 100:g}%"
