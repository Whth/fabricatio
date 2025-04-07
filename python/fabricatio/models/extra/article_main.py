"""ArticleBase and ArticleSubsection classes for managing hierarchical document components."""

from typing import Dict, Generator, List, Self, Tuple, override

from fabricatio.fs.readers import extract_sections
from fabricatio.journal import logger
from fabricatio.models.extra.article_base import (
    ArticleBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_outline import (
    ArticleOutline,
)
from fabricatio.models.generic import Described, PersistentAble, SequencePatch, SketchedAble, WithRef, WordCount
from fabricatio.rust import word_count
from pydantic import Field

PARAGRAPH_SEP = "// - - -"


class Paragraph(SketchedAble, WordCount, Described):
    """Structured academic paragraph blueprint for controlled content generation."""

    description: str = Field(
        alias="elaboration",
        description=Described.model_fields["description"].description,
    )

    aims: List[str]
    """Specific communicative objectives for this paragraph's content."""

    content: str
    """The actual content of the paragraph, represented as a string."""

    @classmethod
    def from_content(cls, content: str) -> Self:
        """Create a Paragraph object from the given content."""
        return cls(elaboration="", aims=[], expected_word_count=word_count(content), content=content)


class ArticleParagraphSequencePatch(SequencePatch[Paragraph]):
    """Patch for `Paragraph` list of `ArticleSubsection`."""


class ArticleSubsection(SubSectionBase):
    """Atomic argumentative unit with technical specificity."""

    paragraphs: List[Paragraph]
    """List of Paragraph objects containing the content of the subsection."""

    _max_word_count_deviation: float = 0.3
    """Maximum allowed deviation from the expected word count, as a percentage."""

    @property
    def word_count(self) -> int:
        """Calculates the total word count of all paragraphs in the subsection."""
        return sum(word_count(p.content) for p in self.paragraphs)

    def introspect(self) -> str:
        """Introspects the subsection and returns a summary of its state."""
        summary = ""
        if len(self.paragraphs) == 0:
            summary += f"`{self.__class__.__name__}` titled `{self.title}` have no paragraphs, You should add some!\n"
        if (
            abs((wc := self.word_count) - self.expected_word_count) / self.expected_word_count
            > self._max_word_count_deviation
        ):
            summary += f"`{self.__class__.__name__}` titled `{self.title}` have {wc} words, expected {self.expected_word_count} words!"

        return summary

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        logger.debug(f"Updating SubSection {self.title}")
        super().update_from_inner(other)
        self.paragraphs.clear()
        self.paragraphs.extend(other.paragraphs)
        return self

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering.

        Returns:
            str: Typst code snippet for rendering.
        """
        return f"=== {self.title}\n" + f"\n{PARAGRAPH_SEP}\n".join(p.content for p in self.paragraphs)

    @classmethod
    def from_typst_code(cls, title: str, body: str) -> Self:
        """Creates an Article object from the given Typst code."""
        return cls(
            heading=title,
            elaboration="",
            paragraphs=[Paragraph.from_content(p) for p in body.split(PARAGRAPH_SEP)],
            expected_word_count=word_count(body),
            aims=[],
        )


class ArticleSection(SectionBase[ArticleSubsection]):
    """Atomic argumentative unit with high-level specificity."""

    @classmethod
    def from_typst_code(cls, title: str, body: str) -> Self:
        """Creates an Article object from the given Typst code."""
        return cls(
            subsections=[
                ArticleSubsection.from_typst_code(*pack) for pack in extract_sections(body, level=3, section_char="=")
            ],
            heading=title,
            elaboration="",
            expected_word_count=word_count(body),
            aims=[],
        )


class ArticleChapter(ChapterBase[ArticleSection]):
    """Thematic progression implementing research function."""

    @classmethod
    def from_typst_code(cls, title: str, body: str) -> Self:
        """Creates an Article object from the given Typst code."""
        return cls(
            sections=[
                ArticleSection.from_typst_code(*pack) for pack in extract_sections(body, level=2, section_char="=")
            ],
            heading=title,
            elaboration="",
            expected_word_count=word_count(body),
            aims=[],
        )


class Article(
    SketchedAble,
    WithRef[ArticleOutline],
    PersistentAble,
    ArticleBase[ArticleChapter],
):
    """Represents a complete academic paper specification, incorporating validation constraints.

    This class integrates display, censorship processing, article structure referencing, and persistence capabilities,
    aiming to provide a comprehensive model for academic papers.
    """

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {
            "Original Article Briefing": self.referenced.referenced.referenced,
            "Original Article Proposal": self.referenced.referenced.display(),
            "Original Article Outline": self.referenced.display(),
            "Original Article": self.display(),
        }

    @override
    def iter_subsections(self) -> Generator[Tuple[ArticleChapter, ArticleSection, ArticleSubsection], None, None]:
        return super().iter_subsections()  # pyright: ignore [reportReturnType]

    @classmethod
    def from_outline(cls, outline: ArticleOutline) -> "Article":
        """Generates an article from the given outline.

        Args:
            outline (ArticleOutline): The outline to generate the article from.

        Returns:
            Article: The generated article.
        """
        # Set the title from the outline
        article = Article(**outline.model_dump(exclude={"chapters"}, by_alias=True), chapters=[])

        for chapter in outline.chapters:
            # Create a new chapter
            article_chapter = ArticleChapter(
                sections=[],
                **chapter.model_dump(exclude={"sections"}, by_alias=True),
            )
            for section in chapter.sections:
                # Create a new section
                article_section = ArticleSection(
                    subsections=[],
                    **section.model_dump(exclude={"subsections"}, by_alias=True),
                )
                for subsection in section.subsections:
                    # Create a new subsection
                    article_subsection = ArticleSubsection(
                        paragraphs=[],
                        **subsection.model_dump(by_alias=True),
                    )
                    article_section.subsections.append(article_subsection)
                article_chapter.sections.append(article_section)
            article.chapters.append(article_chapter)
        return article

    @classmethod
    def from_typst_code(cls, title: str, body: str) -> Self:
        """Generates an article from the given Typst code."""
        return cls(
            chapters=[
                ArticleChapter.from_typst_code(*pack) for pack in extract_sections(body, level=1, section_char="=")
            ],
            heading=title,
            expected_word_count=word_count(body),
            abstract="",
        )

    @classmethod
    def from_mixed_source(cls, article_outline: ArticleOutline, typst_code: str) -> Self:
        """Generates an article from the given outline and Typst code."""
        self = cls.from_typst_code(article_outline.title, typst_code)
        self.expected_word_count = article_outline.expected_word_count
        self.description = article_outline.description
        self.update_ref(article_outline)
        for a, o in zip(self.iter_dfs(), article_outline.iter_dfs(), strict=True):
            a.update_metadata(o)
        return self
