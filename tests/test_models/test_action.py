import pytest

from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.task import Task


class TestAction(Action):
    async def _execute(self, *args, **kwargs):
        return "executed"

@pytest.mark.asyncio
async def test_action_execute():
    action = TestAction(name="test_action")
    result = await action._execute()
    assert result == "executed"

@pytest.mark.asyncio
async def test_action_act():
    action = TestAction(name="test_action", output_key="result")
    context = {"input": "data"}
    await action.act(context)
    assert context["result"] == "executed"

@pytest.mark.asyncio
async def test_workflow_execute():
    class TestWorkflowAction(Action):
        async def _execute(self, *args, **kwargs):
            return "executed"

    workflow = WorkFlow(steps=(TestWorkflowAction(name="test_workflow_action"),), name="test_workflow")
    await workflow.execute()

@pytest.mark.asyncio
async def test_workflow_model_post_init():
    class TestWorkflowAction(Action):
        async def _execute(self, *args, **kwargs):
            return "executed"

    workflow = WorkFlow(steps=(TestWorkflowAction(name="test_workflow_action"),), name="test_workflow")
    workflow.model_post_init(None)
    assert workflow.steps[0].llm_api_endpoint == workflow.llm_api_endpoint

@pytest.mark.asyncio
async def test_workflow_serve():
    class TestWorkflowAction(Action):
        async def _execute(self, *args, **kwargs):
            return "executed"

    workflow = WorkFlow(steps=(TestWorkflowAction(name="test_workflow_action"),), name="test_workflow")
    task = Task(input="data")
    await workflow.serve(task)
    assert task.status == "finished"
    assert task.output == "executed"
