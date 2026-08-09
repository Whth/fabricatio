from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel, NovelMetadata
from fabricatio_novel.models.plan import NovelPlan


class NovelCompose(ChapterCompose, ABC):
    """This class contains the capabilities for the novel."""

    async def before_compose_novel(
        self,
        ctx: NovelContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext:
        return ctx

    async def after_compose_novel(
        self,
        ctx: NovelContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext:
        return ctx

    async def post_process_novel(self, ctx: NovelContext, novel: Novel, **kwargs: Unpack[LLMKwargs]) -> Novel:
        return novel

    async def plan_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> NovelPlan | None:
        logger.debug("Planning novel structure from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.novel_plan_template,
            {"outline": ctx.outline, "language": ctx.language},
        )
        return await self.propose(NovelPlan, requirement, send_to, **kwargs)

    async def generate_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None:
        logger.debug("Proposing novel metadata from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.novel_metadata_requirement_template,
            {"outline": ctx.outline, "language": ctx.language},
        )
        meta = await self.propose(NovelMetadata, requirement, send_to, **kwargs)
        if meta is None:
            return None
        ctx.title = meta.title
        ctx.description = meta.description
        ctx.expected_word_count = meta.expected_word_count
        ctx.series_bible = meta.series_bible
        logger.info(f"Novel metadata proposed: '{meta.title}' ({meta.expected_word_count} words)")
        if not ctx.chapter_context:
            plan = await self.plan_novel(ctx, send_to, **kwargs)
            if plan is None:
                return None
            ctx.chapter_context = plan.build_chapter_contexts(ctx.language)
            logger.info(f"Planned {len(ctx.chapter_context)} chapter(s)")
        for chapter_ctx in ctx.chapter_context:
            if await self.compose_chapter(chapter_ctx, send_to, **kwargs) is None:
                return None
        logger.info(f"Composed {len(ctx.chapter_context)} chapter(s)")
        return Novel.from_context(ctx)

    async def compose_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None:
        ctx = await self.before_compose_novel(ctx, **kwargs)
        novel = await self.generate_novel(ctx, send_to, **kwargs)
        ctx = await self.after_compose_novel(ctx, **kwargs)

        if novel is None:
            return None
        ok_novel = await self.post_process_novel(ctx, novel, **kwargs)

        return ok_novel
