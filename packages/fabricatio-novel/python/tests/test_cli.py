"""Tests for the fanvl CLI helpers."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fabricatio_novel.cli import _stamped_run_dir


def test_stamped_run_dir_returns_timestamped_subdir(tmp_path: Path) -> None:
    """Each run resolves to a timestamped subdirectory under the persist root."""
    with patch("fabricatio_novel.cli.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 8, 18, 15, 30, 45)
        run_dir = _stamped_run_dir(tmp_path / "novels")
    assert run_dir == tmp_path / "novels" / "20260818-153045"
    assert not run_dir.exists()


def test_stamped_run_dir_uniquifies_same_second_runs(tmp_path: Path) -> None:
    """A timestamp collision gets a -N suffix so consecutive runs never overwrite."""
    target = tmp_path / "novels"
    (target / "20260818-153045").mkdir(parents=True)
    with patch("fabricatio_novel.cli.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 8, 18, 15, 30, 45)
        run_dir = _stamped_run_dir(target)
    assert run_dir == target / "20260818-153045-2"
