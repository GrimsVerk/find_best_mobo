"""The `ingest` command — the stage that stores a claims file, or refuses it.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 1) while the
implementation is authored in parallel, so failing imports are the expected
state until assembly. Nothing here is faked: ingest is Python over files, so
every test runs the real command against a real `tmp_path`.

This file is the slice's CLI deliverable under test. `tests/test_claims.py` and
`tests/test_claimstore.py` pin the schema and the store as units; what nothing
else would notice is a defect in the wiring between them — a wrong exit code, a
refusal that appends anyway, a message naming only the first of four faults, a
missing file arriving as a traceback. Those are what the cases below are for,
which is why every refusal here asserts on the STORE'S CONTENTS as well as on
the exit code: a refusal that printed correctly and appended anyway is the
failure R10 and R27 exist to prevent, and it reads identically at the console.

**Six behaviours, one per class.** A valid file is stored (exit 0, claims in the
store, the count and the batch reported). An invalid one is refused with EVERY
fault and nothing appended. A batch already stored is refused and the store's
bytes are untouched. A missing file refuses in R1005's shape rather than
raising. A valid file holding no claims is a real value, not a failure. And an
undeclared flag is rejected by name (R1006) — `find-best-mobo ingest
--nonsense` must say `--nonsense`, which an implementation whose arguments are
`required=True` cannot do, because argparse reports missing required arguments
before unrecognised ones.

**The claims file's serialisation is not fixed by the plan** — the Signatures
block gives `parse_claims(raw, path, batch)` and stops there. So rather than
guess a dialect and test the guess, `claims_dialect()` below discovers which one
the schema accepts by offering it candidates and keeping the one that parses.
The command's behaviour is what is asserted; the encoding it reads is the
schema's business and `tests/test_claims.py`'s.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-1 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from find_best_mobo.cli import main
from find_best_mobo.claims import Claim, parse_claims
from find_best_mobo.claimstore import append_claims, batches_stored, read_claims, store_path
from find_best_mobo.commands.ingest import parse_args, run
from find_best_mobo.config import Config

Row = dict[str, Any]


def make_config(data_dir: Path) -> Config:
    """The shipped defaults over a temporary corpus; ingest reads no lever of its own."""
    return Config(
        channel_url="https://www.youtube.com/@ActuallyHardcoreOverclocking",
        start_date=date(2023, 1, 1),
        data_dir=data_dir,
        shorts_max_seconds=120,
        mention_threshold=3,
        window_before_seconds=120,
        window_after_seconds=300,
        per_video_excerpt_cap=10,
        bundle_token_cap=24000,
        calibration_batch_size=12,
        batch_count=3,
        chars_per_token=4.0,
        consecutive_fetch_error_limit=3,
        fetch_error_rate_limit=0.03,
        missing_caption_rate_limit=0.05,
    )


def make_row(
    board: str,
    *,
    video_id: str = "abc123XYZ_1",
    video_title: str = "The B650 boards worth buying",
    timestamp_seconds: float = 1234.5,
    snippet: str = "the VRM on this one is genuinely overbuilt for the price",
    category: str = "tested",
    subject: str = "vrm_capacity",
    polarity: str = "positive",
) -> Row:
    """One claim as it appears in a claims file: every field of §9's Claim but `batch`.

    `batch` is absent because `parse_claims` is handed it — the batch tags the
    claim at ingest rather than being something the extracting agent asserts
    about itself. A dialect that wants it in the file is still discovered below.
    """
    return {
        "board": board,
        "video_id": video_id,
        "video_title": video_title,
        "timestamp_seconds": timestamp_seconds,
        "snippet": snippet,
        "category": category,
        "subject": subject,
        "polarity": polarity,
    }


THREE_CLAIMS: tuple[Row, ...] = (
    make_row("MSI MAG B650 Tomahawk WiFi"),
    make_row(
        "ASUS ROG Crosshair X670E Hero",
        category="warning",
        subject="voltage_firmware_safety",
        polarity="negative",
        snippet="that board pushed way too much SOC voltage before the fix",
    ),
    make_row(
        "Gigabyte B650 AORUS Elite AX",
        category="reasoned",
        subject="value",
        polarity="mixed",
        snippet="for the money it is fine, but nothing about it is special",
    ),
)


# --- the claims file's dialect, discovered rather than assumed -----------------


def _as_json_array(rows: Sequence[Row], batch: int) -> str:
    return json.dumps(list(rows), indent=2) + "\n"


def _as_jsonl(rows: Sequence[Row], batch: int) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _as_wrapped(rows: Sequence[Row], batch: int) -> str:
    return json.dumps({"claims": list(rows)}, indent=2) + "\n"


def _tagged(rows: Sequence[Row], batch: int) -> list[Row]:
    return [{**row, "batch": batch} for row in rows]


def _timestamp_key(rows: Sequence[Row]) -> list[Row]:
    renamed = []
    for row in rows:
        copy = dict(row)
        copy["timestamp"] = copy.pop("timestamp_seconds")
        renamed.append(copy)
    return renamed


Dialect = Callable[[Sequence[Row], int], str]

# Ordered candidates. Each renders the canonical rows above into one file body;
# the first one `parse_claims` accepts is the one every test then writes.
CANDIDATE_DIALECTS: tuple[tuple[str, Dialect], ...] = (
    ("json array", _as_json_array),
    ("jsonl", _as_jsonl),
    ("wrapped in a claims key", _as_wrapped),
    (
        "json array, batch in the file",
        lambda rows, batch: _as_json_array(_tagged(rows, batch), batch),
    ),
    ("jsonl, batch in the file", lambda rows, batch: _as_jsonl(_tagged(rows, batch), batch)),
    ("wrapped, batch in the file", lambda rows, batch: _as_wrapped(_tagged(rows, batch), batch)),
    ("json array, `timestamp`", lambda rows, batch: _as_json_array(_timestamp_key(rows), batch)),
    ("jsonl, `timestamp`", lambda rows, batch: _as_jsonl(_timestamp_key(rows), batch)),
    ("wrapped, `timestamp`", lambda rows, batch: _as_wrapped(_timestamp_key(rows), batch)),
)

_RESOLVED: list[tuple[str, Dialect]] = []


def claims_dialect() -> Dialect:
    """The serialisation `parse_claims` accepts, found by offering it candidates.

    The plan fixes the schema's FIELDS and its vocabularies and leaves the
    encoding to the implementation, so a test file that hard-coded one would be
    testing its own guess. The probe is pure — `parse_claims` takes a string —
    so it touches no disk and runs once for the module.
    """
    if _RESOLVED:
        return _RESOLVED[0][1]
    probe = (make_row("MSI MAG B650 Tomahawk WiFi"), make_row("ASUS ROG Crosshair X670E Hero"))
    tried = []
    for name, render in CANDIDATE_DIALECTS:
        try:
            parsed = parse_claims(render(probe, 3), Path("probe-claims.json"), 3)
        except Exception as error:  # noqa: BLE001 - a rejected candidate is the normal case
            tried.append(f"{name}: {type(error).__name__}")
            continue
        if len(parsed) == 2 and all(claim.batch == 3 for claim in parsed):
            _RESOLVED.append((name, render))
            return render
        tried.append(f"{name}: parsed {len(parsed)} claims")
    raise AssertionError(
        "no candidate claims-file serialisation was accepted by parse_claims; "
        "the tests cannot write a valid file. Tried:\n  " + "\n  ".join(tried)
    )


def write_claims_file(path: Path, rows: Sequence[Row], batch: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(claims_dialect()(rows, batch), encoding="utf-8")
    return path


# --- running the command, and reading what it left behind ---------------------


def run_ingest(config: Config, path: Path, batch: int) -> int:
    """The command as the CLI invokes it: its own parser, then its own `run`.

    Going through `parse_args` rather than building a `Namespace` by hand is
    deliberate — it is what makes these tests independent of what the command
    calls its two arguments, and it is the path a real invocation takes.
    """
    return run(config, parse_args([str(path), "--batch", str(batch)]))


def store_body(config: Config) -> bytes:
    """The store's bytes, with an absent store reading as an empty one.

    Absence and emptiness are the same fact HERE, unlike upstream (R1005): both
    say nothing has been appended, and which one a refusal leaves behind is the
    implementation's business.
    """
    path = store_path(config)
    return path.read_bytes() if path.exists() else b""


def stored_claims(config: Config) -> tuple[Claim, ...]:
    return tuple(read_claims(config))


def spoken(output: str, config: Config, *paths: Path) -> str:
    """The output with every filesystem path blanked out.

    A count or a batch number asserted against raw output would be satisfied by
    a digit inside `/tmp/pytest-of-.../pytest-7/`, which is how a test that
    looks like it checks the reported numbers checks nothing at all.
    """
    elided = output
    candidates = [str(config.data_dir), str(store_path(config))]
    for path in paths:
        candidates.extend([str(path), str(path.parent)])
    for text in sorted(candidates, key=len, reverse=True):
        elided = elided.replace(text, "<path>")
    return elided


def says_number(output: str, number: int) -> bool:
    return re.search(rf"(?<!\d){number}(?!\d)", output) is not None


def out_and_err(capsys: pytest.CaptureFixture[str]) -> str:
    """Both streams. Which one a refusal chooses is not this slice's contract."""
    captured = capsys.readouterr()
    return captured.out + captured.err


class TestAValidFileIsStored:
    def test_the_claims_land_in_the_store(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The success path: three claims in, exit 0, three claims in the store."""
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        assert run_ingest(config, path, 7) == 0
        capsys.readouterr()

        assert [claim.board for claim in stored_claims(config)] == [
            row["board"] for row in THREE_CLAIMS
        ]

    def test_every_stored_claim_carries_the_batch_it_was_ingested_under(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R10: the store is tagged by batch, and the tag comes from the flag."""
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        assert run_ingest(config, path, 7) == 0
        capsys.readouterr()

        assert {claim.batch for claim in stored_claims(config)} == {7}
        assert batches_stored(config) == frozenset({7})

    def test_the_fields_survive_the_round_trip(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A claim is evidence: the snippet and its timestamp are what makes it checkable (R14)."""
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        assert run_ingest(config, path, 7) == 0
        capsys.readouterr()

        warning = next(claim for claim in stored_claims(config) if claim.category == "warning")
        assert warning.board == "ASUS ROG Crosshair X670E Hero"
        assert warning.video_id == "abc123XYZ_1"
        assert warning.video_title == "The B650 boards worth buying"
        assert warning.subject == "voltage_firmware_safety"
        assert warning.polarity == "negative"
        assert warning.timestamp_seconds == pytest.approx(1234.5)
        assert "SOC voltage" in warning.snippet

    def test_it_reports_how_many_claims_and_which_batch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Both quantities, because the operator is deciding whether to run the next batch.

        The paths are blanked before the numbers are looked for, so a digit in
        the temporary directory cannot satisfy either assertion.
        """
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        assert run_ingest(config, path, 7) == 0

        said = spoken(out_and_err(capsys), config, path)
        assert says_number(said, 3), f"the claim count is not reported: {said!r}"
        assert says_number(said, 7), f"the batch is not reported: {said!r}"
        assert "batch" in said.lower(), f"the batch is not named as one: {said!r}"

    def test_nothing_is_appended_twice(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Three claims in the file, three rows in the store — never six.

        A store written once and then appended again reads as a doubled corpus
        downstream, and no console line would say so.
        """
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        assert run_ingest(config, path, 7) == 0
        capsys.readouterr()

        assert len(stored_claims(config)) == 3
        assert len(store_body(config).splitlines()) == 3

    def test_a_second_batch_appends_rather_than_replacing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """R10's whole point: a stop between batches loses no work.

        The refusal is per BATCH, not per store — batch 8 lands on top of batch 7
        and both are readable afterwards.
        """
        config = make_config(tmp_path / "data")
        first = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)
        second = write_claims_file(tmp_path / "claims" / "bundle-002.json", THREE_CLAIMS[:1], 8)

        assert run_ingest(config, first, 7) == 0
        assert run_ingest(config, second, 8) == 0
        capsys.readouterr()

        assert len(stored_claims(config)) == 4
        assert batches_stored(config) == frozenset({7, 8})

    def test_it_runs_through_the_cli_dispatcher(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`find-best-mobo ingest <file> --batch 7`, end to end (R1006).

        The stage is only delivered if the dispatcher reaches it with both
        arguments intact — `run(config, args)` called directly would pass even
        with the command unreachable from the command line.
        """
        config = make_config(tmp_path / "data")
        config_path = tmp_path / "config.toml"
        config_path.write_text(f'data_dir = "{config.data_dir.as_posix()}"\n', encoding="utf-8")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        assert main(["ingest", str(path), "--batch", "7", "--config", str(config_path)]) == 0
        capsys.readouterr()

        assert len(stored_claims(config)) == 3


# --- an invalid file: refused, in full, with nothing appended -----------------

# Four bad rows, one fault each, every fault a different kind and every row a
# different board — so a message that reports only the first names one board and
# one bad value, and a message that reports all four names four of each.
BAD_ROWS: tuple[Row, ...] = (
    make_row("MSI MAG B650 Tomahawk WiFi", category="hearsay"),
    make_row("ASUS ROG Crosshair X670E Hero", subject="cooling"),
    make_row("Gigabyte B650 AORUS Elite AX", polarity="neutral"),
    {
        key: value
        for key, value in make_row("ASRock B650E Steel Legend WiFi").items()
        if key != "snippet"
    },
)

# Two rows that are perfectly good, deliberately mixed in among the four bad
# ones — and the first row of the file is one of them. A model that gets four
# claims wrong out of six is the realistic shape of an invalid file, and it is
# the only shape that can catch a stage which appends what parsed and refuses
# over the rest. An all-bad file has nothing to salvage, so it would pass a
# partial-append defect without noticing it.
SALVAGEABLE: tuple[Row, ...] = (
    make_row("ASRock X670E Taichi", snippet="the rails on the Taichi are the good ones"),
    make_row("Biostar B650MT", polarity="negative", snippet="do not put a 7950X on that"),
)

FOUR_BAD_ROWS: tuple[Row, ...] = (
    SALVAGEABLE[0],
    BAD_ROWS[0],
    SALVAGEABLE[1],
    BAD_ROWS[1],
    BAD_ROWS[2],
    BAD_ROWS[3],
)

# The same file with the last three bad rows repaired. Its first fault is
# identical and sits in the same place, which is what makes the two outputs
# comparable.
ONE_BAD_ROW: tuple[Row, ...] = (
    SALVAGEABLE[0],
    BAD_ROWS[0],
    SALVAGEABLE[1],
    make_row("ASUS ROG Crosshair X670E Hero"),
    make_row("Gigabyte B650 AORUS Elite AX"),
    make_row("ASRock B650E Steel Legend WiFi"),
)

# Per row: the tokens any honest report of that row's fault must contain one of —
# the offending value, the field it is in, or the board that identifies the row.
FAULT_TOKENS: tuple[tuple[str, ...], ...] = (
    ("hearsay", "MSI MAG B650 Tomahawk WiFi"),
    ("cooling", "ASUS ROG Crosshair X670E Hero"),
    ("neutral", "Gigabyte B650 AORUS Elite AX"),
    ("snippet", "ASRock B650E Steel Legend WiFi"),
)


class TestAnInvalidFileIsRefused:
    def test_it_returns_one(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, path, 7) == 1
        assert out_and_err(capsys).strip() != "", "a refusal must say something"

    def test_nothing_is_appended(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """The assertion that matters most. An invalid file must cost the store nothing.

        Appending the rows that happened to parse and refusing over the rest
        would leave the store holding half a bundle's evidence with nothing
        recording which half — the partial append the plan rules out, and the
        one defect a correct-looking console line would hide completely.
        """
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, path, 7) == 1
        capsys.readouterr()

        assert store_body(config) == b""
        assert stored_claims(config) == ()

    def test_the_batch_stays_unconsumed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ "The bundle stays unconsumed" made observable: the retry is still allowed.

        A refusal that recorded the batch — or appended one good row under it —
        would make the corrected file's ingest a duplicate, and the twelve
        bundles already paid for would have nowhere to land.
        """
        config = make_config(tmp_path / "data")
        bad = write_claims_file(tmp_path / "claims" / "bundle-001.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, bad, 7) == 1
        good = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)
        assert run_ingest(config, good, 7) == 0
        capsys.readouterr()

        assert len(stored_claims(config)) == 3
        assert batches_stored(config) == frozenset({7})

    def test_every_fault_is_named_not_only_the_first(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Four bad rows produce four faults in one message.

        Reporting one at a time turns a malformed batch into four round trips,
        and every round trip is paid for — which is why this is a property of
        the message rather than of the exception alone.
        """
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, path, 7) == 1

        said = out_and_err(capsys)
        for number, tokens in enumerate(FAULT_TOKENS, start=1):
            assert any(token in said for token in tokens), (
                f"row {number}'s fault is not named — none of {tokens} appears in:\n{said}"
            )

    def test_four_faults_do_not_read_like_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The same test again with no dependence on wording at all.

        Both files share their first bad row, so an implementation that stops at
        the first fault prints the same message for a file with one fault and a
        file with four. It cannot, and this is what says so.
        """
        config = make_config(tmp_path / "data")
        one = write_claims_file(tmp_path / "one.json", ONE_BAD_ROW, 7)
        four = write_claims_file(tmp_path / "four.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, one, 7) == 1
        one_said = spoken(out_and_err(capsys), config, one)
        assert run_ingest(config, four, 7) == 1
        four_said = spoken(out_and_err(capsys), config, four)

        assert four_said != one_said
        assert len(four_said) > len(one_said), (
            f"four faults reported no more than one:\n{four_said}"
        )

    def test_it_says_which_file_it_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One bundle per file, and several files per batch: the name is the whole address."""
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, path, 7) == 1

        said = out_and_err(capsys)
        assert "bundle-001" in said, f"the refused file is not named: {said!r}"

    def test_a_refusal_is_not_a_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`InvalidClaims` is the stage's own exception and is handled here, not raised.

        `run` returning 1 at all is most of this: an unhandled exception never
        reaches the assertion. The output check is the other half — a stage that
        printed a formatted traceback would still return 1.
        """
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, path, 7) == 1

        assert "Traceback" not in out_and_err(capsys)

    def test_a_file_that_is_not_the_dialect_at_all_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The likeliest real failure: the agent wrote prose, or fenced its output.

        Whatever the schema's encoding turns out to be, an apology in English is
        not it — and it must arrive as a refusal rather than as whatever
        exception the parser happens to raise.
        """
        config = make_config(tmp_path / "data")
        path = tmp_path / "claims" / "bundle-001.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("I could not find any claims in this bundle, sorry!\n", encoding="utf-8")

        assert run_ingest(config, path, 7) == 1

        said = out_and_err(capsys)
        assert said.strip() != ""
        assert "Traceback" not in said
        assert store_body(config) == b""


class TestABatchAlreadyStoredIsRefused:
    """R27's mirror: no completed work is silently rewritten.

    The store is prepopulated through `append_claims` rather than by a first
    `ingest` run, so these tests fail for one reason only — the command did not
    consult `batches_stored` — instead of inheriting a failure from the success
    path above.
    """

    def prepared(self, tmp_path: Path) -> tuple[Config, Path]:
        config = make_config(tmp_path / "data")
        append_claims(
            [
                Claim(
                    board="MSI MAG B650 Tomahawk WiFi",
                    video_id="abc123XYZ_1",
                    video_title="The B650 boards worth buying",
                    timestamp_seconds=99.0,
                    snippet="already ingested, already paid for",
                    category="tested",
                    subject="vrm_capacity",
                    polarity="positive",
                    batch=7,
                )
            ],
            config,
        )
        path = write_claims_file(tmp_path / "claims" / "bundle-002.json", THREE_CLAIMS, 7)
        return config, path

    def test_it_returns_one(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config, path = self.prepared(tmp_path)

        assert run_ingest(config, path, 7) == 1
        assert out_and_err(capsys).strip() != "", "a refusal must say something"

    def test_the_store_is_byte_for_byte_what_it_was(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Not merged, not appended, not rewritten — untouched."""
        config, path = self.prepared(tmp_path)
        before = store_body(config)

        assert run_ingest(config, path, 7) == 1
        capsys.readouterr()

        assert store_body(config) == before
        assert len(stored_claims(config)) == 1

    def test_the_message_names_the_batch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The operator's next move depends on which batch is already in — so it is said."""
        config, path = self.prepared(tmp_path)

        assert run_ingest(config, path, 7) == 1

        said = spoken(out_and_err(capsys), config, path)
        assert says_number(said, 7), f"the refused batch is not named: {said!r}"
        assert "batch" in said.lower(), f"the refusal does not mention the batch: {said!r}"

    def test_a_different_batch_from_the_same_file_is_still_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal is about the batch, not about the file or the store being non-empty."""
        config, path = self.prepared(tmp_path)

        assert run_ingest(config, path, 8) == 0
        capsys.readouterr()

        assert batches_stored(config) == frozenset({7, 8})
        assert len(stored_claims(config)) == 4

    def test_a_refusal_is_not_a_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config, path = self.prepared(tmp_path)

        assert run_ingest(config, path, 7) == 1

        assert "Traceback" not in out_and_err(capsys)


class TestAMissingFileIsRefused:
    """R1005's shape, at this stage's own boundary: absence is an error, and it is named."""

    def test_it_returns_one_and_does_not_raise(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A `FileNotFoundError` escaping `run` fails this test by never reaching the assert.

        Which is the point: the refusal is what the operator sees, and every
        other stage in this pipeline gives it as an exit code and one sentence.
        """
        config = make_config(tmp_path / "data")

        assert run_ingest(config, tmp_path / "claims" / "bundle-404.json", 7) == 1
        assert out_and_err(capsys).strip() != "", "a refusal must say something"

    def test_the_message_names_the_absent_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        path = tmp_path / "claims" / "bundle-404.json"

        assert run_ingest(config, path, 7) == 1

        said = out_and_err(capsys)
        assert "bundle-404" in said, f"the absent file is not named: {said!r}"
        assert "Traceback" not in said

    def test_nothing_is_appended(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = make_config(tmp_path / "data")

        assert run_ingest(config, tmp_path / "claims" / "bundle-404.json", 7) == 1
        capsys.readouterr()

        assert store_body(config) == b""

    def test_a_directory_where_a_file_belongs_is_absence_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`artifacts.require_file` folds the wrong kind of path into the same refusal.

        The operator's remedy is identical, and a second message for a state
        nobody has hit is speculative — but a traceback here is not.
        """
        config = make_config(tmp_path / "data")
        path = tmp_path / "claims" / "bundle-001.json"
        path.mkdir(parents=True)

        assert run_ingest(config, path, 7) == 1

        said = out_and_err(capsys)
        assert "Traceback" not in said
        assert store_body(config) == b""


class TestAValidFileWithNoClaimsIsAResult:
    """A bundle in which Buildzoid named no board is an answer, not a malfunction.

    R9 sets aside a file that FAILS VALIDATION; this one passes it and holds
    nothing. Reading the two the same way would turn every quiet bundle into a
    retry of work that is already finished, and the retry costs a model call.
    """

    def test_it_returns_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-003.json", (), 7)

        assert run_ingest(config, path, 7) == 0
        capsys.readouterr()

    def test_nothing_is_appended(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Zero claims are zero rows. An empty file must not invent one."""
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-003.json", (), 7)

        assert run_ingest(config, path, 7) == 0
        capsys.readouterr()

        assert stored_claims(config) == ()
        assert store_body(config) == b""

    def test_it_says_zero_rather_than_saying_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = make_config(tmp_path / "data")
        path = write_claims_file(tmp_path / "claims" / "bundle-003.json", (), 7)

        assert run_ingest(config, path, 7) == 0

        said = spoken(out_and_err(capsys), config, path)
        assert said.strip() != "", "a run that found nothing still reports"
        assert says_number(said, 0), f"the zero is not reported: {said!r}"

    def test_it_does_not_read_like_a_refusal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The distinguishing pair: an empty result and a rejected file share an exit code
        with nothing else.

        Same batch, same store, same absence of new rows — and opposite
        verdicts. An operator who cannot tell them apart at the console will
        re-run a bundle that was already read correctly.
        """
        config = make_config(tmp_path / "data")
        empty = write_claims_file(tmp_path / "claims" / "bundle-003.json", (), 7)
        invalid = write_claims_file(tmp_path / "claims" / "bundle-004.json", FOUR_BAD_ROWS, 7)

        assert run_ingest(config, empty, 7) == 0
        empty_said = spoken(out_and_err(capsys), config, empty)
        assert run_ingest(config, invalid, 7) == 1
        invalid_said = spoken(out_and_err(capsys), config, invalid)

        assert empty_said != invalid_said
        lowered = empty_said.lower()
        for word in ("refus", "invalid", "traceback"):
            assert word not in lowered, f"an empty result reads as a refusal: {empty_said!r}"


class TestArgumentHandling:
    """R1006: every flag the stage documents is reachable, and every flag it does not is named."""

    def test_an_undeclared_flag_is_rejected_by_name(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`find-best-mobo ingest --nonsense` must say `--nonsense`.

        Argparse reports missing REQUIRED arguments before unrecognised ones, so
        an `ingest` whose path or `--batch` is declared `required=True` answers
        this invocation by complaining about the argument the operator did not
        reach yet — and the typo they actually made is never mentioned. That is
        the defect this case exists for; the rest of the suite would not see it.
        """
        with pytest.raises(SystemExit) as exit_info:
            main(["ingest", "--nonsense"])

        assert exit_info.value.code == 2
        err = capsys.readouterr().err
        assert "--nonsense" in err, f"the flag the operator typed is not named: {err!r}"
        assert "find-best-mobo ingest" in err, f"the error does not name the stage: {err!r}"

    def test_it_is_still_named_when_the_other_arguments_are_present(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The same rule with nothing else to complain about, so the reason cannot be luck."""
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        with pytest.raises(SystemExit) as exit_info:
            main(["ingest", str(path), "--batch", "7", "--nonsense"])

        assert exit_info.value.code == 2
        err = capsys.readouterr().err
        assert "--nonsense" in err
        assert "find-best-mobo ingest" in err

    def test_the_stage_parser_rejects_it_directly_too(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`parse_args` owns the error, per the dispatcher contract — `cli.py` only forwards."""
        with pytest.raises(SystemExit) as exit_info:
            parse_args(["--nonsense"])

        assert exit_info.value.code == 2
        assert "--nonsense" in capsys.readouterr().err

    def test_a_rejected_flag_appends_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Parsing happens before the configuration is loaded and before the store is opened."""
        config = make_config(tmp_path / "data")
        config_path = tmp_path / "config.toml"
        config_path.write_text(f'data_dir = "{config.data_dir.as_posix()}"\n', encoding="utf-8")
        path = write_claims_file(tmp_path / "claims" / "bundle-001.json", THREE_CLAIMS, 7)

        with pytest.raises(SystemExit):
            main(["ingest", str(path), "--batch", "7", "--nonsense", "--config", str(config_path)])
        capsys.readouterr()

        assert not config.data_dir.exists(), "a mistyped flag did work"

    def test_the_help_documents_the_batch_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A flag documented only in source is the defect R1006 was written against (BL-5)."""
        with pytest.raises(SystemExit) as exit_info:
            main(["ingest", "--help"])

        assert exit_info.value.code == 0
        out = capsys.readouterr().out
        assert out.startswith("usage: find-best-mobo ingest")
        assert "--batch" in out
