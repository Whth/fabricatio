import pytest
from fabricatio.models.action import WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.role import Role
from fabricatio.models.tool import ToolBox


@pytest.fixture
def sample_workflow():
    return WorkFlow(name="Test Workflow", steps=[], description="Test workflow description")


@pytest.fixture
def sample_role(sample_workflow):
    return Role(
        registry={"test_event": sample_workflow},
        name="Test Role",
        description="Test role description",
        prompts={},
        personality="Test personality",
    )


def test_role_initialization(sample_workflow):
    role = Role(
        registry={"test_event": sample_workflow},
        name="Test Role",
        description="Test role description",
        prompts={},
        personality="Test personality",
    )
    assert isinstance(role.registry, dict)
    assert len(role.registry) == 1
    assert "test_event" in role.registry


def test_role_register_workflows(sample_role):
    result = sample_role.register_workflows()
    assert isinstance(result, Role)
    assert len(result.registry) == 1


def test_role_resolve_configuration(sample_role):
    result = sample_role.resolve_configuration()
    assert isinstance(result, Role)
    assert len(result.registry) == 1


def test_role_toolboxes(sample_role):
    assert hasattr(sample_role, "toolboxes")
    assert isinstance(sample_role.toolboxes, set)


def test_role_with_event(sample_workflow):
    event = Event(segments=["test", "event"])
    role = Role(
        registry={event: sample_workflow},
        name="Test Role",
        description="Test role description",
        prompts={},
        personality="Test personality",
    )
    assert event in role.registry


def test_role_post_init(sample_role):
    sample_role.model_post_init(None)
    assert len(sample_role.registry) == 1


def test_role_with_multiple_workflows(sample_workflow):
    workflow2 = WorkFlow(name="Test Workflow 2", steps=[], description="Test workflow 2 description")
    role = Role(
        registry={"test_event1": sample_workflow, "test_event2": workflow2},
        name="Test Role",
        description="Test role description",
        prompts={},
        personality="Test personality",
    )
    assert len(role.registry) == 2


def test_role_with_custom_toolbox():
    custom_toolbox = ToolBox(name="Custom Toolbox", description="Custom toolbox description")
    role = Role(
        registry={},
        name="Test Role",
        description="Test role description",
        prompts={},
        personality="Test personality",
        toolboxes={custom_toolbox},
    )
    assert custom_toolbox in role.toolboxes
