"""Tests for the locale."""

import pytest
from fabricatio_locale.capabilities.localize import Localize
from fabricatio_locale.rust import Msg
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_generic_string
from fabricatio_mock.utils import install_router


class LocalizeRole(LLMTestRole, Localize):
    """Test role that combines LLMTestRole with Localize for testing."""


@pytest.fixture
def role() -> LocalizeRole:
    """Create a LocalizeRole instance for testing."""
    return LocalizeRole()


@pytest.mark.parametrize(
    ("messages", "target_language", "mock_responses", "expected_texts"),
    [
        # Single message
        (
            [Msg(id="hello", txt="Hello")],
            "fr",
            ["Bonjour"],
            ["Bonjour"],
        ),
        # Multiple messages
        (
            [
                Msg(id="hello", txt="Hello"),
                Msg(id="world", txt="World"),
            ],
            "es",
            ["Hola", "Mundo"],
            ["Hola", "Mundo"],
        ),
        # Messages with empty translations (should fallback to original)
        (
            [
                Msg(id="hello", txt="Hello"),
                Msg(id="world", txt="World"),
            ],
            "de",
            ["Hallo", ""],  # Empty translation for second message
            ["Hallo", "World"],  # Should fallback to original
        ),
        # Complex messages with longer text
        (
            [
                Msg(id="greeting", txt="Good morning, how are you?"),
                Msg(id="farewell", txt="See you later!"),
            ],
            "fr",
            ["Bonjour, comment allez-vous?", "À bientôt!"],
            ["Bonjour, comment allez-vous?", "À bientôt!"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_localize_parametrized(
    role: LocalizeRole,
    messages: list[Msg],
    target_language: str,
    mock_responses: list[str],
    expected_texts: list[str],
) -> None:
    """Test Localize.localize with various scenarios using mock router."""
    router = return_generic_string(*mock_responses)
    with install_router(router):
        result = await role.localize(messages, target_language=target_language)

        # Check that we get the same number of messages back
        assert len(result) == len(messages)

        # Check that IDs are preserved and texts are translated correctly
        for i, (original_msg, result_msg, expected_txt) in enumerate(
            zip(messages, result, expected_texts, strict=True)
        ):
            assert result_msg.id == original_msg.id, f"Message {i}: ID should be preserved"
            assert result_msg.txt == expected_txt, f"Message {i}: Text should be translated correctly"


@pytest.mark.parametrize(
    ("messages", "target_language", "specification", "mock_responses", "expected_texts"),
    [
        # With specification
        (
            [Msg(id="formal", txt="Hello")],
            "fr",
            "formal",
            ["Bonjour"],
            ["Bonjour"],
        ),
        # With informal specification
        (
            [Msg(id="informal", txt="Hello")],
            "fr",
            "informal",
            ["Salut"],
            ["Salut"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_localize_with_specification_parametrized(
    role: LocalizeRole,
    messages: list[Msg],
    target_language: str,
    specification: str,
    mock_responses: list[str],
    expected_texts: list[str],
) -> None:
    """Test Localize.localize with specification parameter using mock router."""
    router = return_generic_string(*mock_responses)
    with install_router(router):
        result = await role.localize(messages, target_language=target_language, specification=specification)

        # Check that we get the same number of messages back
        assert len(result) == len(messages)

        # Check that IDs are preserved and texts are translated correctly
        for i, (original_msg, result_msg, expected_txt) in enumerate(
            zip(messages, result, expected_texts, strict=False)
        ):
            assert result_msg.id == original_msg.id, f"Message {i}: ID should be preserved"
            assert result_msg.txt == expected_txt, f"Message {i}: Text should be translated correctly"


@pytest.mark.parametrize(
    "messages",
    [
        # Empty list
        [],
        # Single message with special characters
        [Msg(id="special", txt="Hello & welcome! 🎉")],
    ],
)
@pytest.mark.asyncio
async def test_localize_edge_cases_parametrized(
    role: LocalizeRole,
    messages: list[Msg],
) -> None:
    """Test Localize.localize with edge cases using mock router."""
    if not messages:
        # Empty list case
        router = return_generic_string("dummy")  # Won't be called
        with install_router(router):
            result = await role.localize(messages, target_language="fr")
            assert result == []
    else:
        # Special characters case
        mock_response = "Bonjour & bienvenue! 🎉"
        router = return_generic_string(mock_response)
        with install_router(router):
            result = await role.localize(messages, target_language="fr")
            assert len(result) == 1
            assert result[0].id == messages[0].id
            assert result[0].txt == mock_response


@pytest.mark.asyncio
async def test_localize_preserves_message_structure(role: LocalizeRole) -> None:
    """Test that localize preserves the Message structure and IDs."""
    original_messages = [
        Msg(id="msg1", txt="First message"),
        Msg(id="msg2", txt="Second message"),
        Msg(id="msg3", txt="Third message"),
    ]

    mock_responses = ["Premier message", "Deuxième message", "Troisième message"]
    router = return_generic_string(*mock_responses)

    with install_router(router):
        result = await role.localize(original_messages, target_language="fr")

        # Verify structure preservation
        assert len(result) == len(original_messages)
        for original, localized in zip(original_messages, result, strict=False):
            assert isinstance(localized, Msg)
            assert localized.id == original.id
            assert localized.txt != original.txt  # Should be translated
