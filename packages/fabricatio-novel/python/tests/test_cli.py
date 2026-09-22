"""Tests for the fanvl CLI helpers."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from _support import SceneSpec, StorySpec, benchmark_run
from fabricatio_core import Task
from fabricatio_core.models.action import WorkFlow
from fabricatio_novel.commands._helpers import _split_skills
from fabricatio_novel.commands.writing import _stamped_run_dir, app
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def _isolate_probe_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the default probe table at the test's tmp dir, so the suite never reads the project's probes.toml."""
    monkeypatch.chdir(tmp_path)


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


def test_bench_score_help_shows_the_default_table() -> None:
    """`fanvl bench score --help` shows the default probe table path."""
    result = CliRunner().invoke(app, ["bench", "score", "--help"])
    assert result.exit_code == 0
    assert "probes.toml" in result.output


def test_bench_score_skips_a_missing_probe_table(tmp_path: Path) -> None:
    """`--probes` pointing at a file that does not exist measures without the probe rows."""
    result = CliRunner().invoke(
        app, ["bench", "score", str(_staged_run(tmp_path)), "--probes", str(tmp_path / "absent.toml")]
    )

    assert result.exit_code == 0
    assert "not configured" in result.output


def test_bench_scan_measures_a_plain_manuscript(tmp_path: Path) -> None:
    """`fanvl bench scan <file>` measures prose that has no run directory behind it."""
    table = tmp_path / "manual-probes.toml"
    table.write_text('gated = ["Gulls"]\nwatch = ["silver"]\n', encoding="utf-8")
    draft = tmp_path / "draft.txt"
    draft.write_text("The keeper rows past the Gulls in a silver boat.", encoding="utf-8")

    result = CliRunner().invoke(app, ["bench", "scan", str(draft), "--probes", str(table)])

    assert result.exit_code == 0
    assert "FAIL" in result.output
    assert "gated" in result.output
    assert "Gullsx1" in result.output


def test_split_skills_flattens_comma_specs_and_dedupes() -> None:
    """`--skill` specs split on commas, trim, dedupe, and keep the requested order."""
    assert _split_skills(["b, a", "c", "b", " "]) == ["b", "a", "c"]


def _write_task(argv: list[str], tmp_path: Path) -> Task:
    """Invoke `fanvl w` with the workflow dispatch stubbed out and return the task it built."""
    captured: list[Task] = []

    def capture(task: Task, workflow: WorkFlow, namespace: str) -> Path:
        captured.append(task)
        return tmp_path / "novel.epub"

    with (
        patch("fabricatio_novel.commands.writing._run_workflow", capture),
        patch("fabricatio_novel.commands.writing._report_generation"),
    ):
        result = CliRunner().invoke(app, ["w", *argv])
    assert result.exit_code == 0, result.output
    return captured[0]


def test_write_command_omits_an_unset_send_to(tmp_path: Path) -> None:
    """`fanvl w` without `--send-to` leaves the routing key out, so the plan stages keep their PLAN fallback."""
    task = _write_task(["A lighthouse keeper's daughter charts the reef at low tide."], tmp_path)
    assert "send_to" not in task.extra_init_context


def test_write_command_forwards_an_explicit_send_to(tmp_path: Path) -> None:
    """`fanvl w --send-to` names the run's routing group in the init context."""
    task = _write_task(["A lighthouse keeper's daughter charts the reef at low tide.", "--send-to", "glm"], tmp_path)
    assert task.extra_init_context["send_to"] == "glm"
