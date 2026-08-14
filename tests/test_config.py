"""Tests for find_best_mobo.config, written blind from the slice-1 spec.

The implementation is being authored in parallel and is absent from this tree,
so these tests are expected to fail (at import) until assembly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from find_best_mobo.config import Config, load_config

# Flat top-level keys, no sections; start_date is a native TOML date and
# data_dir a string path (settled contract, docs/plans/corpus-and-checkpoint.md).
FULL_TOML = """\
channel_url = "https://example.invalid/@somechannel"
start_date = 2023-06-01
data_dir = "elsewhere/cache"
shorts_max_seconds = 90
mention_threshold = 5
window_before_seconds = 60
window_after_seconds = 240
per_video_excerpt_cap = 7
bundle_token_cap = 20000
calibration_batch_size = 4
batch_count = 2
chars_per_token = 3.5
consecutive_fetch_error_limit = 4
fetch_error_rate_limit = 0.1
missing_caption_rate_limit = 0.2
"""


def test_load_config_reads_every_field(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(FULL_TOML)

    config = load_config(path)

    assert config == Config(
        channel_url="https://example.invalid/@somechannel",
        start_date=date(2023, 6, 1),
        data_dir=Path("elsewhere/cache"),
        shorts_max_seconds=90,
        mention_threshold=5,
        window_before_seconds=60,
        window_after_seconds=240,
        per_video_excerpt_cap=7,
        bundle_token_cap=20000,
        calibration_batch_size=4,
        batch_count=2,
        chars_per_token=3.5,
        consecutive_fetch_error_limit=4,
        fetch_error_rate_limit=0.1,
        missing_caption_rate_limit=0.2,
    )


def test_load_config_empty_file_yields_in_code_defaults(tmp_path: Path) -> None:
    """A config file missing every key is never a crash: defaults live in code.

    Only defaults the design or an owner ruling actually pins are asserted
    exactly; the rest get sanity checks so an unstated default stays the
    implementation's choice.
    """
    path = tmp_path / "config.toml"
    path.write_text("")

    config = load_config(path)

    assert config.start_date == date(2023, 1, 1)  # DESIGN R1
    assert config.mention_threshold == 3  # DESIGN R4: defaults to 3
    assert config.window_before_seconds == 120  # DESIGN R5: 2 minutes before
    assert config.window_after_seconds == 300  # DESIGN R5: 5 minutes after
    assert config.consecutive_fetch_error_limit == 3  # DESIGN R24
    assert config.chars_per_token == 4.0  # plan: chars / 4 starting factor
    # DESIGN R24: the no-captions trigger (5%) is looser than the fetch-error
    # trigger (3%) — true whichever convention (fraction or percent) was picked.
    assert 0 < config.fetch_error_rate_limit < config.missing_caption_rate_limit
    assert config.shorts_max_seconds > 0
    assert "youtube.com" in config.channel_url
    assert config.data_dir == Path("data")


def test_load_config_overrides_only_present_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("mention_threshold = 7\nshorts_max_seconds = 999\n")

    config = load_config(path)

    assert config.mention_threshold == 7
    assert config.shorts_max_seconds == 999
    # Absent keys keep their in-code defaults.
    assert config.window_before_seconds == 120
    assert config.start_date == date(2023, 1, 1)
