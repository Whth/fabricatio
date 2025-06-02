"""A foundation for hierarchical document components with dependency tracking."""

from abc import ABC
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Generator, List, Optional, Self, Tuple, Type

from fabricatio_capabilities.models.generic import (
    FinalizedDumpAble,
    ModelHash,
    PersistentAble,
    ProposedUpdateAble,
)
from fabricatio_core.fs import dump_text, safe_text_read
from fabricatio_core.fs.readers import extract_sections
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import (
    Described,
    Language,
    SketchedAble,
    Titled,
)
from fabricatio_core.rust import (
    detect_language,
    word_count,
)
from fabricatio_core.utils import fallback_kwargs, ok
from pydantic import Field

from fabricatio_typst.models.generic import AsPrompt, Introspect, WordCount
from fabricatio_typst.rust import (
    extract_body,
    replace_thesis_body,
    split_out_metadata,
    strip_comment,
    to_metadata,
)

ARTICLE_WRAPPER = "// =-=-=-=-=-=-=-=-=-="


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

    _unstructured_body: str = ""
    """Store the source of the unknown information."""

    @property
    def typst_metadata_comment(self) -> str:
        """Generates a comment for the metadata of the article component."""
        data = self.model_dump(
            include={"description", "aims", "expected_word_count"},
            by_alias=True,
        )
        return to_metadata({k: v for k, v in data.items() if v})

    @property
    def unstructured_body(self) -> str:
        """Returns the unstructured body of the article component."""
        return self._unstructured_body

    def update_unstructured_body[S: "ArticleMetaData"](self: S, body: str) -> S:
        """Update the unstructured body of the article component."""
        self._unstructured_body = body
        return self

    @property
    def language(self) -> str:
        """Get the language of the article component."""
        return detect_language(self.title)


class FromTypstCode(ArticleMetaData):
    """Base class for article components that can be created from a Typst code snippet."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Converts a Typst code snippet into an article component."""
        data, body = split_out_metadata(body)

        return cls(
            heading=title.strip(),
            **fallback_kwargs(data or {}, elaboration="", expected_word_count=word_count(body), aims=[]),
            **kwargs,
        )


class ToTypstCode(ArticleMetaData):
    """Base class for article components that can be converted to a Typst code snippet."""

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""
        return f"{self.title}\n{self.typst_metadata_comment}\n\n{self._unstructured_body}"


class ArticleOutlineBase(
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

    child_type: ClassVar[Type[SubSectionBase]]

    def to_typst_code(self) -> str:
        """Converts the section into a Typst formatted code snippet.

        Returns:
            str: The formatted Typst code snippet.
        """
        return f"== {super().to_typst_code()}" + "\n\n".join(subsec.to_typst_code() for subsec in self.subsections)

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Creates an Article object from the given Typst code."""
        raw = extract_sections(body, level=3, section_char="=")

        return (
            super()
            .from_typst_code(
                title,
                body,
                subsections=[cls.child_type.from_typst_code(*pack) for pack in raw],
            )
            .update_unstructured_body("" if raw else strip_comment(body))
        )

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

    @property
    def exact_word_count(self) -> int:
        """Returns the exact word count of the article section outline."""
        return sum(a.exact_word_count for a in self.subsections)


class ChapterBase[T: SectionBase](ArticleOutlineBase):
    """Base class for article chapters."""

    sections: List[T]
    """Sections of the chapter. Contains at least one section. You can also add more as needed."""
    child_type: ClassVar[Type[SectionBase]]

    def to_typst_code(self) -> str:
        """Converts the chapter into a Typst formatted code snippet for rendering."""
        return f"= {super().to_typst_code()}" + "\n\n".join(sec.to_typst_code() for sec in self.sections)

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Creates an Article object from the given Typst code."""
        raw_sec = extract_sections(body, level=2, section_char="=")

        return (
            super()
            .from_typst_code(
                title,
                body,
                sections=[cls.child_type.from_typst_code(*pack) for pack in raw_sec],
            )
            .update_unstructured_body("" if raw_sec else strip_comment(body))
        )

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

    @property
    def exact_word_count(self) -> int:
        """Calculates the total word count across all sections in the chapter.

        Returns:
            int: The cumulative word count of all sections.
        """
        return sum(a.exact_word_count for a in self.sections)


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

    child_type: ClassVar[Type[ChapterBase]]

    @property
    def language(self) -> str:
        """Get the language of the article."""
        if self.title:
            return super().language
        return self.chapters[0].language

    @property
    def exact_word_count(self) -> int:
        """Calculates the total word count across all chapters in the article.

        Returns:
            int: The cumulative word count of all chapters.
        """
        return sum(ch.exact_word_count for ch in self.chapters)

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Generates an article from the given Typst code."""
        raw = extract_sections(body, level=1, section_char="=")
        return (
            super()
            .from_typst_code(
                title,
                body,
                chapters=[cls.child_type.from_typst_code(*pack) for pack in raw],
            )
            .update_unstructured_body("" if raw else strip_comment(body))
        )

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
        return f"// #Title: {super().to_typst_code()}\n" + "\n\n".join(a.to_typst_code() for a in self.chapters)

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

    def update_article_file[S: "ArticleBase"](self: S, file: str | Path) -> S:
        """Update the article file."""
        file = Path(file)
        string = safe_text_read(file)
        if updated := replace_thesis_body(string, ARTICLE_WRAPPER, f"\n\n{self.to_typst_code()}\n\n"):
            dump_text(file, updated)
            logger.success(f"Successfully updated {file.as_posix()}.")
        else:
            logger.warning(f"Failed to update {file.as_posix()}. Please make sure there are paired `{ARTICLE_WRAPPER}`")
        return self

    @classmethod
    def from_article_file[S: "ArticleBase"](cls: Type[S], file: str | Path, title: str = "") -> S:
        """Load article from file."""
        file = Path(file)
        string = safe_text_read(file)
        return cls.from_typst_code(
            title, ok(extract_body(string, ARTICLE_WRAPPER), "Failed to extract body from file.")
        )
