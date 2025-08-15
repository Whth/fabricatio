"""Tests for the diff."""
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_diff.capabilities.diff import Diff


class DiffRole(LLMTestRole, Diff):
    """Test role that combines LLMTestRole with Diff for testing."""
