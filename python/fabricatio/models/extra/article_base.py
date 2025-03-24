"""A foundation for hierarchical document components with dependency tracking."""

from abc import abstractmethod
from enum import StrEnum
from functools import cache
from itertools import chain
from typing import Generator, List, Optional, Self, Tuple

from fabricatio.models.generic import (
    CensoredAble,
    Display,
    FinalizedDumpAble,
    Introspect,
    ModelHash,
    PersistentAble,
    ProposedUpdateAble,
    ResolveUpdateConflict,
)


class ReferringType(StrEnum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"


type RefKey = Tuple[str, Optional[str], Optional[str]]


@cache
class ArticleRef(CensoredAble, Display, ProposedUpdateAble):
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

    referred_chapter_title: str
    """`title` Field of the referenced chapter"""
    referred_section_title: Optional[str] = None
    """`title` Field of the referenced section."""
    referred_subsection_title: Optional[str] = None
    """`title` Field of the referenced subsection."""

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        self.referred_chapter_title = other.referred_chapter_title
        self.referred_section_title = other.referred_section_title
        self.referred_subsection_title = other.referred_subsection_title
        return self

    def deref(self, article: "ArticleBase") -> Optional["ArticleOutlineBase"]:
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


class ArticleMetaData(CensoredAble, Display):
    """Metadata for an article component."""

    description: str
    """Description of the research component in academic style."""

    support_to: List[ArticleRef]
    """List of references to other component of this articles that this component supports."""
    depend_on: List[ArticleRef]
    """List of references to other component of this articles that this component depends on."""

    writing_aim: List[str]
    """List of writing aims of the research component in academic style."""
    title: str
    """Do not add any prefix or suffix to the title. should not contain special characters."""


class ArticleOutlineBase(
    ArticleMetaData,
    ResolveUpdateConflict,
    ProposedUpdateAble,
    PersistentAble,
    ModelHash,
    Introspect,
):
    """Base class for article outlines."""

    @property
    def metadata(self) -> ArticleMetaData:
        """Returns the metadata of the article component."""
        return ArticleMetaData.model_validate(self, from_attributes=True)

    def update_metadata(self, other: ArticleMetaData) -> Self:
        """Updates the metadata of the current instance with the attributes of another instance."""
        self.support_to.clear()
        self.support_to.extend(other.support_to)
        self.depend_on.clear()
        self.depend_on.extend(other.depend_on)
        self.writing_aim.clear()
        self.writing_aim.extend(other.writing_aim)
        self.description = other.description
        return self

    def display_metadata(self) -> str:
        """Displays the metadata of the current instance."""
        return self.model_dump_json(
            indent=1, include={"title", "writing_aim", "description", "support_to", "depend_on"}
        )

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        return self.update_metadata(other)

    @abstractmethod
    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""


class SubSectionBase(ArticleOutlineBase):
    """Base class for article sections and subsections."""

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""
        return f"=== {self.title}\n"

    def introspect(self) -> str:
        """Introspects the article subsection outline."""
        return ""

    def resolve_update_conflict(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        if self.title != other.title:
            return f"Title mismatched, expected `{self.title}`, got `{other.title}`"
        return ""


class SectionBase[T: SubSectionBase](ArticleOutlineBase):
    """Base class for article sections and subsections."""

    subsections: List[T]
    """Subsections of the section. Contains at least one subsection. You can also add more as needed."""

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
        super().update_from_inner(other)
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


class ChapterBase[T: SectionBase](ArticleOutlineBase):
    """Base class for article chapters."""

    sections: List[T]
    """Sections of the chapter. Contains at least one section. You can also add more as needed."""

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


class ArticleBase[T: ChapterBase](FinalizedDumpAble):
    """Base class for article outlines."""

    language: str
    """Written language of the article. SHALL be aligned to the language of the article proposal provided."""

    title: str
    """Title of the academic paper."""

    prospect: str
    """Consolidated research statement with four pillars:
    1. Problem Identification: Current limitations
    2. Methodological Response: Technical approach
    3. Empirical Validation: Evaluation strategy
    4. Scholarly Impact: Field contributions
    """

    abstract: str
    """The abstract is a concise summary of the academic paper's main findings."""
    chapters: List[T]
    """Chapters of the article. Contains at least one chapter. You can also add more as needed."""

    def iter_dfs_rev(
        self,
    ) -> Generator[ArticleOutlineBase, None, None]:
        """Performs a depth-first search (DFS) through the article structure in reverse order.

        Returns:
            Generator[ArticleMainBase]: Each component in the article structure in reverse order.
        """
        for chap in self.chapters:
            for sec in chap.sections:
                yield from sec.subsections
                yield sec
            yield chap

    def iter_dfs(self) -> Generator[ArticleOutlineBase, None, None]:
        """Performs a depth-first search (DFS) through the article structure.

        Returns:
            Generator[ArticleMainBase]: Each component in the article structure.
        """
        for chap in self.chapters:
            yield chap
            for sec in chap.sections:
                yield sec
                yield from sec.subsections

    def iter_sections(self) -> Generator[Tuple[ChapterBase, SectionBase], None, None]:
        """Iterates through all sections in the article.

        Returns:
            Generator[ArticleOutlineBase]: Each section in the article.
        """
        for chap in self.chapters:
            for sec in chap.sections:
                yield chap, sec

    def iter_subsections(self) -> Generator[Tuple[ChapterBase, SectionBase, SubSectionBase], None, None]:
        """Iterates through all subsections in the article.

        Returns:
            Generator[ArticleOutlineBase]: Each subsection in the article.
        """
        for chap, sec in self.iter_sections():
            for subsec in sec.subsections:
                yield chap, sec, subsec

    def find_introspected(self) -> Optional[Tuple[ArticleOutlineBase, str]]:
        """Finds the first introspected component in the article structure."""
        summary = ""
        for component in self.iter_dfs_rev():
            summary += component.introspect()
            if summary:
                return component, summary
        return None

    def find_illegal_ref(self) -> Optional[Tuple[ArticleRef, str]]:
        """Finds the first illegal component in the outline.

        Returns:
            Tuple[ArticleOutlineBase, str]: A tuple containing the illegal component and an error message.
        """
        summary = ""
        for component in self.iter_dfs_rev():
            for ref in chain(component.depend_on, component.support_to):
                if not ref.deref(self):
                    summary += f"Invalid internal reference in `{component.__class__.__name__}` titled `{component.title}`, because the referred {ref.referring_type} is not exists within the article, see the original obj dump: {ref.model_dump()}\n"
                if summary:
                    return ref, summary
        return None

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
        return "\n\n".join(a.to_typst_code() for a in self.chapters)
