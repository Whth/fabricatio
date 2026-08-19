"""Tests for the character."""

from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.config import CharacterConfig, character_config
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
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
            roles=["Protagonist"],
            activated_role="Protagonist",
            look="Tall, dark hair, blue eyes",
            act="Calm and analytical",
            want="To find the truth",
            flaw="Overthinks everything",
            where="In a rainy alley, tailing a suspect",
            condition="Healthy but damp",
            mood="Focused",
            metric={"hp": 100, "reputation": 25},
        )

    def test_card_creation(self, card: CharacterCard) -> None:
        """Test basic CharacterCard creation."""
        assert card.name == "Alice"
        assert card.roles == ["Protagonist"]
        assert card.activated_role == "Protagonist"
        assert card.look == "Tall, dark hair, blue eyes"
        assert card.act == "Calm and analytical"
        assert card.want == "To find the truth"
        assert card.flaw == "Overthinks everything"
        assert card.where == "In a rainy alley, tailing a suspect"
        assert card.condition == "Healthy but damp"
        assert card.mood == "Focused"
        assert card.metric == {"hp": 100, "reputation": 25}

    def test_card_model_dump(self, card: CharacterCard) -> None:
        """Test model_dump returns all fields."""
        data = card.model_dump()
        assert data["name"] == "Alice"
        assert data["roles"] == ["Protagonist"]
        assert data["activated_role"] == "Protagonist"
        assert data["look"] == "Tall, dark hair, blue eyes"
        assert data["act"] == "Calm and analytical"
        assert data["want"] == "To find the truth"
        assert data["flaw"] == "Overthinks everything"
        assert data["where"] == "In a rainy alley, tailing a suspect"
        assert data["condition"] == "Healthy but damp"
        assert data["mood"] == "Focused"
        assert data["metric"] == {"hp": 100, "reputation": 25}

    def test_card_as_prompt(self, card: CharacterCard) -> None:
        """Test as_prompt generates a string containing card data."""
        result = card.as_prompt()
        assert isinstance(result, str)
        assert "Alice" in result
        assert "## Where" in result
        assert "## Condition" in result
        assert "## Mood" in result
        assert "## Roles" in result
        assert "## Activated Role" in result
        assert "## Want (core motivation)" in result
        assert "## Metrics" in result
        assert "hp=100, reputation=25" in result

    def test_card_has_all_fields(self) -> None:
        """Test that CharacterCard has all expected fields."""
        fields = CharacterCard.model_fields
        expected = {
            "name",
            "roles",
            "activated_role",
            "look",
            "act",
            "want",
            "flaw",
            "where",
            "condition",
            "mood",
        }
        assert expected.issubset(set(fields.keys()))

    def test_state_fields_roundtrip_through_diff(self, card: CharacterCard) -> None:
        """State fields fold through a CharacterCardDiff; only the changed fields move."""
        updated = card.apply(
            CharacterCardDiff(
                where="In the enemy palace's wine cellar",
                condition="Feverish, limping",
                mood="Smoldering fury",
                reason="Captured and drugged in chapter 4",
            )
        )
        assert updated.name == card.name
        assert updated.roles == card.roles
        assert updated.activated_role == card.activated_role
        assert updated.look == card.look
        assert updated.act == card.act
        assert updated.want == card.want
        assert updated.flaw == card.flaw

    def test_metric_diff_merges_into_card(self, card: CharacterCard) -> None:
        """A metric diff updates only the named entries and keeps the rest."""
        updated = card.apply(CharacterCardDiff(metric={"hp": 60, "sanity": 0.5}, reason="took a hit"))
        assert updated.metric == {"hp": 60, "reputation": 25, "sanity": 0.5}
        # untouched persona and state fields stay put
        assert updated.look == card.look
        assert updated.mood == card.mood

    def test_empty_metric_renders_no_metrics_section(self) -> None:
        """A card without tracked stats omits the Metrics section from its prompt."""
        plain = CharacterCard(
            name="NoStats",
            roles=["bit"],
            activated_role="bit",
            look="plain",
            act="quiet",
            want="none",
            flaw="none",
            where="nowhere",
            condition="fine",
            mood="calm",
        )
        assert plain.metric == {}
        assert "## Metrics" not in plain.as_prompt()


# ---------------------------------------------------------------------------
# dump_card utility tests
# ---------------------------------------------------------------------------


class TestDumpCard:
    """Tests for dump_card utility."""

    def test_dump_single_card(self) -> None:
        """Test dumping a single character card."""
        card = CharacterCard(
            name="Bob",
            roles=["Sidekick"],
            activated_role="Sidekick",
            look="Short",
            act="Loyal",
            want="Adventure",
            flaw="Naive",
            where="Downtown",
            condition="Fine",
            mood="Eager",
        )
        result = dump_card(card)
        assert isinstance(result, str)
        assert "Bob" in result

    def test_dump_multiple_cards(self) -> None:
        """Test dumping multiple character cards."""
        cards = [
            CharacterCard(
                name=f"Char{i}",
                roles=["Role"],
                activated_role="Role",
                look="Look",
                act="Act",
                want="Want",
                flaw="Flaw",
                where="Where",
                condition="Condition",
                mood="Mood",
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
            CharacterCard(
                name="A",
                roles=["R"],
                activated_role="R",
                look="L",
                act="A",
                want="W",
                flaw="F",
                where="X",
                condition="C",
                mood="M",
            ),
            CharacterCard(
                name="B",
                roles=["R"],
                activated_role="R",
                look="L",
                act="A",
                want="W",
                flaw="F",
                where="X",
                condition="C",
                mood="M",
            ),
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
        return CharacterRole(name="character")

    @pytest.mark.asyncio
    async def test_compose_characters_single_string(self, role: CharacterRole) -> None:
        """Test compose_characters with a single requirement string."""
        mock_card = CharacterCard(
            name="Hero",
            roles=["Warrior"],
            activated_role="Warrior",
            look="Strong",
            act="Brave",
            want="Justice",
            flaw="Stubborn",
            where="Arena",
            condition="Rested",
            mood="Resolute",
        )
        with patch.object(type(role), "propose", new_callable=AsyncMock, return_value=mock_card):
            result = await role.compose_characters("Create a warrior character")
        assert isinstance(result, CharacterCard)

    @pytest.mark.asyncio
    async def test_compose_characters_list(self, role: CharacterRole) -> None:
        """Test compose_characters with a list of requirements."""
        mock_cards = [
            CharacterCard(
                name="Hero",
                roles=["Warrior"],
                activated_role="Warrior",
                look="Strong",
                act="Brave",
                want="Justice",
                flaw="Stubborn",
                where="Arena",
                condition="Rested",
                mood="Resolute",
            ),
            CharacterCard(
                name="Mage",
                roles=["Wizard"],
                activated_role="Wizard",
                look="Wise",
                act="Calm",
                want="Knowledge",
                flaw="Arrogant",
                where="Library",
                condition="Fine",
                mood="Curious",
            ),
        ]
        with patch.object(type(role), "propose", new_callable=AsyncMock, return_value=mock_cards):
            result = await role.compose_characters(["warrior", "wizard"])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(c, CharacterCard) for c in result)
