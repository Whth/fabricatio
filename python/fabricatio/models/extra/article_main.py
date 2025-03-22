"""ArticleBase and ArticleSubsection classes for managing hierarchical document components."""

from itertools import chain
from typing import Generator, List, Self, Tuple

from fabricatio.journal import logger
from fabricatio.models.extra.article_base import (
    ArticleBase,
    ArticleMainBase,
    ArticleRef,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_outline import (
    ArticleOutline,
)
from fabricatio.models.generic import CensoredAble, Display, PersistentAble, WithRef
from fabricatio.models.utils import ok


class Paragraph(CensoredAble):
    """Structured academic paragraph blueprint for controlled content generation."""

    description: str
    """Functional summary of the paragraph's role in document structure."""

    writing_aim: List[str]
    """Specific communicative objectives for this paragraph's content."""

    sentences: List[str]
    """List of sentences forming the paragraph's content."""


class ArticleSubsection(ArticleMainBase, SubSectionBase):
    """Atomic argumentative unit with technical specificity."""

    paragraphs: List[Paragraph]
    """List of Paragraph objects containing the content of the subsection."""

    def resolve_update_error(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        if self.title != other.title:
            return f"Title `{other.title}` mismatched, expected `{self.title}`. "
        return ""

    def _update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        logger.debug(f"Updating SubSection {self.title}")
        self.paragraphs = other.paragraphs
        return self

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering.

        Returns:
            str: Typst code snippet for rendering.
        """
        return f"=== {self.title}\n" + "\n\n".join("".join(p.sentences) for p in self.paragraphs)


class ArticleSection(ArticleMainBase, SectionBase[ArticleSubsection]):
    """Atomic argumentative unit with high-level specificity."""

    def resolve_update_error(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        if (s_len := len(self.subsections)) == 0:
            return ""

        if s_len != len(other.subsections):
            return f"Subsections length mismatched, expected {len(self.subsections)}, got {len(other.subsections)}"

        sub_sec_err_seq = [
            out for s, o in zip(self.subsections, other.subsections, strict=True) if (out := s.resolve_update_error(o))
        ]

        if sub_sec_err_seq:
            return "\n".join(sub_sec_err_seq)
        return ""

    def _update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if len(self.subsections) == 0:
            self.subsections = other.subsections
            return self

        for self_subsec, other_subsec in zip(self.subsections, other.subsections, strict=True):
            self_subsec.update_from(other_subsec)
        return self

    def to_typst_code(self) -> str:
        """Converts the section into a Typst formatted code snippet.

        Returns:
            str: The formatted Typst code snippet.
        """
        return f"== {self.title}\n" + "\n\n".join(subsec.to_typst_code() for subsec in self.subsections)


class ArticleChapter(ArticleMainBase, ChapterBase[ArticleSection]):
    """Thematic progression implementing research function."""

    def resolve_update_error(self, other: Self) -> str:
        """Resolve update errors in the article outline."""
        if (s_len := len(self.sections)) == 0:
            return ""

        if s_len != len(other.sections):
            return f"Sections length mismatched, expected {len(self.sections)}, got {len(other.sections)}"
        sec_err_seq = [
            out for s, o in zip(self.sections, other.sections, strict=True) if (out := s.resolve_update_error(o))
        ]
        if sec_err_seq:
            return "\n".join(sec_err_seq)
        return ""

    def _update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        if len(self.sections) == 0:
            self.sections = other.sections
            return self

        for self_sec, other_sec in zip(self.sections, other.sections, strict=True):
            self_sec.update_from(other_sec)
        return self

    def to_typst_code(self) -> str:
        """Converts the chapter into a Typst formatted code snippet for rendering."""
        return f"= {self.title}\n" + "\n\n".join(sec.to_typst_code() for sec in self.sections)


class Article(Display, CensoredAble, WithRef[ArticleOutline], PersistentAble, ArticleBase[ArticleChapter]):
    """Represents a complete academic paper specification, incorporating validation constraints.

    This class integrates display, censorship processing, article structure referencing, and persistence capabilities,
    aiming to provide a comprehensive model for academic papers.
    """

    abstract: str
    """Contains a summary of the academic paper."""

    title: str
    """Represents the title of the academic paper."""

    language: str
    """Written language of the article. SHALL be aligned to the language of the article outline provided."""

    def finalized_dump(self) -> str:
        """Exports the article in `typst` format.

        Returns:
                str: Strictly formatted outline with typst formatting.
        """
        return "\n\n".join(c.to_typst_code() for c in self.chapters)

    @classmethod
    def from_outline(cls, outline: ArticleOutline) -> "Article":
        """Generates an article from the given outline.

        Args:
            outline (ArticleOutline): The outline to generate the article from.

        Returns:
            Article: The generated article.
        """
        # Set the title from the outline
        article = Article(**outline.model_dump(include={"title", "abstract"}), chapters=[])

        for chapter in outline.chapters:
            # Create a new chapter
            article_chapter = ArticleChapter(
                sections=[],
                **chapter.model_dump(exclude={"sections"}),
            )
            for section in chapter.sections:
                # Create a new section
                article_section = ArticleSection(
                    subsections=[],
                    **section.model_dump(exclude={"subsections"}),
                )
                for subsection in section.subsections:
                    # Create a new subsection
                    article_subsection = ArticleSubsection(
                        paragraphs=[],
                        **subsection.model_dump(),
                    )
                    article_section.subsections.append(article_subsection)
                article_chapter.sections.append(article_section)
            article.chapters.append(article_chapter)
        return article

    def iter_dfs(self) -> Generator[ArticleMainBase, None, None]:
        """Performs a depth-first search (DFS) through the article structure.

        Returns:
            Generator[ArticleMainBase]: Each component in the article structure.
        """
        for chap in self.chapters:
            for sec in chap.sections:
                yield from sec.subsections
                yield sec
            yield chap

    def deref(self, ref: ArticleRef) -> ArticleMainBase:
        """Resolves a reference to the corresponding section or subsection in the article.

        Args:
            ref (ArticleRef): The reference to resolve.

        Returns:
            ArticleMainBase: The corresponding section or subsection.
        """
        return ok(ref.deref(self), f"{ref} not found in {self.title}")

    def gather_dependencies(self, article: ArticleMainBase) -> List[ArticleMainBase]:
        """Gathers dependencies for all sections and subsections in the article.

        This method should be called after the article is fully constructed.
        """
        depends = [self.deref(a) for a in article.depend_on]

        supports = []
        for a in self.iter_dfs():
            if article in {self.deref(b) for b in a.support_to}:
                supports.append(a)

        return list(set(depends + supports))

    def gather_dependencies_recursive(self, article: ArticleMainBase) -> List[ArticleMainBase]:
        """Gathers all dependencies recursively for the given article.

        Args:
            article (ArticleMainBase): The article to gather dependencies for.

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
    ) -> Generator[Tuple[ArticleMainBase, List[ArticleMainBase]], None, None]:
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

        for component in self.iter_dfs():
            if not chapter and isinstance(component, ArticleChapter):
                continue
            if not section and isinstance(component, ArticleSection):
                continue
            if not subsection and isinstance(component, ArticleSubsection):
                continue
            yield component, (self.gather_dependencies_recursive(component))
