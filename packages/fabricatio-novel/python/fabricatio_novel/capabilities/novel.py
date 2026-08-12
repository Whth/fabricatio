from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import CharacterTrace
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan, ChapterPlans, NovelPlan


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
    ) -> list[ChapterPlan] | None:
        logger.debug("Planning chapters from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_plan_template,
            {
                "outline": ctx.outline,
                "language": ctx.language,
                "title": ctx.title,
                "description": ctx.description,
                "characters": ctx.dump_charactors(),
            },
        )
        plans = await self.propose(ChapterPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def create_charactor_traces(self, ctx: NovelContext, **kwargs: Unpack[LLMKwargs]) -> None:
        """Create the initial character traces from the setting bible roster."""
        bible = ctx.series_bible
        if bible is None or not bible.characters:
            return
        requirements = [line.strip() for line in bible.characters.splitlines() if line.strip()]
        if not requirements:
            return
        cards = await self.compose_characters(requirements, **kwargs)
        if not cards:
            return
        ctx.set_charactor_traces([CharacterTrace(start=card, end=card) for card in cards if card is not None])

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
        ctx.set_novel_plan(plan).update_from(plan)
        logger.info(f"Novel plan proposed: '{plan.title}' ({plan.expected_word_count} words)")
        if not ctx.character_trace:
            await self.create_charactor_traces(ctx, **kwargs)
        await self.interpolate_characters(ctx, send_to, outline=ctx.outline, **kwargs)
        if not ctx.chapter_context:
            chapter_plans = await self.plan_chapters(ctx, send_to, **kwargs)
            if chapter_plans is None:
                return None
            counts = ctx.allocate([p.weight for p in chapter_plans]) if chapter_plans else []
            for chapter_plan, count in zip(chapter_plans, counts, strict=True):
                ctx.add_chapter_context(
                    ChapterContext(
                        title=chapter_plan.title,
                        description=chapter_plan.description,
                        expected_word_count=count,
                    )
                    .set_language(ctx.language)
                    .set_rag_query(ctx.rag_query)
                    .set_rag_limit(ctx.rag_limit)
                    .set_chapter_plan(chapter_plan)
                )
            logger.info(f"Planned {len(ctx.chapter_context)} chapter(s)")
        ctx.broadcast_settings_bible()
        await self.split_character_slices(ctx, ctx.chapter_context, send_to, **kwargs)
        for chapter_ctx in ctx.iter_prefixed_contexts():
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
