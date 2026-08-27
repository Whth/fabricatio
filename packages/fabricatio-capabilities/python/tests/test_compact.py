"""Tests for the Compact capability."""

from typing import TYPE_CHECKING

import pytest
from fabricatio_capabilities.capabilities.compact import Compact, LengthType, _length
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage

if TYPE_CHECKING:
    import pytest_mock


class CompactTestRole(LLMTestRole, Compact):
    """Test role mixing the dummy LLM into the Compact capability."""


@pytest.fixture
def role() -> CompactTestRole:
    """Instantiate the test role for each test."""
    return CompactTestRole(name="compact")


@pytest.mark.parametrize(
    ("text", "length_type", "expected"),
    [
        ("hello", LengthType.Chars, 5),
        ("héllo wörld", LengthType.Chars, 11),
        ("one two three", LengthType.Words, 3),
        ("  spaced   out  ", LengthType.Words, 2),
        ("First. Second!", LengthType.Sentences, 2),
        ("你好。世界！", LengthType.Sentences, 2),
        ("No punctuation here", LengthType.Sentences, 1),
        ("¿Qué?", LengthType.Sentences, 1),
        ("", LengthType.Sentences, 0),
    ],
)
def test_length_counts(text: str, length_type: LengthType, expected: int) -> None:
    """The length counter matches the documented unit semantics."""
    assert _length(text, length_type) == expected


@pytest.mark.asyncio
async def test_compact_returns_text_within_char_bound(role: CompactTestRole) -> None:
    """A response within the character bound is returned."""
    with install_router_usage("short text"):
        result = await role.compact(
            "A much longer piece of raw text that needs shortening.",
            "keep the main idea",
            target_length=10,
        )
    assert result == "short text"


@pytest.mark.asyncio
async def test_compact_strips_surrounding_whitespace(role: CompactTestRole) -> None:
    """Leading and trailing whitespace is trimmed before measuring and returning."""
    with install_router_usage("  short  "):
        result = await role.compact(
            "A much longer piece of raw text that needs shortening.",
            "keep the main idea",
            target_length=10,
        )
    assert result == "short"


@pytest.mark.asyncio
async def test_compact_rejects_oversized_response(role: CompactTestRole) -> None:
    """Responses over the bound fail validation on every attempt and surface as None."""
    with install_router_usage(*return_router_usage("this is far too long", "still far too long", "way over the bound")):
        result = await role.compact(
            "A much longer piece of raw text that needs shortening.",
            "keep the main idea",
            target_length=10,
        )
    assert result is None


@pytest.mark.asyncio
async def test_compact_retries_until_within_bound(role: CompactTestRole) -> None:
    """An oversized first response is retried and the valid one is returned."""
    with install_router_usage("way too long for the bound", "ok text"):
        result = await role.compact(
            "A much longer piece of raw text that needs shortening.",
            "keep the main idea",
            target_length=10,
        )
    assert result == "ok text"


@pytest.mark.asyncio
async def test_compact_measures_words(role: CompactTestRole) -> None:
    """The Words unit counts whitespace-separated tokens."""
    with install_router_usage("one two three"):
        result = await role.compact(
            "A much longer piece of raw text that needs shortening.",
            "keep the main idea",
            target_length=3,
            length_type=LengthType.Words,
        )
    assert result == "one two three"


@pytest.mark.asyncio
async def test_compact_embeds_raw_text_in_prompt(role: CompactTestRole, mocker: "pytest_mock.MockerFixture") -> None:
    """The raw text, requirement, and length bound reach the rendered prompt."""
    spy = mocker.patch.object(Compact, "aask_validate", autospec=True)
    spy.return_value = "ok"

    result = await role.compact(
        "RAW TEXT TO COMPACT",
        "keep the main idea",
        target_length=10,
        length_type=LengthType.Words,
    )

    assert result == "ok"
    question = spy.call_args.kwargs["question"]
    assert "RAW TEXT TO COMPACT" in question
    assert "keep the main idea" in question
    assert "10 words" in question
