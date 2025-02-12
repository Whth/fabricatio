import pytest
from fabricatio.models.generic import WithToDo, Memorable

@pytest.fixture
def with_todo():
    return WithToDo(todo="test todo")

@pytest.fixture
def memorable():
    return Memorable(memory=[])

async def test_with_todo(with_todo):
    assert with_todo.todo == "test todo"

def test_memorable_add_memory(memorable):
    memorable.add_memory("memory1")
    assert "memory1" in memorable.memory

def test_memorable_top_memories(memorable):
    memorable.add_memory("memory1")
    memorable.add_memory("memory2")
    assert memorable.top_memories(1) == ["memory2"]