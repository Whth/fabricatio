"""Tests for the digest."""

from typing import List, Set

import pytest
from fabricatio_core import Role, Task
from fabricatio_core.models.generic import SketchedAble
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_digest.models.tasklist import TaskList
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string, return_string
from fabricatio_mock.utils import install_router
from litellm import Router


class MockRole(Role):
    """Mock role for testing purposes."""


class DigestRole(LLMTestRole, Digest):
    """A test role that implements the Digest capability."""

    pass


@pytest.fixture
def digest_role() -> DigestRole:
    """Create a DigestRole instance for testing.

    Returns:
        DigestRole: DigestRole instance
    """
    return DigestRole()


@pytest.fixture
def mock_receptions() -> Set[MockRole]:
    """Create mock receptions for testing.

    Returns:
        Set[MockRole]: List of mock roles
    """
    return {
        MockRole(name="Reception 1", description="Reception 1 briefing"),
        MockRole(name="Reception 2", description="Reception 2 briefing"),
        MockRole(name="Reception 3", description="Reception 3 briefing"),
    }


def create_test_tasklist(target: str, task_descriptions: List[str]) -> TaskList:
    """Create a test TaskList with given target and task descriptions.

    Args:
        target (str): The ultimate target
        task_descriptions (List[str]): List of task descriptions

    Returns:
        TaskList: TaskList instance
    """
    tasks = [Task(name=f"Task {i + 1}", description=desc) for i, desc in enumerate(task_descriptions)]
    return TaskList(ultimate_target=target, tasks=tasks)


@pytest.fixture
def router(ret_value: SketchedAble) -> Router:
    """Create a router fixture that returns a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        Router: Router instance
    """
    return return_model_json_string(ret_value)


@pytest.mark.parametrize(
    ("requirement", "expected_target", "expected_task_count"),
    [
        (
            "Build a user management system",
            "Build a user management system",
            3,
        ),
        (
            "Create a data processing pipeline",
            "Create a data processing pipeline",
            4,
        ),
        (
            "Implement authentication flow",
            "Implement authentication flow",
            2,
        ),
    ],
)
@pytest.mark.asyncio
async def test_digest_success(
    digest_role: DigestRole,
    mock_receptions: Set[MockRole],
    requirement: str,
    expected_target: str,
    expected_task_count: int,
) -> None:
    """Test successful digest generation with various requirements.

    Args:
        digest_role (DigestRole): DigestRole fixture
        mock_receptions (Set[MockRole]): Mock receptions
        requirement (str): Test requirement
        expected_target (str): Expected ultimate target
        expected_task_count (int): Expected number of tasks
    """
    # Create test data
    task_descriptions = [f"Task {i + 1} for {requirement}" for i in range(expected_task_count)]
    test_tasklist = create_test_tasklist(expected_target, task_descriptions)

    router = return_model_json_string(test_tasklist)

    with install_router(router):
        result = await digest_role.digest(requirement, mock_receptions)

        assert result is not None
        assert result.ultimate_target == expected_target
        assert len(result.tasks) == expected_task_count
        assert all(isinstance(task, Task) for task in result.tasks)


@pytest.mark.asyncio
async def test_digest_with_empty_receptions(digest_role: DigestRole) -> None:
    """Test digest with empty receptions list.

    Args:
        digest_role (DigestRole): DigestRole fixture
    """
    requirement = "Simple task"
    test_tasklist = create_test_tasklist(requirement, ["Single task"])

    router = return_model_json_string(test_tasklist)

    with install_router(router):
        result = await digest_role.digest(requirement, set())

        assert result is not None
        assert result.ultimate_target == requirement
        assert len(result.tasks) == 1


@pytest.mark.asyncio
async def test_digest_returns_none(digest_role: DigestRole, mock_receptions: Set[MockRole]) -> None:
    """Test digest when it returns None.

    Args:
        digest_role (DigestRole): DigestRole fixture
        mock_receptions (Set[MockRole]): Mock receptions
    """
    router = return_string("null")

    with install_router(router):
        result = await digest_role.digest("Test requirement", mock_receptions)

        assert result is None


@pytest.mark.asyncio
async def test_digest_with_single_reception(digest_role: DigestRole) -> None:
    """Test digest with a single reception.

    Args:
        digest_role (DigestRole): DigestRole fixture
    """
    requirement = "Single reception task"
    single_reception = [MockRole(briefing="Single reception briefing")]
    test_tasklist = create_test_tasklist(requirement, ["Task 1", "Task 2"])

    router = return_model_json_string(test_tasklist)

    with install_router(router):
        result = await digest_role.digest(requirement, single_reception)

        assert result is not None
        assert result.ultimate_target == requirement
        assert len(result.tasks) == 2


@pytest.mark.asyncio
async def test_digest_with_kwargs(digest_role: DigestRole, mock_receptions: Set[MockRole]) -> None:
    """Test digest with additional kwargs.

    Args:
        digest_role (DigestRole): DigestRole fixture
        mock_receptions (Set[MockRole]): Mock receptions
    """
    requirement = "Task with kwargs"
    test_tasklist = create_test_tasklist(requirement, ["Task with custom settings"])

    router = return_model_json_string(test_tasklist)

    with install_router(router):
        result = await digest_role.digest(requirement, mock_receptions, temperature=0.7, model="gpt-4")

        assert result is not None
        assert result.ultimate_target == requirement


@pytest.mark.asyncio
async def test_digest_complex_requirement(digest_role: DigestRole, mock_receptions: Set[MockRole]) -> None:
    """Test digest with a complex, multi-part requirement.

    Args:
        digest_role (DigestRole): DigestRole fixture
        mock_receptions (Set[MockRole]): Mock receptions
    """
    requirement = "Build a complete e-commerce platform with user management, product catalog, shopping cart, and payment processing"
    complex_tasks = [
        "Set up user authentication system",
        "Create product catalog management",
        "Implement shopping cart functionality",
        "Integrate payment processing",
        "Build admin dashboard",
        "Implement order management",
    ]
    test_tasklist = create_test_tasklist(requirement, complex_tasks)

    router = return_model_json_string(test_tasklist)

    with install_router(router):
        result = await digest_role.digest(requirement, mock_receptions)

        assert result is not None
        assert result.ultimate_target == requirement
        assert len(result.tasks) == 6
        assert all(task.description for task in result.tasks)
