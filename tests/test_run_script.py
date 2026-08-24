"""`scripts/run.sh` invokes the CLI, not a Python workaround (OD-10, R1006).

R1006's last sentence — "the `run-scripts` workaround (invoking `aliases`
through Python) reverts to a plain CLI call" — is otherwise observed by nothing
at all. This repository deliberately does not test shell
(`docs/plans/run-scripts.md`), and a bash harness for a four-line change would
be larger than the change; so this is a file-content guard, which is the
smallest thing that notices.

It is a ratchet, not a specification: it says what must NOT come back, and it
says the one command that must be there.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPT = REPO_ROOT / "scripts" / "run.sh"


def test_the_run_script_exists() -> None:
    """A guard against a missing file is a guard that passes when the file is gone."""
    assert RUN_SCRIPT.is_file(), f"no run script at {RUN_SCRIPT}"


def test_the_aliases_diagnostic_goes_through_the_cli() -> None:
    """The flag reaches the stage the way every other argument does."""
    script = RUN_SCRIPT.read_text(encoding="utf-8")

    assert "find-best-mobo aliases --check" in script


def test_no_python_invocation_workaround_remains() -> None:
    """BL-5's workaround reached into `find_best_mobo.commands` and built a Namespace.

    It existed because the dispatcher could not pass a per-subcommand flag. It
    can now, so a `python -c` block here would mean R1006 had been reverted in
    the one place the owner actually runs the pipeline from.
    """
    script = RUN_SCRIPT.read_text(encoding="utf-8")
    body = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))

    assert "python -c" not in body
    assert "Namespace" not in body
