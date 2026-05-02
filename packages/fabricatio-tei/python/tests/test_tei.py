"""Tests for the tei."""

from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_tei.capabilities.tei import Tei


class TeiRole(LLMTestRole, Tei):
    """Test role that combines LLMTestRole with Tei for testing."""
