"""Tests for the character."""

from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.config import CharacterConfig, character_config
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.utils import dump_card
from fabricatio_mock.models.mock_role import ProposeTestRole

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestCharacterConfig:
    """Tests for CharacterConfig."""

    def test_default_template(self) -> None:
        """Test default render_character_card_template value."""
        cfg = CharacterConfig()
        assert cfg.render_character_card_template == "built-in/render_character_card"

    def test_custom_template(self) -> None:
        """Test custom template."""
        cfg = CharacterConfig(render_character_card_template="custom/template")
        assert cfg.render_character_card_template == "custom/template"

    def test_config_is_frozen(self) -> None:
        """Test that CharacterConfig is frozen."""
        cfg = CharacterConfig()
        with pytest.raises(AttributeError):
            cfg.render_character_card_template = "new"  # type: ignore[misc]

    def test_character_config_singleton(self) -> None:
        """Test that character_config singleton is valid."""
        assert isinstance(character_config, CharacterConfig)


# ---------------------------------------------------------------------------
# CharacterCard model tests
# ---------------------------------------------------------------------------


class TestCharacterCard:
    """Tests for CharacterCard model."""

    @pytest.fixture
    def card(self) -> CharacterCard:
        """Create a sample CharacterCard."""
        return CharacterCard(
            name="Alice",
            role="Protagonist",
            look="Tall, dark hair, blue eyes",
            act="Calm and analytical",
            want="To find the truth",
            flaw="Overthinks everything",
        )

    def test_card_creation(self, card: CharacterCard) -> None:
        """Test basic CharacterCard creation."""
        assert card.name == "Alice"
        assert card.role == "Protagonist"
        assert card.look == "Tall, dark hair, blue eyes"
        assert card.act == "Calm and analytical"
        assert card.want == "To find the truth"
        assert card.flaw == "Overthinks everything"

    def test_card_model_dump(self, card: CharacterCard) -> None:
        """Test model_dump returns all fields."""
        data = card.model_dump()
        assert data["name"] == "Alice"
        assert data["role"] == "Protagonist"
        assert data["look"] == "Tall, dark hair, blue eyes"
        assert data["act"] == "Calm and analytical"
        assert data["want"] == "To find the truth"
        assert data["flaw"] == "Overthinks everything"

    def test_card_as_prompt(self, card: CharacterCard) -> None:
        """Test as_prompt generates a string containing card data."""
        result = card.as_prompt()
        assert isinstance(result, str)
        assert "Alice" in result

    def test_card_has_all_fields(self) -> None:
        """Test that CharacterCard has all expected fields."""
        fields = CharacterCard.model_fields
        expected = {"name", "role", "look", "act", "want", "flaw"}
        assert expected.issubset(set(fields.keys()))


# ---------------------------------------------------------------------------
# dump_card utility tests
# ---------------------------------------------------------------------------


class TestDumpCard:
    """Tests for dump_card utility."""

    def test_dump_single_card(self) -> None:
        """Test dumping a single character card."""
        card = CharacterCard(
            name="Bob",
            role="Sidekick",
            look="Short",
            act="Loyal",
            want="Adventure",
            flaw="Naive",
        )
        result = dump_card(card)
        assert isinstance(result, str)
        assert "Bob" in result

    def test_dump_multiple_cards(self) -> None:
        """Test dumping multiple character cards."""
        cards = [
            CharacterCard(
                name=f"Char{i}",
                role="Role",
                look="Look",
                act="Act",
                want="Want",
                flaw="Flaw",
            )
            for i in range(3)
        ]
        result = dump_card(*cards)
        assert isinstance(result, str)
        for i in range(3):
            assert f"Char{i}" in result

    def test_dump_cards_joined_by_newline(self) -> None:
        """Test that multiple cards are joined by newlines."""
        cards = [
            CharacterCard(name="A", role="R", look="L", act="A", want="W", flaw="F"),
            CharacterCard(name="B", role="R", look="L", act="A", want="W", flaw="F"),
        ]
        result = dump_card(*cards)
        assert "\n" in result


# ---------------------------------------------------------------------------
# CharacterCompose capability tests
# ---------------------------------------------------------------------------


class CharacterRole(ProposeTestRole, CharacterCompose):
    """Test role that combines ProposeTestRole with CharacterCompose for testing."""


class TestCharacterCompose:
    """Tests for CharacterCompose capability."""

    @pytest.fixture
    def role(self) -> CharacterRole:
        """Create a CharacterRole instance."""
        return CharacterRole()

    @pytest.mark.asyncio
    async def test_compose_characters_single_string(self, role: CharacterRole) -> None:
        """Test compose_characters with a single requirement string."""
        mock_card = CharacterCard(
            name="Hero",
            role="Warrior",
            look="Strong",
            act="Brave",
            want="Justice",
            flaw="Stubborn",
        )
        with patch.object(type(role), "propose", new_callable=AsyncMock, return_value=mock_card):
            result = await role.compose_characters("Create a warrior character")
        assert isinstance(result, CharacterCard)
        assert result.name == "Hero"

    @pytest.mark.asyncio
    async def test_compose_characters_list(self, role: CharacterRole) -> None:
        """Test compose_characters with a list of requirements."""
        mock_cards = [
            CharacterCard(name="Hero", role="Warrior", look="Strong", act="Brave", want="Justice", flaw="Stubborn"),
            CharacterCard(name="Mage", role="Wizard", look="Wise", act="Calm", want="Knowledge", flaw="Arrogant"),
        ]
        with patch.object(type(role), "propose", new_callable=AsyncMock, return_value=mock_cards):
            result = await role.compose_characters(["warrior", "wizard"])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(c, CharacterCard) for c in result)
