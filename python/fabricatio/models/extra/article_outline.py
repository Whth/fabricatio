"""A module containing the ArticleOutline class, which represents the outline of an academic paper."""

from fabricatio.models.extra.article_base import (
    ArticleBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.generic import CensoredAble, Display, PersistentAble, WithRef


class ArticleSubsectionOutline(SubSectionBase):
    """Atomic research component specification for academic paper generation."""


class ArticleSectionOutline(SectionBase[ArticleSubsectionOutline]):
    """A slightly more detailed research component specification for academic paper generation, Must contain subsections."""


class ArticleChapterOutline(ChapterBase[ArticleSectionOutline]):
    """Macro-structural unit implementing standard academic paper organization. Must contain sections."""


class ArticleOutline(
    Display,
    CensoredAble,
    WithRef[ArticleProposal],
    PersistentAble,
    ArticleBase[ArticleChapterOutline],
):
    """Outline of an academic paper, containing chapters, sections, subsections."""
