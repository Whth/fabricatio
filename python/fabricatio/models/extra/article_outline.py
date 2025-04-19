"""A module containing the ArticleOutline class, which represents the outline of an academic paper."""

from typing import Dict, Self

from fabricatio.fs.readers import extract_sections
from fabricatio.models.extra.article_base import (
    ArticleBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.generic import PersistentAble, WithRef


class ArticleSubsectionOutline(SubSectionBase):
    """Atomic research component specification for academic paper generation."""


class ArticleSectionOutline(SectionBase[ArticleSubsectionOutline]):
    """A slightly more detailed research component specification for academic paper generation, Must contain subsections."""
    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Parse the given Typst code into an ArticleSectionOutline instance."""
        return super().from_typst_code(
            title,
            body,
            subsections=[
                ArticleSubsectionOutline.from_typst_code(*pack)
                for pack in extract_sections(body, level=3, section_char="=")
            ],
        )



class ArticleChapterOutline(ChapterBase[ArticleSectionOutline]):
    """Macro-structural unit implementing standard academic paper organization. Must contain sections."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Parse the given Typst code into an ArticleChapterOutline instance."""
        return super().from_typst_code(
            title,
            body,
            sections=[
                ArticleSectionOutline.from_typst_code(*pack)
                for pack in extract_sections(body, level=2, section_char="=")
            ],

        )



class ArticleOutline(
    WithRef[ArticleProposal],
    PersistentAble,
    ArticleBase[ArticleChapterOutline],
):
    """Outline of an academic paper, containing chapters, sections, subsections."""

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {
            "Original Article Briefing": self.referenced.referenced,
            "Original Article Proposal": self.referenced.display(),
            "Original Article Outline": self.display(),
        }

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Parse the given Typst code into an ArticleOutline instance."""
        return super().from_typst_code(
            title,
            body,
            chapters=[
                ArticleChapterOutline.from_typst_code(*pack)
                for pack in extract_sections(body, level=1, section_char="=")
            ],
        )
