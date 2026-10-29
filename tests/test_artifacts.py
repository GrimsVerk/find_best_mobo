"""Absence and emptiness are different facts (OD-9, R1005).

`artifacts.py` exists to encode one sentence, and this module is what pins it:
an EMPTY artifact is a real value and passes; an ABSENT one is an error that
names the stage producing it. BL-7 measured what happens without the
distinction — `estimate` reading a missing index as a zero denominator, which is
indistinguishable at the console from a real empty corpus.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

from find_best_mobo.artifacts import MissingArtifact, require_directory, require_file


class TestRequireFile:
    def test_an_existing_file_is_returned(self, tmp_path: Path) -> None:
        path = tmp_path / "index.jsonl"
        path.write_text("{}\n", encoding="utf-8")

        assert require_file(path, "index", "index") == path

    def test_an_empty_file_passes(self, tmp_path: Path) -> None:
        """Emptiness is a value: a channel with nothing in range writes an empty index."""
        path = tmp_path / "index.jsonl"
        path.write_text("", encoding="utf-8")

        assert require_file(path, "index", "index") == path

    def test_an_absent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MissingArtifact):
            require_file(tmp_path / "index.jsonl", "index", "index")

    def test_a_directory_where_a_file_is_expected_counts_as_absent(self, tmp_path: Path) -> None:
        """One remedy, so one message: a second class for a state nobody has hit is speculative."""
        path = tmp_path / "index.jsonl"
        path.mkdir()

        with pytest.raises(MissingArtifact):
            require_file(path, "index", "index")


class TestRequireDirectory:
    def test_an_empty_directory_passes(self, tmp_path: Path) -> None:
        """The sentence this module exists to encode.

        `fetch` that ran and cached nothing leaves an empty cache. That is a run
        that happened, and every stage downstream must be able to tell it from a
        run that did not.
        """
        path = tmp_path / "transcripts"
        path.mkdir()

        assert require_directory(path, "cached transcripts", "fetch") == path

    def test_an_absent_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MissingArtifact):
            require_directory(tmp_path / "transcripts", "cached transcripts", "fetch")

    def test_a_file_where_a_directory_is_expected_counts_as_absent(self, tmp_path: Path) -> None:
        path = tmp_path / "transcripts"
        path.write_text("", encoding="utf-8")

        with pytest.raises(MissingArtifact):
            require_directory(path, "cached transcripts", "fetch")


class TestTheRaisedError:
    """The subclass exists so that no existing handler has to change."""

    def test_it_is_a_file_not_found_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            require_file(tmp_path / "index.jsonl", "index", "index")

    def test_it_carries_what_a_file_not_found_error_carries(self, tmp_path: Path) -> None:
        """`.filename` and `.errno` are what existing `except` blocks already read."""
        path = tmp_path / "index.jsonl"

        with pytest.raises(MissingArtifact) as info:
            require_file(path, "index", "index")

        assert info.value.filename == str(path)
        assert info.value.errno == errno.ENOENT

    def test_the_message_names_the_artifact_and_its_producing_command(self, tmp_path: Path) -> None:
        """R1005: naming the absent artifact and the stage that produces it."""
        path = tmp_path / "transcripts"

        with pytest.raises(MissingArtifact) as info:
            require_directory(path, "cached transcripts", "fetch")

        message = info.value.message()
        assert str(path) in message
        assert "cached transcripts" in message
        assert "find-best-mobo fetch" in message
