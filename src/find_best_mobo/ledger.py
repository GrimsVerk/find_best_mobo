"""The failure ledger and the halt triggers that read it.

Gaps in the corpus are recorded, never implied (`docs/DESIGN.md` R24): every
video that could not be fetched lands in `data/failures.jsonl` with its class,
its detail, and how many runs have now tried it. The triggers on top of that
ledger (R21) stop a run that has stopped working — a string of network errors,
or a share of the corpus going missing — rather than letting it grind through a
thousand videos producing nothing.

The file is rewritten from *this* run's failures on every record, while
`failed_ids()` keeps reporting what failed on the *previous* run. That asymmetry
is the whole mechanism: a video that failed last time and succeeds this time is
retried because it is still in `failed_ids()`, and disappears from the file
because it was never recorded this run.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from find_best_mobo.config import Config


@dataclass(frozen=True)
class FetchFailure:
    video_id: str
    title: str
    upload_date: date
    failure_class: str  # "no_captions" | "fetch_error"
    detail: str
    attempts: int


class HaltTriggered(Exception):
    """A halt trigger fired: the run stops here, with its evidence on disk.

    Carries the trigger's name and this run's ledger so the command can report
    both. It is a deliberate stop, not a crash — the caller catches it, prints
    it, and exits non-zero without a traceback reaching the owner.
    """

    def __init__(self, trigger: str, ledger: Sequence[FetchFailure]) -> None:
        super().__init__(f"halt trigger fired: {trigger}")
        self.trigger = trigger
        self.ledger = tuple(ledger)


class Ledger:
    """This run's failures, the previous run's, and the triggers between them.

    `indexed_count` is how many videos this run will attempt; it is the
    denominator of the rate triggers, and a zero never divides.
    """

    def __init__(self, path: Path, config: Config, indexed_count: int) -> None:
        self._path = path
        self._config = config
        self._indexed_count = indexed_count
        self._failures: list[FetchFailure] = []
        self._consecutive_fetch_errors = 0
        self._successes = 0
        previous = _read(path)
        # Both snapshots are frozen at construction. `failed_ids()` answering
        # from the previous run — not from what this run has recorded so far —
        # is what lets a caller ask "what should be retried?" at any point.
        self._previous_attempts: dict[str, int] = {
            failure.video_id: failure.attempts for failure in previous
        }
        self._failed_ids = frozenset(self._previous_attempts)

    def record(self, failure: FetchFailure) -> None:
        """Add a failure for this run and rewrite the file.

        Rewritten on every record rather than once at the end, so a halt — or a
        crash, or a Ctrl-C — still leaves the evidence on disk. `attempts` is
        filled in here because the ledger is the only thing that knows what the
        previous run counted for this video.
        """
        counted = replace(failure, attempts=self._previous_attempts.get(failure.video_id, 0) + 1)
        self._failures.append(counted)
        if counted.failure_class == "fetch_error":
            self._consecutive_fetch_errors += 1
        else:
            # A `no_captions` is a definitive answer from YouTube, so the
            # network is demonstrably working: it breaks the error streak.
            self._consecutive_fetch_errors = 0
        self._write()

    def record_success(self) -> None:
        """Count one fetched video and break the consecutive-error streak.

        Takes no arguments by design: a video that succeeds simply never
        appears in the ledger.
        """
        self._successes += 1
        self._consecutive_fetch_errors = 0

    def check_triggers(self) -> str | None:
        """Name the trigger that has fired, or None while the run is healthy.

        The consecutive-error trigger is checked first because it is the one
        that fires early — the rates need a meaningful share of the corpus
        behind them before they mean anything, by which point a dead network
        would have wasted the whole run.
        """
        if self._consecutive_fetch_errors >= self._config.consecutive_fetch_error_limit:
            return "consecutive_fetch_errors"
        if self._rate("fetch_error") > self._config.fetch_error_rate_limit:
            return "fetch_error_rate"
        if self._rate("no_captions") > self._config.missing_caption_rate_limit:
            return "missing_caption_rate"
        return None

    def failures(self) -> tuple[FetchFailure, ...]:
        """This run's failures, in the order they were recorded."""
        return tuple(self._failures)

    def failed_ids(self) -> frozenset[str]:
        """The ids that failed on the previous run, read at construction.

        Deliberately unaffected by what this run records: it answers "what was
        broken when we started", which is the question a retry has to ask.
        """
        return self._failed_ids

    def _rate(self, failure_class: str) -> float:
        """This run's share of `failure_class`, or 0.0 with nothing indexed."""
        if self._indexed_count <= 0:
            return 0.0
        count = sum(1 for failure in self._failures if failure.failure_class == failure_class)
        return count / self._indexed_count

    def _write(self) -> None:
        """Rewrite the whole file as deterministic JSONL (R23)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8", newline="\n") as handle:
            for failure in self._failures:
                record: dict[str, Any] = {
                    "video_id": failure.video_id,
                    "title": failure.title,
                    "upload_date": failure.upload_date.isoformat(),
                    "failure_class": failure.failure_class,
                    "detail": failure.detail,
                    "attempts": failure.attempts,
                }
                handle.write(json.dumps(record, sort_keys=True))
                handle.write("\n")


def _read(path: Path) -> tuple[FetchFailure, ...]:
    """Read a previous run's ledger; a missing or damaged file reads as empty.

    An unreadable line is skipped rather than raised on, for the same reason a
    corrupt transcript is refetched: the ledger describes work to redo, and the
    worst consequence of losing a line is redoing one video.
    """
    if not path.exists():
        return ()
    failures: list[FetchFailure] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            failures.append(
                FetchFailure(
                    video_id=str(record["video_id"]),
                    title=str(record.get("title", "")),
                    upload_date=date.fromisoformat(record["upload_date"]),
                    failure_class=str(record["failure_class"]),
                    detail=str(record.get("detail", "")),
                    attempts=int(record.get("attempts", 1)),
                )
            )
        except (ValueError, KeyError, TypeError):
            continue
    return tuple(failures)
