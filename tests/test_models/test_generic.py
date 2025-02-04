import pytest

from fabricatio.models.generic import WithToDo, Memorable


@pytest.mark.asyncio
async def test_with_todo():
    todo = WithToDo()
    await todo.add_todo("Task 1")
    await todo.add_todo("Task 2")
    assert await todo.get_todo() == "Task 1"
    assert await todo.get_todo() == "Task 2"


def test_memorable_add_memory():
    memorable = Memorable()
    memorable.add_memory("Memory 1")
    memorable.add_memory(["Memory 2", "Memory 3"])
    assert memorable.memory == ["Memory 1", "Memory 2", "Memory 3"]


def test_memorable_top_memories():
    memorable = Memorable()
    memorable.add_memory(["Memory 1", "Memory 2", "Memory 3"])
    assert memorable.top_memories(2) == ["Memory 2", "Memory 3"]
