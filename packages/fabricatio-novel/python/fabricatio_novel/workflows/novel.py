"""Staged novel writing workflows with per-stage persistence."""

from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleStage,
    ChapterPlanStage,
    CharactersStage,
    DumpEpubStage,
    InitNovelContext,
    MetadataStage,
    RagScenePlanStage,
    RagSceneWriteStage,
    ScenePlanStage,
    SceneWriteStage,
    StoryPlanStage,
)

__all__ = ["DebugNovelWorkflow", "RagDebugNovelWorkflow"]

DebugNovelWorkflow = WorkFlow(
    name="Debug Novel",
    description=(
        "Step-by-step novel generation from an outline; every stage persists a whole-tree "
        "snapshot into the given persist_dir, so a wrong result can be traced to the stage "
        "that produced it. Returns the EPUB path."
    ),
    steps=(
        InitNovelContext,
        MetadataStage,
        CharactersStage,
        ChapterPlanStage,
        StoryPlanStage,
        ScenePlanStage,
        SceneWriteStage,
        AssembleStage,
        DumpEpubStage,
    ),
)

RagDebugNovelWorkflow = WorkFlow(
    name="Debug Novel (RAG)",
    description=(
        "Step-by-step novel generation with writing style RAG; every stage persists a "
        "whole-tree snapshot into the given persist_dir. Returns the EPUB path."
    ),
    steps=(
        InitNovelContext,
        MetadataStage,
        CharactersStage,
        ChapterPlanStage,
        StoryPlanStage,
        RagScenePlanStage,
        RagSceneWriteStage,
        AssembleStage,
        DumpEpubStage,
    ),
)
