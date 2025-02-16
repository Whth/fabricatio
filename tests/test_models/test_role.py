from fabricatio.models.action import WorkFlow
from fabricatio.models.role import Role
from fabricatio.models.task import Task

from tests.test_models.test_action import AnotherTestAction, TestAction  # Import TestAction and AnotherTestAction


class TestWorkflow(WorkFlow):
    name: str = "test"
    steps: list = [TestAction(), AnotherTestAction()]  # Initialize steps field


def test_role_initialization():
    role = Role(name="Test Role", registry={})
    assert role.name == "Test Role"


async def test_role_execution():
    role = Role(name="Test Role", registry={})
    task = Task(name="test task", goal="test", description="test")
    result = await role.act(task)
    assert result is not None


def test_role_add_action():
    role = Role(name="Test Role", registry={})
    role.add_action(TestWorkflow())
    assert len(role.actions) == 2


def test_role_remove_action():
    role = Role(name="Test Role", registry={})
    role.remove_action(TestWorkflow())
    assert len(role.actions) == 0
