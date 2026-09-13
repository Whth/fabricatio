"""Test the Remember capability."""

import uuid
from pathlib import Path
from typing import cast

import pytest
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_memory.config import memory_config
from fabricatio_memory.models.note import Note
from fabricatio_mock import MockScript, Value, make_test_role


def note(content: str = "test content", importance: int = 5, tags: list[str] | None = None) -> Note:
    """Create Note with test data.

    Args:
        content (str): Note content
        importance (float): Importance value
        tags (List[str]): List of tags

    Returns:
        Note: Note object with test data
    """
    return Note(content=content, importance=importance, tags=tags or ["test"])


@pytest.fixture(scope="session")
def shared_temp_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a shared temporary directory for testing."""
    p = tmp_path_factory.mktemp("store_root")

    memory_config.memory_store_root = p
    return p


@pytest.fixture
def role(shared_temp_dir: Path) -> Remember:
    """Create a test role for the Remember capability.

    Args:
        shared_temp_dir (Path): Shared temporary directory fixture

    Returns:
        Remember: Test role with a mounted memory store
    """
    test_role = cast("Remember", make_test_role(Remember, name="remember"))
    test_role.memory_store_name = uuid.uuid4().hex
    return test_role.mount_memory_store()


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
async def test_record(role: Remember, ret_value: SketchedAble, raw_input: str) -> None:
    """Test the record method with different inputs.

    Args:
        role (Remember): Remember test role fixture
        ret_value (SketchedAble): Expected return value
        raw_input (str): Raw input to be recorded
    """
    with MockScript.from_values(Value.from_model(ret_value, name="recorded note")):
        recorded_note = ok(await role.record(raw_input))
        assert recorded_note.model_dump_json() == ret_value.model_dump_json()

        role.access_memory_store().write()
        assert role.access_memory_store().search_memories(recorded_note.content)[0].content == recorded_note.content, (
            "Memory system search failed"
        )


@pytest.mark.asyncio
async def test_recall(role: Remember) -> None:
    """Test the recall method.

    Args:
        role (Remember): Remember test role fixture
    """
    query = "project deadlines"
    expected_response = "Based on your memories, the project deadline is next Friday."

    with MockScript.from_values(Value.from_text(expected_response, name="recall summary")):
        recalled_info = await role.recall(query, top_k=5)
        assert recalled_info == expected_response


@pytest.mark.asyncio
async def test_recall_with_defaults(role: Remember) -> None:
    """Test the recall method with default parameters.

    Args:
        role (Remember): Remember test role fixture
    """
    query = "shopping list"
    expected_response = "You need to buy milk and bread."

    with MockScript.from_values(Value.from_text(expected_response, name="recall summary")):
        recalled_info = await role.recall(query)
        assert recalled_info == expected_response


@pytest.mark.asyncio
async def test_record_multiple_notes(role: Remember) -> None:
    """Test recording multiple notes in sequence.

    Args:
        role (Remember): Remember test role fixture
    """
    notes = [
        note("First note", 70, ["tag1"]),
        note("Second note", 40, ["tag2"]),
        note("Third note", 90, ["tag3"]),
    ]

    with MockScript.from_values(
        *[Value.from_model(expected_note, name=f"note {i}") for i, expected_note in enumerate(notes, start=1)]
    ):
        for i, expected_note in enumerate(notes):
            recorded_note = ok(await role.record(f"Raw input {i + 1}"))
            assert recorded_note.model_dump_json() == expected_note.model_dump_json()


@pytest.mark.asyncio
async def test_recall_different_parameters(role: Remember) -> None:
    """Test the recall method with different parameter combinations.

    Args:
        role (Remember): Remember test role fixture
    """
    query = "work tasks"
    expected_response = "Your work tasks include reviewing code and attending meetings."

    role.access_memory_store().add_memory("You have a meeting at 3 PM today.", 80, ["work"])
    with MockScript.from_values(Value.from_text(expected_response, name="recall summary")):
        # Test with custom top_k and boost_recent=False
        recalled_info = await role.recall(query, top_k=10, boost_recent=False)
        assert recalled_info == expected_response
