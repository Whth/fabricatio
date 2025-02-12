import pytest
from fabricatio.models.role import Role
from fabricatio.models.action import WorkFlow
from fabricatio.models.task import Task

class TestWorkflow(WorkFlow):
    pass

@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")

@pytest.fixture
def test_workflow(task):
    return TestWorkflow(steps=(Action(task_input=task),))

@pytest.fixture
def test_role(test_workflow):
    return Role(name="Test Role", actions=[test_workflow])

async def test_role_act(test_role, task):
    await test_role.act(task)
    assert test_role.actions[0].steps[0].task_input == task