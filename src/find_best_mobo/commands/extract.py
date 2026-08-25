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

This is the first command in the project that spends anything. Everything it
spends goes through `find_best_mobo.extract`; everything it is allowed to spend
goes through `find_best_mobo.spend`.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from pathlib import Path

from find_best_mobo import spend
from find_best_mobo.artifacts import MissingArtifact, require_directory
from find_best_mobo.claims import Claim, InvalidClaims, parse_claims
from find_best_mobo.claimstore import BatchAlreadyStored, append_claims, batches_stored, store_path
from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import Config
from find_best_mobo.extract import ExtractionResult, extract_bundle
from find_best_mobo.spend import CapExceeded, Reading, UsageUnreadable

# How many attempts one bundle gets before it is set aside. Two, not more: a
# claims file that fails the schema twice is a prompt or a bundle that needs
# looking at, and a third attempt would pay for the same misunderstanding again.
_ATTEMPTS = 2


def parse_args(argv: Sequence[str]) -> Namespace:
    """Which batch to extract, and nothing else.

    `--batch` is declared optional to argparse and required below, for the
    reason `commands/ingest.py` records: argparse reports a MISSING required
    argument before an UNRECOGNISED one, so `find-best-mobo extract --nonsense`
    would complain about the absent batch and never name the flag, and R1006's
    rule is that an undeclared flag is always named.
    """
    parser = subcommand_parser(
        "extract",
        "Extract one batch of bundles into claims, stopping before the R26 spend cap.",
    )
    parser.add_argument("--batch", type=int, help="the batch to extract, e.g. 1")
    args = parser.parse_args(list(argv))
    if args.batch is None:
        parser.error("the following arguments are required: --batch")
    return args


def run(config: Config, args: Namespace) -> int:
    """Extract one batch under the cap, and say what it cost and what remains."""
    batch: int = args.batch
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

        # Non-zero unless the whole batch landed. A stop, a set-aside bundle and
        # a store that refused the append all leave a batch that is partial, and
        # the exit code is the only signal a caller reads without parsing this
        # output (R27).
        complete = self.stopped is None and not self.set_aside and not refused
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


def _points(fraction: float) -> str:
    """A fraction rendered as the percentage points the meter is read in."""
    return f"{fraction * 100:g}%"
