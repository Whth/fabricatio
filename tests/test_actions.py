from fabricatio.models.action import Action, WorkFlow


def test_action_imports():
    """Test that all actions are properly imported."""
    assert Action is not None
    assert WorkFlow is not None


def test_action_execution():
    """Test basic action execution."""

    # Create a simple action class
    class TestAction(Action):
        async def _execute(self, *args, **kwargs):
            return "executed"

    action = TestAction()
    result = action._execute()
    assert result == "executed"


# Skip workflow imports test since workflows is not directly in actions module


def test_workflow_execution():
    """Test basic workflow execution."""

    # Create a simple workflow class
    class TestWorkflow(WorkFlow):
        def __init__(self):
            super().__init__("test_workflow", [])

        async def _run(self, *args, **kwargs):
            return "workflow_executed"

    workflow = TestWorkflow()
    result = workflow._run()
    assert result == "workflow_executed"


def test_action_inheritance():
    """Test that custom actions can inherit from Action."""

    class CustomAction(Action):
        def _execute(self):
            return {"result": 42}

    action = CustomAction()
    result = action.execute()
    assert isinstance(result, dict)
    assert result["result"] == 42


def test_workflow_inheritance():
    """Test that custom workflows can inherit from WorkFlow."""

    class CustomWorkflow(WorkFlow):
        def __init__(self):
            super().__init__()

        def _run(self):
            return ["step1", "step2"]

    workflow = CustomWorkflow()
    result = workflow.run()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == "step1"
