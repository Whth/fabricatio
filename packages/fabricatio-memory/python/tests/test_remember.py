"""Test the Remember capability."""

from typing import List

import pytest
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_memory.models.note import Note
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string, return_string
from fabricatio_mock.utils import install_router
from litellm import Router


def note(content: str = "test content", importance: float = 0.5, tags: List[str] | None = None) -> Note:
    """Create Note with test data.

    Args:
        content (str): Note content
        importance (float): Importance value between 0 and 1
        tags (List[str]): List of tags

    Returns:
        Note: Note object with test data
    """
    if tags is None:
        tags = ["test"]
    return Note(content=content, importance=importance, tags=tags)


class RememberRole(LLMTestRole, Remember):
    """A class that tests the Remember capability."""


@pytest.fixture
def router(ret_value: SketchedAble) -> Router:
    """Create a router fixture that returns a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        Router: Router instance
    """
    return return_model_json_string(ret_value)


@pytest.fixture
def role() -> RememberRole:
    """Create a RememberRole instance for testing.

    Returns:
        RememberRole: RememberRole instance
    """
    return RememberRole()


@pytest.mark.parametrize(
    ("ret_value", "raw_input"),
    [
        (
            note("Important meeting notes", 0.8, ["meeting", "work"]),
            "Had a meeting about project deadlines",
        ),
        (
            note("Shopping list", 0.3, ["personal", "shopping"]),
            "Need to buy milk and bread",
        ),
    ],
)
@pytest.mark.asyncio
async def test_record(router: Router, role: RememberRole, ret_value: SketchedAble, raw_input: str) -> None:
    """Test the record method with different inputs.

    Args:
        router (Router): Mocked router fixture
        role (RememberRole): RememberRole fixture
        ret_value (SketchedAble): Expected return value
        raw_input (str): Raw input to be recorded
    """
    with install_router(router):
        recorded_note = ok(await role.record(raw_input))
        assert recorded_note.model_dump_json() == ret_value.model_dump_json()

        assert role.memory_system.search_memories(recorded_note.content)[0].content == recorded_note.content, (
            "Memory system search failed"
        )


@pytest.mark.asyncio
async def test_recall(role: RememberRole) -> None:
    """Test the recall method.

    Args:
        role (RememberRole): RememberRole fixture
    """
    query = "project deadlines"
    expected_response = "Based on your memories, the project deadline is next Friday."

    router = return_string(expected_response)

    with install_router(router):
        recalled_info = await role.recall(query, top_k=5)
        assert recalled_info == expected_response


@pytest.mark.asyncio
async def test_recall_with_defaults(role: RememberRole) -> None:
    """Test the recall method with default parameters.

    Args:
        role (RememberRole): RememberRole fixture
    """
    query = "shopping list"
    expected_response = "You need to buy milk and bread."

    router = return_string(expected_response)

    with install_router(router):
        recalled_info = await role.recall(query)
        assert recalled_info == expected_response


@pytest.mark.asyncio
async def test_record_multiple_notes(role: RememberRole) -> None:
    """Test recording multiple notes in sequence.

    Args:
        role (RememberRole): RememberRole fixture
    """
    notes = [
        note("First note", 0.7, ["tag1"]),
        note("Second note", 0.4, ["tag2"]),
        note("Third note", 0.9, ["tag3"]),
    ]

    router = return_model_json_string(*notes)

    with install_router(router):
        for i, expected_note in enumerate(notes):
            recorded_note = ok(await role.record(f"Raw input {i + 1}"))
            assert recorded_note.model_dump_json() == expected_note.model_dump_json()


@pytest.mark.asyncio
async def test_recall_different_parameters(role: RememberRole) -> None:
    """Test the recall method with different parameter combinations.

    Args:
        role (RememberRole): RememberRole fixture
    """
    query = "work tasks"
    expected_response = "Your work tasks include reviewing code and attending meetings."

    router = return_string(expected_response)
    role.memory_system.add_memory("You have a meeting at 3 PM today.", 0.8, ["work"])
    with install_router(router):
        # Test with custom top_k and boost_recent=False
        recalled_info = await role.recall(query, top_k=10, boost_recent=False)
        assert recalled_info == expected_response
