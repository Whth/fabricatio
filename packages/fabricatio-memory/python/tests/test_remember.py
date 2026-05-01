"""Test the Remember capability."""

import uuid
from pathlib import Path
from typing import List

import pytest
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_memory.config import memory_config
from fabricatio_memory.models.note import Note
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage, return_router_usage
from fabricatio_mock.utils import install_router_usage


def note(content: str = "test content", importance: int = 5, tags: List[str] | None = None) -> Note:
    """Create Note with test data.

    Args:
        content (str): Note content
        importance (float): Importance value
        tags (List[str]): List of tags

    Returns:
        Note: Note object with test data
    """
    return Note(content=content, importance=importance, tags=tags or ["test"])


class RememberRole(LLMTestRole, Remember):
    """A class that tests the Remember capability."""


@pytest.fixture
def responses(ret_value: SketchedAble) -> list[str]:
    """Create mock router responses that return a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        list[str]: List of response strings
    """
    return return_model_json_router_usage(ret_value)


@pytest.fixture(scope="session")
def shared_temp_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a shared temporary directory for testing."""
    p = tmp_path_factory.mktemp("store_root")

    memory_config.memory_store_root = p
    return p


@pytest.fixture
def role(shared_temp_dir: Path) -> RememberRole:
    """Create a RememberRole instance for testing.

    Returns:
        RememberRole: RememberRole instance
    """
    return RememberRole(memory_store_name=uuid.uuid7().hex).mount_memory_store()


@pytest.mark.parametrize(
    ("ret_value", "raw_input"),
    [
        (
            note("Important meeting notes", 80, ["meeting", "work"]),
            "Had a meeting about project deadlines",
        ),
        (
            note("Shopping list", 30, ["personal", "shopping"]),
            "Need to buy milk and bread",
        ),
    ],
)
@pytest.mark.asyncio
async def test_record(responses: list[str], role: RememberRole, ret_value: SketchedAble, raw_input: str) -> None:
    """Test the record method with different inputs.

    Args:
        responses (list[str]): Mocked router responses fixture
        role (RememberRole): RememberRole fixture
        ret_value (SketchedAble): Expected return value
        raw_input (str): Raw input to be recorded
    """
    with install_router_usage(*responses):
        recorded_note = ok(await role.record(raw_input))
        assert recorded_note.model_dump_json() == ret_value.model_dump_json()

        role.access_memory_store().write()
        assert role.access_memory_store().search_memories(recorded_note.content)[0].content == recorded_note.content, (
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

    responses = return_router_usage(expected_response)

    with install_router_usage(*responses):
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

    responses = return_router_usage(expected_response)

    with install_router_usage(*responses):
        recalled_info = await role.recall(query)
        assert recalled_info == expected_response


@pytest.mark.asyncio
async def test_record_multiple_notes(role: RememberRole) -> None:
    """Test recording multiple notes in sequence.

    Args:
        role (RememberRole): RememberRole fixture
    """
    notes = [
        note("First note", 70, ["tag1"]),
        note("Second note", 40, ["tag2"]),
        note("Third note", 90, ["tag3"]),
    ]

    responses = return_model_json_router_usage(*notes)

    with install_router_usage(*responses):
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

    responses = return_router_usage(expected_response)
    role.access_memory_store().add_memory("You have a meeting at 3 PM today.", 80, ["work"])
    with install_router_usage(*responses):
        # Test with custom top_k and boost_recent=False
        recalled_info = await role.recall(query, top_k=10, boost_recent=False)
        assert recalled_info == expected_response
