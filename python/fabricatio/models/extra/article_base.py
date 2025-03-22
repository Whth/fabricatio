"""A foundation for hierarchical document components with dependency tracking."""

from abc import abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, List, Optional, Self, Union, final, overload

from fabricatio.models.generic import Base, CensoredAble, Display, PersistentAble
from pydantic import Field

if TYPE_CHECKING:
    from fabricatio.models.extra.article_main import Article
    from fabricatio.models.extra.article_outline import ArticleOutline


class ReferringType(StrEnum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER: str = "chapter"
    SECTION: str = "section"
    SUBSECTION: str = "subsection"


class ArticleRef(CensoredAble):
    """Reference to a specific chapter, section or subsection within the article. You SHALL not refer to an article component that is external and not present within our own article.

    Examples:
        - Referring to a chapter titled `Introduction`:
            Using Python
            ```python
            ArticleRef(referred_chapter_title="Introduction")
            ```
            Using JSON
            ```json
            {referred_chapter_title="Introduction"}
            ```
        - Referring to a section titled `Background` under the `Introduction` chapter:
            Using Python
            ```python
            ArticleRef(referred_chapter_title="Introduction", referred_section_title="Background")
            ```
            Using JSON
            ```json
            {referred_chapter_title="Introduction", referred_section_title="Background"}
            ```
        - Referring to a subsection titled `Related Work` under the `Background` section of the `Introduction` chapter:
            Using Python
            ```python
            ArticleRef(referred_chapter_title="Introduction", referred_section_title="Background", referred_subsection_title="Related Work")
            ```
            Using JSON
            ```json
            {referred_chapter_title="Introduction", referred_section_title="Background", referred_subsection_title="Related Work"}
            ```
    """

    referred_subsection_title: Optional[str] = None
    """`title` Field of the referenced subsection."""

    referred_section_title: Optional[str] = None
    """`title` Field of the referenced section."""

    referred_chapter_title: str
    """`title` Field of the referenced chapter"""

    def __hash__(self) -> int:
        """Overrides the default hash function to ensure consistent hashing across instances."""
        return hash((self.referred_chapter_title, self.referred_section_title, self.referred_subsection_title))

    @overload
    def deref(self, article: "Article") -> Optional["ArticleMainBase"]:
        """Dereference the reference to the actual section or subsection within the provided article."""

    @overload
    def deref(self, article: "ArticleOutline") -> Optional["ArticleOutlineBase"]:
        """Dereference the reference to the actual section or subsection within the provided article."""

    def deref(
        self, article: Union["ArticleOutline", "Article"]
    ) -> Union["ArticleOutlineBase", "ArticleMainBase", None]:
        """Dereference the reference to the actual section or subsection within the provided article.

        Args:
            article (ArticleOutline | Article): The article to dereference the reference from.

        Returns:
            ArticleMainBase | ArticleOutline | None: The dereferenced section or subsection, or None if not found.
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


class SubSectionBase(Base):
    """Base class for article sections and subsections."""


class SectionBase[T: SubSectionBase](Base):
    """Base class for article sections and subsections."""

    subsections: List[T] = Field(min_length=1)
    """List of subsections, each containing a specific research component. Must contains at least 1 subsection, But do remember you should always add more subsection as required."""


class ChapterBase[T: SectionBase](Base):
    """Base class for article chapters."""

    sections: List[T] = Field(min_length=1)
    """List of sections, each containing a specific research component. Must contains at least 1 section, But do remember you should always add more section as required."""


class ArticleBase[T: ChapterBase](Base):
    """Base class for article outlines."""

    chapters: List[T] = Field(min_length=5)
    """List of chapters, each containing a specific research component. Must contains at least 5 chapters, But do remember you should always add more chapter as required."""


class ArticleOutlineBase(Base):
    """Base class for article outlines."""

    title: str
    """Title of the research component in academic style."""
    description: str
    """Description of the research component in academic style."""

    support_to: List[ArticleRef]
    """Required: List of all essential ArticleRef objects identifying components this section provides evidence for.
    Format: Each reference must point to a specific chapter, section, or subsection.
    Note: References form a directed acyclic graph in the document structure."""
    depend_on: List[ArticleRef]
    """Required: List of all essential ArticleRef objects identifying components this section builds upon.
    Format: Each reference must point to a previously defined chapter, section, or subsection.
    Note: Circular dependencies are not permitted."""

    writing_aim: List[str]
    """Required: List of specific rhetorical objectives (3-5 items).
    Format: Each item must be an actionable phrase starting with a verb.
    Example: ['Establish metric validity', 'Compare with baseline approaches',
             'Justify threshold selection']"""


class ArticleMainBase(CensoredAble, Display, ArticleOutlineBase, PersistentAble):
    """Foundation for hierarchical document components with dependency tracking."""

    @abstractmethod
    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""

    def _update_pre_check(self, other: Self) -> Self:
        if not isinstance(other, self.__class__):
            raise TypeError(f"Cannot update from a non-{self.__class__} instance.")
        if self.title != other.title:
            raise ValueError("Cannot update from a different title.")
        return self

    @abstractmethod
    def resolve_update_error(self, other: Self) -> str:
        """Resolve update errors in the article outline.

        Returns:
            str: Error message indicating update errors in the article outline.
        """

    @abstractmethod
    def _update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""

    @final
    def update_from(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        return self._update_pre_check(other)._update_from_inner(other)

    def __eq__(self, other: "ArticleMainBase") -> bool:
        """Compares two ArticleBase objects based on their model_dump_json representation."""
        return self.model_dump_json() == other.model_dump_json()

    def __hash__(self) -> int:
        """Calculates a hash value for the ArticleBase object based on its model_dump_json representation."""
        return hash(self.model_dump_json())
