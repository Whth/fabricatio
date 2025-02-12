import pytest

from fabricatio.actions.transmission import CycleTask, PublishTask
from fabricatio.models.task import Task


@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")


@pytest.fixture
def publish_task(task):
    return PublishTask(task_input=task)


@pytest.fixture
def cycle_task(task):
    return CycleTask(task_input=task)


async def test_publish_task_execute(publish_task, task):
    result = await publish_task._execute(task)
    assert result == "PublishTask executed"


async def test_cycle_task_execute(cycle_task, task):
    result = await cycle_task._execute(task)
    assert result == "CycleTask executed"
