"""A foundation for hierarchical document components with dependency tracking."""

from abc import ABC
from enum import StrEnum
from typing import Generator, List, Optional, Self, Tuple

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
    SketchedAble,
    Titled,
    WordCount,
)
from fabricatio.rust import split_out_metadata, to_metadata, word_count
from fabricatio.utils import fallback_kwargs
from pydantic import Field


class ReferringType(StrEnum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"


type RefKey = Tuple[str, Optional[str], Optional[str]]


class ArticleMetaData(SketchedAble, Described, WordCount, Titled, Language):
    """Metadata for an article component."""

    description: str = Field(
        alias="elaboration",
        description=Described.model_fields["description"].description,
    )

    title: str = Field(alias="heading", description=Titled.model_fields["title"].description)

    aims: List[str]
    """List of writing aims of the research component in academic style."""

    @property
    def typst_metadata_comment(self) -> str:
        """Generates a comment for the metadata of the article component."""
        return to_metadata(self.model_dump(include={"description", "aims", "expected_word_count"}, by_alias=True))


class FromTypstCode(ArticleMetaData):
    """Base class for article components that can be created from a Typst code snippet."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Converts a Typst code snippet into an article component."""
        data, body = split_out_metadata(body)

        return cls(
            heading=title,
            **fallback_kwargs(
                data or {},
                elaboration="",
                expected_word_count=word_count(body),
                aims=[],
            ),
            **kwargs,
        )


class ToTypstCode(ArticleMetaData):
    """Base class for article components that can be converted to a Typst code snippet."""

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""
        return f"{self.title}\n{self.typst_metadata_comment}\n"


class ArticleOutlineBase(
    ResolveUpdateConflict,
    ProposedUpdateAble,
    PersistentAble,
    ModelHash,
    Introspect,
    FromTypstCode,
    ToTypstCode,
    ABC,
):
    """Base class for article outlines."""

    @property
    def metadata(self) -> ArticleMetaData:
        """Returns the metadata of the article component."""
        return ArticleMetaData.model_validate(self, from_attributes=True)

    def update_metadata(self, other: ArticleMetaData) -> Self:
        """Updates the metadata of the current instance with the attributes of another instance."""
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


class SubSectionBase(ArticleOutlineBase):
    """Base class for article sections and subsections."""

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""
        return f"=== {super().to_typst_code()}"

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
        return f"== {super().to_typst_code()}" + "\n\n".join(subsec.to_typst_code() for subsec in self.subsections)

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
        return f"= {super().to_typst_code()}" + "\n\n".join(sec.to_typst_code() for sec in self.sections)

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


class ArticleBase[T: ChapterBase](FinalizedDumpAble, AsPrompt, FromTypstCode, ToTypstCode, ABC):
    """Base class for article outlines."""

    description: str = Field(
        alias="elaboration",
    )
    """The abstract of this article, which serves as a concise summary of an academic article, encapsulating its core purpose, methodologies, key results,
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

    def to_typst_code(self) -> str:
        """Generates the Typst code representation of the article."""
        return f"// #{super().to_typst_code()}\n\n" + "\n\n".join(a.to_typst_code() for a in self.chapters)

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
        return self.to_typst_code()

    def avg_chap_wordcount[S: "ArticleBase"](self: S) -> S:
        """Set all chap have same word count sum up to be `self.expected_word_count`."""
        avg = int(self.expected_word_count / len(self.chapters))
        for c in self.chapters:
            c.expected_word_count = avg
        return self

    def avg_sec_wordcount[S: "ArticleBase"](self: S) -> S:
        """Set all sec have same word count sum up to be `self.expected_word_count`."""
        for c in self.chapters:
            avg = int(c.expected_word_count / len(c.sections))
            for s in c.sections:
                s.expected_word_count = avg
        return self

    def avg_subsec_wordcount[S: "ArticleBase"](self: S) -> S:
        """Set all subsec have same word count sum up to be `self.expected_word_count`."""
        for _, s in self.iter_sections():
            avg = int(s.expected_word_count / len(s.subsections))
            for ss in s.subsections:
                ss.expected_word_count = avg
        return self

    def avg_wordcount_recursive[S: "ArticleBase"](self: S) -> S:
        """Set all chap, sec, subsec have same word count sum up to be `self.expected_word_count`."""
        return self.avg_chap_wordcount().avg_sec_wordcount().avg_subsec_wordcount()
