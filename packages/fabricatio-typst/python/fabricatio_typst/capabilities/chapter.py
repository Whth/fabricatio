"""Chapter composition: planning a chapter's sections and writing them in order."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK

from fabricatio_typst.capabilities.section import SectionCompose
from fabricatio_typst.config import typst_config
from fabricatio_typst.models.article_main import ArticleChapter
from fabricatio_typst.models.context.chapter import ChapterContext
from fabricatio_typst.models.context.section import SectionContext
from fabricatio_typst.models.context.subsection import SubsectionContext
from fabricatio_typst.models.plan import SectionPlan, SectionPlans


class ChapterCompose[CTX: ChapterContext, S: SectionContext](SectionCompose[S, SubsectionContext], ABC):
    """Composes one chapter: plans its sections, then writes each of them in prefix order."""

    async def before_compose_chapter_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing a chapter; may mutate the context."""
        return ctx

    async def after_compose_chapter_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating a chapter; may mutate the context."""
        return ctx

    async def post_process_chapter(
        self,
        ctx: CTX,
        chapter: ArticleChapter,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleChapter:
        """Identity hook invoked on the composed chapter; may transform and return the chapter."""
        return chapter

    async def plan_sections(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[SectionPlan] | None:
        """Propose this chapter's section plans via the LLM.

        The chapter's own plan is the parent material: the planner sees what the chapter
        must establish, the run's briefing and proposal, and the rules already in force.
        """
        logger.debug(f"Planning sections for chapter '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            typst_config.article_plan_requirement_template,
            {
                "skills": ctx.skill_section(),
                "briefing": ctx.briefing,
                "proposal": ctx.proposal,
                "planning_title": "Section Planning",
                "goal": f"A Chapter is made of Section obj(s), which you need to plan for the chapter `{ctx.title}` now",
                "parent_title": "Chapter",
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "language": ctx.language,
            },
        )
        plans = await self.propose(SectionPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def plan_sections_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan this chapter's sections and materialize them as child contexts.

        The chapter's expected word count is split across the sections by plan weight;
        each child inherits the chapter's writing styles plus its own, and takes the
        section plan's constraints as its own rules.

        Returns:
            bool: True when the sections are planned; False on planning failure.
        """
        if not ctx.child_contexts:
            section_plans = await self.plan_sections(ctx, send_to, **kwargs)
            if section_plans is None:
                logger.error(f"Section planning failed for chapter '{ctx.title}'; aborting chapter generation")
                return False
            counts = ctx.allocate([s.weight for s in section_plans]) if section_plans else []
            for section_plan, count in zip(section_plans, counts, strict=True):
                ctx.add_context(
                    SectionContext.create(ctx.briefing, language=ctx.language)
                    .set_proposal(ctx.proposal)
                    .update_from(section_plan)
                    .set_plan(section_plan)
                    .expect_(count)
                    .set_writing_styles([*ctx.writing_styles, *section_plan.writing_styles])
                    .set_writing_constraints(section_plan.writing_constraints)
                    .with_skills_from(ctx),
                )
            logger.info(f"Planned {len(ctx.child_contexts)} section(s) for chapter '{ctx.title}'")
        return True

    async def compose_sections_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Write every section of this chapter in prefix order.

        Returns:
            bool: True when all sections were written; False as soon as one fails.
        """
        total = len(ctx.child_contexts)
        for index, section_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing section {index}/{total} of chapter '{ctx.title}'")
            if await self.compose_section(section_ctx, send_to, **kwargs) is None:
                logger.error(f"Section '{section_ctx.title}' of chapter '{ctx.title}' came back empty; aborting")
                return False
        return True

    async def generate_chapter_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX | None:
        """Plan this chapter's sections, then write them.

        Returns:
            CTX | None: The generated chapter context, or None when a phase aborted.
        """
        if not await self.plan_sections_phase(ctx, send_to, **kwargs):
            return None
        if not await self.compose_sections_phase(ctx, send_to, **kwargs):
            return None
        return ctx

    async def compose_chapter(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleChapter | None:
        """Compose one chapter end to end: before, generate, after, assemble, post-process.

        Returns:
            ArticleChapter | None: The composed chapter, or None when a phase aborted.
        """
        ctx = await self.before_compose_chapter_context(ctx, send_to=send_to, **kwargs)
        generated = await self.generate_chapter_context(ctx, send_to, **kwargs)
        if generated is None:
            return None
        ctx = await self.after_compose_chapter_context(generated, send_to=send_to, **kwargs)
        chapter = ArticleChapter.from_context(ctx)
        logger.info(
            f"Chapter '{chapter.title}' composed ({len(chapter.sections)} section(s),"
            f" word count satisfaction: {chapter.satisfy_ratio():.2f})",
        )
        return await self.post_process_chapter(ctx, chapter, **kwargs)


__all__ = ["ChapterCompose"]
