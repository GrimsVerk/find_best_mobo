"""Every command module answers for itself (OD-10, R1006).

The point of this module is that it holds **no list of stage names**. It walks
the `find_best_mobo.commands` package and tests whatever it finds, so a stage
added later inherits R1006 rather than re-discovering BL-5 the way `aliases`
did. A hand-written list here would be the subcommand table OD-10 rejected, one
directory over.

No stage is ever run: every test either asks for help or passes a flag that
fails to parse, both of which return before `run` is reached. So nothing here
touches the network or writes to the corpus, and the assertions that no
artifact appeared are what prove it.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

import find_best_mobo.commands
from find_best_mobo.cli import main

# Discovered, never listed. `aliases` is included: it declares a flag, and
# everything asserted here is true of it too.
STAGES = sorted(
    module.name
    for module in pkgutil.iter_modules(find_best_mobo.commands.__path__)
    if not module.name.startswith("_")
)


def test_the_package_actually_holds_stages() -> None:
    """A discovery test that discovers nothing passes everything below vacuously."""
    assert len(STAGES) >= 5, f"expected the five shipped stages, found {STAGES}"
    assert "aliases" in STAGES and "estimate" in STAGES


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_answers_help_naming_itself(
    stage: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1006: `find-best-mobo <stage> --help` prints that stage's help.

    This is the test a later stage's author will see fail if they break R1006 —
    which is the whole reason it iterates the package instead of naming stages.
    """
    with pytest.raises(SystemExit) as exit_info:
        main([stage, "--help"])

    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith(f"usage: find-best-mobo {stage}"), out.splitlines()[:1]
    body = out.split("\n\n", 1)
    assert len(body) == 2 and body[1].strip(), f"{stage} documents nothing about itself"


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_rejects_a_flag_it_does_not_declare(
    stage: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Forwarding must never mean silently accepting, and the error names the stage."""
    with pytest.raises(SystemExit) as exit_info:
        main([stage, "--nonsense"])

    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert f"find-best-mobo {stage}" in err
    assert "--nonsense" in err


@pytest.mark.parametrize("stage", STAGES)
def test_a_rejected_flag_costs_no_work(stage: str, tmp_path: Path) -> None:
    """Parsing happens before the configuration is loaded and before any stage runs.

    Asserted as an empty data directory: `index` would write `index.jsonl`,
    `select` `selected.jsonl`, `estimate` a `bundles/` tree, and `fetch` would
    reach the network — which `tests/conftest.py` would fail the test for. None
    of that may happen for a mistyped flag.
    """
    data_dir = tmp_path / "data"
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'data_dir = "{data_dir.as_posix()}"\n', encoding="utf-8")

    with pytest.raises(SystemExit):
        main([stage, "--nonsense", "--config", str(config_path)])

    assert not data_dir.exists(), f"{stage} did work despite a flag it could not parse"


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_still_exposes_run(stage: str) -> None:
    """`parse_args` is a new entry point beside `run`, never a precondition of it.

    The rest of the suite calls `run(config, Namespace())` directly and must keep
    working unedited; this is the assertion that says so out loud.
    """
    module = importlib.import_module(f"find_best_mobo.commands.{stage}")

    assert callable(module.run)
    assert callable(module.parse_args)
