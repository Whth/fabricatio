"""Tests for the translate."""

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_generic_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_translate.capabilities.translate import Translate


class TranslateRole(LLMTestRole, Translate):
    """Test role that combines LLMTestRole with Translate for testing."""


@pytest.fixture
def role() -> TranslateRole:
    """Create a TranslateRole instance for testing."""
    return TranslateRole()


@pytest.mark.parametrize(
    ("text", "target_language", "mock_response", "expected"),
    [
        ("hello", "fr", "bonjour", "bonjour"),
        ("world", "es", "mundo", "mundo"),
        (["one", "two"], "de", ["eins", "zwei"], ["eins", "zwei"]),
    ],
)
@pytest.mark.asyncio
async def test_translate_parametrized(
    role: TranslateRole,
    text: str | list[str],
    target_language: str,
    mock_response: str | list[str],
    expected: str | list[str],
) -> None:
    """Test Translate.translate with various scenarios using mock router."""
    # Prepare mock router for single or list
    responses = (
        return_generic_router_usage(*mock_response)
        if isinstance(text, list)
        else return_generic_router_usage(mock_response)
    )
    with install_router_usage(*responses):
        result = await role.translate(text, target_language)
        assert result == expected


@pytest.mark.parametrize(
    ("text", "target_language", "mock_response", "expected"),
    [
        (
            "This is a longer paragraph containing multiple sentences. It should be split by sentences for chunked translation.",
            "fr",
            ["C'est une phrase. ", "Une autre phrase. "],
            "C'est une phrase. Une autre phrase. ",
        ),
        (
            ["First sentence in the list.", "Second sentence to be translated."],
            "es",
            [["Primera frase en la lista. "], ["Segunda frase a ser traducida."]],
            ["Primera frase en la lista. ", "Segunda frase a ser traducida."],
        ),
    ],
)
@pytest.mark.asyncio
async def test_translate_chunked_parametrized(
    role: TranslateRole,
    text: str | list[str],
    target_language: str,
    mock_response: str | list[str] | list[list[str]],
    expected: str | list[str],
) -> None:
    """Test Translate.translate_chunked with various scenarios using mock router."""
    # Prepare mock router for chunked responses
    if isinstance(text, list):
        # Flatten the list of lists for router
        flat = [item for sublist in mock_response for item in (sublist if isinstance(sublist, list) else [sublist])]
        responses = return_generic_router_usage(*flat)
    else:
        responses = return_generic_router_usage(*mock_response)
    with install_router_usage(*responses):
        result = await role.translate_chunked(text, target_language, chunk_size=1)
        assert result == expected
