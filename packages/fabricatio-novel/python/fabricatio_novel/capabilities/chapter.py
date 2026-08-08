from abc import ABC
from typing import Unpack

from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.chapter import ChapterContext


class ChapterCompose(StoryCompose, ABC):
    """This class contains the capabilities for the chapter."""

    async def before_compose_chapter(
            self,
            ctx: ChapterContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext: ...

    async def after_compose_chapter(
            self,
            ctx: ChapterContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> ChapterContext: ...

    async def post_process_chapter(
            self, ctx: ChapterContext, chapter: Chapter, **kwargs: Unpack[LLMKwargs]
    ) -> Chapter: ...

    async def generate_chapter(
            self,
            ctx: ChapterContext,
            send_to: str | None = TASK,
            **kwargs: Unpack[LLMKwargs],
    ) -> Chapter | None: ...

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
