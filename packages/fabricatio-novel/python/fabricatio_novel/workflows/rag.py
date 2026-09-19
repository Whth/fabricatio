"""The retrieval variant of the staged novel workflow: writing-style RAG at the novel and story levels."""

from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelStage,
    DumpNovelStage,
    PrepareCharacterSpanStage,
    ProposeNovelMetadataStage,
    ProposeSettingBibleStage,
)
from fabricatio_novel.actions.rag import (
    RagComposeScenesStage,
    RagInitNovelContext,
    RagPlanChaptersStage,
    RagPlanScenesStage,
    RagPlanStoriesStage,
)

__all__ = ["RagDebugNovelWorkflow"]

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
