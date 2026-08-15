"""Novel composition capabilities: planning chapters and composing novels."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import CharacterTrace, merge_writing_constraints
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
        """Identity hook invoked before composing a novel; may mutate the context."""
        return ctx

    async def after_compose_novel(
        self,
        ctx: NovelContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> NovelContext:
        """Identity hook invoked after generating a novel; may mutate the context."""
        return ctx

    async def post_process_novel(self, ctx: NovelContext, novel: Novel, **kwargs: Unpack[LLMKwargs]) -> Novel:
        """Identity hook invoked on the composed novel; may transform and return the novel."""
        return novel

    async def plan_chapters(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[ChapterPlan] | None:
        """Propose chapter plans for the novel via the LLM.

        Renders the chapter plan template from the novel outline and context
        and proposes a ChapterPlans batch, returning the root list of plans
        or None on failure.
        """
        logger.debug("Planning chapters from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_plan_template,
            {
                "outline": ctx.outline,
                "language": ctx.language,
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_style": ctx.writing_style,
                "writing_constraint": ctx.writing_constraint,
                "characters": ctx.dump_charactors(),
            },
        )
        plans = await self.propose(ChapterPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def create_charactor_traces(self, ctx: NovelContext, **kwargs: Unpack[LLMKwargs]) -> None:
        """Create the initial character traces from the setting bible roster."""
        bible = ctx.series_bible
        if bible is None or not bible.characters:
            logger.debug("No setting bible roster; skipping character trace creation")
            return
        requirements = [line.strip() for line in bible.characters.splitlines() if line.strip()]
        if not requirements:
            logger.debug("Setting bible roster is empty; skipping character trace creation")
            return
        cards = await self.compose_characters(requirements, **kwargs)
        if not cards:
            logger.warn("Character proposal returned no cards; skipping character trace creation")
            return
        ctx.set_charactor_traces([CharacterTrace(start=card) for card in cards if card is not None])
        logger.info(f"Created {len(ctx.character_trace)} character trace(s) from the setting bible")

    async def generate_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None:
        """Generate the novel by composing its chapters.

        Proposes novel metadata from the outline, creates the initial
        character traces, interpolates character states, plans chapters (with
        word counts allocated by weight) when none are scheduled, broadcasts
        the settings bible, splits character slices per chapter, and composes
        each chapter in prefix order. Returns the materialized novel or None
        when metadata proposal, chapter planning, or any chapter composition
        fails.
        """
        logger.info(f"Generating novel from outline ({len(ctx.outline)} characters)")
        logger.debug("Proposing novel metadata from outline")
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.novel_metadata_requirement_template,
            {"outline": ctx.outline, "language": ctx.language, "constraint": ctx.writing_constraint},
        )
        plan = await self.propose(NovelPlan, requirement, send_to, **kwargs)
        if plan is None:
            logger.error("Novel metadata proposal failed; aborting novel generation")
            return None
        ctx.set_novel_plan(plan).update_from(plan)
        logger.info(f"Novel plan proposed: '{plan.title}' ({plan.expected_word_count} words)")
        if not ctx.character_trace:
            await self.create_charactor_traces(ctx, **kwargs)
        if ctx.character_trace:
            logger.info(f"Interpolating {len(ctx.character_trace)} character(s) over the novel outline")
        await self.interpolate_characters(ctx, send_to, outline=ctx.outline, **kwargs)
        if not ctx.chapter_context:
            chapter_plans = await self.plan_chapters(ctx, send_to, **kwargs)
            if chapter_plans is None:
                logger.error("Chapter planning failed; aborting novel generation")
                return None
            counts = ctx.allocate([p.weight for p in chapter_plans]) if chapter_plans else []
            for chapter_plan, count in zip(chapter_plans, counts, strict=True):
                ctx.add_chapter_context(
                    ChapterContext.from_plan(chapter_plan, expected_word_count=count)
                    .set_language(ctx.language)
                    .set_rag_query(ctx.rag_query)
                    .set_rag_limit(ctx.rag_limit)
                    .set_writing_constraint(
                        merge_writing_constraints(ctx.writing_constraint, chapter_plan.writing_constraint)
                    )
                )
            logger.info(f"Planned {len(ctx.chapter_context)} chapter(s)")
        ctx.broadcast_settings_bible()
        await self.split_character_slices(ctx, ctx.chapter_context, send_to, **kwargs)
        total = len(ctx.chapter_context)
        for i, chapter_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing chapter {i}/{total} '{chapter_ctx.title}'")
            if await self.compose_chapter(chapter_ctx, send_to, **kwargs) is None:
                logger.error(f"Chapter '{chapter_ctx.title}' failed; aborting novel generation")
                return None
        novel = Novel.from_context(ctx)

        logger.info(
            f"Novel '{novel.title}' composed ({len(novel.chapter)} chapter(s), word count satisfaction: {novel.satisfy_ratio()}"
        )
        return novel

    async def compose_novel(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel | None:
        """Compose a novel end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_novel(ctx, **kwargs)
        novel = await self.generate_novel(ctx, send_to, **kwargs)
        ctx = await self.after_compose_novel(ctx, **kwargs)

        if novel is None:
            return None
        return await self.post_process_novel(ctx, novel, **kwargs)
