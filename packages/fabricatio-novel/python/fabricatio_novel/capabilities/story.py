from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ScenePlans
from fabricatio_novel.models.story import Story


class StoryCompose(SceneCompose, ABC):
    """This class contains the capabilities for the story."""

    async def before_compose_story(
        self,
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> StoryContext:
        return ctx

    async def after_compose_story(
        self,
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> StoryContext:
        return ctx

    async def post_process_story(self, ctx: StoryContext, story: Story, **kwargs: Unpack[LLMKwargs]) -> Story:
        return story

    async def plan_scenes(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> ScenePlans | None:
        logger.debug(f"Planning scenes for story '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.scene_plan_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "language": ctx.language,
            },
        )
        return await self.propose(ScenePlans, requirement, send_to, **kwargs)

    async def generate_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Story | None:
        logger.debug(f"Generating story '{ctx.title}'")
        if not ctx.scene_context:
            plans = await self.plan_scenes(ctx, send_to, **kwargs)
            if plans is None:
                return None
            for scene_plan in plans.scenes:
                ctx.add_scene_context(
                    SceneContext()
                    .set_title(scene_plan.title)
                    .set_description(scene_plan.description)
                    .set_expected_word_count(scene_plan.expected_word_count)
                    .set_language(ctx.language)
                )
            logger.info(f"Planned {len(ctx.scene_context)} scene(s) for story '{ctx.title}'")
        accumulated = ""
        for scene_ctx in ctx.scene_context:
            scene_ctx.set_previous_content(accumulated)
            if await self.compose_scene(scene_ctx, send_to, **kwargs) is None:
                return None
            if scene_ctx.content:
                accumulated = f"{accumulated}\n\n{scene_ctx.content}" if accumulated else scene_ctx.content
        return Story.from_context(ctx)

    async def compose_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Story | None:
        ctx = await self.before_compose_story(ctx, **kwargs)
        story = await self.generate_story(ctx, send_to, **kwargs)
        ctx = await self.after_compose_story(ctx, **kwargs)

        if story is None:
            return None
        ok_story = await self.post_process_story(ctx, story, **kwargs)

        return ok_story
