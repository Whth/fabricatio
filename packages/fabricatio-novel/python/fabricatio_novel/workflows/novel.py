"""The plain staged novel workflow: every stage persists a whole-tree snapshot.

The retrieval variant lives in :mod:`fabricatio_novel.workflows.rag` and the
illustrated one in :mod:`fabricatio_novel.workflows.illustration`.
"""

from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelStage,
    ComposeScenesStage,
    DumpNovelStage,
    InitNovelContext,
    PlanChaptersStage,
    PlanScenesStage,
    PlanStoriesStage,
    PrepareCharacterSpanStage,
    ProposeNovelMetadataStage,
    ProposeSettingBibleStage,
)

__all__ = ["DebugNovelWorkflow"]

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
