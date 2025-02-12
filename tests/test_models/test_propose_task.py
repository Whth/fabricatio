import pytest

from fabricatio.models.task import ProposeTask, Task


@pytest.fixture
def propose_task():
    return ProposeTask()


@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")


def test_propose_task_initialization(propose_task):
    assert propose_task.proposed_task is None


def test_propose_task_propose_task(propose_task, task):
    propose_task.propose_task(task)
    assert propose_task.proposed_task == task
