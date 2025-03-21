"""A module containing the ArticleOutline class, which represents the outline of an academic paper."""

from enum import Enum
from typing import TYPE_CHECKING, Generator, List, Optional, Union, overload

from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.generic import Base, CensoredAble, Display, PersistentAble, WithRef
from pydantic import Field

if TYPE_CHECKING:
    from fabricatio.models.extra.article_main import Article, ArticleBase


class ReferringType(str, Enum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER: str = "chapter"
    SECTION: str = "section"
    SUBSECTION: str = "subsection"


class ArticleRef(CensoredAble):
    """Reference to a specific chapter, section or subsection within the article. You SHALL not refer to an article component that is external and not present within our own article."""

    referred_chapter_title: str
    """`title` Field of the referenced chapter"""

    referred_section_title: Optional[str] = None
    """`title` Field of the referenced section. Defaults to None if not applicable, which means the reference is pointing to the entire chapter."""

    referred_subsection_title: Optional[str] = None
    """`title` Field of the referenced subsection. Defaults to None if not applicable, which means the reference is pointing to the entire section."""

    def __hash__(self) -> int:
        """Overrides the default hash function to ensure consistent hashing across instances."""
        return hash((self.referred_chapter_title, self.referred_section_title, self.referred_subsection_title))

    @overload
    def deref(self, article: "Article") -> Optional["ArticleBase"]:
        """Dereference the reference to the actual section or subsection within the provided article."""

    @overload
    def deref(self, article: "ArticleOutline") -> Optional["ArticleOutlineBase"]:
        """Dereference the reference to the actual section or subsection within the provided article."""

    def deref(self, article: Union["ArticleOutline", "Article"]) -> Union["ArticleOutlineBase", "ArticleBase", None]:
        """Dereference the reference to the actual section or subsection within the provided article.

        Args:
            article (ArticleOutline | Article): The article to dereference the reference from.

        Returns:
            ArticleBase | ArticleOutline | None: The dereferenced section or subsection, or None if not found.
        """
        chap = next((chap for chap in article.chapters if chap.title == self.referred_chapter_title), None)
        if self.referred_section_title is None or chap is None:
            return chap
        sec = next((sec for sec in chap.sections if sec.title == self.referred_section_title), None)
        if self.referred_subsection_title is None or sec is None:
            return sec
        return next((subsec for subsec in sec.subsections if subsec.title == self.referred_subsection_title), None)

    @property
    def referring_type(self) -> ReferringType:
        """Determine the type of reference based on the presence of specific attributes."""
        if self.referred_subsection_title is not None:
            return ReferringType.SUBSECTION
        if self.referred_section_title is not None:
            return ReferringType.SECTION
        return ReferringType.CHAPTER


class ArticleOutlineBase(Base):
    """Base class for article outlines."""

    writing_aim: List[str]
    """Required: List of specific rhetorical objectives (3-5 items).
    Format: Each item must be an actionable phrase starting with a verb.
    Example: ['Establish metric validity', 'Compare with baseline approaches',
             'Justify threshold selection']"""
    depend_on: List[ArticleRef]
    """Required: List of all essential ArticleRef objects identifying components this section builds upon.
    Format: Each reference must point to a previously defined chapter, section, or subsection.
    Note: Circular dependencies are not permitted."""
    support_to: List[ArticleRef]
    """Required: List of all essential ArticleRef objects identifying components this section provides evidence for.
    Format: Each reference must point to a specific chapter, section, or subsection.
    Note: References form a directed acyclic graph in the document structure."""

    description: str = Field(...)
    """Description of the research component in academic style."""
    title: str = Field(...)
    """Title of the research component in academic style."""


class ArticleSubsectionOutline(ArticleOutlineBase):
    """Atomic research component specification for academic paper generation."""


class ArticleSectionOutline(ArticleOutlineBase):
    """A slightly more detailed research component specification for academic paper generation."""

    subsections: List[ArticleSubsectionOutline] = Field(min_length=1)
    """List of subsections, each containing a specific research component. Must contains at least 1 subsection, But do remember you should always add more subsection as required."""


class ArticleChapterOutline(ArticleOutlineBase):
    """Macro-structural unit implementing standard academic paper organization."""

    sections: List[ArticleSectionOutline] = Field(min_length=1)
    """Standard academic progression implementing chapter goals:
    1. Context Establishment
    2. Technical Presentation
    3. Empirical Validation
    4. Comparative Analysis
    5. Synthesis

    Must contains at least 1 sections, But do remember you should always add more section as required.
    """


class ArticleOutline(Display, CensoredAble, WithRef[ArticleProposal], PersistentAble):
    """Complete academic paper blueprint with hierarchical validation."""

    title: str = Field(...)
    """Title of the academic paper."""

    prospect: str = Field(...)
    """Consolidated research statement with four pillars:
    1. Problem Identification: Current limitations
    2. Methodological Response: Technical approach
    3. Empirical Validation: Evaluation strategy
    4. Scholarly Impact: Field contributions

    Example: 'Addressing NAS computational barriers through constrained
    differentiable search spaces, validated via cross-lingual MT experiments
    across 50+ languages, enabling efficient architecture discovery with
    60% reduced search costs.'"""

    chapters: List[ArticleChapterOutline]
    """List of ArticleChapterOutline objects representing the academic paper's structure."""

    abstract: str = Field(...)
    """The abstract is a concise summary of the academic paper's main findings."""

    def finalized_dump(self) -> str:
        """Generates standardized hierarchical markup for academic publishing systems.

        Implements ACL 2024 outline conventions with four-level structure:
        = Chapter Title (Level 1)
        == Section Title (Level 2)
        === Subsection Title (Level 3)
        ==== Subsubsection Title (Level 4)

        Returns:
            str: Strictly formatted outline with academic sectioning

        Example:
            = Methodology
            == Neural Architecture Search Framework
            === Differentiable Search Space
            ==== Constrained Optimization Parameters
            === Implementation Details
            == Evaluation Protocol
        """
        lines: List[str] = []
        for i, chapter in enumerate(self.chapters, 1):
            lines.append(f"= Chapter {i}: {chapter.title}")
            for j, section in enumerate(chapter.sections, 1):
                lines.append(f"== {i}.{j} {section.title}")
                for k, subsection in enumerate(section.subsections, 1):
                    lines.append(f"=== {i}.{j}.{k} {subsection.title}")
        return "\n".join(lines)

    def iter_dfs(self) -> Generator[ArticleOutlineBase, None, None]:
        """Iterates through the article outline in a depth-first manner.

        Returns:
            ArticleOutlineBase: Each component in the article outline.
        """
        for chapter in self.chapters:
            for section in chapter.sections:
                yield from section.subsections
                yield section
            yield chapter

    def resolve_ref_error(self) -> str:
        """Resolve reference errors in the article outline.

        Returns:
            str: Error message indicating reference errors in the article outline.

        Notes:
            This function is designed to find all invalid `ArticleRef` objs in `depend_on` and `support_to` fields, which will be added to the final error summary.
        """
        summary = ""
        for component in self.iter_dfs():
            for ref in component.depend_on:
                if not ref.deref(self):
                    summary += f"Invalid internal reference in {component.__class__.__name__} titled `{component.title}` at `depend_on` field, because the referred {ref.referring_type} is not exists within the article, see the original obj dump: {ref.model_dump()}\n"
            for ref in component.support_to:
                if not ref.deref(self):
                    summary += f"Invalid internal reference in {component.__class__.__name__} titled `{component.title}` at `support_to` field, because the referred {ref.referring_type} is not exists within the article, see the original obj dump: {ref.model_dump()}\n"

        return summary
