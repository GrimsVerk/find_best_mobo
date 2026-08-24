"""The dispatcher forwards what it does not recognise (OD-10, R1006).

Every test here drives the real `main` against a corpus written into
`tmp_path`, because the defect BL-5 filed lived in argument parsing and nowhere
else: calling `run` directly — as the rest of the suite does — passes with the
dispatcher completely broken, which is why `uv run find-best-mobo aliases
--check` stayed unreachable while 447 tests were green.

No network is reached: `aliases --check` walks a cached index and cached
transcripts, and the stages that would fetch are only ever invoked with a bad
flag, which fails before they run.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from find_best_mobo.cli import main
from find_best_mobo.index import Video, write_index
from find_best_mobo.transcripts import Cue, Transcript

ALIAS_TABLE = """\
[[alias]]
canonical = "X670E"
kind = "chipset"
surface_forms = ["x670e", "x 670 e"]

[[alias]]
canonical = "Taichi"
kind = "family"
surface_forms = ["taichi"]
"""


def make_corpus(tmp_path: Path) -> Path:
    """A config, an alias table, an index and one cached transcript. Returns the config path."""
    data_dir = tmp_path / "data"
    table = tmp_path / "aliases.toml"
    table.write_text(ALIAS_TABLE, encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'data_dir = "{data_dir.as_posix()}"\nalias_table_path = "{table.as_posix()}"\n',
        encoding="utf-8",
    )

    video = Video(
        video_id="vid1",
        title="Deep dive",
        upload_date=date(2023, 6, 15),
        duration_seconds=3600,
        was_live=False,
        classification="regular",
        inclusion="pending",
    )
    write_index([video], data_dir / "index.jsonl")

    transcript = Transcript(
        video_id="vid1", cues=(Cue(start_seconds=10.0, text="the x670e board"),)
    )
    cache = data_dir / "transcripts" / "vid1.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "video_id": transcript.video_id,
                "cues": [
                    {"start_seconds": c.start_seconds, "text": c.text} for c in transcript.cues
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return config_path


class TestForwarding:
    """R1006: a flag a subcommand documents is reachable from the CLI."""

    def test_aliases_check_runs_the_recall_report(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BL-5's blocked deliverable. Before R1006 this failed to parse at all."""
        config_path = make_corpus(tmp_path)

        assert main(["aliases", "--check", "--config", str(config_path)]) == 0

        out = capsys.readouterr().out
        assert "X670E" in out
        assert "never matched" in out.lower(), "the zero-match summary must still print"

    def test_the_flag_still_reaches_the_stage_when_config_comes_first(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Order must not matter: the dispatcher forwards leftovers, it does not position them."""
        config_path = make_corpus(tmp_path)

        assert main(["aliases", "--config", str(config_path), "--check"]) == 0

        assert "X670E" in capsys.readouterr().out

    def test_the_missing_flag_is_the_stages_error_not_argparses(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`--check` is a store_true, so the stage keeps its own friendlier usage."""
        config_path = make_corpus(tmp_path)

        assert main(["aliases", "--config", str(config_path)]) == 2

        out = capsys.readouterr().out
        assert "usage: find-best-mobo aliases --check" in out


class TestUndeclaredFlags:
    """Forwarding must not turn a typo into silence."""

    def test_an_undeclared_flag_is_rejected_naming_the_subcommand(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The fallback parser accepts nothing, so `index --nonsense` still exits 2.

        And it names `find-best-mobo index`, not `find-best-mobo` — the
        difference between an error a reader can act on and one that sends them
        to the wrong help screen.
        """
        config_path = make_corpus(tmp_path)

        with pytest.raises(SystemExit) as exit_info:
            main(["index", "--nonsense", "--config", str(config_path)])

        assert exit_info.value.code == 2
        err = capsys.readouterr().err
        assert "find-best-mobo index" in err
        assert "--nonsense" in err

    def test_a_rejected_flag_means_the_stage_never_ran(self, tmp_path: Path) -> None:
        """Parsing happens before the network, so a typo costs nothing."""
        config_path = make_corpus(tmp_path)
        index_path = tmp_path / "data" / "index.jsonl"
        before = index_path.read_bytes()

        with pytest.raises(SystemExit):
            main(["index", "--nonsense", "--config", str(config_path)])

        assert index_path.read_bytes() == before, "the stage ran despite a bad flag"


class TestHelp:
    """OD-18 (on BL-19): `--help` after a subcommand is forwarded, and the subcommand's prints."""

    def test_help_after_a_subcommand_prints_the_subcommands_help(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The only place `--check` is documented, and it was unreachable before."""
        with pytest.raises(SystemExit) as exit_info:
            main(["aliases", "--help"])

        assert exit_info.value.code == 0
        out = capsys.readouterr().out
        assert "usage: find-best-mobo aliases" in out
        assert "--check" in out

    def test_top_level_help_is_unchanged(self, capsys: pytest.CaptureFixture[str]) -> None:
        """`find-best-mobo --help` still prints the dispatcher's help, and exits 0."""
        assert main(["--help"]) == 0

        out = capsys.readouterr().out
        assert "usage: find-best-mobo" in out
        assert "--config" in out

    def test_a_bare_invocation_prints_help_and_returns_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Today's exit code for naming no command, kept."""
        assert main([]) == 2

        assert "usage: find-best-mobo" in capsys.readouterr().out


class TestUnknownCommand:
    def test_the_unknown_command_error_wins_over_a_flag(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Parsing flags for a command that does not exist names the smaller problem."""
        assert main(["bogus", "--check"]) == 2

        assert "unknown command 'bogus'" in capsys.readouterr().err
