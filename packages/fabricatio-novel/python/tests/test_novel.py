"""Tests for the novel."""
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_novel.capabilities.novel import Novel


class NovelRole(LLMTestRole, Novel):
    """Test role that combines LLMTestRole with Novel for testing."""
