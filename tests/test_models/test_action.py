import pytest
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.task import Task


class TestAction(Action):
    name: str = "TestAction"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return "Action executed"


class AnotherTestAction(Action):
    name: str = "AnotherTestAction"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return "Another Action executed"


def test_action_initialization():
    action = TestAction()
    assert action.name == "TestAction"
    assert action.description is not None


def test_workflow_initialization():
    workflow = WorkFlow(name="TestWorkflow", steps=[TestAction(), AnotherTestAction()])
    assert len(workflow.steps) == 2
    assert workflow.name == "TestWorkflow"


async def test_workflow_execution():
    workflow = WorkFlow(name="TestWorkflow", steps=[TestAction(), AnotherTestAction()])
    task = Task(name="test task", goal="test", description="test")
    await workflow.serve(task)  # Use serve method instead of _execute


def test_workflow_fallback_to_self():
    workflow = WorkFlow(name="TestWorkflow", steps=[TestAction(), AnotherTestAction()])
    result = workflow.fallback_to(workflow)  # Use fallback_to method instead of fallback_to_self
    assert result == workflow

# New test cases
def test_workflow_model_post_init():
    workflow = WorkFlow(name="TestWorkflow", steps=[TestAction(), AnotherTestAction()])
    workflow.model_post_init(None)
    # Add assertions based on expected behavior

def test_workflow_inject_personality():
    workflow = WorkFlow(name="TestWorkflow", steps=[TestAction(), AnotherTestAction()])
    workflow.inject_personality("Test Personality")
    # Add assertions based on expected behavior

