"""Retrieval specializations of the staged novel pipeline.

Each stage reuses its plain body from :mod:`fabricatio_novel.actions.novel` and
swaps in the retrieval-aware phase its RAG capability mixin overrides, so the
retrieved style references reach that phase's prompt — and, where the phase
promotes its unit, the sealed context type survives the snapshot round trip.
"""

from typing import Any, ClassVar

from fabricatio_core.rust import PLAN

from fabricatio_novel.actions.novel import (
    ComposeScenesStage,
    InitNovelContext,
    PlanChaptersStage,
    PlanScenesStage,
    PlanStoriesStage,
)
from fabricatio_novel.capabilities.rag import RAGChapterCompose, RAGNovelCompose
from fabricatio_novel.models.context.chapter import RagChapterContext
from fabricatio_novel.models.context.novel import NovelContext

__all__ = [
    "RagComposeScenesStage",
    "RagInitNovelContext",
    "RagPlanChaptersStage",
    "RagPlanScenesStage",
    "RagPlanStoriesStage",
]


class RagInitNovelContext(InitNovelContext, RAGNovelCompose):
    """Init stage of a RAG run: the before hook seals the root and fetches the novel's style references.

    The stage body stays the base one — build, hook, snapshot — because the RAG
    work lives in the hook the mixin overrides, so the single snapshot the base
    writes already holds the sealed root with its references.
    """

    ctx_override: ClassVar[bool] = True


class RagPlanChaptersStage(PlanChaptersStage, RAGNovelCompose):
    """Chapter planning of a RAG run: the novel's references reach the prompt and the chapters carry the RAG type.

    The stage body stays the base one — :meth:`RAGNovelCompose.plan_chapters_phase`
    renders the phase's prompt from the sealed root and promotes what it plans — so
    the snapshot already holds the chapters the later stages seal stories into.
    """


class RagPlanStoriesStage(PlanStoriesStage, RAGChapterCompose):
    """Story planning with the RAG seal.

    :meth:`RAGChapterCompose.plan_stories_phase` seals each chapter's stories with
    the context-overridden retrieval settings right after they are planned;
    each sealed chapter is then promoted to
    :class:`~fabricatio_novel.models.context.chapter.RagChapterContext`, so the
    snapshot tree type-states that its stories are sealed, and the later scene
    stages only consume sealed story contexts.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so planning follows the plan model unless the run routes
    it elsewhere.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        for index, chapter in enumerate(novel_ctx.child_contexts):
            chapter_ctx = await self.before_compose_chapter_context(chapter, send_to=send_to)
            if not await self.plan_stories_phase(chapter_ctx, send_to=send_to):
                await self.snapshot(novel_ctx, cxt)
                return False
            novel_ctx.child_contexts[index] = RagChapterContext.model_validate(vars(chapter_ctx))
        await self.snapshot(novel_ctx, cxt)
        return True


class RagPlanScenesStage(PlanScenesStage, RAGChapterCompose):
    """Scene planning over stories already sealed by :class:`RagPlanStoriesStage`.

    Mixing in :class:`RAGChapterCompose` resolves :meth:`RAGChapterCompose.prepare_story`
    ahead of the plain implementation, so each sealed story's style
    references are retrieved before its scenes are planned.
    """


class RagComposeScenesStage(ComposeScenesStage, RAGChapterCompose):
    """Scene composition over stories already sealed by :class:`RagPlanScenesStage`."""
