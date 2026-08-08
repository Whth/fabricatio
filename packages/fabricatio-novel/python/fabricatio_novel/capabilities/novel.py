from abc import ABC
from typing import Unpack

from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel


class NovelCompose(ChapterCompose, ABC):
    """This class contains the capabilities for the novel."""

    async def before_compose_novel(
            self,
            ctx: NovelContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext: ...

    async def after_compose_novel(
            self,
            ctx: NovelContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext: ...

    async def post_process_novel(self, ctx: NovelContext, novel: Novel, **kwargs: Unpack[LLMKwargs]) -> Novel: ...

    async def generate_novel(
            self,
            ctx: NovelContext,
            send_to: str | None = TASK,
            **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None: ...

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
