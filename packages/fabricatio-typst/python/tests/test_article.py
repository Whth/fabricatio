"""Test suite for article_main.py module.

This module contains unit tests for the article component classes and methods,
including Paragraph, ArticleSubsection, and Article class functionality.
"""

import pytest
from fabricatio_typst.models.article_main import (
    Article,
    ArticleChapter,
    ArticleSection,
    ArticleSubsection,
    Paragraph,
)
from fabricatio_typst.models.article_outline import ArticleOutline


class TestParagraph:
    """Test cases for Paragraph class."""

    def test_from_content_creation(self) -> None:
        """Verify Paragraph creation from content string."""
        content = "Test paragraph content"
        paragraph = Paragraph.from_content(content)
        assert paragraph.content == content.strip()


class TestArticleSubsection:
    """Test cases for ArticleSubsection class."""

    @pytest.fixture
    def subsection(self) -> ArticleSubsection:
        """Create a test subsection with paragraphs."""
        return ArticleSubsection(
            heading="Test Subsection",
            expected_word_count=100,
            elaboration="",
            aims=[],
            paragraphs=[
                Paragraph.from_content("First paragraph with ten words"),
                Paragraph.from_content("Second paragraph with ten words"),
            ],
        )

    def test_introspect_empty_paragraphs(self) -> None:
        """Test introspection for subsection with no paragraphs."""
        subsection = ArticleSubsection(heading="Empty", expected_word_count=100, paragraphs=[], elaboration="", aims=[])
        result = subsection.introspect()
        assert "have no paragraphs" in result


class TestArticleHierarchy:
    """Test cases for article component hierarchy."""

    def test_section_child_type(self) -> None:
        """Verify section child type configuration."""
        assert ArticleSection.child_type == ArticleSubsection

    def test_chapter_child_type(self) -> None:
        """Verify chapter child type configuration."""
        assert ArticleChapter.child_type == ArticleSection


class TestArticle:
    """Test cases for Article class."""

    @pytest.fixture
    def article(self) -> Article:
        """Create a test article instance."""
        outline = ArticleOutline(heading="Outline", expected_word_count=500, elaboration="", aims=[], chapters=[])
        article = Article(heading="Test Article", expected_word_count=500, chapters=[], elaboration="", aims=[])
        article.update_ref(outline)  # Use proper method to set reference
        return article

    def test_convert_tex_processing(self, article: Article) -> None:
        """Test TeX to Typst conversion functionality."""
        # Add test content with TeX math
        chapter = ArticleChapter(heading="Chapter", sections=[], elaboration="", aims=[], expected_word_count=500)
        section = ArticleSection(heading="Section", subsections=[], elaboration="", aims=[], expected_word_count=500)
        subsection = ArticleSubsection(
            heading="Subsection",
            expected_word_count=100,
            paragraphs=[Paragraph.from_content(r"Inline $math$ here")],
            elaboration="",
            aims=[],
        )
        section.subsections.append(subsection)
        chapter.sections.append(section)
        article.chapters.append(chapter)

        # Run conversion
        result = article.convert_tex()
        converted_content = result.chapters[0].sections[0].subsections[0].paragraphs[0].content

        # Verify TeX math conversion (implementation specific)
        assert converted_content != r"Inline $math$ here"  # Should be modified

    async def test_extract_outline(self, article: Article) -> None:
        """Test asynchronous title editing functionality."""
        # Add components to test
        chapter = ArticleChapter(
            heading="Original Chapter", sections=[], elaboration="", aims=[], expected_word_count=500
        )
        section = ArticleSection(
            heading="Original Section", subsections=[], elaboration="", aims=[], expected_word_count=500
        )
        subsection = ArticleSubsection(
            heading="Original Subsection", expected_word_count=100, paragraphs=[], elaboration="", aims=[]
        )
        section.subsections.append(subsection)
        chapter.sections.append(section)
        article.chapters.append(chapter)

        # Mock questionary input would go here in real test
        outline = article.extrac_outline()
        # Verify structure remains intact (would check actual edits with mock input)
        assert outline.chapters[0].title == "Original Chapter"
        assert outline.chapters[0].sections[0].title == "Original Section"
        assert outline.chapters[0].sections[0].subsections[0].title == "Original Subsection"

    def test_iter_subsections(self, article: Article) -> None:
        """Test subsection iteration functionality."""
        # Setup test hierarchy
        chapter = ArticleChapter(heading="Chapter", sections=[], elaboration="", aims=[], expected_word_count=500)
        section = ArticleSection(heading="Section", subsections=[], elaboration="", aims=[], expected_word_count=500)
        subsection = ArticleSubsection(
            heading="Subsection", expected_word_count=100, paragraphs=[], elaboration="", aims=[]
        )
        section.subsections.append(subsection)
        chapter.sections.append(section)
        article.chapters.append(chapter)

        # Test iteration
        results = list(article.iter_subsections())
        assert len(results) == 1
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 3  # (chapter, section, subsection)
