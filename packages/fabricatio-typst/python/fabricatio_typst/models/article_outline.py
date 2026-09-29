"""A module containing the ArticleOutline class, which represents the outline of an academic paper."""

from typing import ClassVar

from fabricatio_capabilities.models.generic import PersistentAble
from pydantic import Field

from fabricatio_typst.models.article_base import (
    ArticleBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio_typst.models.artifacts import ArticleArtifacts
from fabricatio_typst.models.context.article import ArticleContext
from fabricatio_typst.models.context.chapter import ChapterContext
from fabricatio_typst.models.context.section import SectionContext
from fabricatio_typst.models.context.subsection import SubsectionContext


class ArticleSubsectionOutline(SubSectionBase):
    """Atomic research component specification for academic paper generation."""

    @classmethod
    def from_context(cls, ctx: SubsectionContext) -> "ArticleSubsectionOutline":
        """Materialize a subsection outline from its planned context."""
        return cls(
            heading=ctx.title,
            elaboration=ctx.description,
            aims=list(ctx.plan.aims) if ctx.plan is not None else [],
            expected_word_count=ctx.expected_word_count,
        )


class ArticleSectionOutline(SectionBase[ArticleSubsectionOutline]):
    """A slightly more detailed research component specification for academic paper generation, Must contain subsections."""

    child_type: ClassVar[type[SubSectionBase]] = ArticleSubsectionOutline

    @classmethod
    def from_context(cls, ctx: SectionContext) -> "ArticleSectionOutline":
        """Materialize a section outline from its planned context, materializing each subsection recursively."""
        return cls(
            heading=ctx.title,
            elaboration=ctx.description,
            aims=list(ctx.plan.aims) if ctx.plan is not None else [],
            expected_word_count=ctx.expected_word_count,
            subsections=[ArticleSubsectionOutline.from_context(sc) for sc in ctx.child_contexts],
        )


class ArticleChapterOutline(ChapterBase[ArticleSectionOutline]):
    """Macro-structural unit implementing standard academic paper organization. Must contain sections."""

    child_type: ClassVar[type[SectionBase]] = ArticleSectionOutline

    @classmethod
    def from_context(cls, ctx: ChapterContext) -> "ArticleChapterOutline":
        """Materialize a chapter outline from its planned context, materializing each section recursively."""
        return cls(
            heading=ctx.title,
            elaboration=ctx.description,
            aims=list(ctx.plan.aims) if ctx.plan is not None else [],
            expected_word_count=ctx.expected_word_count,
            sections=[ArticleSectionOutline.from_context(sc) for sc in ctx.child_contexts],
        )


class ArticleOutline(
    PersistentAble,
    ArticleBase[ArticleChapterOutline],
):
    """Outline of an academic paper, containing chapters, sections, subsections."""

    artifacts: ArticleArtifacts = Field(default_factory=ArticleArtifacts)
    """Shared pipeline artifacts (briefing, proposal, outline)."""

    child_type: ClassVar[type[ChapterBase]] = ArticleChapterOutline

    @classmethod
    def from_context(cls, ctx: ArticleContext) -> "ArticleOutline":
        """Materialize the planned context tree as the article outline artifact.

        The outline is structure only: the pipeline's artifacts stay on the context root,
        so the artifact container never holds a document that points back at it.
        """
        return cls(
            heading=ctx.title,
            elaboration=ctx.description,
            aims=list(ctx.plan.aims) if ctx.plan is not None else [],
            expected_word_count=ctx.expected_word_count,
            chapters=[ArticleChapterOutline.from_context(sc) for sc in ctx.child_contexts],
        )

    def _as_prompt_inner(self) -> dict[str, str]:
        return {
            "Original Article Briefing": self.artifacts.access_briefing(),
            "Original Article Proposal": self.artifacts.access_proposal().display(),
            "Original Article Outline": self.display(),
        }
