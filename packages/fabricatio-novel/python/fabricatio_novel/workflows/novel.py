"""Staged novel writing workflows with per-stage persistence."""

from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelStage,
    ComposeScenesStage,
    DumpNovelStage,
    IllustrateNovelStage,
    InitNovelContext,
    PlanChaptersStage,
    PlanScenesStage,
    PlanStoriesStage,
    PrepareCharacterSpanStage,
    ProposeNovelMetadataStage,
    ProposeSettingBibleStage,
    RagComposeScenesStage,
    RagInitNovelContext,
    RagPlanChaptersStage,
    RagPlanScenesStage,
    RagPlanStoriesStage,
)

__all__ = ["DebugNovelWorkflow", "RagDebugNovelWorkflow", "RagIllustrationDebugNovelWorkflow"]

DebugNovelWorkflow = WorkFlow(
    name="Debug Novel",
    description=(
        "Step-by-step novel generation from an outline; every stage persists a whole-tree "
        "snapshot into the given persist_dir, so a wrong result can be traced to the stage "
        "that produced it. Returns the exported artifact path."
    ),
    steps=(
        InitNovelContext,
        ProposeNovelMetadataStage,
        ProposeSettingBibleStage,
        PrepareCharacterSpanStage,
        PlanChaptersStage,
        PlanStoriesStage,
        PlanScenesStage,
        ComposeScenesStage,
        AssembleNovelStage,
        DumpNovelStage,
    ),
)

RagDebugNovelWorkflow = WorkFlow(
    name="Debug Novel (RAG)",
    description=(
        "Step-by-step novel generation with writing style RAG; every stage persists a "
        "whole-tree snapshot into the given persist_dir. Returns the exported artifact path."
    ),
    steps=(
        RagInitNovelContext,
        ProposeNovelMetadataStage,
        ProposeSettingBibleStage,
        PrepareCharacterSpanStage,
        RagPlanChaptersStage,
        RagPlanStoriesStage,
        RagPlanScenesStage,
        RagComposeScenesStage,
        AssembleNovelStage,
        DumpNovelStage,
    ),
)

RagIllustrationDebugNovelWorkflow = WorkFlow(
    name="Debug Novel (RAG + Illustration)",
    description=(
        "Step-by-step novel generation with writing style RAG and a single post-process pass "
        "that renders a ComfyUI illustration for every scene into the EPUB; every stage "
        "persists a whole-tree snapshot into the given persist_dir. Returns the exported artifact path."
    ),
    steps=(
        RagInitNovelContext,
        ProposeNovelMetadataStage,
        ProposeSettingBibleStage,
        PrepareCharacterSpanStage,
        RagPlanChaptersStage,
        RagPlanStoriesStage,
        RagPlanScenesStage,
        RagComposeScenesStage,
        AssembleNovelStage,
        IllustrateNovelStage,
    ),
)
