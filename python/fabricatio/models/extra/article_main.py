"""ArticleBase and ArticleSubsection classes for managing hierarchical document components."""

from itertools import chain
from typing import Dict, Generator, List, Self, Tuple, override

from fabricatio.fs.readers import extract_sections
from fabricatio.journal import logger
from fabricatio.models.extra.article_base import (
    ArticleBase,
    ArticleOutlineBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_outline import (
    ArticleOutline,
)
from fabricatio.models.generic import Described, PersistentAble, SequencePatch, SketchedAble, WithRef, WordCount
from fabricatio.rust import detect_language, word_count
from fabricatio.utils import ok
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
        if abs((wc := self.word_count) - self.expected_word_count) / self.expected_word_count > self._max_word_count_deviation:
            summary += (
                f"`{self.__class__.__name__}` titled `{self.title}` have {wc} words, expected {self.word_count} words!"
            )

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
    def from_typst_code(cls, title: str, body: str, language: str) -> Self:
        """Creates an Article object from the given Typst code."""
        return cls(
            heading=title,
            elaboration="",
            paragraphs=[Paragraph.from_content(p) for p in body.split(PARAGRAPH_SEP)],
            expected_word_count=word_count(body),
            language=language,
            aims=[],
            support_to=[],
            depend_on=[],
        )


class ArticleSection(SectionBase[ArticleSubsection]):
    """Atomic argumentative unit with high-level specificity."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, language: str) -> Self:
        """Creates an Article object from the given Typst code."""
        return cls(
            subsections=[
                ArticleSubsection.from_typst_code(*pack, language=language)
                for pack in extract_sections(body, level=3, section_char="=")
            ],
            heading=title,
            elaboration="",
            expected_word_count=word_count(body),
            language=language,
            aims=[],
            support_to=[],
            depend_on=[],
        )


class ArticleChapter(ChapterBase[ArticleSection]):
    """Thematic progression implementing research function."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, language: str) -> Self:
        """Creates an Article object from the given Typst code."""
        return cls(
            sections=[
                ArticleSection.from_typst_code(*pack, language=language)
                for pack in extract_sections(body, level=2, section_char="=")
            ],
            heading=title,
            elaboration="",
            expected_word_count=word_count(body),
            language=language,
            aims=[],
            support_to=[],
            depend_on=[],
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
            language=(lang := detect_language(body)),
            chapters=[
                ArticleChapter.from_typst_code(*pack, language=lang)
                for pack in extract_sections(body, level=1, section_char="=")
            ],
            heading=title,
            expected_word_count=word_count(body),
            abstract="",
        )

    def gather_dependencies(self, article: ArticleOutlineBase) -> List[ArticleOutlineBase]:
        """Gathers dependencies for all sections and subsections in the article.

        This method should be called after the article is fully constructed.
        """
        depends = [ok(a.deref(self)) for a in article.depend_on]

        supports = []
        for a in self.iter_dfs_rev():
            if article in {ok(b.deref(self)) for b in a.support_to}:
                supports.append(a)

        return list(set(depends + supports))

    def gather_dependencies_recursive(self, article: ArticleOutlineBase) -> List[ArticleOutlineBase]:
        """Gathers all dependencies recursively for the given article.

        Args:
            article (ArticleOutlineBase): The article to gather dependencies for.

        Returns:
            List[ArticleBase]: A list of all dependencies for the given article.
        """
        q = self.gather_dependencies(article)

        deps = []
        while q:
            a = q.pop()
            deps.extend(self.gather_dependencies(a))

        deps = list(
            chain(
                filter(lambda x: isinstance(x, ArticleChapter), deps),
                filter(lambda x: isinstance(x, ArticleSection), deps),
                filter(lambda x: isinstance(x, ArticleSubsection), deps),
            )
        )

        # Initialize result containers
        formatted_code = ""
        processed_components = []

        # Process all dependencies
        while deps:
            component = deps.pop()
            # Skip duplicates
            if (component_code := component.to_typst_code()) in formatted_code:
                continue

            # Add this component
            formatted_code += component_code
            processed_components.append(component)

        return processed_components

    def iter_dfs_with_deps(
        self, chapter: bool = True, section: bool = True, subsection: bool = True
    ) -> Generator[Tuple[ArticleOutlineBase, List[ArticleOutlineBase]], None, None]:
        """Iterates through the article in a depth-first manner, yielding each component and its dependencies.

        Args:
            chapter (bool, optional): Whether to include chapter components. Defaults to True.
            section (bool, optional): Whether to include section components. Defaults to True.
            subsection (bool, optional): Whether to include subsection components. Defaults to True.

        Yields:
            Tuple[ArticleBase, List[ArticleBase]]: Each component and its dependencies.
        """
        if all((not chapter, not section, not subsection)):
            raise ValueError("At least one of chapter, section, or subsection must be True.")

        for component in self.iter_dfs_rev():
            if not chapter and isinstance(component, ArticleChapter):
                continue
            if not section and isinstance(component, ArticleSection):
                continue
            if not subsection and isinstance(component, ArticleSubsection):
                continue
            yield component, (self.gather_dependencies_recursive(component))
