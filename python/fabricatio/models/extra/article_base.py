"""A foundation for hierarchical document components with dependency tracking."""
from abc import ABC
from enum import StrEnum
from typing import TYPE_CHECKING, Generator, List, Optional, Self, Union, overload

from fabricatio.models.generic import (
    Base,
    CensoredAble,
    Display,
    Introspect,
    ModelHash,
    PersistentAble,
    ProposedAble,
    ResolveUpdateConflict,
    UpdateFrom,
)

if TYPE_CHECKING:
    from fabricatio.models.extra.article_main import Article
    from fabricatio.models.extra.article_outline import ArticleOutline


class ReferringType(StrEnum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"


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


class SubSectionBase(
    UpdateFrom,
    Introspect,
):
    """Base class for article sections and subsections."""

    title: str
    """Title of the subsection, do not add any prefix or suffix to the title. should not contain special characters."""

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""
        return f"=== {self.title}\n"

    def update_from_inner(self, other: Self) -> Self:
        return self

    def introspect(self) -> str:
        """Introspects the article subsection outline."""
        return ""

    def resolve_update_conflict(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        if self.title != other.title:
            return f"Title mismatched, expected `{self.title}`, got `{other.title}`"
        return ""


class SectionBase[T: SubSectionBase](
    UpdateFrom,
    Introspect,
):
    """Base class for article sections and subsections."""

    subsections: List[T]
    """Subsections of the section. Contains at least one subsection. You can also add more as needed."""
    title: str
    """Title of the section, do not add any prefix or suffix to the title. should not contain special characters."""

    def to_typst_code(self) -> str:
        """Converts the section into a Typst formatted code snippet.

        Returns:
            str: The formatted Typst code snippet.
        """
        return f"== {self.title}\n" + "\n\n".join(subsec.to_typst_code() for subsec in self.subsections)

    def resolve_update_conflict(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        out = ""
        if self.title != other.title:
            out += f"Title mismatched, expected `{self.title}`, got `{other.title}`"
        if len(self.subsections) != len(other.subsections):
            out += f"Section count mismatched, expected `{len(self.subsections)}`, got `{len(other.subsections)}`"
        return out or "\n".join(
            [
                conf
                for s, o in zip(self.subsections, other.subsections, strict=True)
                if (conf := s.resolve_update_conflict(o))
            ]
        )

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if len(self.subsections) == 0:
            self.subsections = other.subsections
            return self

        for self_subsec, other_subsec in zip(self.subsections, other.subsections, strict=True):
            self_subsec.update_from(other_subsec)
        return self

    def introspect(self) -> str:
        """Introspects the article section outline."""
        if len(self.subsections) == 0:
            return f"Section `{self.title}` contains no subsections, expected at least one, but got 0, you can add one or more as needed."
        return ""


class ChapterBase[T: SectionBase](
    UpdateFrom,
    Introspect,
):
    """Base class for article chapters."""

    sections: List[T]
    """Sections of the chapter. Contains at least one section. You can also add more as needed."""
    title: str
    """Title of the chapter, do not add any prefix or suffix to the title. should not contain special characters."""
    def to_typst_code(self) -> str:
        """Converts the chapter into a Typst formatted code snippet for rendering."""
        return f"= {self.title}\n" + "\n\n".join(sec.to_typst_code() for sec in self.sections)

    def resolve_update_conflict(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        out = ""

        if self.title != other.title:
            out += f"Title mismatched, expected `{self.title}`, got `{other.title}`"
        if len(self.sections) == len(other.sections):
            out += f"Chapter count mismatched, expected `{len(self.sections)}`, got `{len(other.sections)}`"

        return out or "\n".join(
            [conf for s, o in zip(self.sections, other.sections, strict=True) if (conf := s.resolve_update_conflict(o))]
        )

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if len(self.sections) == 0:
            self.sections = other.sections
            return self

        for self_sec, other_sec in zip(self.sections, other.sections, strict=True):
            self_sec.update_from(other_sec)
        return self

    def introspect(self) -> str:
        """Introspects the article chapter outline."""
        if len(self.sections) == 0:
            return f"Chapter `{self.title}` contains no sections, expected at least one, but got 0, you can add one or more as needed."
        return ""


class ArticleBase[T: ChapterBase](Base):
    """Base class for article outlines."""

    chapters: List[T]
    """Chapters of the article. Contains at least one chapter. You can also add more as needed."""
    title: str
    """Title of the article outline, do not add any prefix or suffix to the title. should not contain special characters."""

    def iter_dfs(
        self,
    ) -> Generator[ChapterBase | SectionBase | SubSectionBase, None, None]:
        """Performs a depth-first search (DFS) through the article structure.

        Returns:
            Generator[ArticleMainBase]: Each component in the article structure.
        """
        for chap in self.chapters:
            for sec in chap.sections:
                yield from sec.subsections
                yield sec
            yield chap


class ArticleOutlineBase(
    CensoredAble,
    UpdateFrom,
    ResolveUpdateConflict,
    ProposedAble,
    PersistentAble,
    Display,
    ModelHash,
    ABC,
):
    """Base class for article outlines."""

    description: str
    """Description of the research component in academic style."""

    support_to: List[ArticleRef]
    """List of references to other component of this articles that this component supports."""
    depend_on: List[ArticleRef]
    """List of references to other component of this articles that this component depends on."""

    writing_aim: List[str]
    """List of writing aims of the research component in academic style."""

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        self.support_to.clear()
        self.support_to.extend(other.support_to)
        self.depend_on.clear()
        self.depend_on.extend(other.depend_on)
        self.writing_aim.clear()
        self.writing_aim.extend(other.writing_aim)
        self.description = other.description
        return self
