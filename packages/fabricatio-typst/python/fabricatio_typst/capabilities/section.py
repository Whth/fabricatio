"""Section composition: planning a section's subsections and writing them in order."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import PLAN, TASK

from fabricatio_typst.capabilities.subsection import SubsectionCompose
from fabricatio_typst.config import typst_config
from fabricatio_typst.models.article_main import ArticleSection
from fabricatio_typst.models.context.section import SectionContext
from fabricatio_typst.models.context.subsection import SubsectionContext
from fabricatio_typst.models.plan import SubsectionPlan, SubsectionPlans


class SectionCompose[CTX: SectionContext, U: SubsectionContext](SubsectionCompose[U], ABC):
    """Composes one section: plans its subsections, then writes each of them in prefix order."""

    async def before_compose_section_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing a section; may mutate the context."""
        return ctx

    async def after_compose_section_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating a section; may mutate the context."""
        return ctx

    async def post_process_section(
        self,
        ctx: CTX,
        section: ArticleSection,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleSection:
        """Identity hook invoked on the composed section; may transform and return the section."""
        return section

    async def plan_subsections(
        self,
        ctx: CTX,
        send_to: str | None = PLAN,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[SubsectionPlan] | None:
        """Propose this section's subsection plans via the LLM.

        The section's own plan is the parent material: the planner sees what the section
        must establish, the run's briefing and proposal, and the rules already in force.
        """
        logger.debug(f"Planning subsections for section '{ctx.title}'")
        requirement = TEMPLATE_MANAGER.render_template(
            typst_config.article_plan_requirement_template,
            {
                "skills": ctx.skill_section(),
                "briefing": ctx.briefing,
                "proposal": ctx.proposal,
                "planning_title": "Subsection Planning",
                "goal": f"A Section is made of Subsection obj(s), which you need to plan for the section `{ctx.title}` now",
                "parent_title": "Section",
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "language": ctx.language,
            },
        )
        plans = await self.propose(SubsectionPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def plan_subsections_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan this section's subsections and materialize them as child contexts.

        The section's expected word count is split across the subsections by plan weight;
        each child inherits the section's writing styles plus its own, and takes the
        subsection plan's constraints as its own rules.

        Returns:
            bool: True when the subsections are planned; False on planning failure.
        """
        if not ctx.child_contexts:
            subsection_plans = await self.plan_subsections(ctx, send_to, **kwargs)
            if subsection_plans is None:
                logger.error(f"Subsection planning failed for section '{ctx.title}'; aborting section generation")
                return False
            counts = ctx.allocate([s.weight for s in subsection_plans]) if subsection_plans else []
            for subsection_plan, count in zip(subsection_plans, counts, strict=True):
                ctx.add_context(
                    SubsectionContext.create(ctx.briefing, language=ctx.language)
                    .set_proposal(ctx.proposal)
                    .update_from(subsection_plan)
                    .set_plan(subsection_plan)
                    .expect_(count)
                    .set_writing_styles([*ctx.writing_styles, *subsection_plan.writing_styles])
                    .set_writing_constraints(subsection_plan.writing_constraints)
                    .with_skills_from(ctx),
                )
            logger.info(f"Planned {len(ctx.child_contexts)} subsection(s) for section '{ctx.title}'")
        return True

    async def compose_subsections_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Write every subsection of this section in prefix order.

        Each write sees the running text this section has assembled so far, so a
        subsection never repeats the one before it.

        Returns:
            bool: True when all subsections were written; False as soon as one fails.
        """
        total = len(ctx.child_contexts)
        for index, subsection_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing subsection {index}/{total} of section '{ctx.title}'")
            if await self.compose_subsection(subsection_ctx, send_to, **kwargs) is None:
                logger.error(f"Subsection '{subsection_ctx.title}' of section '{ctx.title}' came back empty; aborting")
                return False
        return True

    async def generate_section_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX | None:
        """Plan this section's subsections, then write them.

        Returns:
            CTX | None: The generated section context, or None when a phase aborted.
        """
        if not await self.plan_subsections_phase(ctx, send_to, **kwargs):
            return None
        if not await self.compose_subsections_phase(ctx, send_to, **kwargs):
            return None
        return ctx

    async def compose_section(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleSection | None:
        """Compose one section end to end: before, generate, after, assemble, post-process.

        Returns:
            ArticleSection | None: The composed section, or None when a phase aborted.
        """
        ctx = await self.before_compose_section_context(ctx, send_to=send_to, **kwargs)
        generated = await self.generate_section_context(ctx, send_to, **kwargs)
        if generated is None:
            return None
        ctx = await self.after_compose_section_context(generated, send_to=send_to, **kwargs)
        section = ArticleSection.from_context(ctx)
        logger.info(
            f"Section '{section.title}' composed ({len(section.subsections)} subsection(s),"
            f" word count satisfaction: {section.satisfy_ratio():.2f})",
        )
        return await self.post_process_section(ctx, section, **kwargs)


__all__ = ["SectionCompose"]
