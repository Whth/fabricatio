from abc import ABC
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.models.context.story import StoryContext
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

    async def generate_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Story | None:
        logger.debug(f"Generating story '{ctx.title}'")
        accumulated = ""
        for scene_ctx in ctx.scene_context:
            scene_ctx.previous_content = accumulated
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
