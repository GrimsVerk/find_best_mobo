"""The append-only claim store, tagged by batch.

One JSON Lines file holding every claim ever extracted, in the order the batches
were ingested. Append-only is not tidiness: R10 promises that a stop between
batches loses no work and that any batch can be resumed, and R27 promises that
no completed work is lost to an overrun. Both are claims about a file that is
only ever added to.

The mirror of R27 is the rule this module actually enforces: **no completed work
is silently REWRITTEN either.** A batch already in the store cannot be ingested
again — not merged, not appended twice. A rerun that quietly doubled a batch's
evidence would corrupt every count downstream while every gate stayed green, and
the store is exactly the artifact nobody re-reads once it is large.

Writes are atomic per FILE. Either every claim in a valid claims file lands or
none does; a partial append would leave the store holding half a bundle's
evidence with nothing recording which half.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Sequence
from dataclasses import asdict
from pathlib import Path

from find_best_mobo.claims import Claim
from find_best_mobo.config import Config


class BatchAlreadyStored(RuntimeError):
    """A batch already in the store cannot be ingested again."""

    def __init__(self, batch: int, path: Path) -> None:
        self.batch = batch
        self.path = path
        super().__init__(self.message())

    def message(self) -> str:
        return (
            f"batch {self.batch} is already in {self.path}. The store is append-only: "
            "re-ingesting would double its evidence rather than replace it. Nothing was "
            "appended. If the batch really must be redone, move the store aside first — "
            "deliberately, and with the old one kept."
        )


def store_path(config: Config) -> Path:
    """`data/claims.jsonl`. One file, because the batch tag is on every row."""
    return config.data_dir / "claims.jsonl"


def append_claims(claims: Sequence[Claim], config: Config) -> int:
    """Append every claim, or none, returning how many landed.

    Atomic per call: the rows are rendered in full before the file is opened, so
    a serialisation fault cannot leave a half-written batch behind. The append
    itself is one `write` of one buffer, flushed and fsynced, because the run
    this protects is one that may be stopped by a spend guard mid-batch (R26).

    An empty sequence is a real value and appends nothing: a bundle whose
    excerpts mention no board it can make a claim about is a valid outcome, not
    a failure.
    """
    if not claims:
        return 0

    path = store_path(config)
    batches = {claim.batch for claim in claims}
    stored = batches_stored(config)
    for batch in sorted(batches & stored):
        raise BatchAlreadyStored(batch, path)

    payload = "".join(json.dumps(asdict(claim), sort_keys=True) + "\n" for claim in claims)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return len(claims)


def read_claims(config: Config) -> Iterator[Claim]:
    """Every stored claim, in the order it was appended.

    A missing store yields nothing — no batch has been ingested yet, which is a
    real state and not a missing artifact. A row that does not parse RAISES:
    this file is append-only evidence that has already been paid for, and a
    reader that skipped a corrupt row would report a smaller corpus than was
    bought without saying so.
    """
    path = store_path(config)
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield Claim(**json.loads(line))
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{number} is not a stored claim: {error}") from error


def batches_stored(config: Config) -> frozenset[int]:
    """Which batches the store already holds. The refusal above reads this."""
    return frozenset(claim.batch for claim in read_claims(config))
