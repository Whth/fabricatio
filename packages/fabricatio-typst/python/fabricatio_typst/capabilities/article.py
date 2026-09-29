"""Article composition: proposing the article's own plan, then planning and writing its chapters."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_skill import Skill, UseSkill

from fabricatio_typst.capabilities.chapter import ChapterCompose
from fabricatio_typst.config import typst_config
from fabricatio_typst.models.article_main import Article
from fabricatio_typst.models.article_outline import ArticleOutline
from fabricatio_typst.models.article_proposal import ArticleProposal
from fabricatio_typst.models.context.article import ArticleContext
from fabricatio_typst.models.context.chapter import ChapterContext
from fabricatio_typst.models.context.section import SectionContext
from fabricatio_typst.models.context.subsection import SubsectionContext
from fabricatio_typst.models.plan import ArticlePlan, ChapterPlan, ChapterPlans, SectionPlan


class ArticleCompose[CTX: ArticleContext](
    ChapterCompose[
        ChapterContext[SectionContext[SubsectionContext, SectionPlan], ChapterPlan],
        SectionContext[SubsectionContext, SectionPlan],
    ],
    UseSkill,
    ABC,
):
    """Composes one article: its own plan, then its chapters planned and written in prefix order."""

    def fetch_skills(self, names: list[str]) -> list[Skill]:
        """Resolve the run's skills by name through the process-wide skill library.

        Skills are built into article composition: a run carries the names the user
        selected and hands them to the fabricatio-skill library, which parses a skill
        once per process and keeps the body for every later walk — the planning
        prompts render them above the briefing and the running text leads with them.
        The lookup roots are the library's own (the cross-client skill dirs plus
        ``[ext.skill] extra_skill_dirs``). Resolution never fails: the library logs
        every name that resolves in no root, and the run goes on with the names that
        did.

        Args:
            names: Skill names the user selected, in the order given.

        Returns:
            The resolved skills, in argument order; names that resolved nowhere are absent.
        """
        wanted = list(dict.fromkeys(names))
        self.gather_skills(wanted)
        skills = self.skill_library.get_many(wanted)
        logger.info(f"Loaded {len(skills)} skill(s) for the article: {', '.join(skill.name for skill in skills)}")
        return skills

    def apply_skills(self, ctx: CTX, names: list[str]) -> CTX:
        """Bind the run's resolved skill selection to the root context.

        The library resolves and parses each name here and logs the ones no root
        provides — resolution never fails the run — while the context carries only the
        names that resolved: the bodies stay in the process-wide library, re-read there
        whenever a tree is rebuilt in a fresh process, so no element keeps a copy of
        the text and every prompt renders the section from the names.
        """
        resolved = [skill.name for skill in self.fetch_skills(names)]
        return ctx.with_skills(resolved)

    async def before_compose_article_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing an article; may mutate the context."""
        return ctx

    async def after_compose_article_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating an article; may mutate the context."""
        return ctx

    async def post_process_article(self, ctx: CTX, article: Article, **kwargs: Unpack[LLMKwargs]) -> Article:
        """Identity hook invoked on the assembled article; may transform and return the article."""
        return article

    async def propose_article_proposal(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Propose the research proposal from the briefing and record it on the context.

        The proposal is rendered once and carried down the tree as the run-wide channel
        every planner reads; the model itself stays on the artifacts record, so a
        persisted context keeps both the text and its shape.

        Returns:
            bool: True when the proposal was proposed and recorded; False on failure.
        """
        logger.info("Proposing the research proposal from the briefing")
        proposal = await self.propose(
            ArticleProposal,
            f"{ctx.briefing}\n\nWrite the value string using `{ctx.language}` as written language.",
            send_to,
            **kwargs,
        )
        if proposal is None:
            logger.error("Article proposal failed; aborting article generation")
            return False
        proposal.artifacts.update_briefing(ctx.briefing)
        ctx.set_proposal(proposal.as_prompt())
        ctx.artifacts.update_briefing(ctx.briefing)
        ctx.artifacts.update_proposal(proposal)
        logger.info("Article proposal recorded")
        return True

    async def propose_article_plan(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Propose the article's own plan and adopt it onto the context.

        The plan's scalar fields are adopted through ``update_from``; the style and
        constraint channels are seeded here explicitly, replacing any preset only when
        the plan proposes entries of its own, so an empty plan leaves the caller's
        intent intact.

        Returns:
            bool: True when the plan was proposed and adopted; False on failure.
        """
        logger.debug("Proposing article metadata from briefing and proposal")
        requirement = TEMPLATE_MANAGER.render_template(
            typst_config.article_metadata_requirement_template,
            {
                "skills": ctx.skill_section(),
                "briefing": ctx.briefing,
                "proposal": ctx.proposal,
                "constraint": ctx.writing_constraints,
                "language": ctx.language,
            },
        )
        plan = await self.propose(ArticlePlan, requirement, send_to, **kwargs)
        if plan is None:
            logger.error("Article plan proposal failed; aborting article generation")
            return False
        ctx.set_plan(plan).update_from(plan).expect_(plan.expected_word_count)
        if plan.writing_styles:
            ctx.set_writing_styles(plan.writing_styles)
        if plan.writing_constraints:
            ctx.set_writing_constraints(plan.writing_constraints)
        logger.info(f"Article plan proposed: '{plan.title}' ({plan.expected_word_count} words)")
        return True

    async def plan_chapters(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[ChapterPlan] | None:
        """Propose this article's chapter plans via the LLM.

        The article's own plan is the parent material: the planner sees what the article
        must establish, the run's briefing and proposal, and the rules already in force.
        """
        logger.debug("Planning chapters from the article plan")
        requirement = TEMPLATE_MANAGER.render_template(
            typst_config.article_plan_requirement_template,
            {
                "skills": ctx.skill_section(),
                "briefing": ctx.briefing,
                "proposal": ctx.proposal,
                "planning_title": "Chapter Planning",
                "goal": f"An Article is made of Chapter obj(s), which you need to plan for the article `{ctx.title}` now",
                "parent_title": "Article",
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "language": ctx.language,
            },
        )
        plans = await self.propose(ChapterPlans, requirement, send_to=send_to, **kwargs)
        return plans.root if plans is not None else None

    async def plan_chapters_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan the article's chapters and materialize them as child contexts.

        The article's expected word count is split across the chapters by plan weight;
        each child inherits the article's writing styles plus its own, and takes the
        chapter plan's constraints as its own rules.

        Returns:
            bool: True when the chapters are planned; False on planning failure.
        """
        if not ctx.child_contexts:
            chapter_plans = await self.plan_chapters(ctx, send_to, **kwargs)
            if chapter_plans is None:
                logger.error("Chapter planning failed; aborting article generation")
                return False
            counts = ctx.allocate([p.weight for p in chapter_plans]) if chapter_plans else []
            for chapter_plan, count in zip(chapter_plans, counts, strict=True):
                ctx.add_context(
                    ChapterContext.create(ctx.briefing, language=ctx.language)
                    .set_proposal(ctx.proposal)
                    .update_from(chapter_plan)
                    .set_plan(chapter_plan)
                    .expect_(count)
                    .set_writing_styles([*ctx.writing_styles, *chapter_plan.writing_styles])
                    .set_writing_constraints(chapter_plan.writing_constraints)
                    .with_skills_from(ctx),
                )
            logger.info(f"Planned {len(ctx.child_contexts)} chapter(s) for the article")
        return True

    async def plan_chapter_sections_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan every chapter's sections: fire each chapter's before hook, then plan its sections.

        Returns:
            bool: True when every chapter's sections are planned; False as soon as one fails.
        """
        for chapter_ctx in ctx.iter_prefixed_contexts():
            prepared = await self.before_compose_chapter_context(chapter_ctx, send_to=send_to, **kwargs)
            if not await self.plan_sections_phase(prepared, send_to=send_to, **kwargs):
                return False
        return True

    async def plan_section_subsections_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan every section's subsections: fire each section's before hook, then plan its subsections.

        Returns:
            bool: True when every section's subsections are planned; False as soon as one fails.
        """
        for chapter_ctx in ctx.iter_prefixed_contexts():
            for section_ctx in chapter_ctx.iter_prefixed_contexts():
                prepared = await self.before_compose_section_context(section_ctx, send_to=send_to, **kwargs)
                if not await self.plan_subsections_phase(prepared, send_to=send_to, **kwargs):
                    return False
        return True

    def seed_outline(self, ctx: CTX) -> CTX:
        """Seed the article's planned outline into the running text every later write reads.

        The seed is the article's whole structure — every planned heading at once — so a
        subsection's writes are grounded on the complete paper, not only on what has been
        written before them. Seeding is idempotent: a context that already carries its
        outline keeps the one it has.
        """
        ctx.seed_outline_prefix(ArticleOutline.from_context(ctx).finalized_dump())
        return ctx

    async def compose_chapters_phase(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Seed the article's outline into the running prefix and compose every chapter in order.

        The seed is the article's whole structure — every planned heading at once — so
        each chapter's writes are grounded on the complete paper, not only on what has
        been written before them.

        Returns:
            bool: True when every chapter composed; False on any failure.
        """
        self.seed_outline(ctx)
        total = len(ctx.child_contexts)
        for index, chapter_ctx in enumerate(ctx.iter_prefixed_contexts(), start=1):
            logger.info(f"Composing chapter {index}/{total} '{chapter_ctx.title}'")
            if await self.compose_chapter(chapter_ctx, send_to, **kwargs) is None:
                logger.error(f"Chapter '{chapter_ctx.title}' failed; aborting article generation")
                return False
        return True

    def assemble_article(self, ctx: CTX) -> Article:
        """Materialize the composed context tree as an Article and record its outline."""
        outline = ArticleOutline.from_context(ctx)
        ctx.artifacts.update_outline(outline)
        article = Article.from_context(ctx)
        logger.info(
            f"Article '{article.title}' composed ({len(article.chapters)} chapter(s), "
            f"word count satisfaction: {article.satisfy_ratio():.2f})",
        )
        return article

    async def generate_article_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX | None:
        """Generate the article by planning its own metadata and composing its chapters.

        Runs the staged phases in order: proposal, article plan proposal, chapter
        planning, and chapter composition. Returns the composed context or None when any
        phase fails.
        """
        logger.info(f"Generating article '{ctx.title}' from the briefing")
        if not await self.propose_article_proposal(ctx, send_to, **kwargs):
            return None
        if not await self.propose_article_plan(ctx, send_to, **kwargs):
            return None
        if not await self.plan_chapters_phase(ctx, send_to, **kwargs):
            return None
        if not await self.compose_chapters_phase(ctx, send_to, **kwargs):
            return None
        return ctx

    async def finish_article(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Article:
        """Close the article out: fire the after hook, then materialize the composed tree as an Article."""
        closed = await self.after_compose_article_context(ctx, send_to=send_to, **kwargs)
        return self.assemble_article(closed)

    async def compose_article(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Article | None:
        """Compose an article end to end: before, generate, after, assemble, post-process.

        Returns:
            Article | None: The composed article, or None when generation failed.
        """
        ctx = await self.before_compose_article_context(ctx, send_to=send_to, **kwargs)
        generated = await self.generate_article_context(ctx, send_to, **kwargs)
        if generated is None:
            return None
        return await self.post_process_article(ctx, await self.finish_article(generated, send_to, **kwargs), **kwargs)


__all__ = ["ArticleCompose"]
