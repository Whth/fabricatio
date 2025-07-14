"""Tests for the capable."""

from fabricatio_capable.capabilities.capable import Capable
from fabricatio_mock.models.mock_role import LLMTestRole


class CapableRole(LLMTestRole, Capable):
    """Test role that combines LLMTestRole with Capable for testing."""
