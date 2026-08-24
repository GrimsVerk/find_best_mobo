"""The alias table is tracked, outside `data/`, and a fresh clone carries it.

This module exists because nothing else in the suite would notice the table
falling back out of git — which is the defect BL-4 filed. Every other alias test
writes its own table into `tmp_path`, so all of them pass with the shipped file
untracked, ignored, force-added, or moved back under the gitignored corpus
directory. R1007 (OD-11) is the rule; these are the assertions that make it
observable rather than merely asserted.

The `git` assertions run as subprocesses against the real checkout. Per R20 and
`AGENTS.md`'s optional-resource rule they SKIP with a stated reason where git is
unavailable or this tree is not a work tree — the suite must stay green from an
unpacked source archive. No network: `tests/conftest.py`'s offline guard is
untouched, and every call runs with `cwd=REPO_ROOT`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from find_best_mobo.aliases import load_aliases
from find_best_mobo.config import DEFAULT_ALIAS_TABLE, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_TABLE = REPO_ROOT / DEFAULT_ALIAS_TABLE


def git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run git in the checkout, capturing output and never raising on non-zero."""
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def require_git() -> None:
    """Skip, with the reason stated, where the git assertions cannot mean anything."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH: tracked-and-not-ignored cannot be checked here")
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        pytest.skip("not a git work tree (an unpacked source archive): nothing to ask git")


def test_the_default_alias_table_is_a_real_parsable_file() -> None:
    """A fresh clone must carry a table the loader can read.

    This is the property BL-4 says is currently bought with `git add -f`, and it
    is asserted against the default path rather than a fixture: what R1007
    guarantees is that the DEFAULT resolves to something real.
    """
    assert SHIPPED_TABLE.is_file(), f"no alias table at the default path {SHIPPED_TABLE}"

    aliases = load_aliases(SHIPPED_TABLE)

    assert aliases, "the shipped alias table parsed to no entries"


def test_git_tracks_the_alias_table() -> None:
    """R1007: the table is a git-tracked input, so a clone has it."""
    require_git()

    result = git("ls-files", "--error-unmatch", str(DEFAULT_ALIAS_TABLE))

    assert result.returncode == 0, (
        f"git does not track {DEFAULT_ALIAS_TABLE}: {result.stderr.strip()}"
    )


def test_git_does_not_ignore_the_alias_table() -> None:
    """Tracked is not enough: a force-added file inside an ignored tree is BL-4.

    The negative control is what stops this passing vacuously. `check-ignore`
    exits non-zero both when a path is genuinely not ignored and when the ignore
    machinery is not working at all, so the assertion is paired with `data/`,
    which R21 requires to be ignored. Without the pair, a missing `.gitignore`
    would make this test green.
    """
    require_git()

    table = git("check-ignore", "-q", str(DEFAULT_ALIAS_TABLE))
    corpus = git("check-ignore", "-q", "data")

    assert corpus.returncode == 0, "negative control failed: `data/` is not ignored (R21)"
    assert table.returncode != 0, f"{DEFAULT_ALIAS_TABLE} is inside the gitignored corpus tree"


def test_the_alias_table_is_not_under_the_corpus_directory() -> None:
    """R1007 states it as a location rule, so it is asserted as one.

    Stated separately from the ignore check so that a failure says which rule
    broke: a table moved under `data/` while `.gitignore` happened to be absent
    would satisfy the check above and still be the arrangement OD-11 retired.
    """
    config = load_config(REPO_ROOT / "config.toml")

    parts = config.alias_table_path.parts

    assert parts[0] != config.data_dir.parts[0], (
        f"the alias table {config.alias_table_path} sits under the corpus directory "
        f"{config.data_dir}; R1007 puts hand-authored input outside it"
    )


def test_the_shipped_config_points_at_the_shipped_table() -> None:
    """The lever and the file agree, so a clean checkout runs with no edits."""
    config = load_config(REPO_ROOT / "config.toml")

    assert (REPO_ROOT / config.alias_table_path).is_file()
    assert config.alias_table_path == DEFAULT_ALIAS_TABLE
