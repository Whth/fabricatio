from abc import ABC
from typing import Unpack

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
    ) -> StoryContext: ...

    async def after_compose_story(
            self,
            ctx: StoryContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> StoryContext: ...

    async def post_process_story(self, ctx: StoryContext, story: Story, **kwargs: Unpack[LLMKwargs]) -> Story: ...

    async def generate_story(
            self,
            ctx: StoryContext,
            send_to: str | None = TASK,
            **kwargs: Unpack[LLMKwargs],
    ) -> Story | None: ...

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
