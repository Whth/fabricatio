"""Tests for the capable."""

from typing import Set

import pytest
from fabricatio_capable.capabilities.capable import Capable
from fabricatio_core.utils import ok
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string, return_string
from fabricatio_mock.utils import install_router
from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.toolboxes import arithmetic_toolbox


class CapableRole(LLMTestRole, Capable):
    """Test role that combines LLMTestRole with Capable for testing."""


@pytest.fixture
def toolbox_set() -> Set[ToolBox]:
    """Provide a minimal, valid set of toolboxes for the capable tests.

    Returns:
        set: A set containing the arithmetic_toolbox.
    """
    return {arithmetic_toolbox}


@pytest.fixture
def capable_role() -> CapableRole:
    """Create a CapableRole instance for testing.

    Returns:
        CapableRole: An instance of CapableRole with name "tester" and description "test role".
    """
    return CapableRole(name="tester", description="test role")


@pytest.mark.asyncio
async def test_capable_single_string(capable_role: CapableRole, toolbox_set: Set[ToolBox]) -> None:
    """Test capable method with a single string request.

    This test verifies that the capable method correctly processes a single string
    request and returns the expected JudgeMent object.

    Args:
        capable_role: A CapableRole instance provided by the fixture.
        toolbox_set: A set of toolboxes provided by the fixture.
    """
    desired = JudgeMent(
        issue_to_judge="test issue",
        affirm_evidence=["e1"],
        deny_evidence=["e2"],
        final_judgement=True,
    )
    router = return_model_json_string(desired)
    with install_router(router):
        result = ok(
            await capable_role.capable(
                request="test input",
                toolboxes=toolbox_set,
            )
        )
        assert result.model_dump_json() == desired.model_dump_json()
        assert bool(result) is True


@pytest.mark.asyncio
async def test_capable_list_of_strings(capable_role: CapableRole, toolbox_set: Set[ToolBox]) -> None:
    """Test capable method with a list of string requests.

    This test verifies that the capable method correctly processes a list of string
    requests and returns a list of corresponding JudgeMent objects.

    Args:
        capable_role: A CapableRole instance provided by the fixture.
        toolbox_set: A set of toolboxes provided by the fixture.
    """
    desires = [
        JudgeMent(
            issue_to_judge=f"issue {i}",
            affirm_evidence=["a"],
            deny_evidence=["d"],
            final_judgement=bool(i % 2),
        )
        for i in range(3)
    ]
    router = return_model_json_string(*desires)
    with install_router(router):
        results = ok(
            await capable_role.capable(
                request=[f"req {i}" for i in range(3)],
                toolboxes=toolbox_set,
            )
        )
        assert isinstance(results, list)
        assert len(results) == 3
        for actual, expected in zip(results, desires, strict=False):
            assert actual is not None
            assert actual.model_dump_json() == expected.model_dump_json()
            assert bool(actual) == expected.final_judgement


@pytest.mark.asyncio
async def test_capable_none_response(capable_role: CapableRole, toolbox_set: Set[ToolBox]) -> None:
    """Test capable method when LLM returns None.

    This test verifies that the capable method raises a ValueError when the LLM
    returns None (empty string in this simulation).

    Args:
        capable_role: A CapableRole instance provided by the fixture.
        toolbox_set: A set of toolboxes provided by the fixture.
    """
    # Simulate None returned by LLM
    router = return_string("")
    with install_router(router):
        assert (
            await capable_role.capable(
                request="should be none",
                toolboxes=toolbox_set,
            )
            == None
        )
