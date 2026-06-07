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
from fabricatio_typst.models.article_outline import (
    ArticleChapterOutline,
    ArticleOutline,
    ArticleSectionOutline,
    ArticleSubsectionOutline,
)


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
        article.artifacts.update_outline(outline)
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
        outline = article.extract_outline()
        # Verify structure remains intact (would check actual edits with mock input)
        assert outline.chapters[0].title == "Original Chapter"
        assert outline.chapters[0].sections[0].title == "Original Section"
        assert outline.chapters[0].sections[0].subsections[0].title == "Original Subsection"

    def test_iter_subsections(self, article: Article) -> None:
        """Test subsection iteration functionality."""
        chapter = ArticleChapter(heading="Chapter", sections=[], elaboration="", aims=[], expected_word_count=500)
        section = ArticleSection(heading="Section", subsections=[], elaboration="", aims=[], expected_word_count=500)
        subsection = ArticleSubsection(
            heading="Subsection", expected_word_count=100, paragraphs=[], elaboration="", aims=[]
        )
        section.subsections.append(subsection)
        chapter.sections.append(section)
        article.chapters.append(chapter)

        results = list(article.iter_subsections())
        assert len(results) == 1
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 3  # (chapter, section, subsection)

    def test_extract_outline_preserves_structure(self) -> None:
        """Verify outline extraction preserves chapter/section/subsection hierarchy."""
        article = Article(heading="Test", expected_word_count=100, elaboration="", aims=[], chapters=[])
        sub = ArticleSubsection(heading="Sub", expected_word_count=10, paragraphs=[], elaboration="", aims=[])
        sec = ArticleSection(heading="Sec", subsections=[sub], elaboration="", aims=[], expected_word_count=10)
        chap = ArticleChapter(heading="Chap", sections=[sec], elaboration="", aims=[], expected_word_count=10)
        article.chapters.append(chap)

        outline = article.extract_outline()
        assert outline.title == "Test"
        assert len(outline.chapters) == 1
        assert outline.chapters[0].title == "Chap"
        assert outline.chapters[0].sections[0].title == "Sec"
        assert outline.chapters[0].sections[0].subsections[0].title == "Sub"

    def test_from_outline_creates_article(self) -> None:
        """from_outline creates an Article with matching structure."""
        sub = ArticleSubsectionOutline(heading="Sub", expected_word_count=10, elaboration="", aims=[])
        sec = ArticleSectionOutline(heading="Sec", subsections=[sub], elaboration="", aims=[], expected_word_count=10)
        chap = ArticleChapterOutline(heading="Chap", sections=[sec], elaboration="", aims=[], expected_word_count=10)
        outline = ArticleOutline(heading="Test", expected_word_count=100, elaboration="", aims=[], chapters=[chap])

        article = Article.from_outline(outline)
        assert article.title == "Test"
        assert len(article.chapters) == 1
        assert article.chapters[0].title == "Chap"
        assert article.chapters[0].sections[0].title == "Sec"

    def test_artifacts_propagate_through_from_outline(self) -> None:
        """Artifacts survive from_outline round-trip."""
        outline = ArticleOutline(heading="T", expected_word_count=10, elaboration="", aims=[], chapters=[])
        outline.artifacts.update_briefing("test briefing")

        article = Article.from_outline(outline)
        assert article.artifacts.briefing == "test briefing"
        assert article.artifacts is outline.artifacts  # same object

    def test_artifacts_propagate_through_extract_outline(self) -> None:
        """Artifacts survive extract_outline round-trip."""
        article = Article(heading="T", expected_word_count=10, elaboration="", aims=[], chapters=[])
        article.artifacts.update_briefing("hello")

        outline = article.extract_outline()
        assert outline.artifacts.briefing == "hello"
        assert outline.artifacts is article.artifacts  # same object


class TestConflictResolution:
    """Test resolve_update_conflict across the hierarchy."""

    def _make_chapter(self, title: str, sec_title: str = "S") -> ArticleChapterOutline:
        sub = ArticleSubsectionOutline(heading=sec_title, expected_word_count=10, elaboration="", aims=[])
        sec = ArticleSectionOutline(
            heading=sec_title, subsections=[sub], elaboration="", aims=[], expected_word_count=10
        )
        return ArticleChapterOutline(heading=title, sections=[sec], elaboration="", aims=[], expected_word_count=10)

    def test_no_conflict_on_identical(self) -> None:
        """Identical chapters produce empty conflict string."""
        a = self._make_chapter("Same")
        b = self._make_chapter("Same")
        assert a.resolve_update_conflict(b) == ""

    def test_title_mismatch_detected(self) -> None:
        """Verify that differing chapter titles are detected as conflicts."""
        a = self._make_chapter("A")
        b = self._make_chapter("B")
        result = a.resolve_update_conflict(b)
        assert "Title mismatched" in result

    def test_section_count_mismatch_detected(self) -> None:
        """Verify that section count mismatches are detected."""
        a = self._make_chapter("T")
        b = self._make_chapter("T")
        extra_sub = ArticleSubsectionOutline(heading="X", expected_word_count=10, elaboration="", aims=[])
        extra_sec = ArticleSectionOutline(
            heading="X", subsections=[extra_sub], elaboration="", aims=[], expected_word_count=10
        )
        b.sections.append(extra_sec)
        result = a.resolve_update_conflict(b)
        assert "Chapter count mismatched" in result

    def test_subsection_title_mismatch_detected(self) -> None:
        """Verify that differing subsection titles are detected as conflicts."""
        a = self._make_chapter("T", sec_title="Orig")
        b = self._make_chapter("T", sec_title="Changed")
        result = a.resolve_update_conflict(b)
        assert "Title mismatched" in result
