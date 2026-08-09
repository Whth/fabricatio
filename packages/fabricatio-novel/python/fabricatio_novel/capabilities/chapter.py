from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan, plan_list_question, plan_list_validator


class ChapterCompose(StoryCompose, ABC):
    """This class contains the capabilities for the chapter."""

    async def before_compose_chapter(
        self,
        ctx: ChapterContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext:
        return ctx

    async def after_compose_chapter(
        self,
        ctx: ChapterContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext:
        return ctx

    async def post_process_chapter(self, ctx: ChapterContext, chapter: Chapter, **kwargs: Unpack[LLMKwargs]) -> Chapter:
        return chapter

    async def plan_stories(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[StoryPlan] | None:
        logger.debug(f"Planning stories for chapter '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.story_plan_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "language": ctx.language,
            },
        )
        return await self.aask_validate(
            plan_list_question(requirement, StoryPlan),
            plan_list_validator(StoryPlan),
            send_to=send_to,
            **kwargs,
        )

    async def generate_chapter(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        logger.debug(f"Generating chapter '{ctx.title}'")
        if not ctx.story_context:
            story_plans = await self.plan_stories(ctx, send_to, **kwargs)
            if story_plans is None:
                return None
            ctx.set_story_plan(story_plans)
            for story_plan in story_plans:
                ctx.add_story_context(
                    StoryContext()
                    .set_title(story_plan.title)
                    .set_description(story_plan.description)
                    .set_expected_word_count(story_plan.expected_word_count)
                    .set_language(ctx.language)
                )
            logger.info(f"Planned {len(ctx.story_context)} story(s) for chapter '{ctx.title}'")
        for story_ctx in ctx.story_context:
            if await self.compose_story(story_ctx, send_to, **kwargs) is None:
                return None
        return Chapter.from_context(ctx)

    async def compose_chapter(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        ctx = await self.before_compose_chapter(ctx, **kwargs)
        chapter = await self.generate_chapter(ctx, send_to, **kwargs)
        ctx = await self.after_compose_chapter(ctx, **kwargs)

        if chapter is None:
            return None
        ok_chapter = await self.post_process_chapter(ctx, chapter, **kwargs)

        return ok_chapter
