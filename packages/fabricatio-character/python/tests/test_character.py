"""Tests for the character."""

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_mock.models.mock_role import LLMTestRole


class CharacterRole(LLMTestRole, CharacterCompose):
    """Test role that combines LLMTestRole with Character for testing."""
