"""Tests for Stage B slice 1's claim schema — the file is data until it passes.

Written blind from `docs/plans/oracle/stage-b-extraction.md` (slice 1) and the
shared contract while the implementation is authored in parallel, so failing
imports are the expected state until assembly.

Nothing here is faked and nothing here touches the disk: `parse_claims` takes
the file's TEXT and a path used only for the message, so every test in this file
is pure. The store's side of the slice lives in `tests/test_claimstore.py`.

Two conventions this file assumes, both taken from the exception classes the
repository already has (`ledger.HaltTriggered`, `artifacts.MissingArtifact`):
an exception's constructor parameters are its attributes, so `InvalidClaims`
carries `.path` and `.faults`; and the JSON keys a claims file uses are the
field names of the `Claim` dataclass the plan declares.
"""

# ruff: noqa: I001
# Import sorting is switched off for this file on purpose. The slice-1 modules
# below do not exist yet, so the isort rule classifies them as third-party and
# would demand a different grouping from the one it demands once they do — the
# block is written in its post-assembly order, which is the stable one.
from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from find_best_mobo.claims import (
    CATEGORIES,
    POLARITIES,
    SUBJECTS,
    Claim,
    InvalidClaims,
    parse_claims,
)

# The path is a label in this slice, not a file: `parse_claims` is handed the
# text. Deliberately a path that does not exist, so a test fails loudly if the
# schema ever starts reading from disk behind the caller's back.
CLAIMS_PATH = Path("/nonexistent/claims/batch-1/bundle-0007.json")

# One row exactly as the extraction agent is meant to write it. Every fault
# fixture below is this row with one thing wrong, so a failure names the defect
# rather than the fixture.
VALID_ROW: dict[str, object] = {
    "board": "ASRock X670E Taichi",
    "video_id": "dQw4w9WgXcQ",
    "video_title": "X670E VRM breakdown — which boards are actually overbuilt",
    "timestamp_seconds": 62.25,
    "snippet": "the Taichi's VRM is genuinely overbuilt for anything you can socket",
    "category": "tested",
    "subject": "vrm_capacity",
    "polarity": "positive",
}

# The eight fields the FILE carries. `batch` is the ninth field of `Claim` and
# is not one of them: `parse_claims` takes the batch as an argument, because the
# ingest step is what knows which batch it is ingesting.
FILE_FIELDS: tuple[str, ...] = tuple(VALID_ROW)

# Every field of §9's Claim, which is what a parsed claim must carry.
CLAIM_FIELDS: frozenset[str] = frozenset(FILE_FIELDS) | {"batch"}

DROP = object()
"""Sentinel for `row(field=DROP)` — leave the key out of the row entirely."""


def row(**overrides: object) -> dict[str, object]:
    """The valid row with `overrides` applied; `DROP` removes a key."""
    merged = dict(VALID_ROW) | overrides
    return {key: value for key, value in merged.items() if value is not DROP}


def render(*rows: object) -> str:
    """The rows as a claims file's text."""
    return json.dumps(list(rows), indent=2)


def parse(*rows: object, batch: int = 1) -> tuple[Claim, ...]:
    return parse_claims(render(*rows), CLAIMS_PATH, batch)


def refusal(*rows: object, batch: int = 1) -> InvalidClaims:
    """Parse rows that must be refused, and hand back the refusal."""
    with pytest.raises(InvalidClaims) as caught:
        parse(*rows, batch=batch)
    return caught.value


def refusal_text(*rows: object, batch: int = 1) -> str:
    """The refusal's message, lowercased for substring assertions."""
    return refusal(*rows, batch=batch).message().lower()


class TestVocabularies:
    """The three declared tuples, pinned exactly. A model may write only these."""

    def test_categories_are_the_four_from_the_design(self) -> None:
        assert CATEGORIES == ("tested", "reasoned", "secondhand", "warning")

    def test_subjects_are_the_five_from_the_design(self) -> None:
        assert SUBJECTS == (
            "vrm_capacity",
            "voltage_firmware_safety",
            "memory",
            "features",
            "value",
        )

    def test_polarities_are_the_three_from_the_design(self) -> None:
        assert POLARITIES == ("positive", "negative", "mixed")

    @pytest.mark.parametrize("vocabulary", [CATEGORIES, SUBJECTS, POLARITIES])
    def test_each_vocabulary_is_a_tuple_of_strings(self, vocabulary: tuple[str, ...]) -> None:
        assert isinstance(vocabulary, tuple)
        assert all(isinstance(term, str) for term in vocabulary)


class TestClaimEntity:
    """§9's Claim: nine fields, frozen, comparable."""

    def test_carries_every_field_of_the_design_entity_and_no_others(self) -> None:
        fields = {field.name for field in dataclasses.fields(Claim)}

        assert fields == CLAIM_FIELDS

    def test_is_frozen(self) -> None:
        claim = parse(row())[0]

        with pytest.raises(FrozenInstanceError):
            claim.board = "Gigabyte B650 Aorus Elite"  # type: ignore[misc]

    def test_two_claims_from_the_same_row_are_equal_and_hashable(self) -> None:
        first = parse(row())[0]
        second = parse(row())[0]

        assert first == second
        assert len({first, second}) == 1, "a claim must be usable in a set"


class TestValidFile:
    def test_a_well_formed_file_parses_to_a_tuple_of_claims(self) -> None:
        claims = parse(row(), row(board="MSI B650 Tomahawk"))

        assert isinstance(claims, tuple)
        assert len(claims) == 2
        assert all(isinstance(claim, Claim) for claim in claims)

    def test_every_field_is_carried_through_unchanged(self) -> None:
        claim = parse(row())[0]

        assert claim.board == VALID_ROW["board"]
        assert claim.video_id == VALID_ROW["video_id"]
        assert claim.video_title == VALID_ROW["video_title"]
        assert claim.timestamp_seconds == pytest.approx(62.25)
        assert claim.snippet == VALID_ROW["snippet"]
        assert claim.category == "tested"
        assert claim.subject == "vrm_capacity"
        assert claim.polarity == "positive"

    def test_rows_keep_the_order_they_were_written_in(self) -> None:
        claims = parse(
            row(board="third", timestamp_seconds=300.0),
            row(board="first", timestamp_seconds=10.0),
            row(board="second", timestamp_seconds=100.0),
        )

        assert [claim.board for claim in claims] == ["third", "first", "second"]

    def test_the_batch_comes_from_the_argument(self) -> None:
        # The file never names its own batch: the ingest step knows which batch
        # it is ingesting, and R10's tag has to be trustworthy.
        claims = parse(row(), row(board="MSI B650 Tomahawk"), batch=7)

        assert {claim.batch for claim in claims} == {7}

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_declared_category_is_accepted(self, category: str) -> None:
        assert parse(row(category=category))[0].category == category

    @pytest.mark.parametrize("subject", SUBJECTS)
    def test_every_declared_subject_is_accepted(self, subject: str) -> None:
        assert parse(row(subject=subject))[0].subject == subject

    @pytest.mark.parametrize("polarity", POLARITIES)
    def test_every_declared_polarity_is_accepted(self, polarity: str) -> None:
        assert parse(row(polarity=polarity))[0].polarity == polarity

    def test_a_timestamp_of_zero_is_a_real_timestamp(self) -> None:
        # A claim made in the first second of a video, not a missing value.
        assert parse(row(timestamp_seconds=0))[0].timestamp_seconds == pytest.approx(0.0)

    def test_a_whole_number_timestamp_is_accepted(self) -> None:
        # JSON writes 120 for a round number; that is not a type error.
        assert parse(row(timestamp_seconds=120))[0].timestamp_seconds == pytest.approx(120.0)

    def test_a_long_video_timestamp_survives_intact(self) -> None:
        assert parse(row(timestamp_seconds=7384.5))[0].timestamp_seconds == pytest.approx(7384.5)

    def test_snippet_text_is_preserved_verbatim(self) -> None:
        # R14 quotes these back at the buyer, so nothing may be normalized here.
        snippet = '  he said "it\'s fine" — 12+2+1, 110 A stages\n'
        assert parse(row(snippet=snippet))[0].snippet == snippet

    def test_parsing_reads_nothing_from_disk(self) -> None:
        # CLAIMS_PATH does not exist and never has to.
        assert not CLAIMS_PATH.exists()
        assert parse(row())


class TestRequiredFields:
    """Every field of §9's Claim is required. There are no optional ones."""

    @pytest.mark.parametrize("field", FILE_FIELDS)
    def test_a_missing_field_is_a_fault(self, field: str) -> None:
        error = refusal(row(**{field: DROP}))

        assert len(error.faults) == 1
        assert field in error.message()

    @pytest.mark.parametrize("field", FILE_FIELDS)
    def test_a_null_where_a_value_belongs_is_a_fault(self, field: str) -> None:
        # The commonest shape of a model not finding something: the key is
        # there, and it answers with nothing.
        error = refusal(row(**{field: None}))

        assert len(error.faults) == 1
        assert field in error.message()

    def test_an_empty_object_faults_on_every_missing_field(self) -> None:
        # Deliberately does not pin a fault COUNT: whether eight missing fields
        # are eight faults or one fault listing eight names is the
        # implementation's call. Naming all eight is not.
        error = refusal({})

        assert error.faults
        message = error.message()
        for field in FILE_FIELDS:
            assert field in message


class TestFieldTypes:
    def test_a_timestamp_written_as_a_string_is_a_fault(self) -> None:
        # Not coerced: "62.25" from a model is a model ignoring the contract,
        # and "1:02" would coerce to nothing at all.
        message = refusal_text(row(timestamp_seconds="62.25"))

        assert "timestamp_seconds" in message

    def test_a_clock_style_timestamp_is_a_fault(self) -> None:
        assert "timestamp_seconds" in refusal_text(row(timestamp_seconds="1:02"))

    @pytest.mark.parametrize("field", ["board", "video_id", "video_title", "snippet"])
    def test_a_number_where_a_string_belongs_is_a_fault(self, field: str) -> None:
        error = refusal(row(**{field: 12}))

        assert len(error.faults) == 1
        assert field in error.message()

    @pytest.mark.parametrize("field", ["category", "subject", "polarity"])
    def test_a_list_where_a_vocabulary_term_belongs_is_a_fault(self, field: str) -> None:
        # A model hedging between two answers writes both.
        error = refusal(row(**{field: ["tested", "reasoned"]}))

        assert error.faults
        assert field in error.message()

    def test_an_empty_snippet_is_a_fault(self) -> None:
        # R14: the snippet is what lets a buyer verify the claim. An empty one
        # is a claim with no evidence behind it.
        assert "snippet" in refusal_text(row(snippet=""))

    def test_an_empty_board_name_is_a_fault(self) -> None:
        # A claim about no board is not a claim.
        assert "board" in refusal_text(row(board=""))


class TestVocabularyFaults:
    def test_an_invented_category_is_a_fault(self) -> None:
        message = refusal_text(row(category="opinion"))

        assert "category" in message
        assert "opinion" in message

    def test_a_capitalized_category_is_a_fault(self) -> None:
        # Case-sensitive on purpose: the vocabulary is a fixed set of tokens,
        # and a model that title-cases them is a model paraphrasing the prompt.
        message = refusal_text(row(category="Tested"))

        assert "category" in message
        assert "tested" in message

    @pytest.mark.parametrize("category", ["TESTED", " tested", "tested "])
    def test_a_category_that_is_only_nearly_right_is_a_fault(self, category: str) -> None:
        assert refusal(row(category=category)).faults

    def test_an_invented_subject_is_a_fault(self) -> None:
        message = refusal_text(row(subject="pcie_lanes"))

        assert "subject" in message
        assert "pcie_lanes" in message

    def test_a_prose_subject_is_a_fault(self) -> None:
        # The design writes the subjects as prose ("VRM capacity"); the schema
        # is the tuple, and the prose form is not in it.
        assert refusal(row(subject="VRM capacity")).faults

    def test_an_invented_polarity_is_a_fault(self) -> None:
        message = refusal_text(row(polarity="neutral"))

        assert "polarity" in message
        assert "neutral" in message

    def test_an_empty_vocabulary_value_is_a_fault(self) -> None:
        assert refusal(row(polarity="")).faults


class TestUnknownKeys:
    """A model that invents a field misunderstood the contract."""

    def test_an_extra_key_is_a_fault_rather_than_something_ignored(self) -> None:
        message = refusal_text(row(confidence=0.8))

        assert "confidence" in message

    def test_every_extra_key_is_named(self) -> None:
        message = refusal_text(row(confidence=0.8, reasoning="he sounded sure", source_url="x"))

        for key in ("confidence", "reasoning", "source_url"):
            assert key in message

    def test_an_extra_key_faults_even_when_every_required_field_is_right(self) -> None:
        error = refusal(row(notes=""))

        assert error.faults
        assert "notes" in error.message()

    def test_a_misspelled_field_faults_twice_over(self) -> None:
        # `video_titl` is both an unknown key and a missing required field, and
        # a message naming only one of them tells the reader half the story.
        message = refusal_text(row(video_title=DROP, video_titl="X670E VRM breakdown"))

        assert "video_titl" in message
        assert "video_title" in message


class TestFileShape:
    def test_a_file_that_is_not_json_is_refused(self) -> None:
        with pytest.raises(InvalidClaims):
            parse_claims("Here are the claims I found:\n\n- the Taichi is good\n", CLAIMS_PATH, 1)

    def test_a_file_wrapped_in_a_markdown_fence_is_refused(self) -> None:
        # The commonest way a model breaks a JSON contract.
        fenced = f"```json\n{render(row())}\n```\n"

        with pytest.raises(InvalidClaims):
            parse_claims(fenced, CLAIMS_PATH, 1)

    def test_an_empty_file_is_refused(self) -> None:
        with pytest.raises(InvalidClaims):
            parse_claims("", CLAIMS_PATH, 1)

    def test_a_top_level_object_is_refused(self) -> None:
        # `{"claims": [...]}` is a different contract from the one asked for.
        with pytest.raises(InvalidClaims):
            parse_claims(json.dumps({"claims": [VALID_ROW]}), CLAIMS_PATH, 1)

    def test_a_bare_object_that_is_one_claim_is_refused(self) -> None:
        with pytest.raises(InvalidClaims):
            parse_claims(json.dumps(VALID_ROW), CLAIMS_PATH, 1)

    def test_a_null_file_is_refused(self) -> None:
        with pytest.raises(InvalidClaims):
            parse_claims("null", CLAIMS_PATH, 1)

    @pytest.mark.parametrize("element", ["a claim", 7, None, ["board", "x"]])
    def test_a_list_element_that_is_not_an_object_is_refused(self, element: object) -> None:
        assert refusal(row(), element).faults


class TestEveryFaultIsReported:
    """One round trip per file, not one per fault — each round trip is paid for."""

    def test_four_bad_rows_produce_four_faults(self) -> None:
        error = refusal(
            row(board=""),
            row(category="Tested"),
            row(timestamp_seconds="62.25"),
            row(confidence=0.9),
        )

        assert len(error.faults) == 4

    def test_one_message_carries_all_four(self) -> None:
        message = refusal_text(
            row(board=""),
            row(category="opinion"),
            row(timestamp_seconds="62.25"),
            row(confidence=0.9),
        ).lower()

        for expected in ("board", "opinion", "timestamp_seconds", "confidence"):
            assert expected in message

    def test_a_row_with_several_defects_reports_all_of_them(self) -> None:
        error = refusal(row(snippet=DROP, category="Warning", polarity=None))

        assert error.faults
        message = error.message()
        for expected in ("snippet", "category", "polarity"):
            assert expected in message

    def test_the_same_fault_in_two_rows_is_counted_twice(self) -> None:
        # Faults are per row, not a deduplicated set of complaints: the reader
        # has to know how much of the file is wrong.
        error = refusal(row(snippet=DROP), row(snippet=DROP))

        assert len(error.faults) == 2

    def test_a_good_row_beside_a_bad_one_still_refuses_the_file(self) -> None:
        # Nothing partial: R9's "never silently dropped" cuts both ways.
        error = refusal(row(), row(polarity="neutral"), row(board="MSI B650 Tomahawk"))

        assert len(error.faults) == 1

    def test_every_fault_is_a_string(self) -> None:
        error = refusal(row(board=""), row(category="opinion"))

        assert all(isinstance(fault, str) for fault in error.faults)
        assert all(fault.strip() for fault in error.faults)


class TestDuplicateClaims:
    def test_the_same_claim_twice_in_one_file_is_a_fault(self) -> None:
        # A model looping on itself writes the same row twice, and a store that
        # accepts it counts one statement as two pieces of evidence.
        error = refusal(row(), row())

        assert error.faults

    def test_rows_differing_in_one_field_are_not_duplicates(self) -> None:
        claims = parse(row(), row(polarity="negative"))

        assert len(claims) == 2

    def test_two_claims_about_one_board_at_different_timestamps_are_fine(self) -> None:
        claims = parse(row(timestamp_seconds=62.25), row(timestamp_seconds=400.0))

        assert len(claims) == 2


class TestInvalidClaims:
    def test_is_a_value_error(self) -> None:
        error = InvalidClaims(CLAIMS_PATH, ["board: empty"])

        assert isinstance(error, ValueError)

    def test_carries_the_path_and_the_faults_it_was_built_with(self) -> None:
        faults = ["row 0: board is empty", "row 2: unknown key 'confidence'"]

        error = InvalidClaims(CLAIMS_PATH, faults)

        assert error.path == CLAIMS_PATH
        assert list(error.faults) == faults

    def test_the_message_names_the_file_and_every_fault(self) -> None:
        faults = ["row 0: board is empty", "row 2: unknown key 'confidence'"]

        message = InvalidClaims(CLAIMS_PATH, faults).message()

        assert str(CLAIMS_PATH) in message
        for fault in faults:
            assert fault in message

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(InvalidClaims) as caught:
            raise InvalidClaims(CLAIMS_PATH, ["row 0: board is empty"])

        assert caught.value.path == CLAIMS_PATH

    def test_a_real_refusal_names_the_file_it_refused(self) -> None:
        error = refusal(row(board=""))

        assert error.path == CLAIMS_PATH
        assert str(CLAIMS_PATH) in error.message()


class TestNothingReachesAModel:
    """Slice 1 is fully exercisable offline: that is what makes it testable."""

    def test_neither_module_imports_a_network_or_model_boundary(self) -> None:
        code = (
            "import sys\n"
            "import find_best_mobo.claims\n"
            "import find_best_mobo.claimstore\n"
            "print('\\n'.join(sorted(n for n in sys.modules if n.startswith('find_best_mobo'))))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        loaded = set(result.stdout.split())

        assert {"find_best_mobo.claims", "find_best_mobo.claimstore"} <= loaded
        for forbidden in ("find_best_mobo.extract", "find_best_mobo.ytdlp", "find_best_mobo.spend"):
            assert forbidden not in loaded, f"slice 1 must not import {forbidden}"

    def test_the_modules_hold_no_network_machinery(self) -> None:
        import find_best_mobo.claims as claims_module
        import find_best_mobo.claimstore as claimstore_module

        for module in (claims_module, claimstore_module):
            for name in ("socket", "urllib", "requests", "httpx", "subprocess"):
                assert not hasattr(module, name), f"{module.__name__} imported {name}"
