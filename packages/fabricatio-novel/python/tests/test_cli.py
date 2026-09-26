"""Tests for the fanvl CLI helpers."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from _support import SceneSpec, StorySpec, benchmark_run
from fabricatio_core import Task
from fabricatio_core.models.action import WorkFlow
from fabricatio_novel.actions.stage import StageAction
from fabricatio_novel.commands._helpers import _split_skills
from fabricatio_novel.commands.writing import _stamped_run_dir, app
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext
from fabricatio_novel.workflows.novel import DebugNovelWorkflow
from fabricatio_novel.workflows.rag import RagDebugNovelWorkflow
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


@dataclass(frozen=True, slots=True)
class _Invocation:
    """One stubbed `fanvl` write invocation: the task it built, the workflow it drove, and what it printed."""

    task: Task
    workflow: WorkFlow
    output: str


def _write_run(argv: list[str], tmp_path: Path, command: str = "w") -> _Invocation:
    """Invoke `fanvl <command>` with the workflow dispatch stubbed out and return what it built and printed."""
    tasks: list[Task] = []
    workflows: list[WorkFlow] = []

    def capture(task: Task, workflow: WorkFlow, namespace: str) -> Path:
        tasks.append(task)
        workflows.append(workflow)
        return tmp_path / "novel.epub"

    with (
        patch("fabricatio_novel.commands.writing._run_workflow", capture),
        patch("fabricatio_novel.commands.writing._report_generation"),
    ):
        result = CliRunner().invoke(app, [command, *argv])
    assert result.exit_code == 0, result.output
    return _Invocation(task=tasks[0], workflow=workflows[0], output=result.output)


def test_write_command_omits_an_unset_send_to(tmp_path: Path) -> None:
    """`fanvl w` without `--send-to` leaves the routing key out, so the plan stages keep their PLAN fallback."""
    run = _write_run(["A lighthouse keeper's daughter charts the reef at low tide."], tmp_path)
    assert "send_to" not in run.task.extra_init_context


def test_write_command_forwards_an_explicit_send_to(tmp_path: Path) -> None:
    """`fanvl w --send-to` names the run's routing group in the init context."""
    run = _write_run(["A lighthouse keeper's daughter charts the reef at low tide.", "--send-to", "glm"], tmp_path)
    assert run.task.extra_init_context["send_to"] == "glm"


def test_write_command_forwards_the_illustration_flags(tmp_path: Path) -> None:
    """`fanvl wri --choose-loras --judge --judge-tries 5` carries all three illustration knobs into the init context."""
    run = _write_run(
        [
            "A lighthouse keeper's daughter charts the reef at low tide.",
            "--choose-loras",
            "--judge",
            "--judge-tries",
            "5",
        ],
        tmp_path,
        command="wri",
    )
    context = run.task.extra_init_context
    assert context["illustration_choose_loras"] is True
    assert context["illustration_judge"] is True
    assert context["illustration_judge_max_tries"] == 5


def test_write_command_defers_the_illustration_knobs_when_unset(tmp_path: Path) -> None:
    """`fanvl wri` without the illustration flags leaves each knob None, so the [ext.novel] defaults stand."""
    run = _write_run(["A lighthouse keeper's daughter charts the reef at low tide."], tmp_path, command="wri")
    context = run.task.extra_init_context
    assert context["illustration_choose_loras"] is None
    assert context["illustration_judge"] is None
    assert context["illustration_judge_max_tries"] is None


def test_write_command_reads_a_zero_judge_tries_as_the_config_default(tmp_path: Path) -> None:
    """`--judge-tries 0` means 'config default', so the init context carries None rather than a zero budget."""
    run = _write_run(
        ["A lighthouse keeper's daughter charts the reef at low tide.", "--judge-tries", "0"],
        tmp_path,
        command="wri",
    )
    assert run.task.extra_init_context["illustration_judge_max_tries"] is None


def test_write_command_restarts_at_the_named_stage(tmp_path: Path) -> None:
    """`fanvl w --resume <run> --stage 08_scenes` runs that stage over the state the run persisted before it."""
    run_dir = _staged_run(tmp_path)

    run = _write_run(
        [
            "A lighthouse keeper's daughter charts the reef at low tide.",
            "--resume",
            str(run_dir),
            "--stage",
            "08_scenes",
        ],
        tmp_path,
    )

    assert run.task.extra_init_context["persist_dir"] == run_dir
    assert isinstance(run.task.extra_init_context["novel_ctx"], NovelContext)
    assert run.workflow is DebugNovelWorkflow
    assert run.task.extra_init_context[StageAction.held_key] == (
        "01_init",
        "02_metadata",
        "03_bible",
        "04_characters",
        "05_chapter_plans",
        "06_story_plans",
        "07_scene_plans",
    )


def test_write_command_restarts_after_the_newest_stage_by_default(tmp_path: Path) -> None:
    """`--resume` without `--stage` restarts at the stage after the newest one the run persisted, and reports it."""
    run_dir = _staged_run(tmp_path)

    run = _write_run(
        ["A lighthouse keeper's daughter charts the reef at low tide.", "--resume", str(run_dir)], tmp_path
    )

    assert "Resuming" in run.output
    assert "at stage 09_novel" in run.output
    assert run.workflow is DebugNovelWorkflow
    assert run.task.extra_init_context[StageAction.held_key] == (
        "01_init",
        "02_metadata",
        "03_bible",
        "04_characters",
        "05_chapter_plans",
        "06_story_plans",
        "07_scene_plans",
        "08_scenes",
    )


def test_write_command_resumes_without_an_outline(tmp_path: Path) -> None:
    """The outline rides the snapshot a resumed run continues from, so the command never asks for it again."""
    run_dir = _staged_run(tmp_path)

    run = _write_run(["--resume", str(run_dir), "--stage", "08_scenes"], tmp_path)

    assert run.task.extra_init_context["novel_outline"] == ""


def test_write_command_resumes_a_run_by_its_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--resume` takes a bare run name and resolves it under `--persist-dir`, not under the working directory."""
    run_dir = _staged_run(tmp_path, name="20260101-202020")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    run = _write_run(
        ["--resume", "20260101-202020", "--persist-dir", str(tmp_path), "--stage", "08_scenes"],
        tmp_path,
    )

    assert run.task.extra_init_context["persist_dir"] == run_dir


def test_write_command_refuses_a_stage_without_a_resume() -> None:
    """`--stage` names a resume point, so the command refuses it when there is no run to resume."""
    result = CliRunner().invoke(
        app, ["w", "A lighthouse keeper's daughter charts the reef at low tide.", "--stage", "08_scenes"]
    )

    assert result.exit_code == 1
    assert "--stage needs --resume" in result.output


def test_write_command_refuses_a_resume_directory_that_does_not_exist(tmp_path: Path) -> None:
    """`--resume` pointing nowhere fails on the spot instead of quietly stamping a fresh run."""
    result = CliRunner().invoke(
        app, ["w", "A lighthouse keeper's daughter charts the reef at low tide.", "--resume", str(tmp_path / "absent")]
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_write_command_refuses_a_stage_the_run_holds_no_state_before(tmp_path: Path) -> None:
    """A restart stage with no persisted state before it fails fast instead of running on nothing."""
    run_dir = _staged_run(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "w",
            "A lighthouse keeper's daughter charts the reef at low tide.",
            "--resume",
            str(run_dir),
            "--stage",
            "06_story_plans",
        ],
    )

    assert result.exit_code == 1
    assert "holds no snapshot before stage '06_story_plans'" in result.output
    assert "it holds: 06_story_plans, 08_scenes" in result.output


def test_write_command_refuses_to_resume_a_plain_run_with_rag(tmp_path: Path) -> None:
    """A plain run resumed by the RAG command would retrieve styles it was never written with, so the fix is named."""
    run_dir = _staged_run(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "wr",
            "A lighthouse keeper's daughter charts the reef at low tide.",
            "--resume",
            str(run_dir),
            "--stage",
            "08_scenes",
        ],
    )

    assert result.exit_code == 1
    assert "holds a plain run; resume it with fanvl w" in result.output


def test_write_command_refuses_to_resume_a_rag_run_without_retrieval(tmp_path: Path) -> None:
    """A sealed run resumed without its retrieval would write the rest of the novel unwrapped, so the RAG commands are named."""
    run_dir = benchmark_run(
        tmp_path,
        (
            StorySpec(
                "Arrival",
                "The keeper leaves the lamp and rows out.",
                (SceneSpec("Rowing", "The keeper rows out to the rocks.", "The keeper rows out under a grey sky."),),
            ),
        ),
        name="20260101-303030",
        novel_docs=("The grey sea keeps its own counsel along the reef.",),
    )

    result = CliRunner().invoke(
        app,
        [
            "w",
            "A lighthouse keeper's daughter charts the reef at low tide.",
            "--resume",
            str(run_dir),
            "--stage",
            "09_novel",
        ],
    )

    assert result.exit_code == 1
    assert "holds a RAG run; resume it with fanvl wr or fanvl wri" in result.output


def test_write_command_resumes_a_rag_run_with_the_rag_command(tmp_path: Path) -> None:
    """A sealed run resumed by `fanvl wr` keeps its retrieval: the sealed tree rides the init context."""
    run_dir = benchmark_run(
        tmp_path,
        (
            StorySpec(
                "Arrival",
                "The keeper leaves the lamp and rows out.",
                (SceneSpec("Rowing", "The keeper rows out to the rocks.", "The keeper rows out under a grey sky."),),
            ),
        ),
        name="20260101-404040",
        novel_docs=("The grey sea keeps its own counsel along the reef.",),
    )

    run = _write_run(
        [
            "A lighthouse keeper's daughter charts the reef at low tide.",
            "--resume",
            str(run_dir),
            "--stage",
            "09_novel",
        ],
        tmp_path,
        command="wr",
    )

    assert isinstance(run.task.extra_init_context["novel_ctx"], RagNovelContext)
    assert run.workflow is RagDebugNovelWorkflow
