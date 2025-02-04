import pytest

from fabricatio.models.action import Action, WorkFlow


class TestAction(Action):
    async def execute(self, *args, **kwargs):
        return "executed"


@pytest.mark.asyncio
async def test_action_execute():
    action = TestAction()
    result = await action.execute()
    assert result == "executed"


@pytest.mark.asyncio
async def test_workflow_execute():
    class TestWorkflowAction(Action):
        async def execute(self, *args, **kwargs):
            return "executed"

    workflow = WorkFlow(steps=(TestWorkflowAction(),))
    await workflow.execute()
