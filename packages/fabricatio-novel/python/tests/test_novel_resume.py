"""Tests for resuming a persisted run: where it restarts and which stages it leaves out.

Every fixture is a synthetic staged run built from the pipeline's own context models, so a
resume is exercisable without a live LLM. The runs below reach their artifacts with no mock
script installed at all, which is what proves the skip: a stage that ran would ask the model.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from _support import SceneSpec, StorySpec, benchmark_run
from fabricatio_core import Event, Task
from fabricatio_core.models.action import WorkFlow
from fabricatio_mock import make_test_role
from fabricatio_novel.actions.stage import StageAction
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext
from fabricatio_novel.resume import ResumeError, ResumePoint
from fabricatio_novel.workflows.illustration import RagIllustrationDebugNovelWorkflow
from fabricatio_novel.workflows.novel import DebugNovelWorkflow
from fabricatio_novel.workflows.rag import RagDebugNovelWorkflow

KEEPER_PROSE = "The keeper rows out to the rocks under a grey sky. The sea is quiet."
"""The composed prose of the fixture run's single scene."""

SEA_DOC = "The grey sea keeps its own counsel along the reef."
"""A retrieved style reference for the RAG fixture, sealing its snapshot as a RAG run."""

STAGES = (
    "01_init",
    "02_metadata",
    "03_bible",
    "04_characters",
    "05_chapter_plans",
    "06_story_plans",
    "07_scene_plans",
    "08_scenes",
    "09_novel",
)
"""Every stage the staged workflows persist, in run order."""


def _fixture_run(root: Path, *, docs: tuple[str, ...] = ()) -> Path:
    """Persist a two-stage fixture run -- story plans and composed scenes -- and return its directory."""
    specs = (
        StorySpec(
            title="The reef",
            description="The keeper's watch.",
            styles=("quiet",),
            scenes=(SceneSpec(title="Low tide", description="The keeper rows out.", content=KEEPER_PROSE),),
        ),
    )
    return benchmark_run(root, specs, novel_docs=docs)


async def _drive(point: ResumePoint, run_dir: Path, tag: str, workflow: WorkFlow = DebugNovelWorkflow) -> Path | None:
    """Drive a workflow over a run directory from a restart point, the way the commands do.

    The outline is seeded empty: the init stage's signature asks for it, but a resumed run never
    reaches that stage -- the state it continues from is the one the run already persisted.
    """
    namespace = f"wf_resume_{tag}_{uuid4().hex[:8]}"
    make_test_role(name=f"resume_{tag}").subscribe(Event.quick_instantiate(namespace), workflow).dispatch()
    task = Task(name=f"resumed novel {tag}").update_init_context(
        persist_dir=run_dir,
        novel_outline="",
        novel_ctx=point.context,
        **{StageAction.held_key: point.done},
    )
    return await task.delegate(namespace)


def test_resume_point_restarts_at_the_named_stage(tmp_path: Path) -> None:
    """``--stage 09_novel`` runs that stage from the tree the run persisted before it and leaves the rest out."""
    run_dir = _fixture_run(tmp_path)

    point = ResumePoint.of(DebugNovelWorkflow, run_dir, "09_novel")

    assert point.stage == "09_novel"
    assert point.done == STAGES[:-1]
    written = [
        scene.content
        for chapter in point.context.child_contexts
        for story in chapter.child_contexts
        for scene in story.child_contexts
    ]
    assert written == [KEEPER_PROSE]


def test_resume_point_defaults_to_the_stage_after_the_newest_snapshot(tmp_path: Path) -> None:
    """Without ``--stage`` the run restarts at the stage after the newest one it persisted."""
    run_dir = _fixture_run(tmp_path)

    point = ResumePoint.of(DebugNovelWorkflow, run_dir)

    assert point.stage == "09_novel"
    assert point.done == STAGES[:-1]


def test_resume_point_restarts_a_complete_run_at_its_last_stage(tmp_path: Path) -> None:
    """A run that reached the last stage restarts there, so a finished novel can be exported afresh."""
    run_dir = _fixture_run(tmp_path)
    last = run_dir / "stage_09_novel"
    last.mkdir()
    ResumePoint.of(DebugNovelWorkflow, run_dir).context.persist(last)

    point = ResumePoint.of(DebugNovelWorkflow, run_dir)

    assert point.stage == "09_novel"
    assert point.done == STAGES[:-1]


def test_resume_point_accepts_the_snapshot_directory_name(tmp_path: Path) -> None:
    """The stage may be named as its snapshot directory is spelled, so ``stage_09_novel`` restarts the same run."""
    run_dir = _fixture_run(tmp_path)

    assert ResumePoint.of(DebugNovelWorkflow, run_dir, "stage_09_novel").stage == "09_novel"


def test_resume_refuses_a_stage_nothing_precedes(tmp_path: Path) -> None:
    """A restart stage with no persisted state before it fails the resume instead of running on nothing."""
    run_dir = _fixture_run(tmp_path)

    with pytest.raises(ResumeError, match="holds no snapshot before stage '06_story_plans'") as excinfo:
        ResumePoint.of(DebugNovelWorkflow, run_dir, "06_story_plans")

    assert "it holds: 06_story_plans, 08_scenes" in str(excinfo.value)


def test_resume_refuses_a_stage_the_workflow_does_not_run(tmp_path: Path) -> None:
    """A mistyped stage names no step of the workflow, which the error spells out with the stages it does run."""
    run_dir = _fixture_run(tmp_path)

    with pytest.raises(ResumeError, match="the run has no stage '11_epub'; its stages are: 01_init, "):
        ResumePoint.of(DebugNovelWorkflow, run_dir, "11_epub")


def test_resume_refuses_a_run_without_snapshots(tmp_path: Path) -> None:
    """A directory holding no stage snapshot has no state to continue from."""
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(ResumeError, match="holds no stage snapshot to resume from"):
        ResumePoint.of(DebugNovelWorkflow, empty)


def test_resume_loads_a_sealed_run_as_the_rag_context(tmp_path: Path) -> None:
    """A run written with retrieval reloads as the sealed root, which the RAG commands continue."""
    run_dir = _fixture_run(tmp_path, docs=(SEA_DOC,))

    point = ResumePoint.of(RagDebugNovelWorkflow, run_dir, "09_novel")

    assert isinstance(point.context, RagNovelContext)
    assert point.done == STAGES[:-1]


async def test_a_resumed_run_leaves_out_the_stages_the_run_holds(tmp_path: Path) -> None:
    """The workflow runs in place: the stages before the restart point leave themselves out and nothing is written twice."""
    run_dir = _fixture_run(tmp_path)

    artifact = await _drive(ResumePoint.of(DebugNovelWorkflow, run_dir, "09_novel"), run_dir, "held")

    assert artifact is not None
    assert artifact == run_dir / "novel.epub"
    assert artifact.is_file()
    # Only the restart stage snapshotted and the export ran: the plan and prose stages the run was
    # resumed from kept exactly the one snapshot they persisted, and the scene-planning stage never
    # ran -- no stage before the restart point asked a model for the calls it would have made.
    assert sorted(path.name for path in run_dir.iterdir() if path.is_dir()) == [
        "chapters",
        "stage_06_story_plans",
        "stage_08_scenes",
        "stage_09_novel",
    ]
    assert len(list((run_dir / "stage_06_story_plans").glob("*.json"))) == 1
    assert len(list((run_dir / "stage_08_scenes").glob("*.json"))) == 1


async def test_a_written_novel_resumes_into_the_illustrated_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resuming a sealed run at ``09_novel`` with the illustrated command assembles it and draws every scene."""
    from fabricatio_novel.actions.illustration import IllustrateNovelStage
    from fabricatio_novel.models.novel import Novel

    run_dir = _fixture_run(tmp_path, docs=(SEA_DOC,))
    drawn: list[str] = []

    async def sketch(self: object, ctx: NovelContext, novel: Novel, **kwargs: object) -> Novel:
        drawn.append(novel.title)
        return novel

    monkeypatch.setattr(IllustrateNovelStage, "post_process_novel", sketch)

    point = ResumePoint.of(RagIllustrationDebugNovelWorkflow, run_dir, "09_novel")
    artifact = await _drive(point, run_dir, "illustrate", RagIllustrationDebugNovelWorkflow)

    assert drawn == ["Bench Novel"]
    assert artifact is not None
    assert artifact == run_dir / "novel.epub"
