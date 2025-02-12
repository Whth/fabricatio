import pytest
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.task import Task

class TestAction(Action):
    async def _execute(self, task_input: Task[str], **_) -> str:
        return "TestAction executed"

@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")

@pytest.fixture
def test_action(task):
    return TestAction(task_input=task)

@pytest.fixture
def test_workflow(test_action):
    return WorkFlow(steps=(test_action,))

async def test_workflow_execute(test_workflow, task):
    await test_workflow.execute(task)
    assert test_workflow.steps[0].task_input == task

async def test_workflow_model_post_init(test_workflow):
    assert test_workflow._instances == test_workflow.steps

async def test_workflow_serve(test_workflow, task):
    await test_workflow.serve(task)
    assert test_workflow.steps[0].task_input == task