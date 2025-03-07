import pytest
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.task import Task
from fabricatio.models.utils import TaskStatus


class DemoAction(Action):
    name: str = "TestAction"

    async def _execute(self, **_) -> str:
        return "test result"


class FailingAction(Action):
    name: str = "FailingAction"

    async def _execute(self, **_) -> str:
        raise RuntimeError("Test error")


@pytest.fixture
def basic_action():
    return DemoAction()


@pytest.fixture
def basic_workflow():
    return WorkFlow(name="TestWorkflow", steps=(DemoAction(),))


# Action Tests
def test_action_basic_attributes(basic_action):
    assert basic_action.name == "TestAction"
    assert basic_action.personality == ""
    assert basic_action.output_key == ""


def test_action_with_personality():
    action = DemoAction(personality="Helpful Assistant")
    assert action.personality == "Helpful Assistant"


def test_action_with_output_key():
    action = DemoAction(output_key="test_output")
    assert action.output_key == "test_output"


@pytest.mark.asyncio
async def test_action_act_without_output_key(basic_action):
    context = {}
    result = await basic_action.act(context)
    assert result == {}


@pytest.mark.asyncio
async def test_action_act_with_output_key():
    action = DemoAction(output_key="result")
    context = {}
    result = await action.act(context)
    assert result["result"] == "test result"


def test_action_briefing_without_personality(basic_action):
    briefing = basic_action.briefing
    assert "personality" not in briefing.lower()


def test_action_briefing_with_personality():
    action = DemoAction(personality="Helper")
    briefing = action.briefing
    assert "personality" in briefing.lower()
    assert "Helper" in briefing


# WorkFlow Tests
def test_workflow_basic_attributes(basic_workflow):
    assert basic_workflow.name == "TestWorkflow"
    assert len(basic_workflow.steps) == 1
    assert basic_workflow.task_input_key == "task_input"
    assert basic_workflow.task_output_key == "task_output"


def test_workflow_with_multiple_steps():
    workflow = WorkFlow(name="MultiStep", steps=[DemoAction(), DemoAction()])
    assert len(workflow.steps) == 2
    assert len(workflow._instances) == 2


def test_workflow_with_custom_keys():
    workflow = WorkFlow(
        name="CustomKeys", steps=[DemoAction()], task_input_key="custom_input", task_output_key="custom_output"
    )
    assert workflow.task_input_key == "custom_input"
    assert workflow.task_output_key == "custom_output"


def test_workflow_with_extra_context():
    extra_context = {"key": "value"}
    workflow = WorkFlow(name="ExtraContext", steps=[DemoAction()], extra_init_context=extra_context)
    assert workflow.extra_init_context == extra_context


@pytest.mark.asyncio
async def test_workflow_serve_success():
    workflow = WorkFlow(name="TestServe", steps=[DemoAction()])
    task = Task(name="test", goals=["test"], description="test")
    await workflow.serve(task)
    assert task._status == TaskStatus.Finished


@pytest.mark.asyncio
async def test_workflow_serve_failure():
    workflow = WorkFlow(name="TestServeFail", steps=[FailingAction()])
    task = Task(name="test", goals=["test"], description="test")
    await workflow.serve(task)
    assert task
