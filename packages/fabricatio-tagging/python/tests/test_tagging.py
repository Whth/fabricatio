"""Tests for the tagging capability."""

import asyncio
import json
from typing import List

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_tagging.capabilities.tagging import Tagging


class TaggingRole(LLMTestRole, Tagging):
    """A class that tests the tagging methods."""


@pytest.fixture
def role() -> TaggingRole:
    """Create a TaggingRole instance for testing.

    Returns:
        TaggingRole: TaggingRole instance
    """
    return TaggingRole()


@pytest.fixture
def responses(mock_tags: List[str]) -> list[str]:
    """Create a responses fixture that returns a specific JSON tag list.

    Args:
        mock_tags: Tags to be returned by the router

    Returns:
        list[str]: Response strings in JSON array format
    """
    return return_router_usage(json.dumps(mock_tags))


@pytest.mark.parametrize(
    ("mock_tags", "text", "requirement", "k"),
    [
        (["python", "rust", "programming"], "This is a Python and Rust tutorial", "", 0),
        (["ai", "machine-learning"], "An introduction to AI and ML", "tag the topic", 0),
        (["tag1"], "Some text", "", 1),
        (["a", "b", "c", "d", "e"], "Text with many tags", "generate tags", 0),
    ],
    ids=["basic_tags", "with_requirement", "single_tag", "many_tags"],
)
@pytest.mark.asyncio
async def test_tagging_single_string(
    responses: list[str], role: TaggingRole, mock_tags: List[str], text: str, requirement: str, k: int
) -> None:
    """Test the tagging method with a single text string.

    Args:
        responses: Mocked response strings
        role: TaggingRole fixture
        mock_tags: Expected tags
        text: Input text to tag
        requirement: Tagging requirement
        k: Maximum number of tags
    """
    with install_router_usage(*responses):
        result = await role.tagging(text, requirement=requirement, k=k)
        assert result == mock_tags


@pytest.mark.asyncio
async def test_tagging_single_string_returns_none(
    role: TaggingRole,
) -> None:
    """Test the tagging method returns None when LLM response is invalid."""
    # Empty JSON array won't parse correctly as a list of strings for k > 0
    responses = return_router_usage("invalid json response")
    with install_router_usage(*responses):
        result = await role.tagging("some text")
        assert result is None


@pytest.mark.asyncio
async def test_tagging_list_of_strings(
    role: TaggingRole,
) -> None:
    """Test the tagging method with a list of text strings."""
    responses = return_router_usage(
        json.dumps(["python"]),
        json.dumps(["rust", "systems"]),
        json.dumps(["web", "frontend"]),
    )

    with install_router_usage(*responses):
        result = await role.tagging(["text1", "text2", "text3"])
        assert len(result) == 3
        # asyncio.gather processes items concurrently; order may differ
        assert sorted(result) == sorted([["python"], ["rust", "systems"], ["web", "frontend"]])


@pytest.mark.asyncio
async def test_tagging_list_empty_texts(
    role: TaggingRole,
) -> None:
    """Test the tagging method with empty strings in the list."""
    responses = return_router_usage(json.dumps([]), json.dumps([]))

    with install_router_usage(*responses):
        result = await role.tagging(["", ""])
        assert result == [[], []]


@pytest.mark.asyncio
async def test_tagging_list_returns_empty_for_none(
    role: TaggingRole,
) -> None:
    """Test the tagging method with list input returns empty list when LLM returns None."""
    responses = return_router_usage("invalid json")

    with install_router_usage(*responses):
        result = await role.tagging(["some text"])
        # When alist_v returns None for a list item, the code converts it to []
        assert result == [[]]


def test_tagging_invalid_type_raises(
    role: TaggingRole,
) -> None:
    """Test the tagging method raises TypeError for invalid input types."""
    with pytest.raises(TypeError, match=r"text must be str or List\[str\]"):
        asyncio.run(role.tagging(123))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("mock_tags", "text", "requirement"),
    [
        (["science", "physics", "quantum"], "Quantum mechanics is a branch of physics", "Focus on scientific topics"),
        (["programming", "tutorial"], "Learn to code with Python", "Identify programming-related tags"),
    ],
    ids=["science_tags", "programming_tags"],
)
@pytest.mark.asyncio
async def test_tagging_with_requirement(
    responses: list[str], role: TaggingRole, mock_tags: List[str], text: str, requirement: str
) -> None:
    """Test the tagging method with various requirements.

    Args:
        responses: Mocked response strings
        role: TaggingRole fixture
        mock_tags: Expected tags
        text: Input text to tag
        requirement: Tagging requirement
    """
    with install_router_usage(*responses):
        result = await role.tagging(text, requirement=requirement)
        assert result == mock_tags


@pytest.mark.asyncio
async def test_tagging_empty_string(
    role: TaggingRole,
) -> None:
    """Test the tagging method with an empty text string."""
    responses = return_router_usage(json.dumps(["empty"]))
    with install_router_usage(*responses):
        result = await role.tagging("")
        assert result == ["empty"]


@pytest.mark.asyncio
async def test_tagging_single_tag(
    role: TaggingRole,
) -> None:
    """Test the tagging method returning a single tag."""
    responses = return_router_usage(json.dumps(["only-tag"]))
    with install_router_usage(*responses):
        result = await role.tagging("some content")
        assert result == ["only-tag"]


@pytest.mark.asyncio
async def test_tagging_preserves_order(
    role: TaggingRole,
) -> None:
    """Test that tagging preserves the order of tags in the response."""
    ordered_tags = ["z_tag", "a_tag", "m_tag"]
    responses = return_router_usage(json.dumps(ordered_tags))
    with install_router_usage(*responses):
        result = await role.tagging("text")
        assert result == ordered_tags
        assert result is not None
        assert result[0] == "z_tag"
        assert result[-1] == "m_tag"


@pytest.mark.asyncio
async def test_tagging_list_mixed_results(
    role: TaggingRole,
) -> None:
    """Test the tagging method with list input where some items succeed and some fail."""
    # First item returns valid tags, second returns invalid JSON
    responses = return_router_usage(json.dumps(["valid_tag"]), "not valid json")

    with install_router_usage(*responses):
        result = await role.tagging(["text1", "text2"])
        assert len(result) == 2
        # asyncio.gather processes items concurrently; order may differ
        assert sorted(result) == sorted([[], ["valid_tag"]])


@pytest.mark.asyncio
async def test_tagging_list_longer_input(
    role: TaggingRole,
) -> None:
    """Test the tagging method with a longer list of text strings."""
    texts = [f"text_{i}" for i in range(5)]
    expected_tags = [[f"tag_{i}_a", f"tag_{i}_b"] for i in range(5)]

    responses = return_router_usage(*[json.dumps(tags) for tags in expected_tags])

    with install_router_usage(*responses):
        result = await role.tagging(texts)
        assert len(result) == 5
        # asyncio.gather processes items concurrently, so overall order may differ
        assert sorted(result) == sorted(expected_tags)
