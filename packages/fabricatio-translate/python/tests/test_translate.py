"""Tests for the translate."""

import pytest
from fabricatio_core import Role
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_translate.capabilities.translate import Translate


@pytest.fixture
def role() -> Role:
    """Create a translate test role instance."""
    return make_test_role(Translate, name="translate")


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
    role: Role,
    text: str | list[str],
    target_language: str,
    mock_response: str | list[str],
    expected: str | list[str],
) -> None:
    """Test Translate.translate with various scenarios using mock router."""
    # Prepare mock script for single or list
    responses = (
        [
            Value.from_generic(item, name=f"translation {position}")
            for position, item in enumerate(mock_response, start=1)
        ]
        if isinstance(text, list)
        else [Value.from_generic(mock_response, name="translation")]
    )
    with MockScript.from_values(*responses):
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
    role: Role,
    text: str | list[str],
    target_language: str,
    mock_response: str | list[str] | list[list[str]],
    expected: str | list[str],
) -> None:
    """Test Translate.translate_chunked with various scenarios using mock router."""
    # Prepare mock script for chunked responses
    if isinstance(text, list):
        # Flatten the list of lists for router
        flat = [item for sublist in mock_response for item in (sublist if isinstance(sublist, list) else [sublist])]
        responses = [Value.from_generic(item, name=f"chunk {position}") for position, item in enumerate(flat, start=1)]
    else:
        responses = [
            Value.from_generic(item, name=f"chunk {position}") for position, item in enumerate(mock_response, start=1)
        ]
    with MockScript.from_values(*responses):
        result = await role.translate_chunked(text, target_language, chunk_size=1)
        assert result == expected
