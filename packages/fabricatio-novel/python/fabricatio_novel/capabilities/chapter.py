"""Chapter composition capabilities: planning stories and composing chapters."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.base import merge_writing_constraints
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import StoryPlan, StoryPlans


class ChapterCompose(StoryCompose, ABC):
    """This class contains the capabilities for the chapter."""

    async def before_compose_chapter(
        self,
        ctx: ChapterContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext:
        """Identity hook invoked before composing a chapter; may mutate the context."""
        return ctx

    async def after_compose_chapter(
        self,
        ctx: ChapterContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext:
        """Identity hook invoked after generating a chapter; may mutate the context."""
        return ctx

    async def post_process_chapter(self, ctx: ChapterContext, chapter: Chapter, **kwargs: Unpack[LLMKwargs]) -> Chapter:
        """Identity hook invoked on the composed chapter; may transform and return the chapter."""
        return chapter

    async def plan_stories(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[StoryPlan] | None:
        """Propose story plans for the chapter via the LLM.

        Renders the story plan template from the chapter context and proposes
        a StoryPlans batch, returning the root list of plans or None on failure.
        """
        logger.debug(f"Planning stories for chapter '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.story_plan_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_style": ctx.writing_style,
                "writing_constraint": ctx.writing_constraint,
                "language": ctx.language,
                "characters": ctx.dump_charactors(),
            },
        )
        plans = await self.propose(StoryPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def generate_chapter(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        """Generate the chapter by composing its stories.

        Interpolates character states, plans stories (with word counts
        allocated by weight) when none are scheduled, broadcasts the settings
        bible, splits character slices per story, and composes each story in
        prefix order. Returns the materialized chapter or None when planning
        or any story composition fails.
        """
        logger.debug(f"Generating chapter '{ctx.title}'")
        await self.interpolate_characters(ctx, send_to, **kwargs)
        if not ctx.story_context:
            story_plans = await self.plan_stories(ctx, send_to, **kwargs)
            if story_plans is None:
                logger.error(f"Story planning failed for chapter '{ctx.title}'; aborting chapter generation")
                return None
            counts = ctx.allocate([s.weight for s in story_plans]) if story_plans else []
            for story_plan, count in zip(story_plans, counts, strict=True):
                ctx.add_story_context(
                    StoryContext.from_plan(story_plan, expected_word_count=count)
                    .set_language(ctx.language)
                    .set_rag_query(ctx.rag_query)
                    .set_rag_limit(ctx.rag_limit)
                    .set_writing_constraint(
                        merge_writing_constraints(ctx.writing_constraint, story_plan.writing_constraint)
                    )
                )
            logger.info(f"Planned {len(ctx.story_context)} story(s) for chapter '{ctx.title}'")
        ctx.broadcast_settings_bible()
        await self.split_character_slices(ctx, ctx.story_context, send_to, **kwargs)
        total = len(ctx.story_context)
        for i, story_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing story {i}/{total} '{story_ctx.title}'")
            if await self.compose_story(story_ctx, send_to, **kwargs) is None:
                logger.error(f"Story '{story_ctx.title}' failed; aborting chapter '{ctx.title}'")
                return None
        chapter = Chapter.from_context(ctx)
        logger.info(
            f"Chapter '{chapter.title}' composed ({len(chapter.story)} story(s),  word count satisfaction: {chapter.satisfy_ratio()}"
        )
        return chapter

    async def compose_chapter(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None:
        """Compose a chapter end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_chapter(ctx, **kwargs)
        chapter = await self.generate_chapter(ctx, send_to, **kwargs)
        ctx = await self.after_compose_chapter(ctx, **kwargs)

        if chapter is None:
            return None
        return await self.post_process_chapter(ctx, chapter, **kwargs)
