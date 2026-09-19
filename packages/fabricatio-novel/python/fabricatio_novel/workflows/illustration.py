"""The illustrated retrieval variant of the staged novel workflow: one post-process pass draws every scene."""

from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.illustration import IllustrateNovelStage
from fabricatio_novel.actions.novel import (
    AssembleNovelStage,
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

__all__ = ["RagIllustrationDebugNovelWorkflow"]

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
