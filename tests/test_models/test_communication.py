import pytest

from fabricatio.actions.communication import Talk
from fabricatio.models.task import Task


@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")


@pytest.fixture
def talk(task):
    return Talk(task_input=task)


async def test_talk_execute(talk, task):
    result = await talk._execute(task)
    assert result == "Talk executed"
