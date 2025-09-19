"""Tests for the character."""

from fabricatio_character.capabilities.character import Character
from fabricatio_mock.models.mock_role import LLMTestRole


class CharacterRole(LLMTestRole, Character):
    """Test role that combines LLMTestRole with Character for testing."""
