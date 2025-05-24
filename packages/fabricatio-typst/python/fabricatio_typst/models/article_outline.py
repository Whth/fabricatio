"""A module containing the ArticleOutline class, which represents the outline of an academic paper."""

from typing import ClassVar, Dict, Type

from fabricatio_capabilities.models.generic import PersistentAble

from fabricatio_typst.models.article_base import (
    ArticleBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio_typst.models.article_proposal import ArticleProposal
from fabricatio_typst.models.generic import WithRef


class ArticleSubsectionOutline(SubSectionBase):
    """Atomic research component specification for academic paper generation."""


class ArticleSectionOutline(SectionBase[ArticleSubsectionOutline]):
    """A slightly more detailed research component specification for academic paper generation, Must contain subsections."""

    child_type: ClassVar[Type[SubSectionBase]] = ArticleSubsectionOutline


class ArticleChapterOutline(ChapterBase[ArticleSectionOutline]):
    """Macro-structural unit implementing standard academic paper organization. Must contain sections."""

    child_type: ClassVar[Type[SectionBase]] = ArticleSectionOutline


class ArticleOutline(
    WithRef[ArticleProposal],
    PersistentAble,
    ArticleBase[ArticleChapterOutline],
):
    """Outline of an academic paper, containing chapters, sections, subsections."""

    child_type: ClassVar[Type[ChapterBase]] = ArticleChapterOutline

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {
            "Original Article Briefing": self.referenced.referenced,
            "Original Article Proposal": self.referenced.display(),
            "Original Article Outline": self.display(),
        }
