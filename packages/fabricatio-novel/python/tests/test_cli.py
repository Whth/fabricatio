"""Tests for the fanvl CLI helpers."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from _support import SceneSpec, StorySpec, benchmark_run
from fabricatio_novel.commands.writing import _stamped_run_dir, app
from typer.testing import CliRunner


def _staged_run(tmp_path: Path, name: str = "20260101-101010") -> Path:
    """Persist a one-scene staged run for the benchmark commands."""
    return benchmark_run(
        tmp_path,
        (
            StorySpec(
                "Arrival",
                "The keeper leaves the lamp and rows out.",
                (SceneSpec("Rowing", "The keeper rows out to the rocks.", "The keeper rows out under a grey sky."),),
            ),
        ),
        name=name,
    )


def test_stamped_run_dir_returns_timestamped_subdir(tmp_path: Path) -> None:
    """Each run resolves to a timestamped subdirectory under the persist root."""
    with patch("fabricatio_novel.commands.writing.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 8, 18, 15, 30, 45).astimezone()
        run_dir = _stamped_run_dir(tmp_path / "novels")
    assert run_dir == tmp_path / "novels" / "20260818-153045"
    assert not run_dir.exists()


def test_stamped_run_dir_uniquifies_same_second_runs(tmp_path: Path) -> None:
    """A timestamp collision gets a -N suffix so consecutive runs never overwrite."""
    target = tmp_path / "novels"
    (target / "20260818-153045").mkdir(parents=True)
    with patch("fabricatio_novel.commands.writing.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 8, 18, 15, 30, 45).astimezone()
        run_dir = _stamped_run_dir(target)
    assert run_dir == target / "20260818-153045-2"


def test_wri_help_advertises_choose_loras() -> None:
    """`fanvl wri --help` advertises the opt-in --choose-loras flag."""
    result = CliRunner().invoke(app, ["wri", "--help"])
    assert result.exit_code == 0
    assert "--choose-loras" in result.output


def test_wri_help_advertises_judge_flags() -> None:
    """`fanvl wri --help` advertises the opt-in --judge and --judge-tries flags."""
    result = CliRunner().invoke(app, ["wri", "--help"])
    assert result.exit_code == 0
    assert "--judge" in result.output
    assert "--judge-tries" in result.output


def test_bench_score_prints_a_scorecard(tmp_path: Path) -> None:
    """`fanvl bench score <run>` prints the scorecard of a staged run."""
    result = CliRunner().invoke(app, ["bench", "score", str(_staged_run(tmp_path))])
    assert result.exit_code == 0
    assert "gates   PASS" in result.output


def test_bench_board_lists_runs(tmp_path: Path) -> None:
    """`fanvl bench board <dir>` scores the run directories under a persist directory."""
    _staged_run(tmp_path)
    result = CliRunner().invoke(app, ["bench", "board", str(tmp_path)])
    assert result.exit_code == 0
    assert "20260101-101010" in result.output
