"""Tests for the ordering capabilities."""

from typing import List, Union

import pytest
from fabricatio_capabilities.capabilities.order import Ordering
from fabricatio_core.models.generic import WithBriefing
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_json_obj_string
from fabricatio_mock.utils import install_router
from litellm import Router


def with_briefing_factory(name: str, briefing: str) -> WithBriefing:
    """Create WithBriefing object with test data.

    Args:
        name (str): Name for the WithBriefing object
        briefing (str): Briefing content for the object

    Returns:
        WithBriefing: WithBriefing object with name and briefing
    """
    return WithBriefing(name=name, description=briefing)


class OrderingRole(LLMTestRole, Ordering):
    """A class that tests the ordering methods."""


@pytest.fixture
def router(ret_value: List[str]) -> Router:
    """Create a router fixture that returns a specific list of strings.

    Args:
        ret_value (List[str]): List of strings to be returned by the router

    Returns:
        Router: Router instance
    """
    return return_json_obj_string(ret_value)


@pytest.fixture
def scores_router(ret_value: List[float]) -> Router:
    """Create a router fixture that returns specific scores as JSON.

    Args:
        ret_value (List[float]): List of scores to be returned by the router

    Returns:
        Router: Router instance
    """
    return return_json_obj_string(ret_value)


@pytest.fixture
def role() -> OrderingRole:
    """Create an OrderingRole instance for testing.

    Returns:
        OrderingRole: OrderingRole instance
    """
    return OrderingRole()


@pytest.mark.parametrize(
    ("ret_value", "seq", "requirement", "reverse", "expected_result"),
    [
        (
            ["apple", "banana", "cherry"],
            ["cherry", "apple", "banana"],
            "alphabetical order",
            False,
            ["apple", "banana", "cherry"],
        ),
        (
            ["cherry", "banana", "apple"],
            ["apple", "banana", "cherry"],
            "reverse alphabetical order",
            True,
            ["cherry", "banana", "apple"],
        ),
        (
            ["short", "medium text", "very long text here"],
            ["very long text here", "short", "medium text"],
            "order by length",
            False,
            ["short", "medium text", "very long text here"],
        ),
        (
            ["urgent", "normal", "low"],
            ["low", "urgent", "normal"],
            "order by priority",
            False,
            ["urgent", "normal", "low"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_order_string_success(
    router: Router,
    role: OrderingRole,
    ret_value: List[str],
    seq: List[str],
    requirement: str,
    reverse: bool,
    expected_result: List[str],
) -> None:
    """Test the order_string method with successful cases.

    Args:
        router (Router): Mocked router fixture
        role (OrderingRole): OrderingRole fixture
        ret_value (List[str]): Expected ordered sequence from router
        seq (List[str]): Input sequence to order
        requirement (str): Requirement for ordering
        reverse (bool): Whether to reverse the order
        expected_result (List[str]): Expected result after ordering
    """
    with install_router(router):
        result = await role.order_string(seq, requirement, reverse)
        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "seq", "requirement"),
    [
        (
            ["apple", "cherry"],  # Missing "banana"
            ["cherry", "apple", "banana"],
            "alphabetical order",
        ),
        (
            ["apple", "banana", "cherry", "extra"],  # Extra item
            ["cherry", "apple", "banana"],
            "alphabetical order",
        ),
        (
            ["different", "items", "entirely"],  # Completely different items
            ["cherry", "apple", "banana"],
            "alphabetical order",
        ),
    ],
)
@pytest.mark.asyncio
async def test_order_string_invalid_response(
    router: Router,
    role: OrderingRole,
    ret_value: List[str],
    seq: List[str],
    requirement: str,
) -> None:
    """Test order_string when LLM returns invalid sequence.

    Args:
        router (Router): Mocked router fixture
        role (OrderingRole): OrderingRole fixture
        ret_value (List[str]): Invalid sequence returned by LLM
        seq (List[str]): Input sequence
        requirement (str): Requirement for ordering
    """
    with install_router(router):
        result = await role.order_string(seq, requirement)
        assert result is None


@pytest.mark.parametrize(
    ("ret_value", "seq", "requirement", "expected_result"),
    [
        (
            ["apple", "banana", "cherry"],
            ["cherry", "apple", "banana"],
            "alphabetical order",
            ["apple", "banana", "cherry"],
        ),
        (
            ["task3", "task1", "task2"],
            ["task1", "task2", "task3"],
            "order by complexity",
            ["task3", "task1", "task2"],
        ),
        (
            [],
            [],
            "order empty list",
            None,
        ),
        (
            ["single"],
            ["single"],
            "order single item",
            ["single"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_order_with_strings(
    router: Router,
    role: OrderingRole,
    ret_value: List[str],
    seq: List[str],
    requirement: str,
    expected_result: List[str],
) -> None:
    """Test the order method with string sequences.

    Args:
        router (Router): Mocked router fixture
        role (OrderingRole): OrderingRole fixture
        ret_value (List[str]): Expected ordered sequence from router
        seq (List[str]): Input string sequence
        requirement (str): Requirement for ordering
        expected_result (List[str]): Expected result
    """
    with install_router(router):
        result = await role.order(seq, requirement)
        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "seq", "requirement", "expected_names"),
    [
        (
            ["task_a", "task_b", "task_c"],
            [
                with_briefing_factory("task_c", "Complex task requiring analysis"),
                with_briefing_factory("task_a", "Simple task"),
                with_briefing_factory("task_b", "Medium complexity task"),
            ],
            "order by complexity",
            ["task_a", "task_b", "task_c"],
        ),
        (
            ["high_priority", "medium_priority", "low_priority"],
            [
                with_briefing_factory("low_priority", "Can be done later"),
                with_briefing_factory("high_priority", "Urgent task"),
                with_briefing_factory("medium_priority", "Important but not urgent"),
            ],
            "order by priority",
            ["high_priority", "medium_priority", "low_priority"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_order_briefed_success(
    router: Router,
    role: OrderingRole,
    ret_value: List[str],
    seq: List[WithBriefing],
    requirement: str,
    expected_names: List[str],
) -> None:
    """Test the order_briefed method with WithBriefing sequences.

    Args:
        router (Router): Mocked router fixture
        role (OrderingRole): OrderingRole fixture
        ret_value (List[str]): Expected ordered names from router
        seq (List[WithBriefing]): Input WithBriefing sequence
        requirement (str): Requirement for ordering
        expected_names (List[str]): Expected ordered names
    """
    with install_router(router):
        result = await role.order_briefed(seq, requirement)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == len(expected_names)
        result_names = [item.name for item in result]
        assert result_names == expected_names


@pytest.mark.parametrize(
    ("ret_value", "seq", "requirement", "expected_names"),
    [
        (
            ["task_a", "task_b", "task_c"],
            [
                with_briefing_factory("task_c", "Complex task requiring analysis"),
                with_briefing_factory("task_a", "Simple task"),
                with_briefing_factory("task_b", "Medium complexity task"),
            ],
            "order by complexity",
            ["task_a", "task_b", "task_c"],
        ),
        (
            ["high_priority", "medium_priority", "low_priority"],
            [
                with_briefing_factory("low_priority", "Can be done later"),
                with_briefing_factory("high_priority", "Urgent task"),
                with_briefing_factory("medium_priority", "Important but not urgent"),
            ],
            "order by priority",
            ["high_priority", "medium_priority", "low_priority"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_order_with_briefings(
    router: Router,
    role: OrderingRole,
    ret_value: List[str],
    seq: List[WithBriefing],
    requirement: str,
    expected_names: List[str],
) -> None:
    """Test the order method with WithBriefing sequences.

    Args:
        router (Router): Mocked router fixture
        role (OrderingRole): OrderingRole fixture
        ret_value (List[str]): Expected ordered names from router
        seq (List[WithBriefing]): Input WithBriefing sequence
        requirement (str): Requirement for ordering
        expected_names (List[str]): Expected ordered names
    """
    with install_router(router):
        result = await role.order(seq, requirement)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == len(expected_names)
        result_names = [item.name for item in result]
        assert result_names == expected_names


@pytest.mark.parametrize(
    "seq",
    [
        ["string", with_briefing_factory("mixed", "briefing")],  # Mixed types
        [1, 2, 3],  # Wrong types
    ],
)
@pytest.mark.asyncio
async def test_order_invalid_input(
    role: OrderingRole,
    seq: List[Union[str, WithBriefing, int]],
) -> None:
    """Test order method with invalid input types.

    Args:
        role (OrderingRole): OrderingRole fixture
        seq (List[Union[str, WithBriefing, int]]): Invalid input sequence
    """
    with pytest.raises(ValueError, match=r"The sequence must be a list of strings or a list of WithBriefing objects\."):
        await role.order(seq, "test requirement")
