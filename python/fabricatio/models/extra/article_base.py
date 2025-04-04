"""A foundation for hierarchical document components with dependency tracking."""

from abc import ABC, abstractmethod
from enum import StrEnum
from itertools import chain
from typing import Generator, List, Optional, Self, Tuple, overload

from fabricatio.models.generic import (
    AsPrompt,
    Described,
    FinalizedDumpAble,
    Introspect,
    Language,
    ModelHash,
    PersistentAble,
    ProposedUpdateAble,
    ResolveUpdateConflict,
    SequencePatch,
    SketchedAble,
    Titled,
    WordCount,
)
from pydantic import Field


class ReferringType(StrEnum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"


type RefKey = Tuple[str, Optional[str], Optional[str]]


class ArticleRef(ProposedUpdateAble):
    """Reference to a specific chapter, section or subsection within the article. You SHALL not refer to an article component that is external and not present within our own article.

    Examples:
        - Referring to a chapter titled `Introduction`:
            Using Python
            ```python
            ArticleRef(chap="Introduction")
            ```
            Using JSON
            ```json
            {chap="Introduction"}
            ```
        - Referring to a section titled `Background` under the `Introduction` chapter:
            Using Python
            ```python
            ArticleRef(chap="Introduction", sec="Background")
            ```
            Using JSON
            ```json
            {chap="Introduction", sec="Background"}
            ```
        - Referring to a subsection titled `Related Work` under the `Background` section of the `Introduction` chapter:
            Using Python
            ```python
            ArticleRef(chap="Introduction", sec="Background", subsec="Related Work")
            ```
            Using JSON
            ```json
            {chap="Introduction", sec="Background", subsec="Related Work"}
            ```
    """

    chap: str
    """`title` Field of the referenced chapter"""
    sec: Optional[str] = None
    """`title` Field of the referenced section."""
    subsec: Optional[str] = None
    """`title` Field of the referenced subsection."""

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        self.chap = other.chap
        self.sec = other.sec
        self.subsec = other.subsec
        return self

    def deref(self, article: "ArticleBase") -> Optional["ArticleOutlineBase"]:
        """Dereference the reference to the actual section or subsection within the provided article.

        Args:
            article (ArticleOutline | Article): The article to dereference the reference from.

        Returns:
            ArticleMainBase | ArticleOutline | None: The dereferenced section or subsection, or None if not found.
        """
        chap = next((chap for chap in article.chapters if chap.title == self.chap), None)
        if self.sec is None or chap is None:
            return chap
        sec = next((sec for sec in chap.sections if sec.title == self.sec), None)
        if self.subsec is None or sec is None:
            return sec
        return next((subsec for subsec in sec.subsections if subsec.title == self.subsec), None)

    @property
    def referring_type(self) -> ReferringType:
        """Determine the type of reference based on the presence of specific attributes."""
        if self.subsec is not None:
            return ReferringType.SUBSECTION
        if self.sec is not None:
            return ReferringType.SECTION
        return ReferringType.CHAPTER


class ArticleMetaData(SketchedAble, Described, WordCount, Titled, Language):
    """Metadata for an article component."""

    description: str = Field(
        alias="elaboration",
        description=Described.model_fields["description"].description,
    )

    title: str = Field(alias="heading", description=Titled.model_fields["title"].description)

    aims: List[str]
    """List of writing aims of the research component in academic style."""

    support_to: List[ArticleRef]
    """List of references to other future components in this article that this component supports to."""
    depend_on: List[ArticleRef]
    """List of references to other previous components in this article that this component depends on."""


class ArticleRefSequencePatch(SequencePatch[ArticleRef]):
    """Patch for article refs."""


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
        self.aims.clear()
        self.aims.extend(other.aims)
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


class ArticleBase[T: ChapterBase](FinalizedDumpAble, AsPrompt, WordCount, Described, Titled, Language, ABC):
    """Base class for article outlines."""

    title: str = Field(alias="heading", description=Titled.model_fields["title"].description)
    description: str = Field(alias="abstract")
    """The abstract serves as a concise summary of an academic article, encapsulating its core purpose, methodologies, key results,
    and conclusions while enabling readers to rapidly assess the relevance and significance of the study.
    Functioning as the article's distilled essence, it succinctly articulates the research problem, objectives,
    and scope, providing a roadmap for the full text while also facilitating database indexing, literature reviews,
    and citation tracking through standardized metadata. Additionally, it acts as an accessibility gateway,
    allowing scholars to gauge the study's contribution to existing knowledge, its methodological rigor,
    and its broader implications without engaging with the entire manuscript, thereby optimizing scholarly communication efficiency."""

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

    def iter_support_on(self, rev: bool = False) -> Generator[ArticleRef, None, None]:
        """Iterates over all references that the article components support.

        Args:
            rev (bool): If True, iterate in reverse order.

        Yields:
            ArticleRef: Each reference that the article components support.
        """
        if rev:
            yield from chain(*[a.support_to for a in self.iter_dfs_rev()])
            return
        yield from chain(*[a.support_to for a in self.iter_dfs()])

    def iter_depend_on(self, rev: bool = False) -> Generator[ArticleRef, None, None]:
        """Iterates over all references that the article components depend on.

        Args:
            rev (bool): If True, iterate in reverse order.

        Yields:
            ArticleRef: Each reference that the article components depend on.
        """
        if rev:
            yield from chain(*[a.depend_on for a in self.iter_dfs_rev()])
            return
        yield from chain(*[a.depend_on for a in self.iter_dfs()])

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

    def gather_introspected(self) -> Optional[str]:
        """Gathers all introspected components in the article structure."""
        return "\n".join([i for component in self.chapters if (i := component.introspect())])

    @overload
    def find_illegal_ref(self, gather_identical: bool) -> Optional[Tuple[ArticleRef | List[ArticleRef], str]]: ...

    @overload
    def find_illegal_ref(self) -> Optional[Tuple[ArticleRef, str]]: ...

    def iter_chap_title(self) -> Generator[str, None, None]:
        """Iterates through all chapter titles in the article."""
        for chap in self.chapters:
            yield chap.title

    def iter_section_title(self) -> Generator[str, None, None]:
        """Iterates through all section titles in the article."""
        for _, sec in self.iter_sections():
            yield sec.title

    def iter_subsection_title(self) -> Generator[str, None, None]:
        """Iterates through all subsection titles in the article."""
        for _, _, subsec in self.iter_subsections():
            yield subsec.title

    def find_illegal_ref(self, gather_identical: bool = False) -> Optional[Tuple[ArticleRef | List[ArticleRef], str]]:
        """Finds the first illegal component in the outline.

        Returns:
            Tuple[ArticleOutlineBase, str]: A tuple containing the illegal component and an error message.
        """
        summary = ""
        chap_titles_set = set(self.iter_chap_title())
        sec_titles_set = set(self.iter_section_title())
        subsec_titles_set = set(self.iter_subsection_title())

        for component in self.iter_dfs_rev():
            for ref in chain(component.depend_on, component.support_to):
                if not ref.deref(self):
                    summary += f"Invalid internal reference in `{component.__class__.__name__}` titled `{component.title}`, because the referred {ref.referring_type} is not exists within the article, see the original obj dump: {ref.model_dump()}\n"

                    if ref.chap not in (chap_titles_set):
                        summary += f"Chapter titled `{ref.chap}` is not any of {chap_titles_set}\n"
                    if ref.sec and ref.sec not in (sec_titles_set):
                        summary += f"Section Titled `{ref.sec}` is not any of {sec_titles_set}\n"
                    if ref.subsec and ref.subsec not in (subsec_titles_set):
                        summary += f"Subsection Titled `{ref.subsec}` is not any of {subsec_titles_set}"

                if summary:
                    return (
                        (
                            [
                                identical_ref
                                for identical_ref in chain(self.iter_depend_on(), self.iter_support_on())
                                if identical_ref == ref
                            ],
                            summary,
                        )
                        if gather_identical
                        else (ref, summary)
                    )

        return None

    def gather_illegal_ref(self) -> Tuple[List[ArticleRef], str]:
        """Gathers all illegal references in the article."""
        summary = []
        chap_titles_set = set(self.iter_chap_title())
        sec_titles_set = set(self.iter_section_title())
        subsec_titles_set = set(self.iter_subsection_title())
        res_seq = []

        for component in self.iter_dfs():
            for ref in (
                r for r in chain(component.depend_on, component.support_to) if not r.deref(self) and r not in res_seq
            ):
                res_seq.append(ref)
                if ref.chap not in chap_titles_set:
                    summary.append(
                        f"Chapter titled `{ref.chap}` is not exist, since it is not any of {chap_titles_set}."
                    )
                if ref.sec and (ref.sec not in sec_titles_set):
                    summary.append(f"Section Titled `{ref.sec}` is not exist, since it is not any of {sec_titles_set}")
                if ref.subsec and (ref.subsec not in subsec_titles_set):
                    summary.append(
                        f"Subsection Titled `{ref.subsec}` is not exist, since it is not any of {subsec_titles_set}"
                    )

        return res_seq, "\n".join(summary)

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
