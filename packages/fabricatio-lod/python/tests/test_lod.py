"""Tests for the lod."""

from fabricatio_lod.capabilities.lod import Lod
from fabricatio_mock.models.mock_role import LLMTestRole


class LodRole(LLMTestRole, Lod):
    """Test role that combines LLMTestRole with Lod for testing."""
