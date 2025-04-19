"""ArticleBase and ArticleSubsection classes for managing hierarchical document components."""

from typing import Dict, Generator, List, Self, Tuple, override

from fabricatio.decorators import precheck_package
from fabricatio.fs.readers import extract_sections
from fabricatio.journal import logger
from fabricatio.models.extra.article_base import (
    ArticleBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_outline import (
    ArticleChapterOutline,
    ArticleOutline,
    ArticleSectionOutline,
    ArticleSubsectionOutline,
)
from fabricatio.models.generic import Described, PersistentAble, SequencePatch, SketchedAble, WithRef, WordCount
from fabricatio.rust import (
    convert_all_block_tex,
    convert_all_inline_tex,
    fix_misplaced_labels,
    split_out_metadata,
    word_count,
)
from pydantic import Field, NonNegativeInt

PARAGRAPH_SEP = "\n\n// - - -\n\n"


class Paragraph(SketchedAble, WordCount, Described):
    """Structured academic paragraph blueprint for controlled content generation."""

    expected_word_count: NonNegativeInt = 0
    """The expected word count of this paragraph, 0 means not specified"""

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
        return super().to_typst_code() + PARAGRAPH_SEP.join(p.content for p in self.paragraphs)

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Creates an Article object from the given Typst code."""
        _, para_body = split_out_metadata(body)

        return super().from_typst_code(
            title,
            body,
            paragraphs=[Paragraph.from_content(p) for p in para_body.split(PARAGRAPH_SEP)],
        )


class ArticleSection(SectionBase[ArticleSubsection]):
    """Atomic argumentative unit with high-level specificity."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Creates an Article object from the given Typst code."""
        return super().from_typst_code(
            title,
            body,
            subsections=[
                ArticleSubsection.from_typst_code(*pack) for pack in extract_sections(body, level=3, section_char="=")
            ],
        )


class ArticleChapter(ChapterBase[ArticleSection]):
    """Thematic progression implementing research function."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Creates an Article object from the given Typst code."""
        return super().from_typst_code(
            title,
            body,
            sections=[
                ArticleSection.from_typst_code(*pack) for pack in extract_sections(body, level=2, section_char="=")
            ],
        )


class Article(
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

    def convert_tex(self) -> Self:
        """Convert tex to typst code."""
        for _, _, subsec in self.iter_subsections():
            for p in subsec.paragraphs:
                p.content = fix_misplaced_labels(p.content)
                p.content = convert_all_inline_tex(p.content)
                p.content = convert_all_block_tex(p.content)
        return self

    @override
    def iter_subsections(self) -> Generator[Tuple[ArticleChapter, ArticleSection, ArticleSubsection], None, None]:
        return super().iter_subsections()  # pyright: ignore [reportReturnType]

    def extrac_outline(self) -> ArticleOutline:
        """Extract outline from article."""
        # Create an empty list to hold chapter outlines
        chapters = []

        # Iterate through each chapter in the article
        for chapter in self.chapters:
            # Create an empty list to hold section outlines
            sections = []

            # Iterate through each section in the chapter
            for section in chapter.sections:
                # Create an empty list to hold subsection outlines
                subsections = []

                # Iterate through each subsection in the section
                for subsection in section.subsections:
                    # Create a subsection outline and add it to the list
                    subsections.append(
                        ArticleSubsectionOutline(**subsection.model_dump(exclude={"paragraphs"}, by_alias=True))
                    )

                # Create a section outline and add it to the list
                sections.append(
                    ArticleSectionOutline(
                        **section.model_dump(exclude={"subsections"}, by_alias=True),
                        subsections=subsections,
                    )
                )

            # Create a chapter outline and add it to the list
            chapters.append(
                ArticleChapterOutline(
                    **chapter.model_dump(exclude={"sections"}, by_alias=True),
                    sections=sections,
                )
            )

        # Create and return the article outline
        return ArticleOutline(
            **self.model_dump(exclude={"chapters"}, by_alias=True),
            chapters=chapters,
        )

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
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Generates an article from the given Typst code."""
        return super().from_typst_code(
            title,
            body,
            chapters=[
                ArticleChapter.from_typst_code(*pack) for pack in extract_sections(body, level=1, section_char="=")
            ],
        )

    @classmethod
    def from_mixed_source(cls, article_outline: ArticleOutline, typst_code: str) -> Self:
        """Generates an article from the given outline and Typst code."""
        self = cls.from_typst_code(article_outline.title, typst_code)
        self.expected_word_count = article_outline.expected_word_count
        self.description = article_outline.description
        for a, o in zip(self.iter_dfs(), article_outline.iter_dfs(), strict=True):
            a.update_metadata(o)
        return self.update_ref(article_outline)

    @precheck_package(
        "questionary", "'questionary' is required to run this function. Have you installed `fabricatio[qa]`?."
    )
    async def edit_titles(self) -> Self:
        """Edits the titles of the article."""
        from questionary import text

        for a in self.iter_dfs():
            a.title = await text(f"Edit `{a.title}`.", default=a.title).ask_async() or a.title
        return self
