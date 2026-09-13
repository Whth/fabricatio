"""Tests for the capable."""

import pytest
from fabricatio_capable.capabilities.capable import Capable
from fabricatio_core import Role
from fabricatio_core.utils import ok
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_tool.models.tool import ToolBox


@pytest.fixture
def toolbox_set() -> set[ToolBox]:
    """Provide a minimal, valid set of toolboxes for the capable tests.

    Returns:
        set: A set containing the arithmetic_toolbox.
    """
    return {ToolBox(name="arithmetic_toolbox")}


@pytest.fixture
def capable_role() -> Role:
    """Create a test role that composes Capable with the mock LLM test role.

    Returns:
        Role: A role named "tester" with description "test role".
    """
    return make_test_role(Capable, name="tester", description="test role")


@pytest.mark.asyncio
async def test_capable_single_string(capable_role: Role, toolbox_set: set[ToolBox]) -> None:
    """Test capable method with a single string request.

    This test verifies that the capable method correctly processes a single string
    request and returns the expected JudgeMent object.

    Args:
        capable_role: A test role instance provided by the fixture.
        toolbox_set: A set of toolboxes provided by the fixture.
    """
    desired = JudgeMent(
        issue_to_judge="test issue",
        affirm_evidence=["e1"],
        deny_evidence=["e2"],
        final_judgement=True,
    )
    with MockScript.from_values(Value.from_model(desired, name="judgement")):
        result = ok(
            await capable_role.capable(
                request="test input",
                toolboxes=toolbox_set,
            ),
        )
        assert result.model_dump_json() == desired.model_dump_json()
        assert bool(result) is True


@pytest.mark.asyncio
async def test_capable_list_of_strings(capable_role: Role, toolbox_set: set[ToolBox]) -> None:
    """Test capable method with a list of string requests.

    This test verifies that the capable method correctly processes a list of string
    requests and returns a list of corresponding JudgeMent objects.

    Args:
        capable_role: A test role instance provided by the fixture.
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
    with MockScript.from_values(
        *[Value.from_model(judgement, name=f"judgement {i}") for i, judgement in enumerate(desires, start=1)]
    ):
        results = ok(
            await capable_role.capable(
                request=[f"req {i}" for i in range(3)],
                toolboxes=toolbox_set,
            ),
        )
        assert isinstance(results, list)
        assert len(results) == 3
        # asyncio.gather processes the per-item LLM calls concurrently; the
        # dummy mock's LIFO response queue does not preserve submission order
        # under concurrent access, so match by content.
        actual_by_issue = {r.issue_to_judge: r for r in results}
        for expected in desires:
            actual = actual_by_issue[expected.issue_to_judge]
            assert actual is not None
            assert actual.model_dump_json() == expected.model_dump_json()
            assert bool(actual) == expected.final_judgement


@pytest.mark.asyncio
async def test_capable_none_response(capable_role: Role, toolbox_set: set[ToolBox]) -> None:
    """Test capable method when LLM returns None.

    This test verifies that the capable method raises a ValueError when the LLM
    returns None (empty string in this simulation).

    Args:
        capable_role: A test role instance provided by the fixture.
        toolbox_set: A set of toolboxes provided by the fixture.
    """
    # Simulate None returned by LLM
    with MockScript.from_values(Value.from_text("", name="empty response")):
        assert (
            await capable_role.capable(
                request="should be none",
                toolboxes=toolbox_set,
            )
            == None
        )
