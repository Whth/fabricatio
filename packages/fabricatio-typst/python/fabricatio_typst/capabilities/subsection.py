"""Subsection composition: writing the prose of one subsection from its plan and the running text."""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok

from fabricatio_typst.config import typst_config
from fabricatio_typst.models.article_main import ArticleSubsection
from fabricatio_typst.models.context.subsection import SubsectionContext


def clean_prose(prose: str) -> str:
    """Drop the scaffolding a model likes to wrap prose in: markdown headings and whole-line bold.

    A subsection's prose is written into the article as plain paragraphs, so a line that
    opens a markdown heading, or is nothing but a bold marker, would leak markup into the
    manuscript; every other line is kept verbatim.
    """
    return "\n".join(
        line
        for line in prose.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.rstrip().endswith("**")
    ).strip()


class SubsectionCompose[CTX: SubsectionContext](Propose, ABC):
    """Composes one subsection: its requirement, its prose, and the hooks around the write."""

    async def before_compose_subsection_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing a subsection; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def after_compose_subsection_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating a subsection; may mutate the context."""
        return ctx

    async def post_process_subsection(
        self,
        ctx: CTX,
        subsection: ArticleSubsection,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleSubsection:
        """Identity hook invoked on the composed subsection before it is written back to the context.

        Subclasses that repair or annotate the prose — a ruleset pass, citation rewriting
        — override this and return the subsection to store.
        """
        return subsection

    def prepare_subsection_requirement(
        self,
        ctx: CTX,
        *,
        references: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render this subsection's write requirement from its plan and the running text.

        ``references`` fills the retrieved-citation block; the plain arm leaves it empty
        and the template skips that section.
        """
        return TEMPLATE_MANAGER.render_template(
            typst_config.subsection_requirement_template,
            {
                "skills": ctx.skill_section(),
                "article_so_far": ctx.prefix_log.render(),
                "title": ctx.title,
                "description": ctx.description,
                "aims": list(ctx.plan.aims) if ctx.plan is not None else [],
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "section_opening": ctx.is_section_opening(),
                "language": ctx.language,
                "expected_word_count": ctx.expected_word_count,
                "references": references,
            },
        )

    async def generate_subsection_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Write the subsection's prose with one call and store it on the context.

        The reply is taken as prose: paragraphs are split locally when the article is
        assembled, so no second model call parses the text back into a model.
        """
        requirement = self.prepare_subsection_requirement(ctx, **kwargs)
        logger.info(f"Writing subsection '{ctx.title}' ({ctx.expected_word_count} words expected)")
        content = clean_prose(
            ok(await self.aask(requirement, send_to, **kwargs), f"Subsection '{ctx.title}' came back empty"),
        )
        return ctx.set_content(content)

    async def compose_subsection(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleSubsection | None:
        """Write one subsection end to end: before, generate, after, then post-process.

        The post-processed subsection is written back onto the context, so the tree — not
        the returned model — is what the assembly and every later prompt read.
        """
        ctx = await self.before_compose_subsection_context(ctx, send_to=send_to, **kwargs)
        ctx = await self.generate_subsection_context(ctx, send_to, **kwargs)
        ctx = await self.after_compose_subsection_context(ctx, send_to=send_to, **kwargs)
        subsection = await self.post_process_subsection(ctx, ArticleSubsection.from_context(ctx), **kwargs)
        ctx.set_content("\n\n".join(p.content for p in subsection.paragraphs))
        return subsection


__all__ = ["SubsectionCompose", "clean_prose"]
