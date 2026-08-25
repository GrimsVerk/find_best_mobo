"""`scripts/run.sh` invokes the CLI, not a Python workaround (OD-10, R1006).

R1006's last sentence — "the `run-scripts` workaround (invoking `aliases`
through Python) reverts to a plain CLI call" — is otherwise observed by nothing
at all. This repository deliberately does not test shell
(`docs/plans/run-scripts.md`), and a bash harness for a four-line change would
be larger than the change; so this is a file-content guard, which is the
smallest thing that notices.

It is a ratchet, not a specification: it says what must NOT come back, and it
says the one command that must be there.

`run-scripts` slice 2 adds a second thing worth a file-content guard: the script
now runs `extract`, so it SPENDS, and its header used to promise the opposite.
A stale promise in a header is exactly the kind of thing nothing else notices —
the code around it changes, the sentence stays, and it goes on being read as
true. The assertions below therefore name the sentences that must be gone, the
stage that must be in the default list, and the forwarding a stage's own flags
depend on. Nothing here EXECUTES the script: running it would invoke a model and
spend real money (R20), so the text is what is read.
"""

from __future__ import annotations

import re
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


# The pipeline order is the contract (`docs/plans/run-scripts.md`), and slice 2
# adds `extract` to the end of it: `run.sh` is "the thing to run when you want to
# run the software", and a wrapper that omits a third of the pipeline is a list
# of the parts that existed when it was written.
DEFAULT_STAGES = ["index", "fetch", "select", "estimate", "extract"]

# Sentences that were true when nothing here could spend and are false now.
# Matched case-insensitively, because a header that merely changed its
# capitalisation has not stopped making the promise.
STALE_PROMISES = (
    "Nothing in this script spends money",
    "nothing here spends money",
    "No model is invoked",
    "no model has been invoked",
    "no model is invoked by anything here",
)


def script_text() -> str:
    return RUN_SCRIPT.read_text(encoding="utf-8")


def default_stage_list(script: str) -> list[str]:
    """The stages a bare `./scripts/run.sh` runs, read out of the array it holds."""
    match = re.search(r"STAGES=\(([^)]*)\)", script)
    assert match is not None, "no stage array in the script, so a bare run has no stages"
    return match.group(1).split()


def test_the_default_stages_are_the_whole_pipeline_including_extraction() -> None:
    """A bare `./scripts/run.sh` runs the software, extraction included.

    Order matters as much as membership: `extract` reads the bundles `estimate`
    writes, so a list holding both in the wrong order would run a stage against
    the previous run's data.
    """
    assert default_stage_list(script_text()) == DEFAULT_STAGES


def test_the_stage_validation_lets_extraction_through() -> None:
    """A stage in the default list that validation rejects fails every bare run.

    Read off the alternation the validator matches stage names against. An
    implementation that validates some other way has no such alternation and is
    not judged here — this catches the version that kept the case statement and
    forgot to add the new stage to it.
    """
    alternations = [
        line
        for line in script_text().splitlines()
        if re.match(r"\s*[a-z]+(\|[a-z]+)+\)", line.strip()) and "estimate" in line
    ]

    for line in alternations:
        assert "extract" in line, f"a bare run would be refused by its own validator: {line!r}"


def test_arguments_after_a_stage_reach_the_command() -> None:
    """`./scripts/run.sh extract --batches all` must reach `extract`, not fail on `--batches`.

    The script used to treat every argument as a stage name, so a per-stage flag
    was a validation error. Whatever shape the forwarding takes — an array or a
    shifted `$@` — the extra arguments have to appear on the command line the
    script actually runs.
    """
    script = script_text()

    forwarded = re.search(r'find-best-mobo[^\n]*("\$@"|\$\{[A-Za-z_]+\[@\]\})', script)

    assert forwarded is not None, (
        "nothing is forwarded to the subcommand, so `./scripts/run.sh extract "
        "--batches all` cannot reach the stage that understands `--batches`"
    )


def test_the_script_no_longer_promises_that_it_cannot_spend() -> None:
    """The header stops promising what it cannot keep.

    `run.sh` runs `extract`, which invokes a model and spends real subscription
    budget. A header still saying otherwise is worse than no header: it is read,
    it is believed, and nothing else in the tree contradicts it.
    """
    script = script_text().lower()

    for promise in STALE_PROMISES:
        assert promise.lower() not in script, (
            f"`run.sh` still claims {promise!r}, and it now runs `extract`"
        )


def test_the_script_names_the_ceiling_that_bounds_what_it_costs() -> None:
    """What replaces the promise has to say what is actually true.

    R26's ceiling is the reason "this spends money" is not the end of the story,
    so the script names it where the old promise stood.
    """
    assert "R26" in script_text(), (
        "nothing in `run.sh` names the ceiling that bounds what a run can cost"
    )
