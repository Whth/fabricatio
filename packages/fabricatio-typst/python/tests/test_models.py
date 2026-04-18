"""Test module for article model classes in fabricatio-typst.

This module contains pytest test cases for article model classes including
ArticleOutline, ArticleProposal, and related hierarchy classes.
"""

import pytest
from fabricatio_typst.models.article_outline import (
    ArticleChapterOutline,
    ArticleOutline,
    ArticleSectionOutline,
    ArticleSubsectionOutline,
)
from fabricatio_typst.models.article_proposal import ArticleProposal


class TestArticleSubsectionOutline:
    """Test suite for ArticleSubsectionOutline class."""

    def test_creation(self) -> None:
        """Test basic creation of ArticleSubsectionOutline."""
        outline = ArticleSubsectionOutline(
            heading="Test Subsection",
            expected_word_count=100,
            elaboration="Test elaboration",
            aims=["aim1", "aim2"],
        )
        assert outline.title == "Test Subsection"
        assert outline.expected_word_count == 100


class TestArticleSectionOutline:
    """Test suite for ArticleSectionOutline class."""

    def test_child_type(self) -> None:
        """Test child_type class variable."""
        assert ArticleSectionOutline.child_type == ArticleSubsectionOutline


class TestArticleChapterOutline:
    """Test suite for ArticleChapterOutline class."""

    def test_child_type(self) -> None:
        """Test child_type class variable."""
        assert ArticleChapterOutline.child_type == ArticleSectionOutline


class TestArticleOutline:
    """Test suite for ArticleOutline class."""

    def test_child_type(self) -> None:
        """Test child_type class variable."""
        assert ArticleOutline.child_type == ArticleChapterOutline

    def test_creation(self) -> None:
        """Test basic creation of ArticleOutline."""
        outline = ArticleOutline(
            heading="Test Outline",
            expected_word_count=1000,
            elaboration="",
            aims=[],
            chapters=[],
        )
        assert outline.title == "Test Outline"
        assert outline.expected_word_count == 1000


class TestArticleProposal:
    """Test suite for ArticleProposal class."""

    @pytest.fixture
    def proposal(self) -> ArticleProposal:
        """Create a valid test ArticleProposal."""
        # Note: description has alias="abstract", so we pass abstract=...
        proposal = ArticleProposal(
            focused_problem=["Problem 1"],
            technical_approaches=["Approach 1"],
            research_methods=["Method 1"],
            research_aim=["Aim 1"],
            literature_review=["Ref 1"],
            expected_outcomes=["Outcome 1"],
            keywords=["keyword1"],
            abstract="Test abstract",  # alias for description field
            expected_word_count=500,
            title="Research Title",
        )
        # WithRef[str] requires update_ref to set the briefing string
        proposal.update_ref("Test briefing string")
        return proposal

    def test_creation(self, proposal: ArticleProposal) -> None:
        """Test basic creation of ArticleProposal."""
        assert proposal.title == "Research Title"
        assert proposal.description == "Test abstract"  # accessing via actual field name

    def test_as_prompt_inner(self, proposal: ArticleProposal) -> None:
        """Test _as_prompt_inner method."""
        result = proposal._as_prompt_inner()
        assert isinstance(result, dict)

    def test_display_method(self, proposal: ArticleProposal) -> None:
        """Test display() method exists and returns string."""
        result = proposal.display()
        assert isinstance(result, str)
        assert len(result) > 0
