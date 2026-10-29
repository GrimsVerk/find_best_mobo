"""Tests for Stage B slice 3's R26 guard — the meter, and the line it stops before.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 3), the
owner's 2026-08-25 rulings in `docs/DECISIONS.md`, BL-24 and R26, while the
implementation is authored in parallel — so failing imports are the expected
state until assembly.

**Nothing here invokes a reader.** Two guards make that mechanical rather than a
promise. `never_shell_out` is autouse and replaces every way this process could
start a subprocess with something that fails the test, so a seam this file
missed shows up as a loud assertion instead of a real `claude -p "/usage"` that
would spend against the very limit under test. `install_reader` then hands the
tests a fake, patched both on `subprocess` itself and on any name `spend` bound
from it at import — the two import styles `ytdlp.py` chooses between, since the
plan tells the implementer to shape this seam like that module's.

Three properties here are the ones a plausible-looking guard gets wrong:

- the ceiling is `baseline + 0.10`, **measured from the baseline**. A run that
  starts at 43% stops at 53% and is not refused outright, because R26 caps the
  extraction EFFORT and not the account. Every ceiling test below therefore uses
  a baseline well above 10%: one starting at 2% would pass against an
  implementation reading the cap as an absolute 10% and would refuse every real
  run on the owner's machine.
- `Weekly (7-day)` governs, matched by that exact label. The payloads below put
  it third among four limits, with a model-scoped limit first carrying a
  different number, so an implementation taking `limits[0]` reads 7% where the
  account is at 43%.
- `Reading.source` records WHICH reader answered, because the fallback starts a
  session and so spends against the limit it reads.

Two things the plan does not rule, and which are deliberately NOT asserted here:
whether a reading exactly EQUAL to the ceiling raises (only strictly-above and
strictly-below are pinned), and what `claude -p "/usage"` prints — the fallback
is fed the same JSON shape as the primary, which is the only thing a blind test
can assume.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose, exactly as in
# tests/test_claims.py: `find_best_mobo.spend` does not exist yet, so the isort
# rule classifies it as third-party and would demand a different grouping from
# the one it demands once the slice lands. The block is written in its
# post-assembly order, which is the stable one.
from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import FrozenInstanceError, fields
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from find_best_mobo import spend
from find_best_mobo.config import Config
from find_best_mobo.spend import (
    WEEKLY_LABEL,
    CapExceeded,
    Reading,
    ceiling,
    check,
    take_reading,
)

# Captured at import, before `never_shell_out` replaces them. `install_reader`
# needs the REAL functions to recognise a name `spend` bound with
# `from subprocess import run`, which points at the original object forever.
_REAL_RUN = subprocess.run
_REAL_CHECK_OUTPUT = subprocess.check_output
_REAL_WHICH = shutil.which

# Which module-level names `spend` bound from `subprocess`/`shutil` at import,
# recorded ONCE and before anything is patched. `ytdlp.py` binds its boundary
# that way (`from yt_dlp import YoutubeDL`) and its tests patch the bound name;
# an implementation that wrote `import subprocess` instead is covered by
# patching `subprocess` itself. Scanning here rather than inside the helper
# matters because a second install would otherwise find the first install's
# replacement sitting where the original was.
_SPEND_ALIASES: dict[str, object] = {
    name: value
    for name, value in vars(spend).items()
    if value is _REAL_RUN or value is _REAL_CHECK_OUTPUT or value is _REAL_WHICH
}

# The reader R26 names, and the fallback BL-24 rules is a fallback.
OMARCHY = "omarchy-agent-usage-claude"
CLAUDE = "claude"

RESETS_AT = "2026-09-01T00:00:00+00:00"

# The account-wide weekly figure the owner ruled governs, at a level well above
# the 10% cap — which is the whole point of the fixture.
WEEKLY_PERCENT = 0.43

# Four limits, in the shape the reader returns them, with `Weekly (7-day)` NOT
# first and every decoy carrying a DIFFERENT number. An implementation reading
# `limits[0]`, or the largest, or the last, reads a value no test below accepts.
LIMITS: tuple[dict[str, Any], ...] = (
    {"label": "Opus 5 (weekly)", "percent": 0.07, "resetsAt": RESETS_AT},
    {"label": "Session (5-hour)", "percent": 0.88, "resetsAt": RESETS_AT},
    {"label": WEEKLY_LABEL, "percent": WEEKLY_PERCENT, "resetsAt": RESETS_AT},
    {"label": "Weekly (Opus)", "percent": 0.12, "resetsAt": RESETS_AT},
)


def make_config(data_dir: Path) -> Config:
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=date(2023, 1, 1),
        data_dir=data_dir,
        shorts_max_seconds=120,
        mention_threshold=3,
        window_before_seconds=120,
        window_after_seconds=300,
        per_video_excerpt_cap=10,
        bundle_token_cap=30000,
        calibration_batch_size=12,
        batch_count=3,
        chars_per_token=4.0,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return make_config(tmp_path / "data")


def payload(*limits: dict[str, Any]) -> str:
    """The reader's JSON: a `limits` array of label/percent/resetsAt objects."""
    return json.dumps({"limits": list(limits)})


def reading(percent: float, *, label: str = WEEKLY_LABEL, source: str = "test") -> Reading:
    """A constructed reading. The guard's arithmetic is pinned against these."""
    return Reading(label=label, percent=percent, taken_at=RESETS_AT, source=source)


def digits(value: float) -> str:
    """`0.53` as `53` — the substring shared by every plausible rendering.

    A message may print a fraction (`0.53`), a percentage (`53%`), or a rounded
    point (`53.0`). All three contain these digits, and none of the other
    numbers in this file do, so this asserts the number is REPORTED without
    pinning a format the plan never states.
    """
    return f"{round(value * 100)}"


def allowed(taken: Reading, line: float) -> bool:
    """True when `check` let the run continue — it neither raised nor returned.

    Both halves of the original assertion survive here, in the one place mypy
    has to be told about: `check` is declared `-> None` in the plan's Signatures
    block, so using its result at a call site is a type error rather than a test
    that could ever fail. What the call sites are really about is that the guard
    does NOT refuse, and a `CapExceeded` raised inside propagates out of this
    helper with its own message intact — a better failure than any assertion
    text could be.
    """
    outcome: object = check(taken, line)  # type: ignore[func-returns-value]
    return outcome is None


@pytest.fixture(autouse=True)
def never_shell_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test in this file may start a real process.

    The stakes are asymmetric and specific: if a test missed the seam, the
    implementation would try the real `omarchy-agent-usage-claude`, fail, and
    fall back to `claude -p "/usage"` — which starts a session and SPENDS
    against the weekly limit these tests exist to protect. A loud failure here
    is the only acceptable outcome of a missed seam.
    """

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            f"a test started a real process: {args!r}. The reader seam was not "
            "patched, and the fallback reader spends against the limit under test."
        )

    for name in ("run", "check_output", "check_call", "call", "Popen"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(os, "system", forbidden)


class FakeReader:
    """Stands in for both readers, and records which one was asked, in order.

    Answers are keyed by which command the argv names, so the fake never has to
    know how the implementation assembles either command line — only that one
    mentions `omarchy-agent-usage-claude` and the other `claude`.

    An answer is either a `str` (the reader's stdout, exit code zero), an
    `Exception` (raised, e.g. a missing binary), or an `int` (a non-zero exit).
    """

    def __init__(self, *, omarchy: object, claude: object = None) -> None:
        self.answers: dict[str, object] = {OMARCHY: omarchy, CLAUDE: claude}
        self.calls: list[tuple[str, ...]] = []

    # -- classification -------------------------------------------------

    def _which(self, argv: Sequence[object]) -> str:
        words = " ".join(str(part) for part in argv)
        if OMARCHY in words:
            return OMARCHY
        if CLAUDE in words:
            return CLAUDE
        raise AssertionError(f"a reader this test does not know about was asked: {words!r}")

    def _answer(self, argv: Sequence[object]) -> tuple[int, str]:
        as_tuple = tuple(str(part) for part in argv)
        self.calls.append(as_tuple)
        answer = self.answers[self._which(argv)]
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, int):
            return answer, ""
        if answer is None:
            raise AssertionError(
                f"the fallback reader was asked but this test gave it no answer: {as_tuple}"
            )
        return 0, str(answer)

    # -- the two entry points an implementation might have bound ---------

    @staticmethod
    def _encode(text: str, kwargs: dict[str, object]) -> Any:
        """`str` when the caller asked for text mode, `bytes` otherwise."""
        textual = kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding")
        return text if textual else text.encode("utf-8")

    def run(self, args: Sequence[object], **kwargs: object) -> subprocess.CompletedProcess[Any]:
        # `args` is deliberately `Sequence[object]`: an implementation may put a
        # `Path` in its argv, and the fake must accept whatever the real runner
        # would. `CompletedProcess` and `CalledProcessError` want strings, so the
        # rendering the fake already does for classification is reused here.
        command = [str(part) for part in args]
        code, out = self._answer(args)
        if code and kwargs.get("check"):
            raise subprocess.CalledProcessError(code, command, self._encode(out, kwargs))
        return subprocess.CompletedProcess(
            args=command,
            returncode=code,
            stdout=self._encode(out, kwargs),
            stderr=self._encode("reader failed" if code else "", kwargs),
        )

    def check_output(self, args: Sequence[object], **kwargs: object) -> Any:
        command = [str(part) for part in args]
        code, out = self._answer(args)
        if code:
            raise subprocess.CalledProcessError(code, command, self._encode(out, kwargs))
        return self._encode(out, kwargs)

    # -- what the recording is for --------------------------------------

    @property
    def asked(self) -> list[str]:
        """Which reader answered each call, in order."""
        return [self._which(call) for call in self.calls]


def install_reader(monkeypatch: pytest.MonkeyPatch, reader: FakeReader) -> FakeReader:
    """Patch every way `spend` could reach a reader, both import styles.

    `ytdlp.py` binds its boundary at module level (`from yt_dlp import
    YoutubeDL`) and its tests patch that name; an implementation that wrote
    `import subprocess` instead is patched through `subprocess` itself. Both are
    covered rather than guessed at, because which one the implementer chose is
    exactly what a blind test may not know.
    """

    def found(command: str, *rest: object, **kwargs: object) -> str:
        # A reader looked up on PATH must be found, or an implementation that
        # probes before running would take the fallback for the wrong reason.
        return f"/usr/bin/{command}"

    replacements: dict[object, Callable[..., Any]] = {
        _REAL_RUN: reader.run,
        _REAL_CHECK_OUTPUT: reader.check_output,
        _REAL_WHICH: found,
    }
    monkeypatch.setattr(subprocess, "run", reader.run)
    monkeypatch.setattr(subprocess, "check_output", reader.check_output)
    monkeypatch.setattr(shutil, "which", found)
    for attribute, original in _SPEND_ALIASES.items():
        monkeypatch.setattr(spend, attribute, replacements[original])
    return reader


class TestTheLabelThatGoverns:
    """The owner's 2026-08-25 ruling, as a constant other modules can read."""

    def test_the_weekly_seven_day_limit_is_the_one_named(self) -> None:
        assert WEEKLY_LABEL == "Weekly (7-day)"

    def test_the_label_is_not_a_model_scoped_one(self) -> None:
        # The model-scoped limit ignores spend on every other model, which is
        # the specific reason the owner ruled against it.
        assert "opus" not in WEEKLY_LABEL.lower()
        assert "sonnet" not in WEEKLY_LABEL.lower()


class TestTheCeilingIsMeasuredFromTheBaseline:
    """R26 caps the extraction EFFORT, not the account."""

    def test_a_run_starting_at_forty_three_percent_stops_at_fifty_three(
        self, config: Config
    ) -> None:
        assert ceiling(reading(0.43), config) == pytest.approx(0.53)

    def test_a_baseline_over_ten_percent_is_not_a_refusal(self, config: Config) -> None:
        """The failure this pins: an absolute 10% ceiling refuses every real run.

        The owner's machine sits well above 10% of the weekly limit most weeks.
        An implementation reading R26 as "stop if the account is over 10%" would
        refuse before extracting anything, forever, and would look correct to a
        test whose baseline was 0.02.
        """
        baseline = reading(0.43)
        line = ceiling(baseline, config)

        assert line > baseline.percent, "the ceiling must leave room to extract in"
        assert line != pytest.approx(0.10), "the cap is 10% ABOVE the baseline, not 10% absolute"
        assert allowed(baseline, line), "a run at 43% is not refused for being at 43%"

    def test_a_fresh_week_ceilings_at_ten_percent(self, config: Config) -> None:
        assert ceiling(reading(0.0), config) == pytest.approx(0.10)

    @pytest.mark.parametrize("baseline", [0.0, 0.02, 0.31, 0.43, 0.5, 0.899])
    def test_the_ceiling_is_the_baseline_plus_ten_points(
        self, config: Config, baseline: float
    ) -> None:
        assert ceiling(reading(baseline), config) == pytest.approx(baseline + 0.10)

    @pytest.mark.parametrize("baseline", [0.91, 0.95, 0.99, 1.0])
    def test_the_ceiling_is_clamped_at_the_whole_limit(
        self, config: Config, baseline: float
    ) -> None:
        """Above 90% there is no 10% left, and a ceiling over 1.0 is not a place."""
        assert ceiling(reading(baseline), config) == pytest.approx(1.0)

    def test_the_ceiling_reads_the_baseline_rather_than_the_meter(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`ceiling` is arithmetic over the reading it is handed, and nothing else.

        Asserted by leaving the reader forbidden: `never_shell_out` is autouse,
        so a `ceiling` that took its own reading fails here rather than in
        production.
        """
        assert ceiling(reading(0.43), config) == pytest.approx(0.53)


class TestTheCheckStopsBeforeTheLine:
    def test_a_reading_below_the_ceiling_passes(self) -> None:
        assert allowed(reading(0.49), 0.53)

    def test_a_reading_well_below_the_ceiling_passes(self) -> None:
        assert allowed(reading(0.43), 0.53)

    def test_a_reading_over_the_ceiling_raises(self) -> None:
        with pytest.raises(CapExceeded):
            check(reading(0.61), 0.53)

    def test_the_refusal_carries_the_reading_and_the_ceiling(self) -> None:
        """Constructor parameters are attributes, as `InvalidClaims` and
        `MissingArtifact` already establish in this repository."""
        crossed = reading(0.61)

        with pytest.raises(CapExceeded) as caught:
            check(crossed, 0.53)

        assert caught.value.reading == crossed
        assert caught.value.ceiling == pytest.approx(0.53)

    def test_the_refusal_says_what_it_read_and_what_the_line_was(self) -> None:
        with pytest.raises(CapExceeded) as caught:
            check(reading(0.61), 0.53)

        message = caught.value.message()
        assert digits(0.61) in message, f"the refusal does not say what it read: {message!r}"
        assert digits(0.53) in message, f"the refusal does not say where the line was: {message!r}"

    def test_the_refusal_names_the_limit_it_is_about(self) -> None:
        with pytest.raises(CapExceeded) as caught:
            check(reading(0.61), 0.53)

        assert WEEKLY_LABEL in caught.value.message()

    def test_cap_exceeded_is_a_runtime_error(self) -> None:
        assert issubclass(CapExceeded, RuntimeError)


class TestReadingIsEvidence:
    def test_a_reading_carries_the_four_declared_fields(self) -> None:
        assert tuple(field.name for field in fields(Reading)) == (
            "label",
            "percent",
            "taken_at",
            "source",
        )

    def test_a_reading_is_frozen(self) -> None:
        taken = reading(0.43)

        with pytest.raises(FrozenInstanceError):
            taken.percent = 0.01  # type: ignore[misc]


class TestWhichReaderAnswered:
    """BL-24's ruling: the omarchy reader first, `claude -p "/usage"` as fallback.

    The fallback is a fallback because it starts a session and so spends against
    the very limit it reads, which is why `Reading.source` has to say which one
    answered — a reading that perturbed the meter is a different kind of
    evidence from one that did not.
    """

    def test_the_omarchy_reader_is_asked_first(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reader = install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))

        take_reading(config)

        assert reader.asked[:1] == [OMARCHY], f"the first reader asked was {reader.asked}"

    def test_the_omarchy_reader_is_asked_the_way_r26_names_it(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reader = install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))

        take_reading(config)

        words = " ".join(reader.calls[0])
        assert "--limits-only" in words, words
        assert "--force" in words, words

    def test_the_fallback_is_not_asked_when_the_first_reader_answers(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fallback taken eagerly spends every time the guard looks at the meter."""
        reader = install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))

        take_reading(config)

        assert reader.asked == [OMARCHY], f"the session-starting reader was asked: {reader.calls}"

    def test_the_source_names_the_reader_that_answered(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))

        taken = take_reading(config)

        assert OMARCHY in taken.source, (
            f"the reading does not record which reader produced it: {taken.source!r}"
        )

    @pytest.mark.parametrize(
        ("failure", "case"),
        [
            (FileNotFoundError(2, "No such file or directory", OMARCHY), "the binary is absent"),
            (1, "the reader exits non-zero"),
            ("not json at all", "the reader prints something unparseable"),
        ],
    )
    def test_the_fallback_answers_when_the_first_reader_fails(
        self,
        config: Config,
        monkeypatch: pytest.MonkeyPatch,
        failure: object,
        case: str,
    ) -> None:
        reader = install_reader(monkeypatch, FakeReader(omarchy=failure, claude=payload(*LIMITS)))

        taken = take_reading(config)

        assert reader.asked == [OMARCHY, CLAUDE], f"{case}: asked {reader.asked}"
        assert taken.percent == pytest.approx(WEEKLY_PERCENT), case

    def test_the_fallbacks_reading_says_it_was_the_fallback(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The two sources must be distinguishable, because one of them spent."""
        install_reader(
            monkeypatch,
            FakeReader(omarchy=FileNotFoundError(2, "absent", OMARCHY), claude=payload(*LIMITS)),
        )

        taken = take_reading(config)

        assert CLAUDE in taken.source, taken.source
        assert OMARCHY not in taken.source, (
            f"the fallback reported the reader that failed: {taken.source!r}"
        )

    def test_the_two_readers_produce_different_sources(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))
        first = take_reading(config)

        # No `monkeypatch.undo()`: it would also lift `never_shell_out`, and the
        # second `install_reader` simply layers over the first.
        install_reader(
            monkeypatch,
            FakeReader(omarchy=FileNotFoundError(2, "absent", OMARCHY), claude=payload(*LIMITS)),
        )
        second = take_reading(config)

        assert first.source != second.source
        assert first.percent == pytest.approx(second.percent), (
            "the same meter read twice, so only the source may differ"
        )

    def test_both_readers_failing_is_reported_rather_than_guessed(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guard that invented a reading when it could not take one is not a guard."""
        install_reader(
            monkeypatch,
            FakeReader(
                omarchy=FileNotFoundError(2, "absent", OMARCHY),
                claude=FileNotFoundError(2, "absent", CLAUDE),
            ),
        )

        with pytest.raises((OSError, LookupError, RuntimeError, ValueError)):
            take_reading(config)


class TestWhatTheReaderSaysIsRead:
    @pytest.fixture
    def reader(self, monkeypatch: pytest.MonkeyPatch) -> FakeReader:
        return install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))

    def test_the_weekly_limit_governs_and_not_the_one_beside_it(
        self, config: Config, reader: FakeReader
    ) -> None:
        """`Weekly (7-day)` is matched by LABEL, never by position.

        The payload puts a model-scoped limit first at 7% and a five-hour limit
        second at 88%. An implementation taking `limits[0]` reads 7% and would
        happily spend an account already at 43%; one taking the largest reads
        88% and would refuse.
        """
        assert take_reading(config).percent == pytest.approx(WEEKLY_PERCENT)

    def test_the_reading_is_labelled_with_the_limit_it_came_from(
        self, config: Config, reader: FakeReader
    ) -> None:
        assert take_reading(config).label == WEEKLY_LABEL

    def test_the_percent_stays_the_fraction_the_reader_reported(
        self, config: Config, reader: FakeReader
    ) -> None:
        """`ceiling` adds 0.10 to it, so a percentage scale would cap at 10.1%."""
        taken = take_reading(config)

        assert 0.0 <= taken.percent <= 1.0
        assert taken.percent == pytest.approx(0.43)

    def test_the_reading_records_when_it_was_taken(
        self, config: Config, reader: FakeReader
    ) -> None:
        taken = take_reading(config)

        assert taken.taken_at, "a reading with no time on it cannot be compared with another"
        datetime.fromisoformat(taken.taken_at)

    def test_the_order_of_the_limits_does_not_matter(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(monkeypatch, FakeReader(omarchy=payload(*reversed(LIMITS))))

        assert take_reading(config).percent == pytest.approx(WEEKLY_PERCENT)

    def test_a_lone_weekly_limit_reads_the_same(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(monkeypatch, FakeReader(omarchy=payload(LIMITS[2])))

        assert take_reading(config).percent == pytest.approx(WEEKLY_PERCENT)

    def test_a_payload_without_the_weekly_limit_is_refused(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falling back to whichever limit IS present would cap against a figure
        that ignores spend on every other model — the owner's ruling, inverted.

        BOTH readers answer without the weekly limit, because whether a reader
        that answered-but-not-usefully counts as a failure worth falling back
        from is not something the plan rules. Either way the run must refuse,
        and the refusal must name the label it could not find.
        """
        weekly_less = payload(LIMITS[0], LIMITS[1])
        install_reader(monkeypatch, FakeReader(omarchy=weekly_less, claude=weekly_less))

        with pytest.raises((LookupError, RuntimeError, ValueError)) as caught:
            take_reading(config)

        assert WEEKLY_LABEL in str(caught.value), str(caught.value)

    def test_a_label_that_merely_contains_the_weekly_one_is_not_it(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(
            monkeypatch,
            FakeReader(
                omarchy=payload(
                    {"label": f"{WEEKLY_LABEL} — Opus", "percent": 0.05, "resetsAt": RESETS_AT},
                    dict(LIMITS[2]),
                )
            ),
        )

        assert take_reading(config).percent == pytest.approx(WEEKLY_PERCENT)


class TestTheGuardEndToEnd:
    """One reading, one ceiling, one decision — the shape the command drives."""

    def test_a_batch_that_stays_under_the_line_is_allowed_all_the_way(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))
        baseline = take_reading(config)
        line = ceiling(baseline, config)

        for percent in (0.43, 0.46, 0.49, 0.52):
            assert allowed(reading(percent), line), percent

    def test_the_first_reading_over_the_line_is_where_it_stops(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_reader(monkeypatch, FakeReader(omarchy=payload(*LIMITS)))
        line = ceiling(take_reading(config), config)

        with pytest.raises(CapExceeded) as caught:
            check(reading(0.54), line)

        assert caught.value.reading.percent == pytest.approx(0.54)
