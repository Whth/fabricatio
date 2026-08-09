from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlans, NovelPlan


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

    async def plan_chapters(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterPlans | None:
        logger.debug("Planning chapters from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_plan_template,
            {
                "outline": ctx.outline,
                "language": ctx.language,
                "title": ctx.title,
                "description": ctx.description,
            },
        )
        return await self.propose(ChapterPlans, requirement, send_to, **kwargs)

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
        plan = await self.propose(NovelPlan, requirement, send_to, **kwargs)
        if plan is None:
            return None
        ctx.set_title(plan.title).set_description(plan.description).set_expected_word_count(
            plan.expected_word_count
        ).set_series_bible(plan.series_bible)
        logger.info(f"Novel plan proposed: '{plan.title}' ({plan.expected_word_count} words)")
        if not ctx.chapter_context:
            plans = await self.plan_chapters(ctx, send_to, **kwargs)
            if plans is None:
                return None
            for chapter_plan in plans.chapters:
                ctx.add_chapter_context(
                    ChapterContext()
                    .set_title(chapter_plan.title)
                    .set_description(chapter_plan.description)
                    .set_expected_word_count(chapter_plan.expected_word_count)
                    .set_language(ctx.language)
                )
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
